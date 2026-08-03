"""Contracts shared by the registry and character feature packages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from card_duel.application.choices import ChoiceProvider
from card_duel.core.models import CharacterState, GameState


class CombatPort(Protocol):
    def apply_damage(
        self, damage: int, target_player_id: int, announce=None
    ) -> int: ...

    def lose_life(self, amount: int, target_player_id: int, announce=None) -> int: ...

    def resolve_attack(
        self,
        context: CardPlayContext,
        damage: int,
        card_name: str,
        on_player_penetrate=None,
    ) -> int: ...


class RegistryPort(Protocol):
    def play(self, **kwargs) -> bool | int: ...


class TurnRegistrar(Protocol):
    def register_phase_handler(self, phase, handler, priority=100) -> None: ...


@dataclass(slots=True)
class CardPlayContext:
    """Everything a card needs, supplied explicitly at the application edge."""

    state: GameState
    source_player_id: int
    target_player_id: int
    announce: Callable[[str], None]
    choices: ChoiceProvider
    combat: CombatPort
    registry: RegistryPort
    ignore_cost: bool = False

    @property
    def source(self) -> CharacterState:
        return self.state.players[self.source_player_id]

    @property
    def target(self) -> CharacterState:
        return self.state.players[self.target_player_id]

    def play_card(self, card_id: int, *, ignore_cost: bool = False) -> bool | int:
        character_id = self.state.character_ids[self.source_player_id]
        if character_id is None:
            raise RuntimeError("出牌玩家尚未选择角色")
        return self.registry.play(
            state=self.state,
            character_id=character_id,
            card_id=card_id,
            source_player_id=self.source_player_id,
            target_player_id=self.target_player_id,
            announce=self.announce,
            choices=self.choices,
            combat=self.combat,
            ignore_cost=ignore_cost,
        )


class CardHandler(Protocol):
    def __call__(self, context: CardPlayContext) -> bool | int: ...


@dataclass(frozen=True, slots=True)
class CardDefinition:
    character_id: int
    card_id: int
    name: str
    handler: CardHandler
    exhausted: bool = False
    card_type: str = "卡牌"
    cost: int | None = None
    description: str = ""


class CharacterRules(Protocol):
    """Lifecycle hooks implemented by one playable character package."""

    def create_data(self) -> object: ...

    def initialize(self, player: CharacterState) -> None: ...

    def register_turn_handlers(
        self, turn: TurnRegistrar, combat: CombatPort
    ) -> None: ...

    def prevent_life_loss(self, player: CharacterState, amount: int) -> int: ...

    def on_life_depleted(
        self,
        state: GameState,
        player_id: int,
        announce: Callable[[str], None] | None = None,
    ) -> None: ...

    def is_defeated(self, player: CharacterState) -> bool: ...

    def format_status(self, player: CharacterState) -> str: ...


@dataclass(frozen=True, slots=True)
class CharacterDefinition:
    character_id: int
    name: str
    deck_counts: Mapping[int, int]
    cards: tuple[CardDefinition, ...]
    rules: CharacterRules
