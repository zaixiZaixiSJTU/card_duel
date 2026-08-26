"""Typed runtime data owned exclusively by Slugcat."""

from dataclasses import dataclass, field

from card_duel.cards.slugcat.specs import FORM_NAMES, SLUGCAT_CARD_SPECS

MAX_KARMA = 10
MAX_SATIETY = 6
SLUGCAT_HEALTH = 5


@dataclass(slots=True)
class SlugcatData:
    karma: int = 3
    karma_max: int = 3
    satiety_max: int = MAX_SATIETY
    agility: int = 0
    momentum: int = 0
    satiety: int = 0
    last_card_id: int = 0
    jump_followup: bool = False
    form: str = "普通"
    seen_discoveries: list[int] = field(default_factory=list)
    discovery_pool: list[int] = field(default_factory=lambda: [27])
    discovery_discard: list[int] = field(default_factory=list)
    unlocked_creature_counts: dict[int, int] = field(
        default_factory=lambda: {
            spec.card_id: spec.source_count
            for spec in SLUGCAT_CARD_SPECS
            if 16 <= spec.card_id <= 26 and spec.source_count > 0
        }
    )
    creature_discard: list[int] = field(default_factory=list)
    redirect_creatures_to_opponent: bool = False
    discovery_discount: dict[int, int] = field(default_factory=dict)
    next_bubble_mode: str | None = None
    last_centipede_round: int = -1
    pearls_given: int = 0
    scavengers_killed: int = 0
    scavenger_kills: int = 0
    ability_unlocks: set[int] = field(default_factory=set)
    karma_flower_pending: bool = False
    hunter_spear_bonus: int = 0
    hunter_hand_bonus: int = 0
    wave_skill_returned: bool = False
    chaotic_last_energy: int = 0
    forage_satiety_count: int = 0
    consecutive_run_away_rounds: int = 0
    last_run_away_round: int = -1
    last_damage_round: int = -1
    last_damage_amount: int = 0
    lock_layers: int = 0
    has_grown_karma: bool = False
    spear_kill_types: set[int] = field(default_factory=set)
    maze_agility_reached: bool = False
    sky_colored_pearl_played: bool = False
    form_copies: dict[int, int] = field(default_factory=dict)


def slugcat_data(player) -> SlugcatData:
    if not isinstance(player.character_data, SlugcatData):
        raise TypeError("当前玩家不是蛞蝓猫或尚未初始化")
    return player.character_data


def gain_satiety(data: SlugcatData, amount: int) -> int:
    """Gain satiety capped at the maximum (6)."""
    previous = data.satiety
    data.satiety = min(MAX_SATIETY, data.satiety + max(0, amount))
    return data.satiety - previous


def has_form(data: SlugcatData, form_id: int) -> bool:
    """A form passive only applies while that form card has been played."""
    return data.form == FORM_NAMES[form_id]
