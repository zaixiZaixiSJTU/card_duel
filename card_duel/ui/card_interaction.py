"""Consistent hand-card arming and preview interaction."""

from __future__ import annotations

import FreeSimpleGUI as sg

from card_duel.ui.card_animations import enlarged_card_image
from card_duel.ui.network_style import (
    COLOR_BLUE,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    COLOR_PAPER_DARK,
    FONT_BODY,
    FONT_BODY_BOLD,
    MAX_HAND_BUTTONS,
)

RIGHT_CLICK_SUFFIX = " RIGHT"


def bind_hand_card_events(window) -> None:
    """Make right-click events distinguishable from ordinary card clicks."""
    for index in range(MAX_HAND_BUTTONS):
        try:
            element = window[f"-BTN{index}-"]
            element.bind("<Button-3>", RIGHT_CLICK_SUFFIX)
            widget = element.Widget
            widget.configure(cursor="hand2", relief="flat")
            widget.bind("<Enter>", _hover_enter, add="+")
            widget.bind("<Leave>", _hover_leave, add="+")
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
    hand_count = len(session.state.hand_cards)
    creatures = [
        item
        for item in session.state.local_player.statuses.hand_creatures
        if item.card_id != 26
    ]
    if index >= hand_count + len(creatures):
        return None
    if index >= hand_count:
        creature_index = index - hand_count
        if preview:
            open_card_preview(
                session, session.card_images[creatures[creature_index].card_id]
            )
            return "preview_creature", creature_index
        if session.armed_creature_index == creature_index:
            _mark_armed(session, index, False)
            session.armed_creature_index = None
            _set_card_hint(session, "生物已确认，正在结算……")
            return "confirmed_creature", creature_index
        if session.armed_creature_index is not None:
            _mark_armed(
                session, hand_count + session.armed_creature_index, False
            )
        session.armed_creature_index = creature_index
        _mark_armed(session, index, True)
        _set_card_hint(session, "生物已抬起 · 再次左键确认打出 · 右键放大预览")
        return "armed_creature", creature_index
    if preview:
        preview_hand_card(session, index)
        return "preview", index
    if session.armed_hand_index == index:
        _mark_armed(session, index, False)
        session.armed_hand_index = None
        _set_card_hint(session, "卡牌已确认，正在结算……")
        return "confirmed", index
    if session.armed_hand_index is not None:
        _mark_armed(session, session.armed_hand_index, False)
    session.armed_hand_index = index
    _mark_armed(session, index, True)
    _set_card_hint(session, "卡牌已抬起 · 再次左键确认 · 右键放大预览")
    return "armed", index


def clear_armed_card(session) -> None:
    if session.armed_hand_index is not None:
        _mark_armed(session, session.armed_hand_index, False)
    creature_index = getattr(session, "armed_creature_index", None)
    if creature_index is not None:
        _mark_armed(session, len(session.state.hand_cards) + creature_index, False)
    session.armed_hand_index = None
    session.armed_creature_index = None
    _set_card_hint(session, "左键一次选中，再次确认 · 右键放大预览")


def preview_hand_card(session, hand_index: int) -> None:
    card_id = session.state.hand_cards[hand_index]
    open_card_preview(session, session.card_images[card_id])


def open_card_preview(session, image_data: bytes, parent=None) -> None:
    """Create a preview and return immediately; the main loop drives it.

    按住右键放大预览，松开右键即消失。
    """
    close_card_preview(session)
    window = sg.Window(
        "卡牌预览",
        [
            [
                sg.Text(
                    "卡牌详情",
                    font=FONT_BODY_BOLD,
                    text_color=COLOR_PAPER,
                    background_color=COLOR_INK,
                    expand_x=True,
                    justification="center",
                )
            ],
            [
                sg.Image(
                    data=enlarged_card_image(image_data),
                    key="-PREVIEW-CARD-",
                    background_color=COLOR_INK,
                    pad=(18, 12),
                )
            ],
            [
                sg.Text(
                    "松开右键关闭 · 不会暂停联机对局",
                    font=FONT_BODY,
                    text_color=COLOR_MUTED,
                    background_color=COLOR_INK,
                    expand_x=True,
                    justification="center",
                )
            ],
        ],
        finalize=True,
        keep_on_top=True,
        no_titlebar=True,
        background_color=COLOR_INK,
        element_justification="center",
        margins=(12, 12),
    )
    window.bind("<Escape>", "-CLOSE-")
    window.TKroot.attributes("-topmost", 1)
    # 全局绑定：松开右键 0.4 秒后关闭预览（无论鼠标在哪个窗口上）
    def _close_on_release(_event):
        def _delayed_close():
            if getattr(session, "preview_window", None) is window:
                close_card_preview(session)
        window.TKroot.after(400, _delayed_close)
    window.TKroot.bind_all("<ButtonRelease-3>", _close_on_release, add="+")
    session._preview_release_handler = _close_on_release
    session.preview_window = window
    try:
        parent = parent or session.require_window()
        window.TKroot.transient(parent.TKroot)
        window.TKroot.lift()
        window.TKroot.focus_force()
        window.TKroot.update_idletasks()
        x = (
            parent.TKroot.winfo_rootx()
            + (parent.TKroot.winfo_width() - window.TKroot.winfo_width()) // 2
        )
        y = (
            parent.TKroot.winfo_rooty()
            + (parent.TKroot.winfo_height() - window.TKroot.winfo_height()) // 2
        )
        window.move(max(0, x), max(0, y))
    except Exception:
        pass


