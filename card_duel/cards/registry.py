"""Central registration area for every playable card."""

from dataclasses import dataclass
from typing import Callable

from card_duel.core import combat
from card_duel.cards.slugcat import get_slugcat_handler
from card_duel.cards.slugcat_data import (
    SLUGCAT_CARD_SPECS,
    SLUGCAT_CHARACTER_ID,
    SLUGCAT_INITIAL_DECK_COUNTS,
)

CardHandler = Callable[..., bool | int]


@dataclass(frozen=True)
class CardDefinition:
    """Static metadata and effect handler for one card."""

    character_id: int
    card_id: int
    name: str
    handler: CardHandler
    exhausted: bool = False
    card_type: str = "卡牌"
    cost: int | None = None
    description: str = ""


# 牌组构成与效果注册集中维护；新增卡牌只需要修改这一处。
CARD_COUNTS_BY_CHARACTER = {
    1: {
        1: 6, 2: 6, 3: 2, 4: 1, 5: 1, 6: 2, 7: 1, 8: 2,
        9: 2, 10: 1, 11: 2, 12: 1, 13: 1, 14: 1, 15: 1, 16: 1,
    },
    2: {1: 2, 2: 3, 3: 1, 4: 4, 5: 2},
    3: {1: 2, 2: 3, 3: 1, 4: 4, 5: 2},
    SLUGCAT_CHARACTER_ID: SLUGCAT_INITIAL_DECK_COUNTS,
}

CARD_REGISTRY = {
    (0, 0): CardDefinition(0, 0, "不可用", combat.play_unavailable_card),
    (1, 0): CardDefinition(1, 0, "不可用", combat.play_unavailable_card),
    (1, 1): CardDefinition(1, 1, "攻", combat.play_attack_card),
    (1, 2): CardDefinition(1, 2, "防", combat.play_defend_card),
    (1, 3): CardDefinition(1, 3, "盾击", combat.play_shield_bash_card),
    (1, 4): CardDefinition(1, 4, "背包之神", combat.play_pack_god_card),
    (1, 5): CardDefinition(1, 5, "献祭", combat.play_sacrifice_card),
    (1, 6): CardDefinition(1, 6, "重剑打击", combat.play_heavy_sword_card),
    (1, 7): CardDefinition(1, 7, "重锤打击", combat.play_heavy_hammer_card),
    (1, 8): CardDefinition(1, 8, "燃烧", combat.play_burn_card),
    (1, 9): CardDefinition(1, 9, "糖原堆积", combat.play_glycogen_card),
    (1, 10): CardDefinition(
        1, 10, "壁垒", combat.play_bastion_card, exhausted=True
    ),
    (1, 11): CardDefinition(1, 11, "巩固", combat.play_consolidate_card),
    (1, 12): CardDefinition(
        1, 12, "全身撞击", combat.play_full_body_slam_card
    ),
    (1, 13): CardDefinition(
        1,
        13,
        "不动如山",
        combat.play_immovable_mountain_card,
        exhausted=True,
    ),
    (1, 14): CardDefinition(1, 14, "心连心", combat.play_heartlink_card),
    (1, 15): CardDefinition(1, 15, "黑闪", combat.play_black_flash_card),
    (1, 16): CardDefinition(1, 16, "燔祭", combat.play_burnt_offering_card),
    (2, 0): CardDefinition(2, 0, "未实现", combat.play_unavailable_card),
    (3, 0): CardDefinition(3, 0, "未实现", combat.play_unavailable_card),
    (SLUGCAT_CHARACTER_ID, 0): CardDefinition(
        SLUGCAT_CHARACTER_ID,
        0,
        "不可用",
        combat.play_unavailable_card,
    ),
}

CARD_REGISTRY.update(
    {
        (SLUGCAT_CHARACTER_ID, spec.card_id): CardDefinition(
            character_id=SLUGCAT_CHARACTER_ID,
            card_id=spec.card_id,
            name=spec.name,
            handler=get_slugcat_handler(spec.card_id),
            exhausted=spec.exhausted,
            card_type=spec.card_type,
            cost=spec.cost,
            description=spec.description,
        )
        for spec in SLUGCAT_CARD_SPECS
    }
)


def get_card_counts(character_id):
    """Return a copy so callers cannot mutate the registry configuration."""
    return CARD_COUNTS_BY_CHARACTER[character_id].copy()


def get_card_definition(character_id, card_id):
    try:
        return CARD_REGISTRY[(character_id, card_id)]
    except KeyError as error:
        raise KeyError(
            f"角色 {character_id} 未注册卡牌 {card_id}"
        ) from error


def get_character_card_catalog(character_id):
    """Return registered definitions ordered by card id for UI rendering."""
    return [
        definition
        for (registered_character_id, _), definition in sorted(
            CARD_REGISTRY.items(), key=lambda item: item[0]
        )
        if registered_character_id == character_id
    ]


def play_registered_card(
    game_state,
    character_id,
    card_id,
    source_player_id,
    target_player_id,
    announce,
    ignore_cost=False,
):
    """Resolve a card through the registry instead of a hard-coded map."""
    definition = get_card_definition(character_id, card_id)
    return definition.handler(
        game_state,
        source_player_id,
        target_player_id,
        announce,
        ignore_cost,
    )
