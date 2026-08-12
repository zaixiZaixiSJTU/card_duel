"""Non-blocking card motion inspired by deck-building combat games."""

from __future__ import annotations

import base64
import io
import math
import tkinter as tk
from collections import Counter
from contextlib import suppress

from PIL import Image, ImageEnhance, ImageTk

ANIMATION_SIZE = (104, 156)
FRAME_INTERVAL_MS = 20
DRAW_DURATION_MS = 480
ACTION_DURATION_MS = 420


def animate_hand_additions(session, previous_hand: list[int]) -> int:
    """Animate cards newly present in hand, preserving duplicate counts."""
    remaining = Counter(session.state.hand_cards) - Counter(previous_hand)
    indexes = []
    for index in range(len(session.state.hand_cards) - 1, -1, -1):
        card_id = session.state.hand_cards[index]
        if remaining[card_id] <= 0:
            continue
        remaining[card_id] -= 1
        indexes.append(index)
    indexes.reverse()
    animate_draw_cards(session, indexes)
    return len(indexes)


def animate_draw_cards(session, hand_indexes) -> None:
    """Fan cards from the deck counter into their rendered hand slots."""
    window = _session_window(session)
    if getattr(window, "TKroot", None) is None:
        return
    _flush_layout(window)
    start = _widget_center(window, "-DECK-COUNT-")
    for order, hand_index in enumerate(hand_indexes):
        if hand_index >= len(session.state.hand_cards):
            continue
        end = _widget_center(window, f"-BTN{hand_index}-")
        card_id = session.state.hand_cards[hand_index]
        _schedule_motion(
            session,
            session.card_images[card_id],
            start,
            end,
            kind="draw",
            delay_ms=order * 90,
            destination_key=f"-BTN{hand_index}-",
        )


