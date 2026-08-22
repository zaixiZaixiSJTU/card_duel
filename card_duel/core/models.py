"""Domain models for a Card Duel match.

This module deliberately contains no GUI, socket, or filesystem dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PlayerId = int
CardId = int


@dataclass(slots=True)
class CreatureState:
    """A creature currently carried in a hand or placed in a threat zone."""

    card_id: CardId
    health: int
    owner_id: PlayerId
    wait_turns: int = 0
    noodle_cost: int = 0
    shell: bool = True
    held_item: int = 0


@dataclass(slots=True)
class InsertedCardState:
    """A foreign card inserted into a player's hand by an attack."""

    card_id: CardId
    owner_id: PlayerId


@dataclass(slots=True)
class CombatStatuses:
    """Cross-character effects that can be applied to any player."""

    persistent_defence: bool = False
    immune_next_attacks: int = 0
    attack_lock: int = 0
    pending_discards: int = 0
    embedded_steel_rods: int = 0
    embedded_electric_spears: int = 0
    electric_strength_penalty: int = 0
    inserted_cards: list[InsertedCardState] = field(default_factory=list)
    hand_creatures: list[CreatureState] = field(default_factory=list)
    creature_threats: list[CreatureState] = field(default_factory=list)
    noodle_fly_immunity_used: bool = False
    last_dead_creature_health: int = 0
    scavenger_attraction: bool = False
    pending_hand_additions: list[CardId] = field(default_factory=list)
    pending_hand_removals: list[CardId] = field(default_factory=list)
    pending_draw_returns: list[CardId] = field(default_factory=list)
    centipede_health: int = 0


@dataclass(slots=True)
class CharacterState:
    """Mutable public combat values for one player."""

    health: int = 30
    max_health: int = 30
    energy: int = 0
    strength: int = 0
    poison: int = 0
    statuses: CombatStatuses = field(default_factory=CombatStatuses)
    character_data: object | None = None
    defences: list[DefenceEffect] = field(default_factory=list)

    @property
    def defence(self) -> int:
        return sum(effect.amount for effect in self.defences)


@dataclass(slots=True)
class ScheduledEvent:
    """A delayed effect waiting on the shared timeline."""

    turns_remaining: int = 1
    effect_type: int = 0
    amount: int = 0
    target_player_id: PlayerId = 0
    message: str | None = None

    def __post_init__(self) -> None:
        if self.message is None:
            self.message = (
                f"玩家{self.target_player_id}的{self.effect_type}类数值"
                f"增加{self.amount}"
            )


@dataclass(slots=True)
class DefenceEffect:
    """A defence amount that expires after a number of turns."""

    turns_remaining: int = 1
    amount: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "turns_remaining": self.turns_remaining,
            "amount": self.amount,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> DefenceEffect:
        return cls(
            turns_remaining=data["turns_remaining"],
            amount=data["amount"],
        )


@dataclass
class GameState:
    """Serializable match state shared by rules and network synchronization.

    Runtime resources such as a socket and a GUI window belong to
    :class:`card_duel.network.session.GameSession`, not to this model.
    """

    players: dict[PlayerId, CharacterState] = field(
        default_factory=lambda: {1: CharacterState(), 2: CharacterState()}
    )
    hand_cards: list[CardId] = field(default_factory=list)
    draw_pile: list[CardId] = field(default_factory=list)
    discard_pile: list[CardId] = field(default_factory=list)
    timeline: list[ScheduledEvent] = field(default_factory=list)
    character_ids: dict[PlayerId, int | None] = field(
        default_factory=lambda: {1: None, 2: None}
    )
    random_seed: int | None = None
    first_player_id: int | None = None
    round1_no_damage: bool = False
    game_over: bool = False
    local_player_id: PlayerId = 1
    round_number: int = 0
    active_player_id: PlayerId | None = None
    current_phase: str | None = None

    @property
    def hand_size(self) -> int:
        return len(self.hand_cards)

    @property
    def local_player(self) -> CharacterState:
        return self.players[self.local_player_id]

    @property
    def opponent_player_id(self) -> PlayerId:
        return 2 if self.local_player_id == 1 else 1

    @property
    def opponent_player(self) -> CharacterState:
        return self.players[self.opponent_player_id]

    @property
    def local_character_id(self) -> int | None:
        return self.character_ids[self.local_player_id]

    @property
    def opponent_character_id(self) -> int | None:
        return self.character_ids[self.opponent_player_id]

    @property
    def local_defences(self) -> list[DefenceEffect]:
        return self.local_player.defences

    @property
    def opponent_defences(self) -> list[DefenceEffect]:
        return self.opponent_player.defences


# Historical name retained for third-party imports.
NetworkGameState = GameState
