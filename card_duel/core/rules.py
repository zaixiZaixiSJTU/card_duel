"""Character-agnostic domain operations."""

from __future__ import annotations

import random

from card_duel.core.models import DefenceEffect, GameState, ScheduledEvent


def build_shuffled_deck(
    first_card_id: int,
    last_card_id: int,
    card_counts: dict[int, int] | None = None,
) -> list[int]:
    counts = card_counts or {
        card_id: 1 for card_id in range(first_card_id, last_card_id + 1)
    }
    deck = [
        card_id
        for card_id in range(first_card_id, last_card_id + 1)
        for _ in range(counts.get(card_id, 0))
    ]
    random.shuffle(deck)
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


def draw_cards(game_state: GameState, amount: int) -> int:
    drawn = min(max(0, amount), len(game_state.draw_pile))
    game_state.hand_cards.extend(game_state.draw_pile[:drawn])
    del game_state.draw_pile[:drawn]
    return drawn
