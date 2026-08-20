"""Slugcat hand-limit and draw-pile operations."""

from card_duel.cards.slugcat.specs import (
    SLUGCAT_CREATURE_IDS,
    SLUGCAT_DISCOVERY_IDS,
)


def count_card(state, card_id: int) -> int:
    return state.hand_cards.count(card_id)


def effective_hand_size(state, player_id: int) -> int:
    """Apply the hand-limit exemption granted by a carried tube worm."""
    total = len(state.hand_cards)
    statuses = state.players[player_id].statuses
    has_tube_worm = any(item.card_id == 26 for item in statuses.hand_creatures)
    if not has_tube_worm:
        return total
    return total - sum(card_id in SLUGCAT_DISCOVERY_IDS for card_id in state.hand_cards)


def draw_non_creatures(state, amount: int) -> int:
    """Draw normal cards while leaving creature cards in the pile.

    When no eligible card sits on top of the draw pile, the discard pile is
    shuffled in (Slay-the-Spire style) before giving up, so that draws keep
    their per-round randomness instead of being blocked by an empty pile.
    """
    from card_duel.core.rules import reshuffle_discard_into_draw

    drawn = 0
    while drawn < max(0, amount):
        index = next(
            (
                index
                for index, card_id in enumerate(state.draw_pile)
                if card_id not in SLUGCAT_CREATURE_IDS
            ),
            None,
        )
        if index is None and state.discard_pile:
            reshuffle_discard_into_draw(state)
            index = next(
                (
                    index
                    for index, card_id in enumerate(state.draw_pile)
                    if card_id not in SLUGCAT_CREATURE_IDS
                ),
                None,
            )
        if index is None:
            break
        state.hand_cards.append(state.draw_pile.pop(index))
        drawn += 1
    return drawn
