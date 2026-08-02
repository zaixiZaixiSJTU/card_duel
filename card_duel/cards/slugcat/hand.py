"""Small hand-zone helpers shared by Slugcat effects and lifecycle hooks."""

from card_duel.cards.slugcat.specs import SLUGCAT_CREATURE_IDS


def count_card(state, card_id: int) -> int:
    return state.hand_cards.count(card_id)


def remove_first(state, card_id: int) -> bool:
    try:
        state.hand_cards.remove(card_id)
        return True
    except ValueError:
        return False


def pop_first_creature(state) -> int | None:
    for index, card_id in enumerate(state.hand_cards):
        if card_id in SLUGCAT_CREATURE_IDS:
            return state.hand_cards.pop(index)
    return None


def remove_all_creatures(state) -> None:
    state.hand_cards[:] = [
        card_id for card_id in state.hand_cards if card_id not in SLUGCAT_CREATURE_IDS
    ]


def add_creature_threat(state, player_id: int, creature_id: int) -> None:
    state.players[player_id].statuses.creature_threats.append(creature_id)
