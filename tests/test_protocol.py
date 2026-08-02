"""Tests for framed network state payloads."""

import socket
import unittest
from types import SimpleNamespace

from card_duel.cards.slugcat.state import SlugcatData
from card_duel.network.protocol import (
    _apply_dataclass_values,
    _receive_json_payload,
    _send_json_payload,
)
from card_duel.network.transport import receive_json, send_json


class _ResponsiveWindow:
    def read(self, timeout=None):
        return "__TIMEOUT__", {}


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


if __name__ == "__main__":
    unittest.main()
