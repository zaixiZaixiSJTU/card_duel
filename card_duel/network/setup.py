"""Shared network-match setup used by host and client roles."""

from __future__ import annotations

import FreeSimpleGUI as sg

from card_duel.core.resources import load_character_images
from card_duel.core.rules import build_shuffled_deck
from card_duel.network.transport import receive_json, send_json
from card_duel.ui.card_interaction import bind_hand_card_events
from card_duel.ui.network import create_main_layout
from card_duel.ui.network_dialogs import character_select_dialog, waiting_dialog
from card_duel.ui.network_style import WINDOW_SIZE, WINDOW_TITLE
from card_duel.ui.network_view import refresh_cards


def exchange_character_choices(session, local_player_id: int) -> bool:
    selected = character_select_dialog(session.registry)
    if selected is None:
        return False

    peer_player_id = 2 if local_player_id == 1 else 1
    waiting_window = waiting_dialog("等待对方选择...")
    try:
        session.state.character_ids[local_player_id] = int(selected)
        send_json(
            session.connection,
            {"type": "character_choice", "character_id": int(selected)},
        )
        peer_choice = receive_json(session.connection.recv)
        if peer_choice.get("type") != "character_choice":
            raise ConnectionError("选角阶段收到非预期消息")
        session.state.character_ids[peer_player_id] = int(peer_choice["character_id"])
        return True
    finally:
        waiting_window.close()


def prepare_game_window(session) -> bool:
    state = session.state
    session.combat.initialize_players()
    character_id = state.local_character_id
    if character_id is None:
        raise ValueError("本地角色尚未选择")

    session.card_images, session.max_card_id = load_character_images(
        character_id, session.registry
    )
    if not session.card_images:
        return False
    state.draw_pile = build_shuffled_deck(
        1,
        session.max_card_id,
        session.registry.get_deck_counts(character_id),
    )
    layout = create_main_layout(session.card_images, state.hand_cards)
    session.window = sg.Window(
        WINDOW_TITLE,
        layout,
        size=WINDOW_SIZE,
        font=("Microsoft YaHei", 10),
        finalize=True,
        resizable=True,
    )
    bind_hand_card_events(session.require_window())
    refresh_cards(state, session.require_window(), session.card_images)
    return True