def poll_card_preview(session) -> None:
    """Process at most one preview event without delaying network I/O."""
    window = getattr(session, "preview_window", None)
    if window is None:
        return
    try:
        event, _values = window.read(timeout=0)
    except Exception:
        close_card_preview(session)
        return
    # Escape 或窗口关闭事件
    if event in (sg.WIN_CLOSED, "-CLOSE-"):
        close_card_preview(session)


def close_card_preview(session) -> None:
    window = getattr(session, "preview_window", None)
    if window is not None:
        # 解除全局 ButtonRelease-3 绑定
        try:
            window.TKroot.unbind_all("<ButtonRelease-3>")
        except Exception:
            pass
    if hasattr(session, "_preview_release_handler"):
        session._preview_release_handler = None
    if hasattr(session, "preview_window"):
        session.preview_window = None
    if window is not None:
        try:
            window.close()
        except Exception:
            return


def _force_visible_centered(window, parent=None) -> None:
    """Force a modal/popup window to be visible, centered, and on top."""
    try:
        window.TKroot.deiconify()
        window.TKroot.update_idletasks()
        if parent is not None and getattr(parent, "TKroot", None) is not None:
            x = parent.TKroot.winfo_rootx() + (
                parent.TKroot.winfo_width() - window.TKroot.winfo_width()
            ) // 2
            y = parent.TKroot.winfo_rooty() + (
                parent.TKroot.winfo_height() - window.TKroot.winfo_height()
            ) // 2
        else:
            screen_w = window.TKroot.winfo_screenwidth()
            screen_h = window.TKroot.winfo_screenheight()
            win_w = window.TKroot.winfo_width()
            win_h = window.TKroot.winfo_height()
            x = max(0, (screen_w - win_w) // 2)
            y = max(0, (screen_h - win_h) // 2)
        window.TKroot.geometry(f"+{max(0, int(x))}+{max(0, int(y))}")
        window.TKroot.lift()
        window.TKroot.attributes("-topmost", 1)
        window.TKroot.focus_force()
    except Exception:
        return


def _mark_armed(session, hand_index: int, armed: bool) -> None:
    if not armed:
        from card_duel.ui.network_view import refresh_cards

        refresh_cards(
            session.state,
            session.require_window(),
            session.card_images,
        )
        try:
            widget = session.require_window()[f"-BTN{hand_index}-"].Widget
            widget._card_armed = False
            _set_card_spacing(widget, False)
            widget.configure(relief="flat", borderwidth=1)
        except Exception:
            pass
        return
    try:
        widget = session.require_window()[f"-BTN{hand_index}-"].Widget
        widget._card_armed = True
        _set_card_spacing(widget, True)
        widget.configure(
            highlightthickness=6,
            highlightbackground=COLOR_BLUE,
            highlightcolor=COLOR_BLUE,
            relief="raised",
            borderwidth=4,
        )
    except Exception:
        return


def _hover_enter(event) -> None:
    widget = event.widget
    if getattr(widget, "_card_armed", False):
        return
    try:
        widget.configure(relief="raised", borderwidth=3)
    except Exception:
        return


def _hover_leave(event) -> None:
    widget = event.widget
    if getattr(widget, "_card_armed", False):
        return
    try:
        widget.configure(relief="flat", borderwidth=1)
    except Exception:
        return


def _set_card_hint(session, text: str) -> None:
    try:
        session.require_window()["-CARD-HINT-"].update(text)
    except Exception:
        return


def _set_card_spacing(widget, armed: bool) -> None:
    """Lift a card using the geometry manager chosen by FreeSimpleGUI."""
    manager = widget.winfo_manager()
    if manager == "pack":
        widget.pack_configure(pady=7 if armed else 0)
    elif manager == "grid":
        widget.grid_configure(pady=(0, 14) if armed else (0, 0))
