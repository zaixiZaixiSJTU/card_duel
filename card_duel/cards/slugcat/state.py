"""Typed runtime data owned exclusively by Slugcat."""

from dataclasses import dataclass, field

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
    discovery_pool: list[int] = field(default_factory=lambda: [27, 27, 27])
    next_x_cost: int | None = None
    next_bubble_mode: str | None = None


def slugcat_data(player) -> SlugcatData:
    if not isinstance(player.character_data, SlugcatData):
        raise TypeError("当前玩家不是蛞蝓猫或尚未初始化")
    return player.character_data
