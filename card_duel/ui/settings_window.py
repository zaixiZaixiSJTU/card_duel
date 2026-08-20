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
_GO_LOGCOLOR_KEY = "-SETTINGS-GO-LOGCOLOR-"
_GO_CARDCOLOR_KEY = "-SETTINGS-GO-CARDCOLOR-"
_BACK_LOGCOLOR_KEY = "-SETTINGS-BACK-LOGCOLOR-"
_BACK_CARDCOLOR_KEY = "-SETTINGS-BACK-CARDCOLOR-"
_CLOSE_KEY = "-SETTINGS-CLOSE-"
_LOG_COLOR_PREFIX = "-LOGCOLOR-"
_CARD_COLOR_PREFIX = "-CARDCOLOR-"
_LOG_SWATCH_PREFIX = "-LOGCOLOR-SWATCH-"
_CARD_SWATCH_PREFIX = "-CARDCOLOR-SWATCH-"


def open_settings(session) -> None:
    """Open a fresh non-blocking settings window with switchable panels."""
    close_settings(session)

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
                "边框颜色暂未实现，仅占位",
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

    window = sg.Window(
        "设置",
        [
            [sg.pin(main)],
            [sg.pin(log_color_panel)],
            [sg.pin(card_color_panel)],
        ],
        finalize=True,
        keep_on_top=True,
        modal=False,
        background_color=COLOR_PAPER,
        margins=(12, 10),
        element_justification="left",
        size=(440, 330),
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
    elif event in (_BACK_LOGCOLOR_KEY, _BACK_CARDCOLOR_KEY):
        _switch_settings_panel(window, _MAIN_KEY)
    _apply_live_color_changes(session, values)


def _switch_settings_panel(window, target_key: str) -> None:
    try:
        for key in (_MAIN_KEY, _LOGCOLOR_KEY, _CARDCOLOR_KEY):
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
            _apply_border_color_placeholder(session, key, color)
    session.settings_color_snapshot = snapshot


def _apply_log_color_live(session, category: str) -> None:
    from card_duel.ui.app_settings import save_settings
    from card_duel.ui.network_log import rerender_log

    rerender_log(session)
    save_settings(session)
    _refresh_swatches(session)


def _apply_border_color_placeholder(session, key: str, color: str) -> None:
    from card_duel.ui.app_settings import save_settings
    from card_duel.ui.network_log import append_log

    save_settings(session)
    _refresh_swatches(session)
    name = next(
        (item[1] for item in CARD_BORDER_TYPES if item[0] == key), key
    )
    append_log(
        session,
        f"卡牌边框颜色（{name}）：未能实现，暂时只占位（{color}）",
    )


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
    session.settings_window = None
    try:
        window.close()
    except Exception:
        pass
