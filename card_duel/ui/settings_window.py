"""Non-blocking display-settings window with live color picking."""

from __future__ import annotations

import FreeSimpleGUI as sg

from card_duel.ui.network_log import (
    LOG_CATEGORIES,
    LOG_TYPE_COLORS,
    LOG_TYPE_NAMES,
)
from card_duel.ui.network_style import (
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
)
from card_duel.ui.network_view import CARD_BORDER_TYPES

SETTINGS_KEY = "-SETTINGS-"
_MAIN_KEY = "-SETTINGS-MAIN-"
_LOGCOLOR_KEY = "-SETTINGS-LOGCOLOR-"
_CARDCOLOR_KEY = "-SETTINGS-CARDCOLOR-"
_SOUND_KEY = "-SETTINGS-SOUND-"
_OP_KEY = "-SETTINGS-OP-"
_GO_LOGCOLOR_KEY = "-SETTINGS-GO-LOGCOLOR-"
_GO_CARDCOLOR_KEY = "-SETTINGS-GO-CARDCOLOR-"
_GO_SOUND_KEY = "-SETTINGS-GO-SOUND-"
_GO_OP_KEY = "-SETTINGS-GO-OP-"
_BACK_LOGCOLOR_KEY = "-SETTINGS-BACK-LOGCOLOR-"
_BACK_CARDCOLOR_KEY = "-SETTINGS-BACK-CARDCOLOR-"
_BACK_SOUND_KEY = "-SETTINGS-BACK-SOUND-"
_BACK_OP_KEY = "-SETTINGS-BACK-OP-"
_CLOSE_KEY = "-SETTINGS-CLOSE-"
_LOG_COLOR_PREFIX = "-LOGCOLOR-"
_CARD_COLOR_PREFIX = "-CARDCOLOR-"
_LOG_SWATCH_PREFIX = "-LOGCOLOR-SWATCH-"
_CARD_SWATCH_PREFIX = "-CARDCOLOR-SWATCH-"
_SOUND_LABELS = {
    "hit": "伤害",
    "draw": "抽牌",
    "warn": "警告",
    "chat": "聊天",
    "turn": "回合",
    "card": "出牌",
    "click": "点击",
}


