"""Slugcat-owned card catalog and registration entry."""

from card_duel.cards.injected import handler_for as inserted_handler
from card_duel.cards.models import CardDefinition, CharacterDefinition
from card_duel.cards.slugcat.effects import make_handler
from card_duel.cards.slugcat.lifecycle import SlugcatRules
from card_duel.cards.slugcat.specs import (
    SLUGCAT_CARD_SPECS,
    SLUGCAT_CHARACTER_ID,
    SLUGCAT_INITIAL_DECK_COUNTS,
)


def unavailable(context):
    context.announce("这张牌不可用")
    return False


def register(registry) -> None:
    cards = [CardDefinition(SLUGCAT_CHARACTER_ID, 0, "不可用", unavailable)]
    cards.extend(
        CardDefinition(
            character_id=SLUGCAT_CHARACTER_ID,
            card_id=spec.card_id,
            name=spec.name,
            handler=(
                inserted_handler(spec.card_id)
                if spec.card_id in (49, 50)
                else make_handler(spec.card_id)
            ),
            exhausted=spec.exhausted,
            card_type=spec.card_type,
            cost=spec.cost,
            description=spec.description,
        )
        for spec in SLUGCAT_CARD_SPECS
    )
    registry.register_character(
        CharacterDefinition(
            character_id=SLUGCAT_CHARACTER_ID,
            name="蛞蝓猫",
            deck_counts=SLUGCAT_INITIAL_DECK_COUNTS,
            cards=tuple(cards),
            rules=SlugcatRules(),
        )
    )
