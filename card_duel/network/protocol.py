"""Framed network messages shared by both players."""

from __future__ import annotations

import select
import types
from contextlib import suppress
from dataclasses import asdict, fields, is_dataclass
from typing import Union, get_args, get_origin, get_type_hints

import FreeSimpleGUI as sg

from card_duel.core.models import DefenceEffect
from card_duel.network.transport import receive_json, send_json
from card_duel.ui.auxiliary_windows import read_primary_window
from card_duel.ui.network_log import append_log
from card_duel.ui.network_style import CHAT_INPUT_KEY, CHAT_SEND_KEY
from card_duel.ui.network_view import refresh_status, show_played_card

DEFAULT_PORT = 65432
MAX_CHAT_LENGTH = 200
PROTOCOL_VERSION = 3

MESSAGE_ANNOUNCEMENT = "announcement"
MESSAGE_CHAT = "chat"
MESSAGE_CARD_PLAYED = "card_played"
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
    original_timeout = connection.gettimeout()
    connection.settimeout(timeout)
    try:
        while True:
            event, values = read_primary_window(session)
            if event == sg.WIN_CLOSED:
                return b""
            if allow_chat and event == CHAT_SEND_KEY:
                send_chat_message(session, values.get(CHAT_INPUT_KEY, ""))
                continue
            if not select.select([connection], [], [], 0)[0]:
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
    append_log(session, f"[我] {clean_message}")
    window = _session_window(session)
    window[CHAT_INPUT_KEY].update("")
    window.refresh()
    return True


def receive_pending_chat(session) -> None:
    while select.select([session.connection], [], [], 0)[0]:
        message = _receive_message(session)
        if message.get("type") != MESSAGE_CHAT:
            raise ConnectionError(f"行动阶段收到非预期消息: {message.get('type')}")
        _show_peer_chat(session, message.get("message", ""))
        _session_window(session).refresh()


def _show_peer_chat(session, message: str) -> None:
    append_log(session, f"[对方] {message}")


def send_announcement(session, message: str) -> None:
    send_json(
        session.connection,
        {"type": MESSAGE_ANNOUNCEMENT, "message": message},
    )
    append_log(session, message)


def send_card_played(session, player_id: int, character_id: int, card_id: int) -> None:
    """Publish the last played card without exposing either player's hand."""
    show_played_card(session, player_id, character_id, card_id)
    send_json(
        session.connection,
        {
            "type": MESSAGE_CARD_PLAYED,
            "player_id": player_id,
            "character_id": character_id,
            "card_id": card_id,
        },
    )


def send_game_state(session) -> None:
    state = session.state
    refresh_status(
        state,
        _session_window(session),
        session.registry,
        getattr(session, "status_snapshots", None),
    )
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
    _clear_transient_queues(state)
    _session_window(session).refresh()


def receive_until_turn_change(session) -> None:
    while True:
        message = _receive_message(session, allow_chat=True)
        message_type = message.get("type")
        if message_type == MESSAGE_TURN_CHANGE:
            refresh_status(
                session.state,
                _session_window(session),
                session.registry,
                getattr(session, "status_snapshots", None),
            )
            return
        if message_type == MESSAGE_STATE:
            _apply_state_message(session, message)
        elif message_type == MESSAGE_CHAT:
            _show_peer_chat(session, message.get("message", ""))
        elif message_type == MESSAGE_ANNOUNCEMENT:
            append_log(session, message.get("message", ""))
        elif message_type == MESSAGE_CARD_PLAYED:
            show_played_card(
                session,
                int(message["player_id"]),
                int(message["character_id"]),
                int(message["card_id"]),
            )
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
    _apply_local_pending_actions(session)
    session.combat.check_game_over()
    refresh_status(
        state,
        _session_window(session),
        session.registry,
        getattr(session, "status_snapshots", None),
    )


def _apply_dataclass_values(instance, values) -> None:
    if not is_dataclass(instance):
        raise TypeError("联机角色数据必须是 dataclass")
    allowed = {item.name for item in fields(instance)}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"收到未知状态字段: {sorted(unknown)}")
    annotations = get_type_hints(type(instance))
    for name, value in values.items():
        setattr(instance, name, _coerce_value(annotations.get(name), value))


def _coerce_value(annotation, value):
    """Restore nested dataclasses and integer dictionary keys after JSON."""
    if annotation is None or value is None:
        return value
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin is list and arguments:
        return [_coerce_value(arguments[0], item) for item in value]
    if origin is dict and len(arguments) == 2:
        key_type, value_type = arguments
        return {
            _coerce_value(key_type, key): _coerce_value(value_type, item)
            for key, item in value.items()
        }
    if origin in (Union, types.UnionType):
        for candidate in arguments:
            if candidate is type(None):
                continue
            try:
                return _coerce_value(candidate, value)
            except (TypeError, ValueError):
                continue
        return value
    if isinstance(annotation, type) and is_dataclass(annotation):
        hints = get_type_hints(annotation)
        return annotation(
            **{
                field.name: _coerce_value(hints.get(field.name), value[field.name])
                for field in fields(annotation)
                if field.name in value
            }
        )
    if annotation is int:
        return int(value)
    return value


def _apply_local_pending_actions(session) -> None:
    state = session.state
    hand_before_actions = list(state.hand_cards)
    player_id = state.local_player_id
    player = state.players[player_id]
    statuses = player.statuses

    state.hand_cards.extend(statuses.pending_hand_additions)
    statuses.pending_hand_additions.clear()
    for card_id in statuses.pending_hand_removals:
        with suppress(ValueError):
            state.hand_cards.remove(card_id)
    statuses.pending_hand_removals.clear()

    if statuses.pending_draw_returns:
        if state.character_ids.get(player_id) == 4:
            from card_duel.cards.slugcat.specs import SLUGCAT_DISCOVERY_IDS
            from card_duel.cards.slugcat.state import slugcat_data

            data = slugcat_data(player)
            for card_id in statuses.pending_draw_returns:
                if card_id in SLUGCAT_DISCOVERY_IDS:
                    data.discovery_pool.append(card_id)
                else:
                    state.draw_pile.append(card_id)
        else:
            state.draw_pile.extend(statuses.pending_draw_returns)
        statuses.pending_draw_returns.clear()

    if statuses.pending_discards:
        from card_duel.cards.slugcat.lifecycle import resolve_pending_discards
        from card_duel.ui.card_animations import animate_card_action

        resolve_pending_discards(
            state,
            player_id,
            announce=lambda message: append_log(session, message),
            on_discard=lambda index, _card_id: animate_card_action(
                session, index, "discard"
            ),
        )

    from card_duel.ui.card_animations import animate_hand_additions
    from card_duel.ui.network_view import refresh_cards

    refresh_cards(state, _session_window(session), session.card_images)
    animate_hand_additions(session, hand_before_actions)


def _clear_transient_queues(state) -> None:
    for player in state.players.values():
        player.statuses.pending_hand_additions.clear()
        player.statuses.pending_hand_removals.clear()
        player.statuses.pending_draw_returns.clear()


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
