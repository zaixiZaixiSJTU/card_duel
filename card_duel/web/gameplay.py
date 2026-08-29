"""Authoritative five-phase match operations for WebSocket rooms."""

from __future__ import annotations

import random
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol

from card_duel.application.combat import CombatEngine
from card_duel.application.turns import (
    can_discard,
    draw_turn_cards,
    effective_hand_size,
    hand_limit_for,
    remove_played_card,
    return_card_after_use,
)
from card_duel.cards.registry import CardRegistry
from card_duel.core.game import TurnEngine, TurnPhase
from card_duel.core.models import GameState
from card_duel.core.rules import add_card_to_hand, reshuffle_discard_into_draw
from card_duel.web.protocol import ActionError


class CardZonePort(Protocol):
    hand: list[int]
    draw_pile: list[int]
    discard_pile: list[int]


class MatchRoomPort(Protocol):
    state: GameState | None
    combat: CombatEngine | None
    card_zones: dict[int, CardZonePort]
    revision: int


@dataclass(slots=True)
class ActionLog:
    announcements: list[str] = field(default_factory=list)
    private_announcements: list[tuple[int, str]] = field(default_factory=list)
    played_card: tuple[int, int, int] | None = None
    private_player_id: int | None = None

    def announce(self, message: str) -> None:
        self.announcements.append(message)

    def announce_private(self, message: str) -> None:
        if self.private_player_id is not None:
            self.private_announcements.append((self.private_player_id, message))

    def extend(self, other: ActionLog) -> None:
        self.announcements.extend(other.announcements)
        self.private_announcements.extend(other.private_announcements)
        if other.played_card is not None:
            self.played_card = other.played_card


@dataclass(frozen=True, slots=True)
class ChoicePrompt:
    kind: str
    title: str
    prompt: str
    options: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    default: object | None = None
    hand: tuple[int, ...] = ()
    count: int | None = None
    excluded_card_id: int | None = None

    def payload(self) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": self.kind,
            "title": self.title,
            "prompt": self.prompt,
            "default": self.default,
        }
        if self.options:
            result["options"] = list(self.options)
        if self.minimum is not None:
            result["minimum"] = self.minimum
        if self.maximum is not None:
            result["maximum"] = self.maximum
        if self.hand:
            result["hand"] = list(self.hand)
        if self.count is not None:
            result["count"] = self.count
        if self.excluded_card_id is not None:
            result["excluded_card_id"] = self.excluded_card_id
        return result


class ChoiceRequired(Exception):
    def __init__(self, choice: ChoicePrompt) -> None:
        super().__init__(choice.prompt)
        self.choice = choice


@dataclass(slots=True)
class PendingAction:
    player_id: int
    action: str
    data: dict[str, Any]
    answers: list[object]
    choice_id: str


class SubmittedChoiceProvider:
    """Consume submitted answers or pause the action at the next missing choice."""

    def __init__(self, answers: Sequence[object]) -> None:
        self.answers = answers
        self.index = 0

    def choose_integer(self, title, prompt, minimum, maximum, default):
        choice = ChoicePrompt(
            kind="integer",
            title=title,
            prompt=prompt,
            minimum=minimum,
            maximum=maximum,
            default=default,
        )
        value = self._next(choice)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ActionError("invalid_choice", "选择结果必须是整数")
        if not minimum <= value <= maximum:
            raise ActionError("invalid_choice", "选择结果超出允许范围")
        return value

    def choose_option(self, title, prompt, options, default):
        choices = tuple(options)
        if len(choices) == 1:
            return choices[0]
        choice = ChoicePrompt(
            kind="option",
            title=title,
            prompt=prompt,
            options=choices,
            default=default,
        )
        value = self._next(choice)
        if not isinstance(value, str) or value not in choices:
            raise ActionError("invalid_choice", "选择结果不在可选项中")
        return value

    def choose_card_indexes(
        self, title, hand, count, excluded_card_id=None
    ) -> list[int]:
        if count == 0:
            return []
        choice = ChoicePrompt(
            kind="card_indexes",
            title=title,
            prompt=f"选择 {count} 张牌",
            hand=tuple(hand),
            count=count,
            excluded_card_id=excluded_card_id,
        )
        value = self._next(choice)
        if not isinstance(value, list) or any(
            isinstance(index, bool) or not isinstance(index, int) for index in value
        ):
            raise ActionError("invalid_choice", "卡牌选择必须是索引数组")
        if len(value) != count or len(set(value)) != count:
            raise ActionError("invalid_choice", f"必须选择 {count} 张不同的牌")
        if any(index < 0 or index >= len(hand) for index in value):
            raise ActionError("invalid_choice", "卡牌索引超出范围")
        if excluded_card_id is not None and any(
            hand[index] == excluded_card_id for index in value
        ):
            raise ActionError("invalid_choice", "选择中包含不可选卡牌")
        return value

    def _next(self, choice: ChoicePrompt) -> object:
        if self.index >= len(self.answers):
            raise ChoiceRequired(choice)
        value = self.answers[self.index]
        self.index += 1
        return value


