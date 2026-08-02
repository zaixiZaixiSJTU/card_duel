"""Slugcat initialization, defeat policy, and turn timing hooks."""

import random

from card_duel.cards.slugcat.hand import count_card, remove_first
from card_duel.cards.slugcat.specs import SLUGCAT_CREATURE_IDS, SLUGCAT_SPECS_BY_ID
from card_duel.cards.slugcat.state import (
    SLUGCAT_HEALTH,
    SlugcatData,
    slugcat_data,
)
from card_duel.core.game import TurnPhase
from card_duel.core.rules import add_card_to_hand


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
                grass_count = count_card(context.game_state, 42)
                if grass_count:
                    data.satiety += grass_count * 2
                    context.announce(f"蝠蝇草提供{grass_count * 2}点饱食度")
            _resolve_pending_discards(context.game_state, player)
            _resolve_inserted_items(
                context.game_state,
                context.player_id,
                context.announce,
                combat,
            )

        def on_turn_end(context):
            player = context.game_state.players[context.player_id]
            _resolve_creatures(
                context.game_state,
                context.player_id,
                context.announce,
                combat,
            )
            penalty = player.statuses.electric_strength_penalty
            if penalty:
                player.strength += penalty
                player.statuses.electric_strength_penalty = 0

        turn.register_phase_handler(TurnPhase.TURN_START, on_turn_start, priority=30)
        turn.register_phase_handler(TurnPhase.TURN_END, on_turn_end, priority=30)

    def prevent_life_loss(self, player, amount: int) -> int:
        data = slugcat_data(player)
        prevented = min(data.agility, amount)
        data.agility -= prevented
        return amount - prevented

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
        return (
            f"业力 {data.karma}/{data.karma_max}  ·  "
            f"敏捷 {data.agility}  ·  动能 {data.momentum}  ·  "
            f"饱食 {data.satiety}"
        )


def _resolve_pending_discards(state, player) -> None:
    pending = player.statuses.pending_discards
    while pending > 0 and state.hand_cards:
        index = random.randrange(len(state.hand_cards))
        state.draw_pile.append(state.hand_cards.pop(index))
        pending -= 1
    player.statuses.pending_discards = pending


def _resolve_inserted_items(state, player_id: int, announce, combat) -> None:
    player = state.players[player_id]
    rods = player.statuses.embedded_steel_rods
    if rods:
        combat.lose_life(rods, player_id, announce)
        announce(f"{rods}根钢筋使玩家{player_id}失去{rods}点生命")
        if player.energy >= 1:
            player.energy -= 1
            player.statuses.embedded_steel_rods -= 1
            announce(f"玩家{player_id}支付1点能量拔出1根钢筋")

    spears = player.statuses.embedded_electric_spears
    if spears:
        penalty = spears * 2
        player.strength -= penalty
        player.statuses.electric_strength_penalty = penalty
        announce(f"电矛使玩家{player_id}本回合力量-{penalty}")
        if player.energy >= 1:
            player.energy -= 1
            player.statuses.embedded_electric_spears -= 1
            announce(f"玩家{player_id}支付1点能量拔出1根电矛")


def _resolve_creatures(state, player_id: int, announce, combat) -> None:
    if state.local_player_id != player_id:
        return
    player = state.players[player_id]
    hand_creatures = [
        card_id for card_id in state.hand_cards if card_id in SLUGCAT_CREATURE_IDS
    ]
    creatures = hand_creatures + list(player.statuses.creature_threats)
    if not creatures:
        return

    centipede_count = creatures.count(22)
    for creature_id in creatures:
        damage = _creature_damage(player, creature_id, centipede_count)
        if damage:
            combat.apply_damage(damage, player_id)
            announce(
                f"{SLUGCAT_SPECS_BY_ID[creature_id].name}"
                f"对玩家{player_id}造成{damage}点伤害"
            )
        if creature_id == 18:
            player.statuses.creature_threats.append(19)
        if creature_id == 16:
            remove_first(state, 16)
            add_card_to_hand(state, 17)
            player.statuses.last_dead_creature_health = 1


def _creature_damage(player, creature_id: int, centipede_count: int) -> int:
    if creature_id == 17:
        return 5
    if creature_id == 19:
        return 10
    if creature_id == 20:
        key = str(creature_id)
        if player.statuses.creature_waits.get(key, 0) == 0:
            player.statuses.creature_waits[key] = 1
            return 0
        return 5
    if creature_id == 21:
        return 3
    if creature_id == 22:
        return 15 if centipede_count >= 3 else 0
    if creature_id == 23:
        return 10
    if creature_id == 24:
        return 15
    if creature_id == 25:
        return random.choices((2, 10, 3, 3), weights=(6, 1, 2, 1), k=1)[0]
    return 0
