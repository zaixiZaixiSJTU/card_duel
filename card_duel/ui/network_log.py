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

# 日志文本类型规范：标识号（ID）+ 显示名 + 默认颜色。
LOG_TYPES = (
    ("chat", "聊天", COLOR_MUTED),
    ("turn", "回合", COLOR_BLUE),
    ("damage", "伤害", COLOR_RED),
    ("gain", "获得", COLOR_GREEN),
    ("warn", "警告", COLOR_GOLD),
    ("normal", "普通", COLOR_INK),
)
LOG_CATEGORIES = tuple(item[0] for item in LOG_TYPES)
LOG_TYPE_NAMES = {item[0]: item[1] for item in LOG_TYPES}
LOG_TYPE_COLORS = {item[0]: item[2] for item in LOG_TYPES}

_SOUND_BY_CATEGORY = {
    "chat": "chat",
    "turn": "turn",
    "damage": "hit",
    "gain": "draw",
    "warn": "warn",
    "normal": "click",
}


def _session_window(session):
    require_window = getattr(session, "require_window", None)
    return require_window() if require_window else session.window


def log_category(message: str) -> str:
    """Semantic display category used by the log display-type filter."""
    if message.startswith("[我]") or message.startswith("[对方]") or set(
        message.strip()
    ) <= {"-"}:
        return "chat"
    if "回合" in message:
        return "turn"
    if any(word in message for word in ("伤害", "失去", "击杀", "插入", "拔出")):
        return "damage"
    if any(word in message for word in ("抽牌", "获得", "恢复", "+")):
        return "gain"
    if any(word in message for word in ("不足", "警告", "无法", "不能")):
        return "warn"
    return "normal"


def classify_log_color(message: str) -> str:
    """Choose a restrained semantic color without coupling rules to the UI."""
    return LOG_TYPE_COLORS[log_category(message)]


def _insert_log_line(session, message: str, widget, color: str) -> None:
    tag = f"log-{color.lstrip('#')}"
    widget.configure(state="normal")
    widget.tag_configure(tag, foreground=color)
    widget.insert("end", f"{message}\n", tag)
    widget.configure(state="disabled")


def append_log(session, message: str, *, color: str | None = None) -> None:
    """Append one line and tolerate a window closing during network cleanup."""
    if not message:
        return
    category = log_category(message)
    configured = getattr(session, "log_type_colors", None) or {}
    resolved = color or configured.get(category) or LOG_TYPE_COLORS[category]
    history = getattr(session, "log_history", None)
    if history is not None:
        history.append(message)
    if getattr(session, "sound_enabled", True):
        from card_duel.ui.sound import play_sound

        sound_name = "card" if "打出" in message else _SOUND_BY_CATEGORY.get(
            category, "click"
        )
        effects = getattr(session, "sound_effects", None)
        if effects is None or sound_name in effects:
            play_sound(sound_name)
    try:
        window = _session_window(session)
        element = window["-OUTPUT-"]
        widget = getattr(element, "Widget", None)
        if widget is None:
            element.update(f"{message}\n", append=True)
            return
        _insert_log_line(session, message, widget, resolved)
        widget.see("end")
    except Exception:
        return


def rerender_log(session) -> None:
    """Rebuild the visible log with the current colors."""
    history = getattr(session, "log_history", None)
    if not history:
        return
    configured = getattr(session, "log_type_colors", None) or {}
    try:
        window = _session_window(session)
        widget = getattr(window["-OUTPUT-"], "Widget", None)
        if widget is None:
            return
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for message in history:
            category = log_category(message)
            color = configured.get(category) or LOG_TYPE_COLORS[category]
            _insert_log_line(session, message, widget, color)
        widget.configure(state="disabled")
        widget.see("end")
    except Exception:
        return
