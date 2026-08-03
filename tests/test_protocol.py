"""Tests for framed network state payloads."""

import socket
import unittest
from collections import defaultdict
from types import SimpleNamespace

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.slugcat.state import SlugcatData
from card_duel.core.models import CombatStatuses, CreatureState, GameState
from card_duel.network.protocol import (
    _apply_dataclass_values,
    _apply_local_pending_actions,
    _receive_json_payload,
    _send_json_payload,
)
from card_duel.network.transport import receive_json, send_json


class _ResponsiveWindow:
    def __init__(self):
        self.elements = defaultdict(_Element)

    def read(self, timeout=None):
        return "__TIMEOUT__", {}

    def __getitem__(self, key):
        return self.elements[key]

    def refresh(self):
        return None


class _Element:
    Widget = None

    def update(self, *args, **kwargs):
        return None


class ProtocolTests(unittest.TestCase):
    def test_large_json_payload_is_received_without_truncation(self):
        sender, receiver = socket.socketpair()
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)
        payload = {
            "special": {
                "discovery_pool": list(range(2_000)),
                "name": "蛞蝓猫",
            }
        }

        _send_json_payload(sender, payload)
        state = SimpleNamespace(
            connection=receiver,
            window=_ResponsiveWindow(),
        )

        self.assertEqual(_receive_json_payload(state), payload)

    def test_consecutive_messages_preserve_tcp_boundaries(self):
        sender, receiver = socket.socketpair()
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)

        send_json(sender, {"type": "chat", "message": "一"})
        send_json(sender, {"type": "turn_change"})

        self.assertEqual(
            receive_json(receiver.recv),
            {"type": "chat", "message": "一"},
        )
        self.assertEqual(receive_json(receiver.recv), {"type": "turn_change"})

    def test_unknown_character_state_field_is_rejected(self):
        data = SlugcatData()

        with self.assertRaises(ValueError):
            _apply_dataclass_values(data, {"unknown_field": 1})

    def test_nested_dataclasses_and_integer_keys_survive_json_payloads(self):
        statuses = CombatStatuses()
        _apply_dataclass_values(
            statuses,
            {"hand_creatures": [{"card_id": 17, "health": 5, "owner_id": 2}]},
        )
        data = SlugcatData()
        _apply_dataclass_values(data, {"unlocked_creature_counts": {"20": 3}})

        self.assertEqual(
            statuses.hand_creatures,
            [CreatureState(card_id=17, health=5, owner_id=2)],
        )
        self.assertEqual(data.unlocked_creature_counts, {20: 3})

    def test_pending_hand_actions_are_applied_once_on_local_endpoint(self):
        state = GameState(character_ids={1: 4, 2: 1}, local_player_id=1)
        combat = CombatEngine(state, DEFAULT_REGISTRY)
        combat.initialize_players()
        state.hand_cards[:] = [7, 6]
        statuses = state.players[1].statuses
        statuses.pending_hand_additions[:] = [49]
        statuses.pending_hand_removals[:] = [7]
        statuses.pending_draw_returns[:] = [27, 1]
        statuses.pending_discards = 1
        session = SimpleNamespace(
            state=state,
            combat=combat,
            registry=DEFAULT_REGISTRY,
            card_images=[b""] * 51,
            window=_ResponsiveWindow(),
        )

        _apply_local_pending_actions(session)

        self.assertEqual(state.hand_cards, [49])
        self.assertEqual(state.draw_pile, [1, 6])
        slugcat_data = state.players[1].character_data
        self.assertIsInstance(slugcat_data, SlugcatData)
        self.assertEqual(slugcat_data.discovery_pool, [27, 27])
        self.assertFalse(statuses.pending_hand_additions)
        self.assertFalse(statuses.pending_hand_removals)
        self.assertFalse(statuses.pending_draw_returns)
        self.assertEqual(statuses.pending_discards, 0)


if __name__ == "__main__":
    unittest.main()
