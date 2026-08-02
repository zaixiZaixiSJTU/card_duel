"""Network game client (player 2)."""

import json
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
    signal_turn_change,
)
from card_duel.ui.network import (
    WINDOW_SIZE,
    WINDOW_TITLE,
    character_select_dialog,
    create_main_layout,
    init_theme,
    refresh_cards,
    set_cards_enabled,
    set_phase,
    waiting_dialog,
)

MAX_CONNECTION_ATTEMPTS = 40


def connect_with_retry(port=DEFAULT_PORT):
    """Prompt for a host and retry until connected or cancelled."""
    server_host = sg.popup_get_text(
        "请输入服务器 IP:",
        default_text="127.0.0.1",
        title="连接设置",
        keep_on_top=True,
    )
    if server_host is None:
        return None

    progress_layout = [
        [
            sg.Text(
                f"正在连接 {server_host}:{port}...",
                font=("Microsoft YaHei", 10),
            )
        ],
        [
            sg.ProgressBar(
                MAX_CONNECTION_ATTEMPTS,
                orientation="h",
                size=(30, 20),
                key="-PROGRESS-",
            )
        ],
        [sg.Button("取消", key="-CANCEL-")],
    ]
    progress_window = sg.Window(
        "连接中", progress_layout, finalize=True, keep_on_top=True
    )

    for attempt_number in range(1, MAX_CONNECTION_ATTEMPTS + 1):
        event, _ = progress_window.read(timeout=100)
        if event in ("-CANCEL-", sg.WIN_CLOSED):
            progress_window.close()
            sg.popup("已取消连接", keep_on_top=True)
            return None

        client_socket = socket.socket()
        client_socket.settimeout(3)
        try:
            client_socket.connect((server_host, port))
        except OSError:
            client_socket.close()
            progress_window["-PROGRESS-"].update(attempt_number)
            if attempt_number < MAX_CONNECTION_ATTEMPTS:
                time.sleep(1)
            continue

        client_socket.settimeout(None)
        progress_window.close()
        sg.popup_ok(
            f"连接成功!\n服务器: {server_host}:{port}", keep_on_top=True
        )
        return client_socket

    progress_window.close()
    sg.popup_error("连接失败", title="错误", keep_on_top=True)
    return None


def receive_welcome_message(connection):
    connection.settimeout(5)
    raw_message = connection.recv(1024)
    welcome_message = json.loads(raw_message.decode("utf-8"))
    connection.sendall(ACK_MESSAGE.encode("utf-8"))
    connection.settimeout(None)
    print(
        "=== 连接成功 ===\n"
        f"服务器时间: {welcome_message['server_time']}\n"
        f"您的地址: {welcome_message['client']}\n"
        "================"
    )


def exchange_character_choices(game_state):
    selected_character = character_select_dialog()
    if selected_character is None:
        return False

    waiting_window = waiting_dialog("等待对方选择...")
    try:
        game_state.character_ids[2] = int(selected_character)
        game_state.connection.sendall(selected_character.encode("utf-8"))
        peer_choice = game_state.connection.recv(1024).decode("utf-8")
        game_state.character_ids[1] = int(peer_choice)
        return True
    finally:
        waiting_window.close()


def prepare_game_window(game_state):
    initialize_character_states(game_state)
    character_id = game_state.character_ids[2]
    game_state.card_images, game_state.max_card_id = load_character_images(
        character_id
    )
    if not game_state.card_images:
        return False

    game_state.draw_pile = build_shuffled_deck(
        1,
        game_state.max_card_id,
        get_card_counts(character_id),
    )
    layout = create_main_layout(game_state.card_images, game_state.hand_cards)
    game_state.window = sg.Window(
        WINDOW_TITLE,
        layout,
        size=WINDOW_SIZE,
        font=("Microsoft YaHei", 10),
        finalize=True,
        keep_on_top=True,
        resizable=True,
    )
    refresh_cards(game_state)
    return True


def run_client_game(game_state):
    set_phase(game_state, "对战开始")
    print(" ---------------------------------------------------- ")
    print(f"你选择了: {CHARACTERS[game_state.character_ids[2]]}")
    print(f"对手选择了: {CHARACTERS[game_state.character_ids[1]]}")
    print("对手先出牌")
    print(" ---------------------------------------------------- ")

    draw_cards(game_state, 2)
    refresh_cards(game_state)
    round_number = 1

    while all(player.health > 0 for player in game_state.players.values()):
        print(f"-------------------- ROUND {round_number} --------------------")
        set_phase(game_state, f"回合 {round_number} - 对手出牌中...")
        set_cards_enabled(game_state, False)
        game_state.window.refresh()

        receive_until_turn_change(game_state)
        print("[对手的回合结束]")
        refresh_cards(game_state)
        print(" ---------------------------------------------------- ")

        if not play_active_turn(game_state, player_id=2, round_number=round_number):
            return
        signal_turn_change(game_state)
        time.sleep(0.3)
        print(" ---------------------------------------------------- ")
        round_number += 1

    set_phase(game_state, "游戏结束")
    game_state.window.read()


def main():
    init_theme()
    game_state = NetworkGameState()
    game_state.local_player_id = 2
    game_state.connection = connect_with_retry()
    if game_state.connection is None:
        return

    try:
        receive_welcome_message(game_state.connection)
        if not exchange_character_choices(game_state):
            return
        if not prepare_game_window(game_state):
            return
        run_client_game(game_state)
    except (ConnectionError, OSError, ValueError, json.JSONDecodeError) as error:
        sg.popup_error(f"联网对战中断: {error}", keep_on_top=True)
    finally:
        if game_state.window is not None:
            game_state.window.close()
        game_state.connection.close()


if __name__ == "__main__":
    main()
