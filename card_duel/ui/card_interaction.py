"""Consistent hand-card arming and preview interaction."""

from __future__ import annotations

import base64
import io

import FreeSimpleGUI as sg

from card_duel.ui.network_style import (
    COLOR_BLUE,
    COLOR_PAPER,
    MAX_HAND_BUTTONS,
)

RIGHT_CLICK_SUFFIX = " RIGHT"


def _enlarge(image_data: bytes, scale: float = 1.5) -> bytes:
    """Upscale a card image so the preview is larger than the original."""
    from PIL import Image

    raw = base64.b64decode(image_data)
    with Image.open(io.BytesIO(raw)) as image:
        target = (int(image.width * scale), int(image.height * scale))
        resized = image.resize(target, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        resized.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


def show_dismissable_preview(image_data: bytes, parent_window) -> None:
    """Show a large always-on-top preview that closes on any click.

    Fixes the "popup invisible until maximize" bug by explicitly mapping the
    window (deiconify), centering it on the parent, and forcing topmost. No
    dedicated close button: a click anywhere inside dismisses it.
    """
    window = sg.Window(
        "卡牌预览",
        [[sg.Image(data=image_data, background_color=COLOR_PAPER)]],
        modal=True,
        finalize=True,
        keep_on_top=True,
        background_color=COLOR_PAPER,
    )
    _force_visible_centered(window, parent_window)
    _bind_dismiss_on_click(window)
    try:
        while True:
            event, _values = window.read()
            if event in (sg.WIN_CLOSED, "-DISMISS-"):
                return
    finally:
        window.close()


def _force_visible_centered(window, parent_window) -> None:
    """Map, center on parent (or screen), and force the popup to the foreground."""
    root = window.TKroot
    parent = parent_window.TKroot if parent_window is not None else None
    try:
        root.update_idletasks()
        if parent is not None:
            parent.update_idletasks()
        root.deiconify()  # ensure the window is mapped (not withdrawn/iconic)
        w = max(1, root.winfo_width())
        h = max(1, root.winfo_height())
        if parent is not None:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = max(1, parent.winfo_width())
            ph = max(1, parent.winfo_height())
            x = max(0, px + (pw - w) // 2)
            y = max(0, py + (ph - h) // 2)
        else:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
        root.geometry(f"+{x}+{y}")
        root.lift()
        root.attributes("-topmost", 1)
        root.focus_force()
    except Exception:
        return


def _bind_dismiss_on_click(window) -> None:
    """Dismiss the popup on any left or right click inside it."""
    dismiss = lambda _e: window.write_event_value("-DISMISS-", "")
    window.TKroot.bind("<Button-1>", dismiss)
    window.TKroot.bind("<Button-3>", dismiss)


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
    show_dismissable_preview(
        _enlarge(session.card_images[card_id]), session.require_window()
    )


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
