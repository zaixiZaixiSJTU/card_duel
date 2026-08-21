"""Main-menu entry point shared by both launchers."""

from __future__ import annotations

import json

import FreeSimpleGUI as sg

from card_duel.core.models import GameState
from card_duel.network.session import GameSession
from card_duel.ui.auxiliary_windows import close_auxiliary_windows
from card_duel.ui.main_menu import (
    MAIN_MENU_CREATE,
    MAIN_MENU_JOIN,
    main_menu_dialog,
)
from card_duel.ui.network_style import init_theme


def run_launcher() -> None:
    """Show the main menu, then run either the host or the join flow."""
    init_theme()
    while True:
        choice = main_menu_dialog()
        if choice is None:
            return
        if choice == MAIN_MENU_CREATE:
            _host_launch()
        elif choice == MAIN_MENU_JOIN:
            _join_launch()
        # 对局结束（退出房间/退出对战）后回到主菜单重新选择


def _host_launch() -> None:
    from card_duel.network.server import accept_client_connection, host_match

    connection = accept_client_connection()
    session = GameSession(
        state=GameState(local_player_id=1), connection=connection
    )
    try:
        host_match(session)
    except (ConnectionError, OSError, ValueError) as error:
        sg.popup_error(f"联网对战中断: {error}", keep_on_top=True)
    finally:
        close_auxiliary_windows(session)
        if session.window is not None:
            session.window.close()
        connection.close()


def _join_launch() -> None:
    from card_duel.network.client import (
        connect_with_retry,
        join_match,
        receive_welcome_message,
    )

    connection = connect_with_retry()
    if connection is None:
        return
    session = GameSession(
        state=GameState(local_player_id=2), connection=connection
    )
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