def begin_turn(
    room: MatchRoomPort, player_id: int, registry: CardRegistry
) -> ActionLog:
    state, combat = _runtime(room)
    if state.game_over:
        raise ActionError("game_over", "对局已经结束")
    if player_id == state.first_player_id:
        _grant_round_energy(state)
    _activate_zone(room, player_id)
    log = ActionLog(private_player_id=player_id)
    turn = _build_turn(room, player_id, registry, log, choices=None)
    turn.enter_phase(TurnPhase.TURN_START)
    # 混沌胃袋等回合开始强制选择弃牌：设了 forced_discards 时回合暂停在
    # TURN_START，等玩家通过 discard_card 完成弃牌后由
    # _resume_chaotic_stomach 补抽并继续 DRAW/PLAY。
    forced_discards = state.players[player_id].statuses.forced_discards
    if combat.check_game_over() is None and forced_discards == 0:
        turn.enter_phase(TurnPhase.DRAW)
        turn.enter_phase(TurnPhase.PLAY)
    _sync_zone(room, player_id)
    _apply_pending_zones(room, log.announce)
    state.local_player_id = player_id
    _activate_zone(room, player_id)
    log.announce(f"轮到玩家{player_id}")
    return log


def play_card(
    room: MatchRoomPort,
    player_id: int,
    data: dict[str, Any],
    registry: CardRegistry,
    choices: SubmittedChoiceProvider,
) -> ActionLog:
    state, combat = _require_active_play(room, player_id)
    source = data.get("source", "hand")
    index = _required_index(data)
    log = ActionLog(private_player_id=player_id)
    character_id = state.character_ids[player_id]
    if character_id is None:
        raise ActionError("character_required", "玩家尚未选择角色")

    if source == "creature":
        creatures = [
            item
            for item in state.players[player_id].statuses.hand_creatures
            if item.card_id != 26
        ]
        if index >= len(creatures):
            raise ActionError("invalid_card", "生物索引超出范围")
        card_id = creatures[index].card_id
        played = registry.play(
            state=state,
            character_id=character_id,
            card_id=card_id,
            source_player_id=player_id,
            target_player_id=_default_target(state, player_id),
            announce=log.announce,
            choices=choices,
            combat=combat,
            private_announce=log.announce_private,
        )
    elif source == "hand":
        if index >= len(state.hand_cards):
            raise ActionError("invalid_card", "手牌索引超出范围")
        card_id = state.hand_cards[index]
        definition = registry.get_card(character_id, card_id)
        played = registry.play(
            state=state,
            character_id=character_id,
            card_id=card_id,
            source_player_id=player_id,
            target_player_id=_default_target(state, player_id),
            announce=log.announce,
            choices=choices,
            combat=combat,
            private_announce=log.announce_private,
        )
        if played:
            if not definition.exhausted:
                return_card_after_use(state, player_id, card_id, from_play=True)
            remove_played_card(state, index, card_id)
    else:
        raise ActionError("invalid_card", "source 必须是 hand 或 creature")

    if not played:
        message = log.announcements[-1] if log.announcements else "卡牌无法打出"
        raise ActionError("card_not_played", message)
    log.played_card = (player_id, character_id, card_id)
    _sync_zone(room, player_id)
    _apply_pending_zones(room, log.announce)
    state.local_player_id = player_id
    _activate_zone(room, player_id)
    combat.check_game_over()
    return log


def discard_card(
    room: MatchRoomPort, player_id: int, data: dict[str, Any], registry=None
) -> ActionLog:
    index = _required_index(data)
    return _discard_indexes(room, player_id, [index], registry=registry)


