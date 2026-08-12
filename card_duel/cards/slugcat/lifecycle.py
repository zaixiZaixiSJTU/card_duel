"""Slugcat initialization, combat hooks, and phase-timed creature effects."""

from __future__ import annotations

import random

from card_duel.cards.slugcat.creatures import (
    add_hand_creature,
    add_threat,
    on_creature_death,
    remove_hand_creature,
    resolve_attack,
)
from card_duel.cards.slugcat.hand import count_card
from card_duel.cards.slugcat.specs import (
    LIZARD_IDS,
    SLUGCAT_NO_DISCARD_IDS,
    SLUGCAT_SPECS_BY_ID,
)
from card_duel.cards.slugcat.state import SLUGCAT_HEALTH, SlugcatData, slugcat_data
from card_duel.core.game import TurnPhase


class SlugcatRules:
    def create_data(self) -> SlugcatData:
        return SlugcatData()

    def initialize(self, player) -> None:
        player.health = SLUGCAT_HEALTH

    def register_turn_handlers(self, turn, combat) -> None:
        def on_turn_start(context):
            player = context.game_state.players[context.player_id]
            if isinstance(player.character_data, SlugcatData):
                data = slugcat_data(player)
                data.agility = 0
                data.momentum = 0
                data.redirect_creatures_to_opponent = False
                data.discovery_discount.clear()
                grass_count = count_card(context.game_state, 42)
                if grass_count:
                    data.satiety += grass_count * 2
                    context.announce(f"蝠蝇草提供{grass_count * 2}点饱食度")
            player.statuses.noodle_fly_immunity_used = False
            _apply_electric_penalty(player, context.player_id, context.announce)

        def on_turn_end(context):
            player = context.game_state.players[context.player_id]
            _resolve_inserted_items(
                context.game_state,
                context.player_id,
                context.announce,
                combat,
            )
            _resolve_creatures(context, combat)
            penalty = player.statuses.electric_strength_penalty
            if penalty:
                player.strength += penalty
                player.statuses.electric_strength_penalty = 0
            if isinstance(player.character_data, SlugcatData):
                slugcat_data(player).momentum = 0

        turn.register_phase_handler(TurnPhase.TURN_START, on_turn_start, priority=30)
        turn.register_phase_handler(TurnPhase.TURN_END, on_turn_end, priority=30)

    def prevent_life_loss(self, player, amount: int) -> int:
        """Agility prevents damage, but not direct life-loss effects."""
        data = slugcat_data(player)
        prevented = min(data.agility, amount)
        remaining = amount - prevented
        data.agility -= min(data.agility, remaining)
        return remaining

    def consume_on_direct_life_loss(self, player, amount: int) -> None:
        data = slugcat_data(player)
        data.agility = max(0, data.agility - amount)

    def modify_incoming_damage(self, state, player_id, amount, announce=None):
        if amount <= 0:
            return amount
        statuses = state.players[player_id].statuses
        creature = next(
            (item for item in statuses.hand_creatures if item.card_id == 22), None
        )
        zone = statuses.hand_creatures
        if creature is None:
            creature = next(
                (item for item in statuses.creature_threats if item.card_id == 22),
                None,
            )
            zone = statuses.creature_threats
        if creature is None:
            return amount
        if zone is statuses.hand_creatures:
            remove_hand_creature(state, player_id, 22)
        else:
            zone.remove(creature)
        if announce:
            announce(f"玩家{player_id}消耗一张烈焰蜈蚣免受本次伤害")
        return 0

    def resolve_attack(
        self, context, damage: int, card_name: str, on_player_penetrate=None
    ) -> int:
        return resolve_attack(context, damage, card_name, on_player_penetrate)

    def on_life_depleted(self, state, player_id, announce=None) -> None:
        player = state.players[player_id]
        data = slugcat_data(player)
        data.karma = max(0, data.karma - 1)
        if data.karma > 0:
            player.health = SLUGCAT_HEALTH
            if announce:
                announce(f"玩家{player_id}消耗1点业力重返雨中（业力{data.karma}）")
        else:
            player.health = 0
            if announce:
                announce(f"玩家{player_id}的业力归零")

    def is_defeated(self, player) -> bool:
        return slugcat_data(player).karma <= 0

    def format_status(self, player) -> str:
        data = slugcat_data(player)
        return f"业力 {data.karma}/{data.karma_max}  ·  饱食 {data.satiety}"


def resolve_pending_discards(state, player_id: int, announce=None) -> int:
    """Resolve explosive-spear discards immediately on the affected endpoint."""
    player = state.players[player_id]
    pending = player.statuses.pending_discards
    discarded = 0
    while pending > 0 and state.hand_cards:
        protected = (
            SLUGCAT_NO_DISCARD_IDS
            if state.character_ids.get(player_id) == 4
            else (49, 50)
        )
        allowed = [
            index
            for index, card_id in enumerate(state.hand_cards)
            if card_id not in protected
        ]
        if not allowed:
            break
        index = random.choice(allowed)
        card_id = state.hand_cards.pop(index)
        _return_discarded_card(state, player_id, card_id)
        pending -= 1
        discarded += 1
        if announce:
            if state.character_ids.get(player_id) == 4:
                name = SLUGCAT_SPECS_BY_ID[card_id].name
            else:
                from card_duel.cards.catalog import DEFAULT_REGISTRY

                name = DEFAULT_REGISTRY.get_card(
                    state.character_ids[player_id], card_id
                ).name
            announce(f"随机弃掉：{name}")
    player.statuses.pending_discards = pending
    return discarded


