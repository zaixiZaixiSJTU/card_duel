"""Start/end match flow: seeded deals, seed exchange, rematch reset."""

import socket
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.core.models import GameState
from card_duel.core.rules import build_shuffled_deck
from card_duel.network.session import GameSession
from card_duel.network.setup import (
    RoomConfig,
    _collect_host_rules,
    announce_room_config,
    apply_room_config,
    exchange_match_seed,
    reset_for_rematch,
    room_phase,
)
from card_duel.ui.main_menu import host_setup_dialog, main_menu_dialog


class MatchFlowTests(unittest.TestCase):
    def test_same_seed_same_deal_different_seed_differs(self):
        deck_a = build_shuffled_deck(1, 20, random_seed=42)
        deck_b = build_shuffled_deck(1, 20, random_seed=42)
        deck_c = build_shuffled_deck(1, 20, random_seed=43)

        self.assertEqual(deck_a, deck_b)
        self.assertNotEqual(deck_a, deck_c)

    def test_registry_lists_characters(self):
        ids = DEFAULT_REGISTRY.get_character_ids()

        self.assertIn(1, ids)
        self.assertIn(4, ids)

    def test_match_seed_exchange_syncs_both_sides(self):
        left, right = socket.socketpair()
        try:
            host = SimpleNamespace(
                connection=left, state=GameState(local_player_id=1)
            )
            client = SimpleNamespace(
                connection=right, state=GameState(local_player_id=2)
            )

            exchange_match_seed(host, 1, is_host=True, seed=12345)
            exchange_match_seed(client, 2, is_host=False)

            self.assertEqual(host.state.random_seed, 12345)
            self.assertEqual(client.state.random_seed, 12345)
        finally:
            left.close()
            right.close()

    def test_reset_for_rematch_clears_match_state(self):
        session = GameSession(state=GameState(local_player_id=1), connection=None)
        session.state.random_seed = 1
        session.armed_hand_index = 0
        session.armed_creature_index = 1
        session.deck_viewer_open = True
        session.log_history = ["x"]

        reset_for_rematch(session, 1)

        self.assertIsNone(session.state.random_seed)
        self.assertIsNone(session.armed_hand_index)
        self.assertIsNone(session.armed_creature_index)
        self.assertFalse(session.deck_viewer_open)
        self.assertEqual(session.log_history, [])
        self.assertIsNotNone(session.combat)
        self.assertEqual(session.state.local_player_id, 1)

    def test_main_menu_returns_chosen_action(self):
        fake = SimpleNamespace(read=lambda: ("join", {}), close=lambda: None)
        with patch("card_duel.ui.main_menu.sg.Window", return_value=fake):
            self.assertEqual(main_menu_dialog(), "join")

        fake_quit = SimpleNamespace(read=lambda: (None, {}), close=lambda: None)
        with patch("card_duel.ui.main_menu.sg.Window", return_value=fake_quit):
            self.assertIsNone(main_menu_dialog())

    def test_host_setup_parses_character_and_seed(self):
        fake = SimpleNamespace(
            read=lambda: (
                "-HOST-START-",
                {"-HOST-CHAR-": "4 蛞蝓猫", "-HOST-SEED-": "123"},
            ),
            close=lambda: None,
        )
        with patch("card_duel.ui.main_menu.sg.Window", return_value=fake):
            self.assertEqual(host_setup_dialog(DEFAULT_REGISTRY), (4, 123))

        fake_random = SimpleNamespace(
            read=lambda: (
                "-HOST-START-",
                {"-HOST-CHAR-": "1 战士", "-HOST-SEED-": ""},
            ),
            close=lambda: None,
        )
        with patch("card_duel.ui.main_menu.sg.Window", return_value=fake_random):
            self.assertEqual(host_setup_dialog(DEFAULT_REGISTRY), (1, None))

    def test_collect_host_rules(self):
        guest = _collect_host_rules(
            {"-ROOM-FIRST-GUEST-": True, "-ROOM-SEED-": "7", "-ROOM-NO-DMG-": True}
        )
        self.assertEqual(guest, (7, 2, True, "guest", "7"))
        host = _collect_host_rules(
            {"-ROOM-FIRST-HOST-": True, "-ROOM-SEED-": "", "-ROOM-NO-DMG-": False}
        )
        self.assertEqual(host[1], 1)
        self.assertEqual(host[3], "host")
        self.assertFalse(host[2])
        bad = _collect_host_rules(
            {"-ROOM-FIRST-HOST-": True, "-ROOM-SEED-": "abc"}
        )
        self.assertIsNone(bad)

    def test_apply_room_config_sets_match_state(self):
        session = GameSession(state=GameState(local_player_id=1), connection=None)
        config = RoomConfig(
            host_character=1,
            guest_character=4,
            seed=123,
            first_player_id=2,
            round1_no_damage=True,
        )

        apply_room_config(session, config, 1)

        self.assertEqual(session.state.character_ids[1], 1)
        self.assertEqual(session.state.character_ids[2], 4)
        self.assertEqual(session.state.random_seed, 123)
        self.assertEqual(session.state.first_player_id, 2)
        self.assertTrue(session.state.round1_no_damage)

    def test_round1_no_damage_blocks_first_player_attack(self):
        game = GameState(character_ids={1: 4, 2: 4}, local_player_id=1)
        game.first_player_id = 1
        game.round1_no_damage = True
        game.round_number = 1
        combat = CombatEngine(game, DEFAULT_REGISTRY)
        combat.initialize_players()
        game.players[1].energy = 1
        game.players[2].health = 20
        game.hand_cards[:] = [1]
        messages = []

        DEFAULT_REGISTRY.play(
            state=game,
            character_id=4,
            card_id=1,
            source_player_id=1,
            target_player_id=2,
            announce=messages.append,
            combat=combat,
        )

        self.assertEqual(game.players[2].health, 20)
        self.assertTrue(any("无法造成生命损失" in m for m in messages))
        # 其他效果保留：钢筋仍插入后手方
        self.assertEqual(game.players[2].statuses.embedded_steel_rods, 1)
        self.assertIn(49, game.players[2].statuses.pending_hand_additions)

        game.round_number = 2
        game.players[1].energy = 1
        DEFAULT_REGISTRY.play(
            state=game,
            character_id=4,
            card_id=1,
            source_player_id=1,
            target_player_id=2,
            announce=messages.append,
            combat=combat,
        )
        self.assertEqual(game.players[2].health, 18)

    def test_announce_room_config_logs_settings(self):
        window = _LogWindow()
        session = SimpleNamespace(
            state=GameState(local_player_id=1),
            registry=DEFAULT_REGISTRY,
            require_window=lambda: window,
        )
        session.state.character_ids[1] = 1
        session.state.character_ids[2] = 4
        session.state.random_seed = 42
        session.state.first_player_id = 2
        session.state.round1_no_damage = True

        announce_room_config(session)

        joined = "".join(window.widget.lines)
        self.assertIn("主机玩家1=战士", joined)
        self.assertIn("客机玩家2=蛞蝓猫", joined)
        self.assertIn("先手：玩家2（客机）", joined)
        self.assertIn("种子：42", joined)
        self.assertIn("开启", joined)