def open_settings(session) -> None:
    """Open a fresh non-blocking settings window with switchable panels."""
    close_settings(session)
    # 打开前从文件重载最新配置（本机 host/guest 双进程共用），并让日志/卡面同步。
    from card_duel.ui.app_settings import load_settings
    from card_duel.ui.network_log import rerender_log
    from card_duel.ui.network_view import refresh_cards

    load_settings(session)
    rerender_log(session)
    try:
        refresh_cards(
            session.state, session.require_window(), session.card_images
        )
    except Exception:
        pass

    main = sg.Column(
        [
            [
                sg.Text("设置", font=FONT_HEADING, text_color=COLOR_INK),
                sg.Text(
                    "显示设置",
                    font=FONT_BODY,
                    text_color=COLOR_MUTED,
                ),
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Button(
                    "日志文本颜色配置",
                    key=_GO_LOGCOLOR_KEY,
                    font=FONT_BODY_BOLD,
                )
            ],
            [
                sg.Button(
                    "卡牌类型边框色彩配置",
                    key=_GO_CARDCOLOR_KEY,
                    font=FONT_BODY_BOLD,
                )
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Button(
                    "音效设置",
                    key=_GO_SOUND_KEY,
                    font=FONT_BODY,
                )
            ],
            [
                sg.Button(
                    "操作设置",
                    key=_GO_OP_KEY,
                    font=FONT_BODY,
                )
            ],
            [sg.HorizontalSeparator()],
            [sg.Button("关闭", key=_CLOSE_KEY, font=FONT_BODY_BOLD)],
        ],
        key=_MAIN_KEY,
        background_color=COLOR_PAPER,
    )

    log_colors = getattr(session, "log_type_colors", None) or {}
    log_color_rows = [
        [
            sg.Text("日志文本颜色", font=FONT_HEADING, text_color=COLOR_INK),
            sg.Button("← 返回", key=_BACK_LOGCOLOR_KEY, font=FONT_BODY_BOLD),
        ],
        [
            sg.Text(
                "调色盘选择后立即生效",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            )
        ],
        [sg.HorizontalSeparator()],
    ]
    for category, name, default in zip(
        LOG_CATEGORIES, LOG_TYPE_NAMES.values(), LOG_TYPE_COLORS.values()
    ):
        current = log_colors.get(category, default)
        log_color_rows.append(
            [
                sg.Text(name, size=(6, 1), font=FONT_BODY),
                sg.Input(
                    current,
                    key=f"{_LOG_COLOR_PREFIX}{category}-",
                    size=(9, 1),
                    font=FONT_BODY,
                    readonly=True,
                ),
                sg.ColorChooserButton(
                    "调色盘",
                    target=f"{_LOG_COLOR_PREFIX}{category}-",
                    font=FONT_BODY,
                ),
                sg.Text(
                    "   ",
                    key=f"{_LOG_SWATCH_PREFIX}{category}-",
                    background_color=current,
                    size=(3, 1),
                    pad=(4, 0),
                ),
            ]
        )
    log_color_panel = sg.Column(
        log_color_rows,
        key=_LOGCOLOR_KEY,
        background_color=COLOR_PAPER,
    )

    border_colors = getattr(session, "card_border_colors", None) or {}
    card_color_rows = [
        [
            sg.Text(
                "卡牌类型边框颜色",
                font=FONT_HEADING,
                text_color=COLOR_INK,
            ),
            sg.Button("← 返回", key=_BACK_CARDCOLOR_KEY, font=FONT_BODY_BOLD),
        ],
        [
            sg.Text(
                "调色盘选择后立即生效",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            )
        ],
        [sg.HorizontalSeparator()],
    ]
    for key, name, default in CARD_BORDER_TYPES:
        current = border_colors.get(key, default)
        card_color_rows.append(
            [
                sg.Text(name, size=(16, 1), font=FONT_BODY),
                sg.Input(
                    current,
                    key=f"{_CARD_COLOR_PREFIX}{key}-",
                    size=(9, 1),
                    font=FONT_BODY,
                    readonly=True,
                ),
                sg.ColorChooserButton(
                    "调色盘",
                    target=f"{_CARD_COLOR_PREFIX}{key}-",
                    font=FONT_BODY,
                ),
                sg.Text(
                    "   ",
                    key=f"{_CARD_SWATCH_PREFIX}{key}-",
                    background_color=current,
                    size=(3, 1),
                    pad=(4, 0),
                ),
            ]
        )
    card_color_panel = sg.Column(
        card_color_rows,
        key=_CARDCOLOR_KEY,
        background_color=COLOR_PAPER,
    )

    sound_effects = set(
        getattr(session, "sound_effects", None)
        or {"hit", "draw", "warn", "chat", "turn", "card", "click"}
    )
    sound_rows = [
        [
            sg.Text("音效设置", font=FONT_HEADING, text_color=COLOR_INK),
            sg.Button("← 返回", key=_BACK_SOUND_KEY, font=FONT_BODY_BOLD),
        ],
        [
            sg.Text(
                "勾选后立即生效",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            )
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Checkbox(
                "启用音效",
                key="-SOUND-ENABLED-",
                default=getattr(session, "sound_enabled", True),
                font=FONT_BODY,
                background_color=COLOR_PAPER,
                enable_events=True,
            )
        ],
        [
            sg.Text(
                "音效类型",
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
            )
        ],
    ]
    for sound_name, label in _SOUND_LABELS.items():
        sound_rows.append(
            [
                sg.Checkbox(
                    label,
                    key=f"-SOUND-EFFECT-{sound_name}-",
                    default=sound_name in sound_effects,
                    font=FONT_BODY,
                    background_color=COLOR_PAPER,
                    enable_events=True,
                )
            ]
        )
    sound_panel = sg.Column(
        sound_rows,
        key=_SOUND_KEY,
        background_color=COLOR_PAPER,
    )

    op_rows = [
        [
            sg.Text("操作设置", font=FONT_HEADING, text_color=COLOR_INK),
            sg.Button("← 返回", key=_BACK_OP_KEY, font=FONT_BODY_BOLD),
        ],
        [
            sg.Text(
                "选择后立即生效",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            )
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Radio(
                "单击出牌",
                "op",
                key="-OP-SINGLE-",
                default=getattr(session, "single_click_play", False),
                font=FONT_BODY,
                background_color=COLOR_PAPER,
                enable_events=True,
            ),
            sg.Radio(
                "双击出牌",
                "op",
                key="-OP-DOUBLE-",
                default=not getattr(session, "single_click_play", False),
                font=FONT_BODY,
                background_color=COLOR_PAPER,
                enable_events=True,
            ),
        ],
        [
            sg.Text(
                "单击：点一下直接打出；双击：点一下选中、再点确认",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            )
        ],
    ]
    op_panel = sg.Column(
        op_rows,
        key=_OP_KEY,
        background_color=COLOR_PAPER,
    )

    window = sg.Window(
        "设置",
        [
            [sg.pin(main)],
            [sg.pin(log_color_panel)],
            [sg.pin(card_color_panel)],
            [sg.pin(sound_panel)],
            [sg.pin(op_panel)],
        ],
        finalize=True,
        keep_on_top=True,
        modal=False,
        background_color=COLOR_PAPER,
        margins=(12, 10),
        element_justification="left",
        size=(440, 360),
        resizable=False,
    )
    session.settings_window = window
    _switch_settings_panel(window, _MAIN_KEY)
    session.settings_color_snapshot = {
        f"{_LOG_COLOR_PREFIX}{category}-": (
            log_colors.get(category, LOG_TYPE_COLORS[category])
        )
        for category in LOG_CATEGORIES
    }
    session.settings_color_snapshot.update(
        {
            f"{_CARD_COLOR_PREFIX}{key}-": (
                border_colors.get(key, default)
            )
            for key, _name, default in CARD_BORDER_TYPES
        }
    )


