"""Headless checks for the interaction features retained from @CuiGer's work."""

import unittest
from collections import defaultdict
from types import SimpleNamespace

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.slugcat.state import slugcat_data
from card_duel.core.models import GameState
from card_duel.ui.card_interaction import (
    parse_hand_card_event,
    route_hand_card_event,
)
from card_duel.ui.deck_viewer import grouped_deck_cards
from card_duel.ui.network_log import classify_log_color
from card_duel.ui.network_style import COLOR_BLUE, COLOR_GREEN, COLOR_RED


class _Widget:
    def configure(self, **_kwargs):
        return None


class _Element:
    Widget = _Widget()

    def update(self, *_args, **_kwargs):
        return None


class _Window:
    AllKeysDict = {"-CARD-HINT-": True}

    def __init__(self):
        self.elements = defaultdict(_Element)

    def __getitem__(self, key):
        return self.elements[key]

    def refresh(self):
        return None


class UiLogicTests(unittest.TestCase):
    def _slugcat_state(self):
        state = GameState(character_ids={1: 4, 2: 1}, local_player_id=1)
        CombatEngine(state, DEFAULT_REGISTRY).initialize_players()
        return state

    def test_right_click_is_parsed_as_preview(self):
        self.assertEqual(parse_hand_card_event("-BTN3- RIGHT"), (3, True))
        self.assertEqual(parse_hand_card_event("-BTN3-"), (3, False))
        self.assertIsNone(parse_hand_card_event("-CHAT-SEND-"))

    def test_card_requires_two_left_clicks_to_confirm(self):
        state = self._slugcat_state()
        state.hand_cards[:] = [6]
        session = SimpleNamespace(
            state=state,
            card_images=[b""] * 51,
            armed_hand_index=None,
            require_window=lambda: _Window(),
        )

        self.assertEqual(route_hand_card_event(session, "-BTN0-"), ("armed", 0))
        self.assertEqual(route_hand_card_event(session, "-BTN0-"), ("confirmed", 0))

    def test_deck_viewer_separates_discoveries_and_creatures(self):
        state = self._slugcat_state()
        state.draw_pile[:] = [1, 1, 6]
        data = slugcat_data(state.local_player)
        data.discovery_pool[:] = [27, 28]
        data.unlocked_creature_counts = {16: 2, 20: 3}
        session = SimpleNamespace(state=state, registry=DEFAULT_REGISTRY)

        groups = grouped_deck_cards(session)

        self.assertEqual(groups["物品"][1], 2)
        self.assertEqual(groups["技能"][6], 1)
        self.assertEqual(groups["见闻牌堆"], {27: 1, 28: 1})
        self.assertEqual(groups["已解锁生物（不可抽取）"], {16: 2, 20: 3})

    def test_log_colors_distinguish_chat_damage_and_draws(self):
        self.assertEqual(classify_log_color("[我] 你好"), COLOR_BLUE)
        self.assertEqual(classify_log_color("玩家2失去3点生命"), COLOR_RED)
        self.assertEqual(classify_log_color("抽牌：翻滚"), COLOR_GREEN)


if __name__ == "__main__":
    unittest.main()