def discard_cards(
    room: MatchRoomPort, player_id: int, data: dict[str, Any], registry=None
) -> ActionLog:
    """Atomically discard a staged selection without index-shift races."""
    return _discard_indexes(
        room, player_id, _required_indexes(data), registry=registry
    )


def _discard_indexes(
    room: MatchRoomPort, player_id: int, indexes: list[int], *, registry=None
) -> ActionLog:
    state, _combat = _require_active(room, player_id)
    statuses = state.players[player_id].statuses
    forced = statuses.forced_discards
    # 强制选择弃牌（混沌胃袋/手牌超限）允许在任意阶段进行；普通手动弃牌
    # 仍只能在出牌/弃牌阶段。
    if forced <= 0 and state.current_phase not in {
        TurnPhase.PLAY.value,
        TurnPhase.DISCARD.value,
    }:
        raise ActionError("wrong_phase", "当前不能弃牌")
    if any(index >= len(state.hand_cards) for index in indexes):
        raise ActionError("invalid_card", "手牌索引超出范围")
    if any(
        not can_discard(state, player_id, state.hand_cards[index])
        for index in indexes
    ):
        raise ActionError("card_not_discardable", "生物牌和插入物不可弃置")
    # 回合开始（混沌胃袋）的强制弃牌只允许弃刚好 forced 张，避免在
    # TURN_START 顺势多弃。
    if (
        forced > 0
        and state.current_phase == TurnPhase.TURN_START.value
        and len(indexes) > forced
    ):
        raise ActionError("invalid_card", "混沌胃袋只需弃1张")

    original_phase = state.current_phase
    discarded_card_ids = [state.hand_cards[index] for index in indexes]
    for index in sorted(indexes, reverse=True):
        state.hand_cards.pop(index)
    for card_id in discarded_card_ids:
        return_card_after_use(state, player_id, card_id)

    if forced > 0:
        statuses.forced_discards = max(0, forced - len(indexes))
        # 混沌胃袋回合开始强制弃牌：弃满后补抽1张并继续 DRAW/PLAY。
        if (
            statuses.forced_discards == 0
            and original_phase == TurnPhase.TURN_START.value
            and registry is not None
        ):
            log = ActionLog(private_player_id=player_id)
            _resume_chaotic_stomach(room, player_id, registry, log)
            _sync_zone(room, player_id)
            return log
        remaining = statuses.forced_discards
        _sync_zone(room, player_id)
        message = (
            f"玩家{player_id}弃掉{len(indexes)}张牌"
            + ("" if remaining == 0 else f"（仍需弃{remaining}张）")
        )
        return ActionLog(announcements=[message])

    # Flexible discard is an out-of-phase action: it must not move the turn
    # into the mandatory discard phase. End turn still validates hand limits.
    state.current_phase = original_phase
    _sync_zone(room, player_id)
    return ActionLog(announcements=[f"玩家{player_id}弃掉{len(indexes)}张牌"])


def _resume_chaotic_stomach(
    room: MatchRoomPort, player_id: int, registry: CardRegistry, log: ActionLog
) -> None:
    """混沌胃袋弃1后：补抽1张，并继续进入 DRAW/PLAY 阶段。

    回合开始阶段（TURN_START）已由 begin_turn 运行过；此处不重放
    TURN_START，而是 resume_after 后进入 DRAW/PLAY。
    """
    state, combat = _runtime(room)
    # 弃1抽1：抽牌堆空则先洗弃牌堆，再从顶抽1张（与原 TURN_START 行为一致）。
    if not state.draw_pile:
        reshuffle_discard_into_draw(state)
    if state.draw_pile:
        add_card_to_hand(state, state.draw_pile.pop(0))
        log.announce("混沌胃袋：弃1抽1，并获得动能")
    else:
        log.announce("混沌胃袋：弃1但无牌可抽，获得动能")
    turn = _build_turn(room, player_id, registry, log, choices=None)
    if combat.check_game_over() is None:
        turn.resume_after(TurnPhase.TURN_START)
        turn.enter_phase(TurnPhase.DRAW)
        turn.enter_phase(TurnPhase.PLAY)
    _sync_zone(room, player_id)
    _apply_pending_zones(room, log.announce)
    state.local_player_id = player_id
    _activate_zone(room, player_id)