class _FakeElement:
    def update(self, *_args, **_kwargs):
        return None


class _ScriptedRoomWindow:
    def __init__(self, script, repeat_start=None):
        self.script = list(script)
        self.repeat_start = repeat_start
        self.retries = 0

    def read(self, timeout=None):
        if self.script:
            return self.script.pop(0)
        if self.repeat_start is not None and self.retries < 40:
            self.retries += 1
            return self.repeat_start
        return "__TIMEOUT__", {}

    def __getitem__(self, key):
        return _FakeElement()

    def close(self):
        self.closed = True


class _LogWidget:
    def __init__(self):
        self.lines = []

    def configure(self, **_kwargs):
        return None

    def tag_configure(self, *_args, **_kwargs):
        return None

    def insert(self, _index, text, *_args):
        self.lines.append(text)

    def see(self, *_args):
        return None


class _LogElement:
    def __init__(self, widget):
        self.Widget = widget

    def update(self, *_args, **_kwargs):
        return None


class _LogWindow:
    def __init__(self):
        self.widget = _LogWidget()
        self.elements = {"-OUTPUT-": _LogElement(self.widget)}

    def __getitem__(self, key):
        return self.elements[key]

    def refresh(self):
        return None


def _room_phase_thread(result, socket_end, registry, is_host, window):
    session = SimpleNamespace(connection=socket_end)
    with patch("card_duel.network.setup.build_room_window", return_value=window):
        result["config"] = room_phase(session, registry, is_host=is_host)


class RoomPhaseTests(unittest.TestCase):
    def test_room_phase_exchanges_config_both_sides(self):
        import tempfile

        from card_duel.network.transport import receive_json, send_json
        from card_duel.ui import app_settings

        left, right = socket.socketpair()
        host_window = _ScriptedRoomWindow(
            [
                (
                    "-ROOM-START-",
                    {
                        "-ROOM-CHAR-": "1 战士",
                        "-ROOM-FIRST-HOST-": True,
                        "-ROOM-SEED-": "42",
                        "-ROOM-NO-DMG-": True,
                    },
                )
            ]
        )
        host_result = {}

        def run_host():
            try:
                session = SimpleNamespace(connection=left)
                with patch(
                    "card_duel.network.setup.build_room_window",
                    return_value=host_window,
                ):
                    host_result["config"] = room_phase(
                        session, DEFAULT_REGISTRY, is_host=True
                    )
            except Exception as error:
                host_result["err"] = repr(error)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                app_settings, "CONFIG_PATH", f"{tmp}/settings.json"
            ):
                host_thread = threading.Thread(target=run_host)
                host_thread.start()
                right.settimeout(3)
                message = receive_json(right.recv)
                self.assertEqual(message.get("type"), "room_start")
                send_json(
                    right, {"type": "room_ready", "guest_character": 4}
                )
                host_thread.join(timeout=5)
                left.close()
                right.close()

        self.assertFalse(host_thread.is_alive())
        host_config = host_result.get("config")
        self.assertIsNotNone(host_config)
        self.assertEqual(host_config.host_character, 1)
        self.assertEqual(host_config.guest_character, 4)
        self.assertEqual(host_config.seed, 42)
        self.assertEqual(host_config.first_player_id, 1)
        self.assertTrue(host_config.round1_no_damage)


if __name__ == "__main__":
    unittest.main()
