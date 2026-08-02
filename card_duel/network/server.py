"""Network game server (player 1)."""

import json
import random
import socket
import time

import FreeSimpleGUI as sg

from card_duel.cards.registry import get_card_counts
from card_duel.core.combat import (
    CHARACTERS,
    NetworkGameState,
    build_shuffled_deck,
    draw_cards,
    initialize_character_states,
    load_character_images,
)
from card_duel.network.gameplay import play_active_turn
from card_duel.network.protocol import (
    ACK_MESSAGE,
    DEFAULT_PORT,
    receive_until_turn_change,
    send_game_state,
    signal_turn_change,
)
from card_duel.ui.network import (
    WINDOW_SIZE,
    WINDOW_TITLE,
    bind_hand_card_events,
    character_select_dialog,
    colored_announce,
    create_main_layout,
    init_theme,
    refresh_cards,
    set_phase,
    waiting_dialog,
)


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
            "event": "connection",
            "status": "success",
            "server_time": time.ctime(),
            "client": f"{client_address[0]}:{client_address[1]}",
        }
        connection.sendall(json.dumps(welcome_message).encode("utf-8"))
        response = connection.recv(1024).decode("utf-8")
        if response != ACK_MESSAGE:
            connection.close()
            raise ConnectionError("客户端未确认连接")
        return connection
    finally:
        waiting_window.close()


def exchange_character_choices(game_state):
    selected_character = character_select_dialog()
    if selected_character is None:
        return False

    waiting_window = waiting_dialog("等待对方选择...")
    try:
        game_state.character_ids[1] = int(selected_character)
        game_state.connection.sendall(selected_character.encode("utf-8"))
        peer_choice = game_state.connection.recv(1024).decode("utf-8")
        game_state.character_ids[2] = int(peer_choice)
        return True
    finally:
        waiting_window.close()


def prepare_game_window(game_state):
    initialize_character_states(game_state)
    character_id = game_state.character_ids[1]
    game_state.card_images, game_state.max_card_id = load_character_images(
        character_id
    )
    if not game_state.card_images:
        return False

    peer_character_id = game_state.character_ids[2]
    game_state.peer_card_images, _ = load_character_images(peer_character_id)

    game_state.draw_pile = build_shuffled_deck(
        1,
        game_state.max_card_id,
        get_card_counts(character_id),
    )
    layout = create_main_layout(
        game_state.card_images,
        game_state.hand_cards,
        local_player_id=game_state.local_player_id,
        character_ids=game_state.character_ids,
    )
    game_state.window = sg.Window(
        WINDOW_TITLE,
        layout,
        size=WINDOW_SIZE,
        font=("Microsoft YaHei", 10),
        finalize=True,
        keep_on_top=True,
        resizable=True,
    )
    bind_hand_card_events(game_state)
    refresh_cards(game_state)
    return True


def run_server_game(game_state):
    set_phase(game_state, "对战开始")
    colored_announce(game_state, " ---------------------------------------------------- ")
    colored_announce(game_state, f"你选择了: {CHARACTERS[game_state.character_ids[1]]}")
    colored_announce(game_state, f"对手选择了: {CHARACTERS[game_state.character_ids[2]]}")
    colored_announce(game_state, "你先出牌")
    colored_announce(game_state, " ---------------------------------------------------- ")

    draw_cards(game_state, 2)
    refresh_cards(game_state)
    round_number = 1

    while all(player.health > 0 for player in game_state.players.values()):
        colored_announce(game_state, f"-------------------- ROUND {round_number} --------------------")
        for player in game_state.players.values():
            player.energy = random.randint(4, 6)
        send_game_state(game_state)

        if not play_active_turn(game_state, player_id=1, round_number=round_number):
            return

        set_phase(game_state, f"回合 {round_number} - 对手出牌中...")
        colored_announce(game_state, " ---------------------------------------------------- ")
        signal_turn_change(game_state)
        receive_until_turn_change(game_state)
        colored_announce(game_state, "[对手的回合结束]")
        refresh_cards(game_state)
        colored_announce(game_state, " ---------------------------------------------------- ")
        round_number += 1

    set_phase(game_state, "游戏结束")
    game_state.window.read()


def main():
    init_theme()
    game_state = NetworkGameState()
    game_state.local_player_id = 1
    game_state.connection = accept_client_connection()

    try:
        if not exchange_character_choices(game_state):
            return
        if not prepare_game_window(game_state):
            return
        run_server_game(game_state)
    except (ConnectionError, OSError, ValueError) as error:
        sg.popup_error(f"联网对战中断: {error}", keep_on_top=True)
    finally:
        if game_state.window is not None:
            game_state.window.close()
        game_state.connection.close()


if __name__ == "__main__":
    main()
