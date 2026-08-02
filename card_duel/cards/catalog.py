"""Application composition root for built-in character packages."""

from card_duel.cards.placeholders import register as register_placeholders
from card_duel.cards.registry import CardRegistry
from card_duel.cards.slugcat import register as register_slugcat
from card_duel.cards.warrior import register as register_warrior


def build_default_registry() -> CardRegistry:
    registry = CardRegistry()
    register_warrior(registry)
    register_placeholders(registry)
    register_slugcat(registry)
    return registry.freeze()


DEFAULT_REGISTRY = build_default_registry()
