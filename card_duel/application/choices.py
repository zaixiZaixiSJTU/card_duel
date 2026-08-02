"""Input boundary used by card effects that require a player decision."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class ChoiceProvider(Protocol):
    def choose_integer(
        self, title: str, prompt: str, minimum: int, maximum: int, default: int
    ) -> int | None: ...

    def choose_option(
        self, title: str, prompt: str, options: Sequence[str], default: str
    ) -> str | None: ...

    def choose_card_indexes(
        self,
        title: str,
        hand: Sequence[int],
        count: int,
        excluded_card_id: int | None = None,
    ) -> list[int] | None: ...


class AutomaticChoiceProvider:
    """Deterministic non-GUI choices for tests and headless integrations."""

    def choose_integer(self, title, prompt, minimum, maximum, default):
        return max(minimum, min(maximum, default))

    def choose_option(self, title, prompt, options, default):
        return default if default in options else (options[0] if options else None)

    def choose_card_indexes(self, title, hand, count, excluded_card_id=None):
        eligible = [
            index for index, card_id in enumerate(hand) if card_id != excluded_card_id
        ]
        return eligible[:count] if len(eligible) >= count else None


DEFAULT_CHOICES = AutomaticChoiceProvider()
