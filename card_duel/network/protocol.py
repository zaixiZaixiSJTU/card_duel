"""Shared socket protocol used by both network players."""

import json
import select
import socket
import time

import FreeSimpleGUI as sg

from card_duel.core.combat import DefenceEffect, check_game_over
from card_duel.ui.network import (
    CHAT_INPUT_KEY,
    CHAT_SEND_KEY,
    REFRESH_HAND_KEY,
    colored_announce,
    refresh_status,
)

ACK_MESSAGE = "pass"
STATE_MESSAGE = "data"
TURN_CHANGE_MESSAGE = "change"
CHAT_MESSAGE_PREFIX = "chat:"
CARD_MESSAGE_PREFIX = "card:"
DEFAULT_PORT = 65432
MAX_CHAT_LENGTH = 200


def receive_with_ui(
    game_state,
    timeout=0.1,
    buffer_size=1024,
    allow_chat=False,
):
    """Receive bytes while keeping the GUI responsive."""
    from card_duel.ui.network import poll_deck_viewer, route_card_event

    connection = game_state.connection
    window = game_state.window
    original_timeout = connection.gettimeout()
    connection.settimeout(timeout)
    try:
        while True:
            event, values = window.read(timeout=120)
            if event == sg.WIN_CLOSED:
                return b""
            if allow_chat and event == CHAT_SEND_KEY:
                send_chat_message(
                    game_state,
                    values.get(CHAT_INPUT_KEY, ""),
                )
                continue
            if event == "-DECK-VIEW-":
                from card_duel.ui.network import open_deck_viewer

                open_deck_viewer(game_state)
                continue
            if event == REFRESH_HAND_KEY:
                from card_duel.ui.network import refresh_cards

                refresh_cards(game_state)
                refresh_status(game_state)
                game_state.window.refresh()
                continue
            poll_deck_viewer(game_state)
            # Only route idle card clicks (left-flash / right-preview) while
            # passively receiving the peer's turn. During acknowledgement
            # waits (allow_chat=False) the active callback may still be set,
            # so routing then could re-enter a card play and corrupt state.
            if allow_chat:
                route_card_event(game_state, event)
            try:
                return connection.recv(buffer_size)
            except socket.timeout:
                continue
    finally:
        connection.settimeout(original_timeout)


def wait_for_acknowledgement(game_state):
    """Wait until the peer acknowledges the previous protocol message."""
    response = None
    while response != ACK_MESSAGE:
        payload = receive_with_ui(game_state)
        if not payload:
            raise ConnectionError("对方已断开连接")
        response = payload.decode("utf-8")
        if response.startswith(CHAT_MESSAGE_PREFIX):
            _show_peer_chat(response, game_state)
            game_state.connection.sendall(ACK_MESSAGE.encode("utf-8"))
            response = None


def send_chat_message(game_state, message):
    """Send one short chat message without mixing it into game rules."""
    clean_message = " ".join(message.strip().splitlines())[:MAX_CHAT_LENGTH]
    if not clean_message:
        return False

    payload = f"{CHAT_MESSAGE_PREFIX}{clean_message}"
    game_state.connection.sendall(payload.encode("utf-8"))
    wait_for_acknowledgement(game_state)
    colored_announce(game_state, f"[我] {clean_message}")
    game_state.window[CHAT_INPUT_KEY].update("")
    game_state.window.refresh()
    return True


def receive_pending_chat(game_state):
    """Read peer chat while the local player is choosing an action."""
    while select.select([game_state.connection], [], [], 0)[0]:
        payload = game_state.connection.recv(1024)
        if not payload:
            raise ConnectionError("对方已断开连接")

        response = payload.decode("utf-8")
        if not response.startswith(CHAT_MESSAGE_PREFIX):
            raise ConnectionError(f"收到非预期的联机消息: {response}")

        _show_peer_chat(response, game_state)
        game_state.connection.sendall(ACK_MESSAGE.encode("utf-8"))
        game_state.window.refresh()


def _show_peer_chat(payload, game_state=None):
    message = f"[对方] {payload.removeprefix(CHAT_MESSAGE_PREFIX)}"
    colored_announce(game_state, message) if game_state is not None else print(message)


def _apply_played_card(game_state, payload):
    """Update the peer's played-card slot from a card: message."""
    data = payload.removeprefix(CARD_MESSAGE_PREFIX)
    player_part, _, card_part = data.partition(":")
    from card_duel.ui.network import show_played_card

    show_played_card(game_state, int(player_part), int(card_part))


def send_announcement(game_state, message):
    game_state.connection.sendall(message.encode("utf-8"))
    wait_for_acknowledgement(game_state)
    colored_announce(game_state, message)


def send_played_card(game_state, player_id, card_id):
    """Tell the peer which card was just played (for the display slot)."""
    payload = f"{CARD_MESSAGE_PREFIX}{player_id}:{card_id}"
    game_state.connection.sendall(payload.encode("utf-8"))
    wait_for_acknowledgement(game_state)


