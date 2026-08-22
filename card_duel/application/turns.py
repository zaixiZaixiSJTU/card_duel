"""Presentation-independent operations shared by desktop and Web turns."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress

from card_duel.core.rules import draw_cards

HAND_LIMIT = 4


def draw_turn_cards(context, local_announce=None) -> None:
    if context.game_state.character_ids.get(context.player_id) == 4:
        draw_slugcat_cards(
            context.game_state,
            2,
            1,
            local_announce or context.announce,
        )
    else:
        draw_cards(context.game_state, 3)


def draw_slugcat_cards(game_state, skill_count, item_count, announce) -> int:
    """Draw by type without ever actively drawing creature cards."""
    from card_duel.cards.slugcat.specs import SLUGCAT_SPECS_BY_ID

    drawn = []

    def draw_type(card_type, amount):
        for _ in range(amount):
            index = next(
                (
                    index
                    for index, card_id in enumerate(game_state.draw_pile)
                    if SLUGCAT_SPECS_BY_ID[card_id].card_type == card_type
                ),
                None,
            )
            if index is None:
                break
            drawn.append(game_state.draw_pile.pop(index))

    draw_type("技能", skill_count)
    draw_type("物品", item_count)
    while len(drawn) < skill_count + item_count:
        index = next(
            (
                index
                for index, card_id in enumerate(game_state.draw_pile)
                if SLUGCAT_SPECS_BY_ID[card_id].card_type not in {"生物", "见闻"}
            ),
            None,
        )
        if index is None:
            break
        drawn.append(game_state.draw_pile.pop(index))
    game_state.hand_cards.extend(drawn)
    if drawn:
        names = "、".join(SLUGCAT_SPECS_BY_ID[card_id].name for card_id in drawn)
        announce(f"抽牌：{names}")
    return len(drawn)


def remove_played_card(game_state, original_index: int, card_id: int) -> None:
    if (
        original_index < len(game_state.hand_cards)
        and game_state.hand_cards[original_index] == card_id
    ):
        game_state.hand_cards.pop(original_index)
        return
    with suppress(ValueError):
        game_state.hand_cards.remove(card_id)


def return_card_after_use(game_state, player_id: int, card_id: int) -> None:
    from card_duel.cards.slugcat.specs import SLUGCAT_DISCOVERY_IDS
    from card_duel.cards.slugcat.state import SlugcatData, slugcat_data

    player = game_state.players[player_id]
    if card_id in SLUGCAT_DISCOVERY_IDS and isinstance(
        player.character_data, SlugcatData
    ):
        slugcat_data(player).discovery_pool.append(card_id)
    else:
        game_state.discard_pile.append(card_id)


def effective_hand_size(
    game_state, player_id: int, hand_cards: Sequence[int] | None = None
) -> int:
    """Return the rule-aware hand size for either the active or a supplied zone."""
    cards = game_state.hand_cards if hand_cards is None else hand_cards
    if game_state.character_ids.get(player_id) != 4:
        return len(cards)

    from card_duel.cards.slugcat.specs import SLUGCAT_DISCOVERY_IDS

    statuses = game_state.players[player_id].statuses
    has_tube_worm = any(item.card_id == 26 for item in statuses.hand_creatures)
    if not has_tube_worm:
        return len(cards)
    return len(cards) - sum(card_id in SLUGCAT_DISCOVERY_IDS for card_id in cards)


def can_discard(game_state, player_id: int, card_id: int) -> bool:
    if game_state.character_ids.get(player_id) != 4:
        return card_id not in (49, 50)
    from card_duel.cards.slugcat.specs import SLUGCAT_NO_DISCARD_IDS

    return card_id not in SLUGCAT_NO_DISCARD_IDS