def poll_settings(session) -> None:
    """Give the settings window one non-blocking event-loop slice."""
    window = getattr(session, "settings_window", None)
    if window is None:
        return
    try:
        event, values = window.read(timeout=50)
    except Exception:
        close_settings(session)
        return
    if event in (sg.WIN_CLOSED, _CLOSE_KEY, None):
        close_settings(session)
        return
    if event == _GO_LOGCOLOR_KEY:
        _switch_settings_panel(window, _LOGCOLOR_KEY)
    elif event == _GO_CARDCOLOR_KEY:
        _switch_settings_panel(window, _CARDCOLOR_KEY)
    elif event == _GO_SOUND_KEY:
        _switch_settings_panel(window, _SOUND_KEY)
    elif event == _GO_OP_KEY:
        _switch_settings_panel(window, _OP_KEY)
    elif event in (
        _BACK_LOGCOLOR_KEY,
        _BACK_CARDCOLOR_KEY,
        _BACK_SOUND_KEY,
        _BACK_OP_KEY,
    ):
        _switch_settings_panel(window, _MAIN_KEY)
    elif event == "-SOUND-ENABLED-":
        _apply_sound_settings(session, values)
    elif isinstance(event, str) and event.startswith("-SOUND-EFFECT-"):
        _apply_sound_settings(session, values)
    elif event in ("-OP-SINGLE-", "-OP-DOUBLE-"):
        _apply_operation_settings(session, values)
    # 兜底：即使勾选事件未触发，也按值变化即时生效并保存。
    sound_value = bool(
        values.get("-SOUND-ENABLED-", getattr(session, "sound_enabled", True))
    )
    if sound_value != getattr(session, "sound_enabled", True):
        _apply_sound_settings(session, values)
    _apply_live_color_changes(session, values)


def _switch_settings_panel(window, target_key: str) -> None:
    try:
        for key in (
            _MAIN_KEY,
            _LOGCOLOR_KEY,
            _CARDCOLOR_KEY,
            _SOUND_KEY,
            _OP_KEY,
        ):
            window[key].update(visible=(key == target_key))
        window.refresh()
    except Exception:
        return