def send_game_state(game_state):
    """Send combat values and defence effects to the peer."""
    refresh_status(game_state)
    game_state.connection.sendall(STATE_MESSAGE.encode("utf-8"))
    wait_for_acknowledgement(game_state)

    player_data = {
        str(player_id): {
            "energy": player.energy,
            "health": player.health,
            "strength": player.strength,
            "poison": player.poison,
            "special": player.special,
        }
        for player_id, player in game_state.players.items()
    }
    _send_json_payload(game_state.connection, player_data)
    wait_for_acknowledgement(game_state)

    # Clear transient communication fields after sending so they are not
    # re-sent on the next sync (which would duplicate insertions/returns).
    for player in game_state.players.values():
        player.special["pending_insertions"] = []
        player.special["pending_draw_returns"] = []

    for player_id in (1, 2):
        defence_data = [
            effect.to_dict() for effect in game_state.defences[player_id]
        ]
        _send_json_payload(game_state.connection, defence_data)
        wait_for_acknowledgement(game_state)

    game_state.window.refresh()


def receive_until_turn_change(game_state):
    """Apply peer updates until the peer signals that its turn ended."""
    while True:
        payload = receive_with_ui(game_state, allow_chat=True)
        if not payload:
            raise ConnectionError("对方已断开连接")
        response = payload.decode("utf-8")

        if response == TURN_CHANGE_MESSAGE:
            refresh_status(game_state)
            game_state.connection.sendall(ACK_MESSAGE.encode("utf-8"))
            time.sleep(0.2)
            return

        if response == STATE_MESSAGE:
            game_state.connection.sendall(ACK_MESSAGE.encode("utf-8"))
            _receive_game_state_payload(game_state)
        elif response.startswith(CHAT_MESSAGE_PREFIX):
            _show_peer_chat(response, game_state)
        elif response.startswith(CARD_MESSAGE_PREFIX):
            _apply_played_card(game_state, response)
        else:
            colored_announce(game_state, response)

        game_state.connection.sendall(ACK_MESSAGE.encode("utf-8"))
        game_state.window.refresh()


def _receive_game_state_payload(game_state):
    player_data = _receive_json_payload(game_state)
    for player_id, player in game_state.players.items():
        values = player_data[str(player_id)]
        player.energy = values["energy"]
        player.health = values["health"]
        player.strength = values.get("strength", player.strength)
        player.poison = values.get("poison", player.poison)
        player.special.update(values.get("special", {}))
        # Process pending card insertions for local player
        if player_id == game_state.local_player_id:
            pending = player.special.get("pending_insertions", [])
            if pending:
                from card_duel.core import combat

                for card_id in pending:
                    combat.add_card_to_hand(game_state, card_id)
                player.special["pending_insertions"] = []
                # Real-time hand refresh so inserted cards appear immediately
                if game_state.window is not None:
                    from card_duel.ui.network import refresh_cards
                    refresh_cards(game_state)
            # Process pending draw pile returns for local player
            pending_returns = player.special.get("pending_draw_returns", [])
            if pending_returns:
                from card_duel.cards.slugcat_data import (
                    SLUGCAT_DISCOVERY_IDS, SLUGCAT_CHARACTER_ID,
                )
                if game_state.character_ids.get(player_id) == SLUGCAT_CHARACTER_ID:
                    pool = player.special.setdefault("discovery_pool", [])
                    for cid in pending_returns:
                        if cid in SLUGCAT_DISCOVERY_IDS:
                            pool.append(cid)
                        else:
                            game_state.draw_pile.append(cid)
                else:
                    game_state.draw_pile.extend(pending_returns)
                player.special["pending_draw_returns"] = []
            # 炸矛穿透：立即随机弃牌（不等下回合开始），播报被弃牌名
            pending_discards = player.special.get("pending_discards", 0)
            if pending_discards > 0:
                from card_duel.cards.slugcat import _resolve_pending_discards
                from card_duel.ui.network import colored_announce

                _resolve_pending_discards(
                    game_state, player,
                    announce=lambda msg: colored_announce(game_state, msg),
                )
                if game_state.window is not None:
                    from card_duel.ui.network import refresh_cards
                    refresh_cards(game_state)
    game_state.connection.sendall(ACK_MESSAGE.encode("utf-8"))

    for player_id in (1, 2):
        defence_data = _receive_json_payload(game_state)
        game_state.defences[player_id] = [
            DefenceEffect.from_dict(item) for item in defence_data
        ]
        if player_id == 1:
            game_state.connection.sendall(ACK_MESSAGE.encode("utf-8"))

    check_game_over(game_state)
    refresh_status(game_state)


def _send_json_payload(connection, data):
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    connection.sendall(len(payload).to_bytes(4, "big") + payload)


def _receive_json_payload(game_state):
    payload_size = int.from_bytes(_receive_exact(game_state, 4), "big")
    return json.loads(_receive_exact(game_state, payload_size).decode("utf-8"))


def _receive_exact(game_state, byte_count):
    chunks = []
    remaining = byte_count
    while remaining:
        chunk = receive_with_ui(game_state, buffer_size=remaining)
        if not chunk:
            raise ConnectionError("对方已断开连接")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def signal_turn_change(game_state):
    game_state.connection.sendall(TURN_CHANGE_MESSAGE.encode("utf-8"))
    wait_for_acknowledgement(game_state)
