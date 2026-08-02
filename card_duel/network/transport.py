"""Length-prefixed JSON framing independent from game rules and GUI code."""

from __future__ import annotations

import json
from collections.abc import Callable
from socket import socket
from typing import Any

Receive = Callable[[int], bytes]


def send_json(connection: socket, data: Any) -> None:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    connection.sendall(len(payload).to_bytes(4, "big") + payload)


def receive_json(receive: Receive) -> Any:
    payload_size = int.from_bytes(receive_exact(receive, 4), "big")
    return json.loads(receive_exact(receive, payload_size).decode("utf-8"))


def receive_exact(receive: Receive, byte_count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining:
        chunk = receive(remaining)
        if not chunk:
            raise ConnectionError("对方已断开连接")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
