"""JSON message contracts used by the browser WebSocket transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_CHAT_LENGTH = 200
WEB_PROTOCOL_VERSION = 2


class ActionError(ValueError):
    """A client action that can be reported without closing the socket."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ClientAction:
    """Validated action envelope sent by a browser client."""

    action: str
    data: dict[str, Any]

    @classmethod
    def parse(cls, payload: object) -> ClientAction:
        if not isinstance(payload, dict):
            raise ActionError("invalid_message", "消息必须是 JSON 对象")
        action = payload.get("action")
        data = payload.get("data", {})
        if not isinstance(action, str) or not action.strip():
            raise ActionError("invalid_message", "消息缺少 action")
        if not isinstance(data, dict):
            raise ActionError("invalid_message", "data 必须是 JSON 对象")
        return cls(action=action.strip(), data=data)


def event(event_type: str, **data: object) -> dict[str, object]:
    """Create one server event envelope."""
    return {
        "type": event_type,
        "protocol_version": WEB_PROTOCOL_VERSION,
        "data": data,
    }


def error_event(error: ActionError) -> dict[str, object]:
    return event("error", code=error.code, message=error.message)
