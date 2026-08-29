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
    vulture_summoned: bool = False
    # 矛作用到生物时挂载的持续效果（生物与玩家是不同个体：生物无手牌，
    # 故弃牌类效果无效，但流血/减伤等持续效果仍挂在生物身上）。
    # embedded_steel_rods：钢筋流血计数，生物攻击其所有者时每根额外造成2点伤害。
    # electric_weakness：电矛减伤计数，生物攻击其所有者时伤害降低此数值。
    embedded_steel_rods: int = 0
    electric_weakness: int = 0


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
    # 强制选择弃牌：玩家须手动选择弃置此数量张牌方可继续（混沌胃袋
    # "弃1抽1" 等）。与 pending_discards（炸矛随机弃，由系统结算）不同，
    # 此字段不自动结算，需玩家通过 discard_card/discard_cards 完成后递减。
    forced_discards: int = 0
    embedded_steel_rods: int = 0
    embedded_electric_spears: int = 0
    inserted_cards: list[InsertedCardState] = field(default_factory=list)
    hand_creatures: list[CreatureState] = field(default_factory=list)
    creature_threats: list[CreatureState] = field(default_factory=list)
    noodle_fly_immunity_used: bool = False
    last_dead_creature_health: int = 0
    scavenger_attraction: bool = False
    pending_hand_additions: list[CardId] = field(default_factory=list)
    pending_hand_removals: list[CardId] = field(default_factory=list)
    pending_draw_returns: list[CardId] = field(default_factory=list)
    pending_draw_additions: list[CardId] = field(default_factory=list)
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
    # 多人对局扩展：玩家是否仍在本局中存活/未淘汰。淘汰制、组队战、
    # 跳过死亡玩家轮转都依赖此字段；2 人模式下保持 True 直至对局结束。
    is_alive: bool = True

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
    # 多人对局扩展。
    # player_teams：座位号 -> 阵营编号；None 表示自由阵营（FFA）。
    # turn_order：本局回合轮转顺序，由房间规则生成（座位号列表）。
    # 2 人模式下保持默认值即可，桌面 TCP 与现有协议不读写这两个字段。
    player_teams: dict[PlayerId, int | None] = field(default_factory=dict)
    turn_order: list[int] = field(default_factory=list)
    random_seed: int | None = None
    first_player_id: int | None = None
    round1_no_damage: bool = False
    game_over: bool = False
    local_player_id: PlayerId = 1
    round_number: int = 0
    active_player_id: PlayerId | None = None
    current_phase: str | None = None
    round1_lock_health: int | None = None

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
