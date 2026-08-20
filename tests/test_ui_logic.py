"""Headless checks for the interaction features retained from @CuiGer's work."""

import base64
import io
import unittest
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.slugcat.state import slugcat_data
from card_duel.core.models import GameState
from card_duel.ui.auxiliary_windows import DECK_EVENT_HANDLED, read_primary_window
from card_duel.ui.card_animations import (
    animate_hand_additions,
    enlarged_card_image,
)
from card_duel.ui.card_interaction import (
    _set_card_spacing,
    parse_hand_card_event,
    route_hand_card_event,
)
from card_duel.ui.deck_viewer import (
    DECK_VIEW_KEY_DISCARD,
    DECK_VIEW_KEY_DRAW,
    grouped_deck_cards,
    handle_deck_viewer_event,
)
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


class _PollingWindow:
    def __init__(self, event="__TIMEOUT__"):
        self.event = event
        self.timeouts = []
        self.closed = False

    def read(self, timeout=None):
        self.timeouts.append(timeout)
        return self.event, {}

    def close(self):
        self.closed = True


class _ManagedWidget:
    def __init__(self, manager):
        self.manager = manager
        self.pack_options = []
        self.grid_options = []

    def winfo_manager(self):
        return self.manager

    def pack_configure(self, **kwargs):
        self.pack_options.append(kwargs)

    def grid_configure(self, **kwargs):
        self.grid_options.append(kwargs)


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
        self.assertEqual(groups["可召唤生物（不进牌堆）"], {16: 2, 20: 3})

    def test_log_colors_distinguish_chat_damage_and_draws(self):
        self.assertEqual(classify_log_color("[我] 你好"), COLOR_BLUE)
        self.assertEqual(classify_log_color("玩家2失去3点生命"), COLOR_RED)
        self.assertEqual(classify_log_color("抽牌：翻滚"), COLOR_GREEN)

    def test_deck_card_preview_requires_right_click(self):
        session = SimpleNamespace(
            deck_viewer_card_ids=[6],
            card_images=[b""] * 51,
        )
        with patch("card_duel.ui.deck_viewer.open_card_preview") as preview:
            self.assertTrue(handle_deck_viewer_event(session, "-DECK-CARD-0-"))
            preview.assert_not_called()

            self.assertTrue(handle_deck_viewer_event(session, "-DECK-CARD-0- RIGHT"))
            preview.assert_called_once_with(session, session.card_images[6])

    def test_deck_view_buttons_open_with_correct_mode(self):
        session = SimpleNamespace()
        with patch("card_duel.ui.deck_viewer.open_deck_viewer") as opener:
            self.assertTrue(handle_deck_viewer_event(session, DECK_VIEW_KEY_DRAW))
            opener.assert_called_once_with(session, mode="draw")

            self.assertTrue(handle_deck_viewer_event(session, DECK_VIEW_KEY_DISCARD))
            opener.assert_called_with(session, mode="discard")

    def test_primary_read_always_gives_auxiliary_windows_a_time_slice(self):
        primary = _PollingWindow(event="main-event")
        preview = _PollingWindow()
        session = SimpleNamespace(
            require_window=lambda: primary,
            deck_viewer_open=False,
            preview_window=preview,
        )

        result = read_primary_window(session, timeout=37)

        self.assertEqual(result, ("main-event", {}))
        self.assertEqual(primary.timeouts, [37])
        self.assertEqual(preview.timeouts, [0])

    def test_deck_events_are_consumed_inside_primary_loop(self):
        primary = _PollingWindow(event="-DECK-CARD-0-")
        session = SimpleNamespace(
            require_window=lambda: primary,
            deck_viewer_open=False,
            deck_viewer_card_ids=[6],
            card_images=[b""] * 51,
            preview_window=None,
        )

        self.assertEqual(
            read_primary_window(session, timeout=10),
            (DECK_EVENT_HANDLED, {}),
        )
        self.assertEqual(primary.timeouts, [10])

    def test_hand_addition_animation_handles_duplicate_card_ids(self):
        session = SimpleNamespace(
            state=SimpleNamespace(hand_cards=[6, 6, 8, 6]),
        )
        with patch("card_duel.ui.card_animations.animate_draw_cards") as animate_draw:
            added = animate_hand_additions(session, [6, 8])

        self.assertEqual(added, 2)
        animate_draw.assert_called_once_with(session, [1, 3])

    def test_right_click_preview_is_rendered_at_double_card_size(self):
        image = Image.new("RGB", (160, 240), "#FFFFFF")
        source = io.BytesIO()
        image.save(source, format="PNG")

        enlarged = enlarged_card_image(base64.b64encode(source.getvalue()))

        with Image.open(io.BytesIO(base64.b64decode(enlarged))) as result:
            self.assertEqual(result.size, (320, 480))

    def test_selection_lift_respects_scrollable_pack_layout(self):
        widget = _ManagedWidget("pack")

        _set_card_spacing(widget, True)
        _set_card_spacing(widget, False)

        self.assertEqual(widget.pack_options, [{"pady": 7}, {"pady": 0}])
        self.assertFalse(widget.grid_options)


if __name__ == "__main__":
    unittest.main()