def end_turn(
    room: MatchRoomPort,
    player_id: int,
    registry: CardRegistry,
    choices: SubmittedChoiceProvider,
) -> ActionLog:
    state, combat = _require_active(room, player_id)
    if state.current_phase not in {TurnPhase.PLAY.value, TurnPhase.DISCARD.value}:
        raise ActionError("wrong_phase", "当前不能结束回合")
    hand_limit = hand_limit_for(state, player_id)
    excess = effective_hand_size(state, player_id) - hand_limit
    if excess > 0:
        # 点击结束回合时手牌超限：不报错，而是自动进入强制选择弃牌阶段
        # （红框 UI），玩家弃到上限后再点结束回合才真正结束。
        state.players[player_id].statuses.forced_discards = excess
        state.current_phase = TurnPhase.DISCARD.value
        _sync_zone(room, player_id)
        log = ActionLog(private_player_id=player_id)
        log.announce(f"手牌超上限，需弃 {excess} 张")
        return log

    # 强制弃牌已满足（或本就未超限），清零以防残留。
    state.players[player_id].statuses.forced_discards = 0
    log = ActionLog(private_player_id=player_id)
    turn = _build_turn(room, player_id, registry, log, choices=choices)
    state.current_phase = TurnPhase.PLAY.value
    turn.resume_after(TurnPhase.PLAY)
    turn.enter_phase(TurnPhase.DISCARD)
    turn.enter_phase(TurnPhase.TURN_END)
    _sync_zone(room, player_id)
    _apply_pending_zones(room, log.announce)
    winner = combat.check_game_over()
    if winner is not None:
        log.announce(f"对局结束：玩家{winner}获胜")
        return log

    # 多人扩展：按 turn_order 找下一个存活座位；回到 first_player 才
    # 视为新一轮开始（round_number += 1）。2 人时与原行为等价（next_player
    # 即对手，仅在 first_player 完成回合后 +1）。
    next_player = _next_alive_player(state, player_id)
    if next_player == state.first_player_id:
        state.round_number += 1
    log.extend(begin_turn(room, next_player, registry))
    return log


def _build_turn(room, player_id, registry, log, choices):
    state, combat = _runtime(room)
    turn = TurnEngine(
        state,
        state.round_number,
        player_id,
        log.announce,
        choices=choices,
        private_announce=log.announce_private,
    )
    turn.register_phase_handler(
        TurnPhase.TURN_START,
        lambda context: combat.advance_turn_effects(
            context.player_id, context.announce
        ),
        priority=10,
    )
    turn.register_phase_handler(TurnPhase.DRAW, draw_turn_cards)
    combat.register_turn_handlers(turn)
    return turn


def _runtime(room: MatchRoomPort) -> tuple[GameState, CombatEngine]:
    if room.state is None or room.combat is None:
        raise ActionError("match_not_started", "对局尚未开始")
    return room.state, room.combat


def _require_active(
    room: MatchRoomPort, player_id: int
) -> tuple[GameState, CombatEngine]:
    state, combat = _runtime(room)
    if state.game_over:
        raise ActionError("game_over", "对局已经结束")
    if state.active_player_id != player_id:
        raise ActionError("not_your_turn", "当前不是你的回合")
    state.local_player_id = player_id
    _activate_zone(room, player_id)
    return state, combat


def _require_active_play(
    room: MatchRoomPort, player_id: int
) -> tuple[GameState, CombatEngine]:
    state, combat = _require_active(room, player_id)
    if state.current_phase != TurnPhase.PLAY.value:
        raise ActionError("wrong_phase", "当前不是出牌阶段")
    return state, combat


def _activate_zone(room: MatchRoomPort, player_id: int) -> None:
    state, _combat = _runtime(room)
    zone = room.card_zones[player_id]
    state.hand_cards = zone.hand
    state.draw_pile = zone.draw_pile
    state.discard_pile = zone.discard_pile


def _sync_zone(room: MatchRoomPort, player_id: int) -> None:
    state, _combat = _runtime(room)
    zone = room.card_zones[player_id]
    zone.hand = state.hand_cards
    zone.draw_pile = state.draw_pile
    zone.discard_pile = state.discard_pile