def _apply_live_color_changes(session, values) -> None:
    """Pick colors take effect immediately (no confirm button needed)."""
    snapshot = dict(getattr(session, "settings_color_snapshot", None) or {})
    log_colors = dict(getattr(session, "log_type_colors", None) or {})
    for category in LOG_CATEGORIES:
        key = f"{_LOG_COLOR_PREFIX}{category}-"
        raw = values.get(key, "")
        color = _parse_hex_color(raw)
        if color is not None and color != snapshot.get(key):
            snapshot[key] = color
            log_colors[category] = color
            session.log_type_colors = log_colors
            _apply_log_color_live(session, category)

    border_colors = dict(getattr(session, "card_border_colors", None) or {})
    for key, _name, default in CARD_BORDER_TYPES:
        input_key = f"{_CARD_COLOR_PREFIX}{key}-"
        raw = values.get(input_key, "")
        color = _parse_hex_color(raw)
        if color is not None and color != snapshot.get(input_key):
            snapshot[input_key] = color
            border_colors[key] = color
            session.card_border_colors = border_colors
            _apply_border_color(session, key)
    session.settings_color_snapshot = snapshot


def _apply_sound_toggle(session, values) -> None:
    enabled = bool(values.get("-SOUND-ENABLED-", True))
    session.sound_enabled = enabled
    from card_duel.ui.app_settings import save_settings
    from card_duel.ui.network_log import append_log
    from card_duel.ui.sound import set_enabled

    set_enabled(enabled)
    save_settings(session)
    append_log(session, f"音效已{'开启' if enabled else '关闭'}")


def _apply_sound_settings(session, values) -> None:
    """Apply master sound switch and per-type sound toggles immediately."""
    from card_duel.ui.app_settings import save_settings
    from card_duel.ui.sound import set_enabled

    session.sound_enabled = bool(values.get("-SOUND-ENABLED-", True))
    current = set(
        getattr(
            session,
            "sound_effects",
            {"hit", "draw", "warn", "chat", "turn", "card", "click"},
        )
    )
    session.sound_effects = {
        name
        for name in _SOUND_LABELS
        if values.get(f"-SOUND-EFFECT-{name}-", name in current)
    }
    set_enabled(session.sound_enabled)
    save_settings(session)


def _apply_operation_settings(session, values) -> None:
    """Apply the single/double click play mode immediately."""
    from card_duel.ui.app_settings import save_settings

    session.single_click_play = bool(values.get("-OP-SINGLE-", False))
    save_settings(session)


def _apply_log_color_live(session, category: str) -> None:
    from card_duel.ui.app_settings import save_settings
    from card_duel.ui.network_log import rerender_log

    rerender_log(session)
    save_settings(session)
    _refresh_swatches(session)


def _apply_border_color(session, key: str) -> None:
    from card_duel.ui.app_settings import save_settings
    from card_duel.ui.network_log import append_log
    from card_duel.ui.network_view import refresh_cards, set_card_border_colors

    set_card_border_colors(session.card_border_colors)
    try:
        refresh_cards(
            session.state,
            session.require_window(),
            session.card_images,
        )
    except Exception:
        pass
    save_settings(session)
    _refresh_swatches(session)
    name = next((item[1] for item in CARD_BORDER_TYPES if item[0] == key), key)
    color = session.card_border_colors.get(key, "")
    append_log(session, f"卡牌边框颜色已更新（{name}）：{color}")


def _refresh_swatches(session) -> None:
    window = getattr(session, "settings_window", None)
    if window is None:
        return
    colors = getattr(session, "log_type_colors", None) or {}
    for category, _name, default in zip(
        LOG_CATEGORIES, LOG_TYPE_NAMES.values(), LOG_TYPE_COLORS.values()
    ):
        try:
            window[f"{_LOG_SWATCH_PREFIX}{category}-"].update(
                background_color=colors.get(category, default)
            )
        except Exception:
            continue
    borders = getattr(session, "card_border_colors", None) or {}
    for key, _name, default in CARD_BORDER_TYPES:
        try:
            window[f"{_CARD_SWATCH_PREFIX}{key}-"].update(
                background_color=borders.get(key, default)
            )
        except Exception:
            continue


def _parse_hex_color(text) -> str | None:
    cleaned = "".join((text or "").split()).upper()
    if len(cleaned) == 7 and cleaned.startswith("#"):
        try:
            int(cleaned[1:], 16)
            return cleaned
        except ValueError:
            return None
    return None


def close_settings(session) -> None:
    window = getattr(session, "settings_window", None)
    if window is None:
        return
    from card_duel.ui.app_settings import save_settings

    save_settings(session)
    session.settings_window = None
    try:
        window.close()
    except Exception:
        pass
