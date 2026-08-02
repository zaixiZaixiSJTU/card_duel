"""Lazy public card API.

Keeping this package initializer lazy means importing the generic registry does
not construct or import any built-in character package.
"""


def _default_registry():
    from card_duel.cards.catalog import DEFAULT_REGISTRY

    return DEFAULT_REGISTRY


def get_card_counts(character_id):
    return _default_registry().get_deck_counts(character_id)


def get_card_definition(character_id, card_id):
    return _default_registry().get_card(character_id, card_id)


def get_character_card_catalog(character_id):
    return _default_registry().get_catalog(character_id)


def play_registered_card(
    game_state,
    character_id,
    card_id,
    source_player_id,
    target_player_id,
    announce,
    ignore_cost=False,
    choices=None,
    combat=None,
):
    """Compatibility wrapper; internal code uses ``CardRegistry.play``."""
    from card_duel.application.combat import CombatEngine

    registry = _default_registry()
    engine = combat or CombatEngine(game_state, registry)
    return registry.play(
        state=game_state,
        character_id=character_id,
        card_id=card_id,
        source_player_id=source_player_id,
        target_player_id=target_player_id,
        announce=announce,
        choices=choices,
        combat=engine,
        ignore_cost=ignore_cost,
    )


def __getattr__(name):
    if name == "DEFAULT_REGISTRY":
        return _default_registry()
    if name in {"CardDefinition", "CardPlayContext"}:
        from card_duel.cards import models

        return getattr(models, name)
    if name == "CardRegistry":
        from card_duel.cards.registry import CardRegistry

        return CardRegistry
    raise AttributeError(name)


__all__ = [
    "CardDefinition",
    "CardPlayContext",
    "CardRegistry",
    "DEFAULT_REGISTRY",
    "get_card_counts",
    "get_card_definition",
    "get_character_card_catalog",
    "play_registered_card",
]
