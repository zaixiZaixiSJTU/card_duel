"""Authoritative five-phase match operations for WebSocket rooms."""

from __future__ import annotations

import random
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol

from card_duel.application.combat import CombatEngine
from card_duel.application.turns import (
    HAND_LIMIT,
    can_discard,
    draw_turn_cards,
    effective_hand_size,
    remove_played_card,
    return_card_after_use,
)
from card_duel.cards.registry import CardRegistry
from card_duel.core.game import TurnEngine, TurnPhase
from card_duel.core.models import GameState
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
    if combat.check_game_over() is None:
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
            target_player_id=_opponent(player_id),
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
            target_player_id=_opponent(player_id),
            announce=log.announce,
            choices=choices,
            combat=combat,
            private_announce=log.announce_private,
        )
        if played:
            if not definition.exhausted:
                return_card_after_use(state, player_id, card_id)
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
    room: MatchRoomPort, player_id: int, data: dict[str, Any]
) -> ActionLog:
    state, _combat = _require_active(room, player_id)
    if state.current_phase == TurnPhase.PLAY.value:
        state.current_phase = TurnPhase.DISCARD.value
    elif state.current_phase != TurnPhase.DISCARD.value:
        raise ActionError("wrong_phase", "当前不能弃牌")
    index = _required_index(data)
    if index >= len(state.hand_cards):
        raise ActionError("invalid_card", "手牌索引超出范围")
    card_id = state.hand_cards[index]
    if not can_discard(state, player_id, card_id):
        raise ActionError("card_not_discardable", "生物牌和插入物不可弃置")
    state.hand_cards.pop(index)
    return_card_after_use(state, player_id, card_id)
    _sync_zone(room, player_id)
    return ActionLog(announcements=[f"玩家{player_id}弃掉一张牌"])


def end_turn(
    room: MatchRoomPort,
    player_id: int,
    registry: CardRegistry,
    choices: SubmittedChoiceProvider,
) -> ActionLog:
    state, combat = _require_active(room, player_id)
    if state.current_phase not in {TurnPhase.PLAY.value, TurnPhase.DISCARD.value}:
        raise ActionError("wrong_phase", "当前不能结束回合")
    if effective_hand_size(state, player_id) > HAND_LIMIT:
        raise ActionError(
            "hand_limit",
            f"手牌超过上限，仍需弃 {effective_hand_size(state, player_id) - HAND_LIMIT} 张",
        )

    log = ActionLog(private_player_id=player_id)
    turn = _build_turn(room, player_id, registry, log, choices=choices)
    if state.current_phase == TurnPhase.PLAY.value:
        turn.resume_after(TurnPhase.PLAY)
        turn.enter_phase(TurnPhase.DISCARD)
    else:
        turn.resume_after(TurnPhase.DISCARD)
    turn.enter_phase(TurnPhase.TURN_END)
    _sync_zone(room, player_id)
    _apply_pending_zones(room, log.announce)
    winner = combat.check_game_over()
    if winner is not None:
        log.announce(f"对局结束：玩家{winner}获胜")
        return log

    next_player = _opponent(player_id)
    if player_id != state.first_player_id:
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
    for player_id in (1, 2):
        state.local_player_id = player_id
        _activate_zone(room, player_id)
        player = state.players[player_id]
        statuses = player.statuses
        state.hand_cards.extend(statuses.pending_hand_additions)
        statuses.pending_hand_additions.clear()
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


def _opponent(player_id: int) -> int:
    return 2 if player_id == 1 else 1
