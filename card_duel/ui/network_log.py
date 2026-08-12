"""Colored, failure-tolerant output for the network match log."""

from __future__ import annotations

from card_duel.ui.network_style import (
    COLOR_BLUE,
    COLOR_GOLD,
    COLOR_GREEN,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_RED,
)


def classify_log_color(message: str) -> str:
    """Choose a restrained semantic color without coupling rules to the UI."""
    if message.startswith("[我]") or "回合" in message:
        return COLOR_BLUE
    if message.startswith("[对方]") or set(message.strip()) <= {"-"}:
        return COLOR_MUTED
    if any(word in message for word in ("伤害", "失去", "击杀", "插入", "拔出")):
        return COLOR_RED
    if any(word in message for word in ("抽牌", "获得", "恢复", "+")):
        return COLOR_GREEN
    if any(word in message for word in ("不足", "警告", "无法", "不能")):
        return COLOR_GOLD
    return COLOR_INK


def append_log(session, message: str, *, color: str | None = None) -> None:
    """Append one line and tolerate a window closing during network cleanup."""
    if not message:
        return
    try:
        require_window = getattr(session, "require_window", None)
        window = require_window() if require_window else session.window
        element = window["-OUTPUT-"]
        widget = getattr(element, "Widget", None)
        if widget is None:
            element.update(f"{message}\n", append=True)
            return
        tag = f"log-{(color or classify_log_color(message)).lstrip('#')}"
        widget.configure(state="normal")
        widget.tag_configure(tag, foreground=color or classify_log_color(message))
        widget.insert("end", f"{message}\n", tag)
        widget.configure(state="disabled")
        widget.see("end")
    except Exception:
        return
