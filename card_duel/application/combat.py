"""Character-aware combat service built on pure domain state."""

from __future__ import annotations

from card_duel.cards.registry import CardRegistry
from card_duel.core.models import CombatStatuses, GameState, ScheduledEvent
from card_duel.core.rules import add_defence, draw_cards


class CombatEngine:
    """Resolve combat while delegating character-specific behavior to the catalog."""

    def __init__(self, state: GameState, registry: CardRegistry) -> None:
        self.state = state
        self.registry = registry

    def initialize_players(self) -> None:
        for player_id, character_id in self.state.character_ids.items():
            if character_id is None:
                raise ValueError(f"玩家 {player_id} 尚未选择角色")
            player = self.state.players[player_id]
            player.health = 30
            player.energy = player.strength = player.poison = 0
            player.defences.clear()
            player.statuses = CombatStatuses()
            rules = self.registry.get_character(character_id).rules
            player.character_data = rules.create_data()
            rules.initialize(player)

    def apply_damage(self, damage: int, target_player_id: int) -> int:
        target = self.state.players[target_player_id]
        if target.statuses.immune_next_attacks:
            target.statuses.immune_next_attacks -= 1
            return 0

        remaining = max(0, damage)
        effects = target.defences
        while effects and remaining:
            absorbed = min(effects[0].amount, remaining)
            effects[0].amount -= absorbed
            remaining -= absorbed
            if effects[0].amount == 0:
                effects.pop(0)
        return self.lose_life(remaining, target_player_id)

    def lose_life(self, amount: int, target_player_id: int, announce=None) -> int:
        target = self.state.players[target_player_id]
        character_id = self.state.character_ids[target_player_id]
        if character_id is None:
            raise RuntimeError(f"玩家 {target_player_id} 尚未选择角色")
        rules = self.registry.get_character(character_id).rules
        actual_loss = rules.prevent_life_loss(target, max(0, amount))
        target.health -= actual_loss
        if target.health <= 0:
            rules.on_life_depleted(self.state, target_player_id, announce=announce)
        return actual_loss

    def resolve_scheduled_event(self, event: ScheduledEvent, announce) -> None:
        target = self.state.players[event.target_player_id]
        announce(event.message or "")
        if event.effect_type == 1:
            self.apply_damage(event.amount, event.target_player_id)
        elif event.effect_type == 2:
            target.energy += event.amount
        elif event.effect_type == 3:
            add_defence(target.defences, event.amount)
        elif event.effect_type == 4:
            target.strength += event.amount
        elif event.effect_type == 5:
            target.poison += event.amount
        elif event.effect_type == 6 and event.amount > 0:
            draw_cards(self.state, event.amount)

    def advance_turn_effects(self, player_id: int, announce) -> None:
        player = self.state.players[player_id]
        effects = player.defences
        if not player.statuses.persistent_defence:
            for effect in effects:
                effect.turns_remaining -= 1
            while effects and effects[0].turns_remaining <= 0:
                announce(f"玩家{player_id}的{effects.pop(0).amount}点防御消散")

        due: list[ScheduledEvent] = []
        pending: list[ScheduledEvent] = []
        for event in self.state.timeline:
            event.turns_remaining -= 1
            (due if event.turns_remaining <= 0 else pending).append(event)
        self.state.timeline = pending
        for event in due:
            self.resolve_scheduled_event(event, announce)

    def register_turn_handlers(self, turn) -> None:
        registered: set[int] = set()
        for character_id in self.state.character_ids.values():
            if character_id is None or character_id in registered:
                continue
            self.registry.get_character(character_id).rules.register_turn_handlers(
                turn, self
            )
            registered.add(character_id)

    def is_player_defeated(self, player_id: int) -> bool:
        character_id = self.state.character_ids[player_id]
        if character_id is None:
            return False
        rules = self.registry.get_character(character_id).rules
        return rules.is_defeated(self.state.players[player_id])

    def winning_player_id(self) -> int | None:
        if self.is_player_defeated(1):
            return 2
        if self.is_player_defeated(2):
            return 1
        return None

    def check_game_over(self) -> int | None:
        winner = self.winning_player_id()
        if winner is not None:
            self.state.game_over = True
        return winner