def _return_discarded_card(state, player_id: int, card_id: int) -> None:
    if 27 <= card_id <= 35 and isinstance(
        state.players[player_id].character_data, SlugcatData
    ):
        slugcat_data(state.players[player_id]).discovery_pool.append(card_id)
    else:
        state.draw_pile.append(card_id)


def _apply_electric_penalty(player, player_id: int, announce) -> None:
    spears = player.statuses.embedded_electric_spears
    if not spears:
        return
    penalty = spears * 2
    player.strength -= penalty
    player.statuses.electric_strength_penalty = penalty
    announce(f"电矛使玩家{player_id}本回合力量-{penalty}")


def _resolve_inserted_items(state, player_id: int, announce, combat) -> None:
    rods = state.players[player_id].statuses.embedded_steel_rods
    if rods:
        announce(f"{rods}根钢筋在体内造成流血")
        combat.lose_life(rods, player_id, announce)


def _resolve_creatures(context, combat) -> None:
    state = context.game_state
    player_id = context.player_id
    if state.local_player_id != player_id:
        return
    player = state.players[player_id]
    statuses = player.statuses
    all_creatures = statuses.hand_creatures + statuses.creature_threats
    if not all_creatures:
        return

    if any(item.card_id in LIZARD_IDS for item in all_creatures):
        for noodle in [item for item in statuses.hand_creatures if item.card_id == 16]:
            remove_hand_creature(state, player_id, 16)
            on_creature_death(
                state,
                player_id,
                noodle,
                context.announce,
                private_announce=context.private_announce,
            )
            context.announce("蜥蜴吃掉了小面条，引来面条蝇")

    for noodle in [item for item in statuses.hand_creatures if item.card_id == 16]:
        remove_hand_creature(state, player_id, 16)
        on_creature_death(
            state,
            player_id,
            noodle,
            context.announce,
            private_announce=context.private_announce,
        )

    if context.choices is not None:
        for _creature in [
            item for item in statuses.hand_creatures if item.card_id == 23
        ]:
            if player.energy < 1:
                break
            choice = context.choices.choose_option(
                "烈焰蜥蜴",
                "是否支付1点能量避免本回合10点伤害？",
                ("支付1点能量", "承受伤害"),
                "承受伤害",
            )
            if choice != "支付1点能量":
                break
            player.energy -= 1
            removed = remove_hand_creature(state, player_id, 23)
            if removed is not None:
                if removed.owner_id == state.local_player_id:
                    state.draw_pile.append(23)
                else:
                    state.players[
                        removed.owner_id
                    ].statuses.pending_draw_returns.append(23)
            context.announce(f"玩家{player_id}支付1点能量，烈焰蜥蜴返回牌堆")

    centipede_count = sum(
        item.card_id == 22
        for item in statuses.hand_creatures + statuses.creature_threats
    )
    for creature in list(statuses.hand_creatures) + list(statuses.creature_threats):
        damage = _creature_damage(
            creature, centipede_count, player_id, context.announce
        )
        if damage:
            combat.apply_damage(damage, player_id, context.announce)
            if creature.card_id != 25:
                context.announce(
                    f"{SLUGCAT_SPECS_BY_ID[creature.card_id].name}"
                    f"对玩家{player_id}造成{damage}点伤害"
                )
        if creature.card_id == 18 and creature in statuses.hand_creatures:
            add_threat(state, player_id, 19, owner_id=player_id)
            context.announce("射线虫存活至回合结束，引来一张秃鹫")

    _resolve_centipede_spread(state, context.round_number, context.announce)


def _creature_damage(creature, centipede_count, player_id, announce) -> int:
    card_id = creature.card_id
    if card_id == 17:
        return 5
    if card_id == 19:
        return 10
    if card_id == 20:
        if creature.wait_turns == 0:
            creature.wait_turns = 1
            announce("绿蜥蜴静止中，下回合将造成5点伤害")
            return 0
        announce(f"绿蜥蜴苏醒，对玩家{player_id}造成5点伤害")
        return 5
    if card_id == 21:
        return 3
    if card_id == 22:
        return 15 if centipede_count >= 3 else 0
    if card_id == 23:
        return 10
    if card_id == 24:
        return 15
    if card_id == 25:
        item, damage = random.choices(
            (("钢筋", 2), ("炸药", 10), ("炸矛", 3), ("电矛", 3)),
            weights=(6, 1, 2, 1),
            k=1,
        )[0]
        announce(f"拾荒者携带{item}对玩家{player_id}造成{damage}点伤害")
        return damage
    return 0


def _resolve_centipede_spread(state, round_number: int, announce) -> None:
    if state.local_player_id != 1:
        return
    marker_owner = state.players[1]
    marker_data = marker_owner.character_data
    if isinstance(marker_data, SlugcatData):
        if marker_data.last_centipede_round == round_number:
            return
        marker_data.last_centipede_round = round_number

    counts = {
        player_id: sum(
            item.card_id == 22
            for item in (
                state.players[player_id].statuses.hand_creatures
                + state.players[player_id].statuses.creature_threats
            )
        )
        for player_id in (1, 2)
    }
    if not any(counts.values()) or counts[1] == counts[2]:
        return
    target_id = 1 if counts[1] > counts[2] else 2
    add_hand_creature(state, target_id, 22, owner_id=target_id)
    announce(f"玩家{target_id}的烈焰蜈蚣增殖了一张")
