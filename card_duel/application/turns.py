"""Presentation-independent operations shared by desktop and Web turns."""

from __future__ import annotations

import random
from collections.abc import Sequence
from contextlib import suppress

from card_duel.core.rules import draw_cards

HAND_LIMIT = 4


def _reshuffle_discard_by_type(game_state, predicate) -> bool:
    """Move only matching discard cards into the draw pile and shuffle.

    Keeps each card type cycling on its own: drawing skills never pulls item
    discard cards back, and vice versa.
    """
    picked = [card_id for card_id in game_state.discard_pile if predicate(card_id)]
    if not picked:
        return False
    for card_id in picked:
        game_state.discard_pile.remove(card_id)
    game_state.draw_pile.extend(picked)
    random.shuffle(game_state.draw_pile)
    return True


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

    def eligible(card_id, card_type):
        return SLUGCAT_SPECS_BY_ID[card_id].card_type == card_type

    def reshuffle_matching(card_type):
        return _reshuffle_discard_by_type(
            game_state,
            lambda cid: SLUGCAT_SPECS_BY_ID[cid].card_type == card_type,
        )

    def take(card_type):
        index = next(
            (
                index
                for index, card_id in enumerate(game_state.draw_pile)
                if eligible(card_id, card_type)
            ),
            None,
        )
        if index is None and reshuffle_matching(card_type):
            index = next(
                (
                    index
                    for index, card_id in enumerate(game_state.draw_pile)
                    if eligible(card_id, card_type)
                ),
                None,
            )
        if index is None:
            return False
        drawn.append(game_state.draw_pile.pop(index))
        return True

    for _ in range(skill_count):
        if not take("技能"):
            break
    for _ in range(item_count):
        if not take("物品"):
            break
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


def return_card_after_use(
    game_state, player_id: int, card_id: int, *, from_play: bool = False
) -> None:
    from card_duel.cards.slugcat.specs import (
        SLUGCAT_DISCOVERY_IDS,
        SLUGCAT_SPECS_BY_ID,
    )
    from card_duel.cards.slugcat.state import SlugcatData, has_form, slugcat_data

    player = game_state.players[player_id]
    if card_id in SLUGCAT_DISCOVERY_IDS and isinstance(
        player.character_data, SlugcatData
    ):
        slugcat_data(player).discovery_discard.append(card_id)
        return
    if from_play and isinstance(player.character_data, SlugcatData):
        data = slugcat_data(player)
        spec = SLUGCAT_SPECS_BY_ID.get(card_id)
        if (
            spec is not None
            and spec.card_type == "技能"
            and has_form(data, 37)
            and not data.wave_skill_returned
        ):
            # 波浪舞者：每回合第一张技能牌回到手牌。
            data.wave_skill_returned = True
            game_state.hand_cards.append(card_id)
            return
    game_state.discard_pile.append(card_id)


def hand_limit_for(game_state, player_id: int) -> int:
    """Rule-aware hand limit (hunter form adds +1 to the slugcat limit)."""
    if game_state.character_ids.get(player_id) == 4:
        from card_duel.cards.slugcat.state import has_form

        data = getattr(game_state.players[player_id], "character_data", None)
        if data is not None and has_form(data, 36):
            return HAND_LIMIT + (getattr(data, "hunter_hand_bonus", 0) or 0)
        return HAND_LIMIT
    return HAND_LIMIT


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
