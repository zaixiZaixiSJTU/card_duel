"""Network game client (player 2)."""

import json
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
from card_duel.network.transport import receive_json
from card_duel.ui.auxiliary_windows import close_auxiliary_windows
from card_duel.ui.network_style import init_theme
from card_duel.ui.network_view import refresh_cards, set_cards_enabled, set_phase

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
        sg.popup_ok(f"连接成功!\n服务器: {server_host}:{port}", keep_on_top=True)
        return client_socket

    progress_window.close()
    sg.popup_error("连接失败", title="错误", keep_on_top=True)
    return None


def receive_welcome_message(connection):
    connection.settimeout(5)
    try:
        welcome_message = receive_json(connection.recv)
    finally:
        connection.settimeout(None)
    if welcome_message.get("type") != "welcome":
        raise ConnectionError("服务器欢迎消息格式无效")
    if welcome_message.get("protocol_version") != PROTOCOL_VERSION:
        raise ConnectionError("客户端与服务器协议版本不一致")
    print(
        "=== 连接成功 ===\n"
        f"服务器时间: {welcome_message['server_time']}\n"
        f"您的地址: {welcome_message['client']}\n"
        "================"
    )


def run_client_game(session):
    game_state = session.state
    window = session.require_window()
    set_phase(window, "对战开始")
    print(" ---------------------------------------------------- ")
    print(
        f"你选择了: {session.registry.get_character(game_state.character_ids[2]).name}"
    )
    print(
        f"对手选择了: {session.registry.get_character(game_state.character_ids[1]).name}"
    )
    print("对手先出牌")
    print(" ---------------------------------------------------- ")

    draw_cards(game_state, 2)
    refresh_cards(game_state, window, session.card_images)
    round_number = 1

    while session.combat.winning_player_id() is None:
        print(f"-------------------- ROUND {round_number} --------------------")
        set_phase(window, f"回合 {round_number} - 对手出牌中...")
        set_cards_enabled(window, False)
        window.refresh()

        receive_until_turn_change(session)
        print("[对手的回合结束]")
        refresh_cards(game_state, window, session.card_images)
        print(" ---------------------------------------------------- ")

        if not play_active_turn(session, player_id=2, round_number=round_number):
            return None
        signal_turn_change(session)
        time.sleep(0.3)
        print(" ---------------------------------------------------- ")
        round_number += 1

    set_phase(window, "游戏结束")
    return session.combat.winning_player_id()


def join_match(session) -> None:
    """Play matches until one side quits; re-select and rematch in between."""
    while True:
        config = room_phase(session, session.registry, is_host=False)
        if config is None:
            return
        apply_room_config(session, config, local_player_id=2)
        if not prepare_game_window(session):
            return
        announce_room_config(session)
        winner = run_client_game(session)
        if winner is None:
            return
        announce_winner(session, winner)
        if not ask_rematch(session, is_host=False):
            return
        reset_for_rematch(session, local_player_id=2)


def main():
    init_theme()
    connection = connect_with_retry()
    if connection is None:
        return
    state = GameState(local_player_id=2)
    session = GameSession(state=state, connection=connection)

    try:
        receive_welcome_message(connection)
        join_match(session)
    except (ConnectionError, OSError, ValueError, json.JSONDecodeError) as error:
        sg.popup_error(f"联网对战中断: {error}", keep_on_top=True)
    finally:
        close_auxiliary_windows(session)
        if session.window is not None:
            session.window.close()
        connection.close()


if __name__ == "__main__":
    main()
