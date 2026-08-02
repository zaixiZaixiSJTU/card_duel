"""Tests for framed network state payloads."""

import socket
import unittest
from types import SimpleNamespace

from card_duel.network.protocol import _receive_json_payload, _send_json_payload


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


if __name__ == "__main__":
    unittest.main()
