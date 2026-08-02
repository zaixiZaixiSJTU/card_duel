"""Warrior-owned card catalog and registration entry."""

from card_duel.cards.models import CardDefinition, CharacterDefinition
from card_duel.cards.warrior import effects
from card_duel.cards.warrior.lifecycle import WarriorRules

CHARACTER_ID = 1
DECK_COUNTS = {
    1: 6,
    2: 6,
    3: 2,
    4: 1,
    5: 1,
    6: 2,
    7: 1,
    8: 2,
    9: 2,
    10: 1,
    11: 2,
    12: 1,
    13: 1,
    14: 1,
    15: 1,
    16: 1,
}

_CARDS = (
    CardDefinition(1, 0, "不可用", effects.unavailable),
    CardDefinition(1, 1, "攻", effects.attack, cost=1),
    CardDefinition(1, 2, "防", effects.defend, cost=2),
    CardDefinition(1, 3, "盾击", effects.shield_bash, cost=2),
    CardDefinition(1, 4, "背包之神", effects.pack_god, cost=0),
    CardDefinition(1, 5, "献祭", effects.sacrifice, cost=2),
    CardDefinition(1, 6, "重剑打击", effects.heavy_sword, cost=3),
    CardDefinition(1, 7, "重锤打击", effects.heavy_hammer, cost=7),
    CardDefinition(1, 8, "燃烧", effects.burn, cost=0),
    CardDefinition(1, 9, "糖原堆积", effects.glycogen, cost=2),
    CardDefinition(1, 10, "壁垒", effects.bastion, exhausted=True, cost=4),
    CardDefinition(1, 11, "巩固", effects.consolidate, cost=3),
    CardDefinition(1, 12, "全身撞击", effects.full_body_slam, cost=4),
    CardDefinition(
        1, 13, "不动如山", effects.immovable_mountain, exhausted=True, cost=3
    ),
    CardDefinition(1, 14, "心连心", effects.heartlink, cost=2),
    CardDefinition(1, 15, "黑闪", effects.black_flash, cost=2),
    CardDefinition(1, 16, "燔祭", effects.burnt_offering, cost=3),
)


def register(registry) -> None:
    registry.register_character(
        CharacterDefinition(
            character_id=CHARACTER_ID,
            name="战士",
            deck_counts=DECK_COUNTS,
            cards=_CARDS,
            rules=WarriorRules(),
        )
    )
