"""Typed runtime data owned exclusively by Slugcat."""

from dataclasses import dataclass, field

from card_duel.cards.slugcat.specs import SLUGCAT_CARD_SPECS

MAX_KARMA = 5
SLUGCAT_HEALTH = 5


@dataclass(slots=True)
class SlugcatData:
    karma: int = 3
    karma_max: int = 3
    agility: int = 0
    momentum: int = 0
    satiety: int = 0
    last_card_id: int = 0
    jump_followup: bool = False
    form: str = "普通"
    seen_discoveries: list[int] = field(default_factory=list)
    discovery_pool: list[int] = field(default_factory=lambda: [27])
    unlocked_creature_counts: dict[int, int] = field(
        default_factory=lambda: {
            spec.card_id: spec.source_count
            for spec in SLUGCAT_CARD_SPECS
            if 16 <= spec.card_id <= 26 and spec.source_count > 0
        }
    )
    redirect_creatures_to_opponent: bool = False
    discovery_discount: dict[int, int] = field(default_factory=dict)
    next_bubble_mode: str | None = None
    last_centipede_round: int = -1
    pearls_given: int = 0
    scavengers_killed: int = 0


def slugcat_data(player) -> SlugcatData:
    if not isinstance(player.character_data, SlugcatData):
        raise TypeError("当前玩家不是蛞蝓猫或尚未初始化")
    return player.character_data
