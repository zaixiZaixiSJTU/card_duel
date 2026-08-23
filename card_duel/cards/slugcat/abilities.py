"""Ability unlock bookkeeping shared by slugcat effects and creature hooks."""

from card_duel.cards.slugcat.specs import ABILITY_CARD_IDS, SLUGCAT_SPECS_BY_ID
from card_duel.cards.slugcat.state import slugcat_data


def unlock_ability_card(player, card_id: int, announce=None) -> bool:
    """Unlock one form ability and put its card into the discovery pool."""
    data = slugcat_data(player)
    if card_id not in ABILITY_CARD_IDS or card_id in data.ability_unlocks:
        return False
    data.ability_unlocks.add(card_id)
    if card_id == 36:
        data.hunter_spear_bonus = 2
        data.hunter_hand_bonus = 1
    if card_id not in data.discovery_pool:
        data.discovery_pool.append(card_id)
    if announce is not None:
        announce(f"解锁形态：{SLUGCAT_SPECS_BY_ID[card_id].name}已加入见闻牌堆")
    return True
