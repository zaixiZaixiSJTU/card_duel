"""Network game server (player 1)."""

import random
import socket
import time

import FreeSimpleGUI as sg

from card_duel.core.models import GameState
from card_duel.core.rules import draw_cards
from card_duel.network.gameplay import play_active_turn
from card_duel.network.protocol import (
    DEFAULT_PORT,
    PROTOCOL_VERSION,
    receive_until_turn_change,
    send_game_state,
    signal_turn_change,
)
from card_duel.network.session import GameSession
from card_duel.network.setup import (
    announce_room_config,
    announce_winner,
    apply_room_config,
    ask_rematch,
    prepare_game_window,
    reset_for_rematch,
    room_phase,
)
from card_duel.network.transport import send_json
from card_duel.ui.auxiliary_windows import close_auxiliary_windows
from card_duel.ui.network_dialogs import waiting_dialog
from card_duel.ui.network_style import init_theme
from card_duel.ui.network_view import refresh_cards, set_phase


def accept_client_connection(port=DEFAULT_PORT):
    """Wait for a client and return its connected socket."""
    waiting_window = waiting_dialog("等待对方连接...")
    try:
        with socket.socket() as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("0.0.0.0", port))
            server_socket.listen()
            connection, client_address = server_socket.accept()

        welcome_message = {
            "type": "welcome",
            "protocol_version": PROTOCOL_VERSION,
            "status": "success",
            "server_time": time.ctime(),
            "client": f"{client_address[0]}:{client_address[1]}",
        }
        send_json(connection, welcome_message)
        return connection
    finally:
        waiting_window.close()


def run_server_game(session):
    game_state = session.state
    window = session.require_window()
    set_phase(window, "对战开始")
    print(" ---------------------------------------------------- ")
    print(
        f"你选择了: {session.registry.get_character(game_state.character_ids[1]).name}"
    )
    print(
        f"对手选择了: {session.registry.get_character(game_state.character_ids[2]).name}"
    )
    print("你先出牌")
    print(" ---------------------------------------------------- ")

    draw_cards(game_state, 2)
    refresh_cards(game_state, window, session.card_images)
    round_number = 1
    host_first = game_state.first_player_id == 1

    while session.combat.winning_player_id() is None:
        print(f"-------------------- ROUND {round_number} --------------------")
        for player in game_state.players.values():
            player.energy = random.randint(4, 6)
        send_game_state(session)

        if host_first:
            if not play_active_turn(
                session, player_id=1, round_number=round_number
            ):
                return None
            set_phase(window, f"回合 {round_number} - 对手出牌中...")
            signal_turn_change(session)
            receive_until_turn_change(session)
        else:
            set_phase(window, f"回合 {round_number} - 对手出牌中...")
            signal_turn_change(session)
            receive_until_turn_change(session)
            if not play_active_turn(
                session, player_id=1, round_number=round_number
            ):
                return None
            signal_turn_change(session)
        print(" ---------------------------------------------------- ")
        print("[对手的回合结束]")
        refresh_cards(game_state, window, session.card_images)
        print(" ---------------------------------------------------- ")
        round_number += 1

    set_phase(window, "游戏结束")
    return session.combat.winning_player_id()


def host_match(session) -> None:
    """Play matches until one side quits; re-select and rematch in between."""
    while True:
        config = room_phase(session, session.registry, is_host=True)
        if config is None:
            return
        apply_room_config(session, config, local_player_id=1)
        if not prepare_game_window(session):
            return
        announce_room_config(session)
        winner = run_server_game(session)
        if winner is None:
            return
        announce_winner(session, winner)
        if not ask_rematch(session, is_host=True):
            return
        reset_for_rematch(session, local_player_id=1)


def main():
    init_theme()
    connection = accept_client_connection()
    state = GameState(local_player_id=1)
    session = GameSession(state=state, connection=connection)

    try:
        host_match(session)
    except (ConnectionError, OSError, ValueError) as error:
        sg.popup_error(f"联网对战中断: {error}", keep_on_top=True)
    finally:
        close_auxiliary_windows(session)
        if session.window is not None:
            session.window.close()
        connection.close()


if __name__ == "__main__":
    main()
