"""Consistent hand-card arming and preview interaction."""

from __future__ import annotations

import FreeSimpleGUI as sg

from card_duel.ui.network_style import (
    COLOR_BLUE,
    COLOR_PAPER,
    MAX_HAND_BUTTONS,
)

RIGHT_CLICK_SUFFIX = " RIGHT"


def bind_hand_card_events(window) -> None:
    """Make right-click events distinguishable from ordinary card clicks."""
    for index in range(MAX_HAND_BUTTONS):
        try:
            window[f"-BTN{index}-"].bind("<Button-3>", RIGHT_CLICK_SUFFIX)
        except (KeyError, AttributeError, RuntimeError):
            continue


def parse_hand_card_event(event) -> tuple[int, bool] | None:
    if not isinstance(event, str) or not event.startswith("-BTN"):
        return None
    preview = event.endswith(RIGHT_CLICK_SUFFIX)
    key = event[: -len(RIGHT_CLICK_SUFFIX)] if preview else event
    try:
        return int(key.removeprefix("-BTN").removesuffix("-")), preview
    except ValueError:
        return None


def route_hand_card_event(session, event) -> tuple[str, int] | None:
    """Return preview/armed/confirmed while retaining state outside GameState."""
    parsed = parse_hand_card_event(event)
    if parsed is None:
        return None
    index, preview = parsed
    if index >= len(session.state.hand_cards):
        return None
    if preview:
        preview_hand_card(session, index)
        return "preview", index
    if session.armed_hand_index == index:
        _mark_armed(session, index, False)
        session.armed_hand_index = None
        return "confirmed", index
    if session.armed_hand_index is not None:
        _mark_armed(session, session.armed_hand_index, False)
    session.armed_hand_index = index
    _mark_armed(session, index, True)
    return "armed", index


def clear_armed_card(session) -> None:
    if session.armed_hand_index is not None:
        _mark_armed(session, session.armed_hand_index, False)
    session.armed_hand_index = None


def preview_hand_card(session, hand_index: int) -> None:
    card_id = session.state.hand_cards[hand_index]
    image = session.card_images[card_id]
    window = sg.Window(
        "卡牌预览",
        [
            [sg.Image(data=image, background_color=COLOR_PAPER)],
            [sg.Button("关闭", key="-CLOSE-", bind_return_key=True)],
        ],
        modal=True,
        finalize=True,
        background_color=COLOR_PAPER,
    )
    try:
        while True:
            event, _values = window.read()
            if event in (sg.WIN_CLOSED, "-CLOSE-"):
                return
    finally:
        window.close()


def _mark_armed(session, hand_index: int, armed: bool) -> None:
    if not armed:
        from card_duel.ui.network_view import refresh_cards

        refresh_cards(
            session.state,
            session.require_window(),
            session.card_images,
        )
        return
    try:
        widget = session.require_window()[f"-BTN{hand_index}-"].Widget
        widget.configure(
            highlightthickness=6,
            highlightbackground=COLOR_BLUE,
            highlightcolor=COLOR_BLUE,
        )
    except (KeyError, AttributeError, RuntimeError):
        return
