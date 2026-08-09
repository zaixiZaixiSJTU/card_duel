"""Slugcat character package."""

from card_duel.cards.slugcat.catalog import register
from card_duel.cards.slugcat.lifecycle import SlugcatRules
from card_duel.cards.slugcat.state import SlugcatData, slugcat_data

__all__ = ["SlugcatData", "SlugcatRules", "register", "slugcat_data"]