def animate_card_action(session, hand_index: int, kind: str) -> None:
    """Animate a confirmed card toward play space or the discard direction."""
    if hand_index >= len(session.state.hand_cards):
        return
    window = _session_window(session)
    if getattr(window, "TKroot", None) is None:
        return
    _flush_layout(window)
    start = _widget_center(window, f"-BTN{hand_index}-")
    root = window.TKroot
    if kind == "play":
        end = (
            root.winfo_rootx() + root.winfo_width() // 2,
            root.winfo_rooty() + max(180, root.winfo_height() // 3),
        )
    else:
        end = (
            root.winfo_rootx() + root.winfo_width() - 80,
            root.winfo_rooty() + root.winfo_height() - 40,
        )
    card_id = session.state.hand_cards[hand_index]
    _schedule_motion(
        session,
        session.card_images[card_id],
        start,
        end,
        kind=kind,
    )


def close_card_animations(session) -> None:
    """Destroy outstanding animation overlays during endpoint shutdown."""
    callbacks = list(getattr(session, "animation_callbacks", ()))
    if hasattr(session, "animation_callbacks"):
        session.animation_callbacks.clear()
    for owner, callback_id in callbacks:
        try:
            owner.after_cancel(callback_id)
        except Exception:
            continue
    windows = list(getattr(session, "animation_windows", ()))
    if hasattr(session, "animation_windows"):
        session.animation_windows.clear()
    for window in windows:
        try:
            window.destroy()
        except Exception:
            continue


def enlarged_card_image(image_data: bytes, size=(320, 480)) -> bytes:
    """Return a crisp two-times preview image accepted by FreeSimpleGUI."""
    with Image.open(io.BytesIO(base64.b64decode(image_data))) as image:
        image = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


def _schedule_motion(
    session,
    image_data: bytes,
    start,
    end,
    *,
    kind: str,
    delay_ms: int = 0,
    destination_key: str | None = None,
) -> None:
    window = _session_window(session)
    root = getattr(window, "TKroot", None)
    if root is None:
        return

    def begin():
        try:
            overlay = tk.Toplevel(root)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            with suppress(tk.TclError):
                overlay.attributes("-disabled", True)
            overlay.configure(background="#171A1F")
            image = _animation_image(image_data, kind)
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(
                overlay,
                image=photo,
                background="#171A1F",
                borderwidth=3,
                relief="solid",
                highlightthickness=2,
                highlightbackground=_accent(kind),
            )
            label.image = photo
            label.pack()
            overlay._card_photo = photo
            overlay.geometry(_geometry_at(start))
            if not hasattr(session, "animation_windows"):
                session.animation_windows = []
            session.animation_windows.append(overlay)
            duration = DRAW_DURATION_MS if kind == "draw" else ACTION_DURATION_MS
            frame_count = max(1, duration // FRAME_INTERVAL_MS)
            _move_frame(
                session,
                overlay,
                start,
                end,
                kind,
                0,
                frame_count,
                destination_key,
            )
        except Exception:
            return

    try:
        _after(session, delay_ms, begin)
    except Exception:
        return


def _move_frame(
    session,
    overlay,
    start,
    end,
    kind,
    frame,
    frame_count,
    destination_key,
) -> None:
    try:
        progress = min(1.0, frame / frame_count)
        eased = 1 - (1 - progress) ** 3
        x = start[0] + (end[0] - start[0]) * eased
        y = start[1] + (end[1] - start[1]) * eased
        if kind == "draw":
            y -= math.sin(progress * math.pi) * 75
            alpha = min(1.0, 0.25 + progress * 1.15)
        elif kind == "play":
            y -= math.sin(progress * math.pi) * 35
            alpha = 1.0 - max(0.0, progress - 0.58) / 0.42
        else:
            x += math.sin(progress * math.pi * 2) * 24
            alpha = 1.0 - max(0.0, progress - 0.42) / 0.58
        overlay.geometry(_geometry_at((x, y)))
        overlay.attributes("-alpha", max(0.08, alpha))
        if frame >= frame_count:
            _finish_motion(session, overlay, destination_key, kind)
            return
        _after(
            session,
            FRAME_INTERVAL_MS,
            lambda: _move_frame(
                session,
                overlay,
                start,
                end,
                kind,
                frame + 1,
                frame_count,
                destination_key,
            ),
        )
    except Exception:
        _destroy_overlay(session, overlay)


def _finish_motion(session, overlay, destination_key, kind) -> None:
    _destroy_overlay(session, overlay)
    if destination_key is None:
        return
    try:
        widget = _session_window(session)[destination_key].Widget
        original = widget.cget("highlightbackground")
        original_thickness = widget.cget("highlightthickness")
        widget.configure(highlightthickness=6, highlightbackground=_accent(kind))
        _after(
            session,
            180,
            lambda: widget.configure(
                highlightthickness=original_thickness,
                highlightbackground=original,
            ),
        )
    except Exception:
        return


def _destroy_overlay(session, overlay) -> None:
    with suppress(ValueError, AttributeError):
        session.animation_windows.remove(overlay)
    try:
        overlay.destroy()
    except Exception:
        return


def _after(session, delay_ms: int, callback) -> str:
    """Schedule and track a callback so shutdown can cancel it safely."""
    if not hasattr(session, "animation_callbacks"):
        session.animation_callbacks = []
    scheduler = _session_window(session).TKroot
    token = [None]

    def run():
        item = (scheduler, token[0])
        with suppress(ValueError):
            session.animation_callbacks.remove(item)
        callback()

    callback_id = scheduler.after(delay_ms, run)
    token[0] = callback_id
    session.animation_callbacks.append((scheduler, callback_id))
    return callback_id


def _animation_image(image_data: bytes, kind: str) -> Image.Image:
    with Image.open(io.BytesIO(base64.b64decode(image_data))) as image:
        image = image.convert("RGB").resize(ANIMATION_SIZE, Image.Resampling.LANCZOS)
    if kind == "discard":
        image = ImageEnhance.Color(image).enhance(0.35)
        tint = Image.new("RGB", image.size, "#8E3B35")
        image = Image.blend(image, tint, 0.28)
    elif kind == "play":
        image = ImageEnhance.Contrast(image).enhance(1.08)
    return image


def _widget_center(window, key) -> tuple[int, int]:
    try:
        widget = window[key].Widget
        return (
            widget.winfo_rootx() + widget.winfo_width() // 2,
            widget.winfo_rooty() + widget.winfo_height() // 2,
        )
    except Exception:
        root = window.TKroot
        return (
            root.winfo_rootx() + root.winfo_width() // 2,
            root.winfo_rooty() + root.winfo_height() // 2,
        )


def _flush_layout(window) -> None:
    try:
        window.TKroot.update_idletasks()
    except Exception:
        return


def _geometry_at(center) -> str:
    x = int(center[0] - ANIMATION_SIZE[0] / 2)
    y = int(center[1] - ANIMATION_SIZE[1] / 2)
    return f"{ANIMATION_SIZE[0]}x{ANIMATION_SIZE[1]}{x:+d}{y:+d}"


def _session_window(session):
    require_window = getattr(session, "require_window", None)
    return require_window() if require_window else session.window


def _accent(kind: str) -> str:
    return {"draw": "#7EB6A2", "play": "#E0B35A", "discard": "#D46A60"}.get(
        kind, "#7EA4C8"
    )