def _apply_pending_zones(room: MatchRoomPort, announce) -> None:
    state, _combat = _runtime(room)
    active_player_id = state.active_player_id or 1
    # 多人扩展：遍历所有座位（不再写死 (1, 2)），跳过已淘汰玩家。
    for player_id in list(state.players):
        if not state.players[player_id].is_alive:
            continue
        state.local_player_id = player_id
        _activate_zone(room, player_id)
        player = state.players[player_id]
        statuses = player.statuses
        state.hand_cards.extend(statuses.pending_hand_additions)
        statuses.pending_hand_additions.clear()
        state.draw_pile.extend(statuses.pending_draw_additions)
        statuses.pending_draw_additions.clear()
        for card_id in statuses.pending_hand_removals:
            with suppress(ValueError):
                state.hand_cards.remove(card_id)
        statuses.pending_hand_removals.clear()
        _apply_pending_returns(state, player_id)
        if statuses.pending_discards:
            from card_duel.cards.slugcat.lifecycle import resolve_pending_discards

            resolve_pending_discards(state, player_id, announce=announce)
        _sync_zone(room, player_id)
    state.local_player_id = active_player_id
    _activate_zone(room, active_player_id)


def _apply_pending_returns(state: GameState, player_id: int) -> None:
    statuses = state.players[player_id].statuses
    if not statuses.pending_draw_returns:
        return
    if state.character_ids.get(player_id) == 4:
        from card_duel.cards.slugcat.specs import (
            SLUGCAT_CREATURE_IDS,
            SLUGCAT_DISCOVERY_IDS,
        )
        from card_duel.cards.slugcat.state import slugcat_data

        data = slugcat_data(state.players[player_id])
        for card_id in statuses.pending_draw_returns:
            if card_id in SLUGCAT_DISCOVERY_IDS:
                data.discovery_pool.append(card_id)
            elif card_id in SLUGCAT_CREATURE_IDS:
                data.unlocked_creature_counts[card_id] = (
                    data.unlocked_creature_counts.get(card_id, 0) + 1
                )
            else:
                state.discard_pile.append(card_id)
    else:
        state.discard_pile.extend(statuses.pending_draw_returns)
    statuses.pending_draw_returns.clear()


def _grant_round_energy(state: GameState) -> None:
    seed = (state.random_seed or 0) ^ (state.round_number * 0x9E3779B1)
    generator = random.Random(seed)
    for player in state.players.values():
        player.energy = generator.randint(4, 6)


def _required_index(data: dict[str, Any]) -> int:
    index = data.get("index")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ActionError("invalid_card", "index 必须是非负整数")
    return index


def _required_indexes(data: dict[str, Any]) -> list[int]:
    indexes = data.get("indexes")
    if not isinstance(indexes, list) or not indexes:
        raise ActionError("invalid_card", "indexes 必须是非空索引数组")
    if any(
        isinstance(index, bool) or not isinstance(index, int) or index < 0
        for index in indexes
    ):
        raise ActionError("invalid_card", "indexes 必须只包含非负整数")
    if len(set(indexes)) != len(indexes):
        raise ActionError("invalid_card", "indexes 不能包含重复索引")
    return indexes


def _opponent(player_id: int) -> int:
    return 2 if player_id == 1 else 1


def _next_alive_player(state: GameState, current_player_id: int) -> int:
    """turn_order 中下一个仍存活的座位号（多人跳过死亡玩家）。

    2 人时退化到 _opponent 的语义：另一方存活则切到另一方，否则保持自己。
    """
    order = list(state.turn_order) if state.turn_order else sorted(state.players)
    if current_player_id not in order:
        order.append(current_player_id)
    current_index = order.index(current_player_id)
    for offset in range(1, len(order) + 1):
        candidate = order[(current_index + offset) % len(order)]
        if state.players[candidate].is_alive:
            return candidate
    return current_player_id  # 只剩自己存活（理论上不会到达，胜负已判定）


def _default_target(state: GameState, source_player_id: int) -> int:
    """出牌默认目标：第一个存活敌方座位号。

    阵营限制：FFA (team_id 为 None) 时所有人互为敌方；组队时 team 不同
    才算敌方。同队不会被选为目标，避免"都选红队还能互打"。
    没有敌方时（如全员同队，正常对局开局校验会拒绝）返回自己作为占位，
    resolve_attack 会再次过滤并 announce 不打。
    """
    source_team = state.player_teams.get(source_player_id)
    for player_id in state.players:
        if player_id == source_player_id:
            continue
        if not state.players[player_id].is_alive:
            continue
        target_team = state.player_teams.get(player_id)
        # FFA (None) 时所有人互为敌方；组队时 team 不同才算敌方。
        if (
            target_team is None
            or source_team is None
            or target_team != source_team
        ):
            return player_id
    # 没有敌方时返回自己占位（开局校验保证不会进入此分支，此处兜底）。
    return source_player_id
