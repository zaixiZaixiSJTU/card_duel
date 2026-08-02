"""Framed network messages shared by both players."""

from __future__ import annotations

import select
from dataclasses import asdict, fields, is_dataclass

import FreeSimpleGUI as sg

from card_duel.core.models import DefenceEffect
from card_duel.network.transport import receive_json, send_json
from card_duel.ui.network_style import CHAT_INPUT_KEY, CHAT_SEND_KEY
from card_duel.ui.network_view import refresh_status

DEFAULT_PORT = 65432
MAX_CHAT_LENGTH = 200
PROTOCOL_VERSION = 1

MESSAGE_ANNOUNCEMENT = "announcement"
MESSAGE_CHAT = "chat"
MESSAGE_STATE = "state"
MESSAGE_TURN_CHANGE = "turn_change"


def _session_window(session):
    require_window = getattr(session, "require_window", None)
    return require_window() if require_window else session.window


def _receive_bytes_with_ui(
    session,
    byte_count: int,
    *,
    timeout: float = 0.1,
    allow_chat: bool = False,
) -> bytes:
    """Receive an exact-frame chunk while continuing to pump GUI events."""
    connection = session.connection
    window = _session_window(session)
    original_timeout = connection.gettimeout()
    connection.settimeout(timeout)
    try:
        while True:
            event, values = window.read(timeout=120)
            if event == sg.WIN_CLOSED:
                return b""
            if allow_chat and event == CHAT_SEND_KEY:
                send_chat_message(session, values.get(CHAT_INPUT_KEY, ""))
                continue
            try:
                return connection.recv(byte_count)
            except TimeoutError:
                continue
    finally:
        connection.settimeout(original_timeout)


def _receive_message(session, *, allow_chat: bool = False):
    return receive_json(
        lambda byte_count: _receive_bytes_with_ui(
            session, byte_count, allow_chat=allow_chat
        )
    )


def send_chat_message(session, message: str) -> bool:
    clean_message = " ".join(message.strip().splitlines())[:MAX_CHAT_LENGTH]
    if not clean_message:
        return False
    send_json(
        session.connection,
        {"type": MESSAGE_CHAT, "message": clean_message},
    )
    print(f"[我] {clean_message}")
    window = _session_window(session)
    window[CHAT_INPUT_KEY].update("")
    window.refresh()
    return True


def receive_pending_chat(session) -> None:
    while select.select([session.connection], [], [], 0)[0]:
        message = _receive_message(session)
        if message.get("type") != MESSAGE_CHAT:
            raise ConnectionError(f"行动阶段收到非预期消息: {message.get('type')}")
        _show_peer_chat(message.get("message", ""))
        _session_window(session).refresh()


def _show_peer_chat(message: str) -> None:
    print(f"[对方] {message}")


def send_announcement(session, message: str) -> None:
    send_json(
        session.connection,
        {"type": MESSAGE_ANNOUNCEMENT, "message": message},
    )
    print(message)


def send_game_state(session) -> None:
    state = session.state
    refresh_status(state, _session_window(session), session.registry)
    players = {
        str(player_id): {
            "energy": player.energy,
            "health": player.health,
            "strength": player.strength,
            "poison": player.poison,
            "statuses": _dataclass_payload(player.statuses),
            "character_data": _dataclass_payload(player.character_data),
        }
        for player_id, player in state.players.items()
    }
    defences = {
        str(player_id): [
            effect.to_dict() for effect in state.players[player_id].defences
        ]
        for player_id in (1, 2)
    }
    send_json(
        session.connection,
        {"type": MESSAGE_STATE, "players": players, "defences": defences},
    )
    _session_window(session).refresh()


def receive_until_turn_change(session) -> None:
    while True:
        message = _receive_message(session, allow_chat=True)
        message_type = message.get("type")
        if message_type == MESSAGE_TURN_CHANGE:
            refresh_status(session.state, _session_window(session), session.registry)
            return
        if message_type == MESSAGE_STATE:
            _apply_state_message(session, message)
        elif message_type == MESSAGE_CHAT:
            _show_peer_chat(message.get("message", ""))
        elif message_type == MESSAGE_ANNOUNCEMENT:
            print(message.get("message", ""))
        else:
            raise ConnectionError(f"未知联机消息类型: {message_type}")
        _session_window(session).refresh()


def _apply_state_message(session, message) -> None:
    state = session.state
    player_payloads = message["players"]
    for player_id, player in state.players.items():
        values = player_payloads[str(player_id)]
        player.energy = values["energy"]
        player.health = values["health"]
        player.strength = values["strength"]
        player.poison = values["poison"]
        _apply_dataclass_values(player.statuses, values["statuses"])
        _apply_dataclass_values(player.character_data, values["character_data"])

    defence_payloads = message["defences"]
    for player_id in (1, 2):
        state.players[player_id].defences = [
            DefenceEffect.from_dict(item) for item in defence_payloads[str(player_id)]
        ]
    session.combat.check_game_over()
    refresh_status(state, _session_window(session), session.registry)


def _apply_dataclass_values(instance, values) -> None:
    if not is_dataclass(instance):
        raise TypeError("联机角色数据必须是 dataclass")
    allowed = {item.name for item in fields(instance)}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"收到未知状态字段: {sorted(unknown)}")
    for name, value in values.items():
        setattr(instance, name, value)


def _dataclass_payload(instance):
    if not is_dataclass(instance):
        raise TypeError("联机角色数据必须是 dataclass")
    return asdict(instance)


def signal_turn_change(session) -> None:
    send_json(session.connection, {"type": MESSAGE_TURN_CHANGE})


# Private compatibility names retained for the framing regression test.
def _send_json_payload(connection, data):
    send_json(connection, data)


def _receive_json_payload(session):
    return _receive_message(session)
