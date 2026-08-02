"""Warrior initialization and timing hooks."""

from card_duel.cards.warrior.state import WarriorData, warrior_data
from card_duel.core.game import TurnPhase
from card_duel.core.rules import draw_cards


class WarriorRules:
    def create_data(self) -> WarriorData:
        return WarriorData()

    def initialize(self, player) -> None:
        player.health = 30

    def register_turn_handlers(self, turn, combat) -> None:
        def resolve_heartlink(context):
            player = context.game_state.players[context.player_id]
            if not isinstance(player.character_data, WarriorData):
                return
            data = warrior_data(player)
            if not data.heartlink_layers:
                return
            context.announce(f"心连心（双方-{data.heartlink_layers}生命）")
            combat.apply_damage(data.heartlink_layers, context.player_id)
            if data.sacrifice_layers:
                draw_cards(
                    context.game_state,
                    data.heartlink_layers * data.sacrifice_layers,
                )
            combat.apply_damage(data.heartlink_layers, context.opponent_id)

        turn.register_phase_handler(
            TurnPhase.TURN_START, resolve_heartlink, priority=20
        )

    def prevent_life_loss(self, player, amount: int) -> int:
        return amount

    def on_life_depleted(self, state, player_id, announce=None) -> None:
        return None

    def is_defeated(self, player) -> bool:
        return player.health <= 0

    def format_status(self, player) -> str:
        data = warrior_data(player)
        parts = []
        if data.sacrifice_layers:
            parts.append(f"献祭 {data.sacrifice_layers}")
        if data.heartlink_layers:
            parts.append(f"心连心 {data.heartlink_layers}")
        if player.statuses.persistent_defence:
            parts.append("壁垒")
        return "  ·  ".join(parts)
