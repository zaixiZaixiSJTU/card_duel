"""Character-agnostic domain operations."""

from __future__ import annotations

import random

from card_duel.core.models import DefenceEffect, GameState, ScheduledEvent


def build_shuffled_deck(
    first_card_id: int,
    last_card_id: int,
    card_counts: dict[int, int] | None = None,
    *,
    random_seed: int | None = None,
) -> list[int]:
    counts = card_counts or {
        card_id: 1 for card_id in range(first_card_id, last_card_id + 1)
    }
    deck = [
        card_id
        for card_id in range(first_card_id, last_card_id + 1)
        for _ in range(counts.get(card_id, 0))
    ]
    if random_seed is None:
        random.shuffle(deck)
    else:
        random.Random(random_seed).shuffle(deck)
    return deck


def add_defence(
    defence_list: list[DefenceEffect], amount: int, turns_remaining: int = 1
) -> None:
    """Insert or merge defence while preserving expiry order."""
    new_effect = DefenceEffect(turns_remaining, amount)
    for index, effect in enumerate(defence_list):
        if effect.turns_remaining == turns_remaining:
            effect.amount += amount
            return
        if effect.turns_remaining > turns_remaining:
            defence_list.insert(index, new_effect)
            return
    defence_list.append(new_effect)


def schedule_event(timeline: list[ScheduledEvent], event: ScheduledEvent) -> None:
    """Insert a delayed event in ascending resolution order."""
    index = 0
    while (
        index < len(timeline)
        and event.turns_remaining >= timeline[index].turns_remaining
    ):
        index += 1
    timeline.insert(index, event)


def add_card_to_hand(game_state: GameState, card_id: int) -> None:
    game_state.hand_cards.append(card_id)


def reshuffle_discard_into_draw(game_state: GameState) -> bool:
    """Move every card from the discard pile into the draw pile and shuffle.

    Implements the Slay-the-Spire cycle: when the draw pile cannot satisfy a
    draw, the discard pile is shuffled in to refresh it. Returns ``True`` if
    any cards were moved.
    """
    if not game_state.discard_pile:
        return False
    game_state.draw_pile.extend(game_state.discard_pile)
    game_state.discard_pile.clear()
    random.shuffle(game_state.draw_pile)
    return True


def draw_cards(game_state: GameState, amount: int) -> int:
    """Draw ``amount`` cards from the top of the draw pile.

    When the draw pile runs out, the discard pile is shuffled in to form a
    fresh draw pile (Slay-the-Spire style) so that each round's draw order is
    not fixed. Returns the number of cards actually drawn.
    """
    drawn = 0
    while drawn < amount:
        if not game_state.draw_pile:
            reshuffle_discard_into_draw(game_state)
            if not game_state.draw_pile:
                break  # Both piles exhausted.
        game_state.hand_cards.append(game_state.draw_pile.pop(0))
        drawn += 1
    return drawn
