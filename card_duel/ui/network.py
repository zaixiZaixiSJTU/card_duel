"""Minimalist sketch-style interface for the network game."""

import base64
import io
import time

import FreeSimpleGUI as sg
from PIL import Image

from card_duel.core.combat import check_game_over, update_defence_totals

THEME = "SketchPaper"
WINDOW_SIZE = (1280, 800)
WINDOW_TITLE = "Card Duel · 手绘对战"

# Warm paper and muted marker colors shared by every network screen.
COLOR_BACKGROUND = "#F5F0E6"
COLOR_PAPER = "#FFFDF8"
COLOR_PAPER_DARK = "#EFE6D8"
COLOR_INK = "#2E2A26"
COLOR_MUTED = "#837A70"
COLOR_LINE = "#B9AEA0"
COLOR_RED = "#C86655"
COLOR_RED_LIGHT = "#E8C8BE"
COLOR_BLUE = "#6F89A8"
COLOR_GREEN = "#719775"
COLOR_GOLD = "#C39A55"
COLOR_DISABLED = "#D8D0C5"
COLOR_HIGHLIGHT = "#F2D98A"

FONT_TITLE = ("KaiTi", 24, "bold")
FONT_HEADING = ("KaiTi", 16, "bold")
FONT_BODY = ("Microsoft YaHei UI", 11)
FONT_BODY_BOLD = ("Microsoft YaHei UI", 11, "bold")
FONT_MONO = ("Consolas", 10)

MAX_HAND_BUTTONS = 18
HAND_COLS = 6  # 每行最多6张手牌
MAX_ENERGY_ORBS = 8
SLOT_THUMB_SIZE = (96, 138)

PHASE_LABELS = (
    "回合开始时",
    "抽牌阶段",
    "出牌阶段",
    "弃牌阶段",
    "回合结束时",
)

# Light tints used to mark the current phase across the background band.
PHASE_TINTS = {
    "回合开始时": "#E6EEF5",
    "抽牌阶段": "#E8F0E6",
    "出牌阶段": "#F5EDE0",
    "弃牌阶段": "#F5E8D8",
    "回合结束时": "#EDE6F0",
}
DEFAULT_TINT = "#ECEAE6"

CHAT_INPUT_KEY = "-CHAT-INPUT-"
CHAT_SEND_KEY = "-CHAT-SEND-"
MODE_HINT_KEY = "-MODE-HINT-"
PHASE_BAND_KEY = "-PHASE-BAND-"
REFRESH_HAND_KEY = "-REFRESH-HAND-"


def init_theme():
    """Register the paper palette once, then activate it."""
    if THEME not in sg.theme_list():
        sg.theme_add_new(
            THEME,
            {
                "BACKGROUND": COLOR_BACKGROUND,
                "TEXT": COLOR_INK,
                "INPUT": COLOR_PAPER,
                "TEXT_INPUT": COLOR_INK,
                "SCROLL": COLOR_PAPER_DARK,
                "BUTTON": (COLOR_INK, COLOR_PAPER),
                "PROGRESS": (COLOR_RED, COLOR_RED_LIGHT),
                "BORDER": 1,
                "SLIDER_DEPTH": 0,
                "PROGRESS_DEPTH": 0,
            },
        )
    sg.theme(THEME)


# ============================================================
# Layout
# ============================================================
def _hp_max_for(character_id):
    """Pick a progress-bar ceiling so the bar is meaningful per character."""
    if character_id == 4:
        return 5
    return 45


def _build_player_panel(player_id, character_name, is_local, hp_max):
    """One compact player panel: played-card slot + status with a big HP bar."""
    slot_key = f"-P{player_id}-PLAYED-"
    hp_key = f"-P{player_id}-HP-"
    energy_key = f"-P{player_id}-EN-"
    defence_key = f"-P{player_id}-DEF-"
    defence_label_key = f"-P{player_id}-DEF-LABEL-"
    strength_key = f"-P{player_id}-STR-"
    strength_label_key = f"-P{player_id}-STR-LABEL-"
    orb_key = f"-P{player_id}-ORB-"
    hp_bar_key = f"-P{player_id}-HP-BAR-"
    special_key = f"-P{player_id}-SPECIAL-"
    tag_key = f"-P{player_id}-TAG-"

    accent = COLOR_GREEN if is_local else COLOR_RED
    tag_text = "我方" if is_local else "对手"

    status_block = [
        [
            sg.Text(
                character_name,
                font=FONT_HEADING,
                text_color=accent,
                background_color=COLOR_PAPER,
                size=(8, 1),
            ),
            sg.Text(
                tag_text,
                key=tag_key,
                font=FONT_BODY_BOLD,
                text_color=COLOR_PAPER,
                background_color=accent,
                size=(4, 1),
                justification="center",
            ),
        ],
        [
            sg.Text(
                "HP",
                font=FONT_BODY_BOLD,
                text_color=COLOR_RED,
                background_color=COLOR_PAPER,
            ),
            sg.Text(
                "0",
                key=hp_key,
                font=FONT_TITLE,
                text_color=COLOR_INK,
                background_color=COLOR_PAPER,
                size=(4, 1),
            ),
        ],
        [
            sg.ProgressBar(
                hp_max,
                orientation="h",
                size=(30, 16),
                key=hp_bar_key,
                bar_color=(COLOR_RED, COLOR_RED_LIGHT),
                relief=sg.RELIEF_FLAT,
            )
        ],
        [sg.HorizontalSeparator(color=COLOR_LINE)],
        [
            sg.Text(
                "能量",
                font=FONT_BODY,
                text_color=COLOR_BLUE,
                background_color=COLOR_PAPER,
            ),
            sg.Text(
                "○○○○○○○○",
                key=orb_key,
                font=("Segoe UI Symbol", 13),
                text_color=COLOR_BLUE,
                background_color=COLOR_PAPER,
                size=(9, 1),
            ),
            sg.Text(
                "",
                key=energy_key,
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
                background_color=COLOR_PAPER,
                size=(4, 1),
            ),
        ],
        [
            sg.Text(
                "防御",
                key=defence_label_key,
                font=FONT_BODY,
                text_color=COLOR_MUTED,
                background_color=COLOR_PAPER,
            ),
            sg.Text(
                "0",
                key=defence_key,
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
                background_color=COLOR_PAPER,
                size=(4, 1),
            ),
            sg.Text(
                "力量",
                key=strength_label_key,
                font=FONT_BODY,
                text_color=COLOR_GOLD,
                background_color=COLOR_PAPER,
            ),
            sg.Text(
                "0",
                key=strength_key,
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
                background_color=COLOR_PAPER,
                size=(4, 1),
            ),
        ],
        [
            sg.Text(
                "",
                key=special_key,
                font=("Microsoft YaHei UI", 9),
                text_color=COLOR_MUTED,
                background_color=COLOR_PAPER,
                size=(32, 1),
            )
        ],
    ]

    layout = [
        [
            sg.Column(
                [
                    [
                        sg.Text(
                            "出牌",
                            font=("Microsoft YaHei UI", 8),
                            text_color=COLOR_MUTED,
                            background_color=COLOR_PAPER,
                            justification="center",
                            size=(8, 1),
                        )
                    ],
                    [
                        sg.Image(
                            key=slot_key,
                            size=SLOT_THUMB_SIZE,
                            background_color=COLOR_PAPER_DARK,
                        )
                    ],
                ],
                background_color=COLOR_PAPER,
                element_justification="c",
                pad=(2, 2),
            ),
            sg.Column(
                status_block,
                background_color=COLOR_PAPER,
                pad=(6, 2),
            ),
        ]
    ]
    return sg.Frame(
        "",
        layout,
        background_color=COLOR_PAPER,
        border_width=1,
        relief=sg.RELIEF_SOLID,
        pad=(4, 4),
        element_justification="left",
    )


def _build_card_grid(card_images, hand_cards):
    """Build the hand-card grid WITHOUT binding events.

    每行最多 HAND_COLS(6) 张，超过换行，整体竖向滚动。
    All event binding happens in ``bind_hand_card_events`` AFTER the
    window is finalized, because PySimpleGUI refuses to operate on
    elements whose underlying Tk widget has not been created yet.
    """
    rows = []
    current_row = []
    for button_index in range(MAX_HAND_BUTTONS):
        card_id = (
            hand_cards[button_index]
            if button_index < len(hand_cards)
            else 0
        )
        image_data = None
        if card_images:
            safe_card_id = card_id if 0 <= card_id < len(card_images) else 0
            image_data = card_images[safe_card_id]
        button = sg.Button(
            image_data=image_data,
            key=f"-BTN{button_index}-",
            pad=(6, 5),
            button_color=(COLOR_PAPER, COLOR_PAPER),
            border_width=1,
        )
        current_row.append(button)
        if len(current_row) >= HAND_COLS:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    return sg.Column(
        rows,
        scrollable=True,
        size=(WINDOW_SIZE[0] - 70, 260),
        vertical_scroll_only=True,
        background_color=COLOR_PAPER,
        expand_x=True,
        key="-CARD-COL-",
    )


def bind_hand_card_events(game_state):
    """Attach right-click bindings to every hand button.

    Must be called AFTER ``Window(finalize=True)`` so the Tk widgets exist.
    """
    for button_index in range(MAX_HAND_BUTTONS):
        key = f"-BTN{button_index}-"
        if key in game_state.window.AllKeysDict:
            game_state.window[key].bind("<Button-3>", " RIGHT")


def _parse_hand_event(event):
    """Return (hand_index, is_right_click) for a hand-button event, or None."""
    if not isinstance(event, str) or not event.startswith("-BTN"):
        return None
    is_right = event.endswith(" RIGHT")
    core = event.removesuffix(" RIGHT") if is_right else event
    if not core.startswith("-BTN") or not core.endswith("-"):
        return None
    index_str = core.removeprefix("-BTN").removesuffix("-")
    if not index_str.isdigit():
        return None
    return int(index_str), is_right


def create_main_layout(card_images, hand_cards, local_player_id=1, character_ids=None):
    """Build a compact top-to-bottom workspace for network play."""
    from card_duel.core.characters import CHARACTER_NAMES

    character_ids = character_ids or {1: 1, 2: 1}

    title_row = [
        sg.Text(
            "CARD DUEL",
            font=FONT_TITLE,
            text_color=COLOR_INK,
            background_color=COLOR_BACKGROUND,
            pad=(8, 4),
        ),
        sg.Text(
            "联机对战手记",
            font=FONT_BODY,
            text_color=COLOR_MUTED,
            background_color=COLOR_BACKGROUND,
            pad=(4, 7),
        ),
        sg.Text("", background_color=COLOR_BACKGROUND, expand_x=True),
        sg.Text(
            "等待开始",
            key="-PHASE-",
            font=FONT_BODY_BOLD,
            text_color=COLOR_INK,
            background_color=COLOR_PAPER_DARK,
            justification="center",
            size=(28, 1),
            pad=(8, 7),
        ),
    ]

    phase_band = sg.Text(
        " ",
        key=PHASE_BAND_KEY,
        background_color=DEFAULT_TINT,
        size=(WINDOW_SIZE[0] // 8, 1),
        expand_x=True,
    )

    phase_tracker = sg.Frame(
        "",
        [
            [
                sg.Text(
                    f"{phase_index + 1:02d}  {phase_label}",
                    key=f"-PHASE-STEP-{phase_index}-",
                    font=FONT_BODY_BOLD,
                    text_color=COLOR_MUTED,
                    background_color=COLOR_PAPER,
                    justification="center",
                    size=(17, 1),
                    pad=(4, 6),
                )
                for phase_index, phase_label in enumerate(PHASE_LABELS)
            ]
        ],
        background_color=COLOR_PAPER,
        border_width=1,
        relief=sg.RELIEF_SOLID,
        expand_x=True,
        element_justification="center",
    )

    panels = []
    for player_id in (1, 2):
        character_id = character_ids.get(player_id) or 1
        character_name = CHARACTER_NAMES.get(character_id, "?")
        is_local = player_id == local_player_id
        panels.append(
            _build_player_panel(
                player_id,
                character_name,
                is_local,
                _hp_max_for(character_id),
            )
        )

    log_panel = sg.Frame(
        " 战斗记录 / NOTES ",
        [
            [
                sg.Multiline(
                    size=(55, 9),
                    key="-OUTPUT-",
                    autoscroll=True,
                    disabled=True,
                    font=FONT_MONO,
                    background_color=COLOR_PAPER,
                    text_color=COLOR_INK,
                    expand_x=True,
                )
            ],
            [
                sg.Input(
                    key=CHAT_INPUT_KEY,
                    font=FONT_BODY,
                    background_color=COLOR_PAPER,
                    text_color=COLOR_INK,
                    border_width=1,
                    expand_x=True,
                    tooltip="输入消息，按回车或点击发送",
                ),
                sg.Button(
                    "发送  ↗",
                    key=CHAT_SEND_KEY,
                    bind_return_key=True,
                    font=FONT_BODY_BOLD,
                    button_color=(COLOR_INK, COLOR_PAPER_DARK),
                    border_width=1,
                ),
            ],
        ],
        font=FONT_BODY_BOLD,
        title_color=COLOR_INK,
        background_color=COLOR_PAPER,
        relief=sg.RELIEF_SOLID,
        border_width=1,
        expand_x=True,
    )

    mode_hint = sg.Text(
        "等待开始",
        key=MODE_HINT_KEY,
        font=FONT_BODY_BOLD,
        text_color=COLOR_INK,
        background_color=COLOR_PAPER_DARK,
        justification="center",
        expand_x=True,
        size=(WINDOW_SIZE[0] // 8, 1),
        pad=(4, 4),
    )

    card_panel = sg.Frame(
        " 手牌 / HAND ",
        [
            [
                sg.Text(
                    "牌堆",
                    font=FONT_BODY,
                    text_color=COLOR_MUTED,
                    background_color=COLOR_PAPER,
                ),
                sg.Text(
                    "0",
                    key="-DECK-COUNT-",
                    font=FONT_BODY_BOLD,
                    text_color=COLOR_GOLD,
                    background_color=COLOR_PAPER,
                    size=(4, 1),
                ),
                sg.Text(
                    "手牌",
                    font=FONT_BODY,
                    text_color=COLOR_MUTED,
                    background_color=COLOR_PAPER,
                ),
                sg.Text(
                    "0",
                    key="-HAND-COUNT-",
                    font=FONT_BODY_BOLD,
                    text_color=COLOR_GREEN,
                    background_color=COLOR_PAPER,
                    size=(4, 1),
                ),
                sg.Text("", background_color=COLOR_PAPER, expand_x=True),
                sg.Button(
                    "刷新手牌  ↻",
                    size=(12, 1),
                    key=REFRESH_HAND_KEY,
                    font=FONT_BODY_BOLD,
                    button_color=(COLOR_INK, COLOR_PAPER_DARK),
                ),
                sg.Button(
                    "查看牌堆  📂",
                    size=(14, 1),
                    key="-DECK-VIEW-",
                    font=FONT_BODY_BOLD,
                    button_color=(COLOR_INK, COLOR_PAPER_DARK),
                ),
                sg.Button(
                    "完成当前阶段  →",
                    size=(16, 1),
                    key="-btn1-",
                    disabled=True,
                    font=FONT_BODY_BOLD,
                    button_color=(COLOR_MUTED, COLOR_DISABLED),
                ),
            ],
            [_build_card_grid(card_images, hand_cards)],
        ],
        font=FONT_BODY_BOLD,
        title_color=COLOR_INK,
        background_color=COLOR_PAPER,
        relief=sg.RELIEF_SOLID,
        border_width=1,
        expand_x=True,
    )

    players_row = sg.Column(
        [[panels[0], panels[1]]],
        background_color=COLOR_BACKGROUND,
        element_justification="c",
        justification="c",
        expand_x=True,
        pad=(2, 2),
    )

    content = [
        title_row,
        [phase_band],
        [phase_tracker],
        [players_row],
        [log_panel],
        [mode_hint],
        [card_panel],
    ]
    return [
        [
            sg.Column(
                content,
                background_color=COLOR_BACKGROUND,
                expand_x=True,
                expand_y=True,
                pad=(10, 6),
                key="-ROOT-COL-",
            )
        ]
    ]


def character_select_dialog():
    """Use three outlined marker-color buttons as simple character cards."""
    layout = [
        [
            sg.Text(
                "选择角色",
                font=FONT_TITLE,
                text_color=COLOR_INK,
                background_color=COLOR_BACKGROUND,
                justification="center",
                expand_x=True,
            )
        ],
        [
            sg.Text(
                "挑一个顺眼的，然后开始。",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
                background_color=COLOR_BACKGROUND,
                justification="center",
                expand_x=True,
            )
        ],
        [
            sg.Button(
                "01\n战 士",
                font=FONT_HEADING,
                button_color=(COLOR_INK, "#E8C8BE"),
                size=(12, 3),
                key="1",
                pad=(7, 12),
            ),
            sg.Button(
                "02\n女 猎 手",
                font=FONT_HEADING,
                button_color=(COLOR_INK, "#D6E2D4"),
                size=(12, 3),
                key="2",
                pad=(7, 12),
            ),
            sg.Button(
                "03\n时间守护者",
                font=FONT_HEADING,
                button_color=(COLOR_INK, "#DDD5E8"),
                size=(12, 3),
                key="3",
                pad=(7, 12),
            ),
            sg.Button(
                "04\n蛞 蝓 猫",
                font=FONT_HEADING,
                button_color=(COLOR_INK, "#E8DFC3"),
                size=(12, 3),
                key="4",
                pad=(7, 12),
            ),
        ],
    ]
    character, _ = sg.Window(
        "角色选择",
        layout,
        keep_on_top=True,
        no_titlebar=True,
        background_color=COLOR_BACKGROUND,
        element_justification="center",
        margins=(22, 20),
    ).read(close=True)
    return character


def waiting_dialog(text="等待对方..."):
    waiting_window = sg.Window(
        "等待",
        [
            [sg.Text("···", font=FONT_TITLE, text_color=COLOR_BLUE)],
            [sg.Text(text, font=FONT_BODY_BOLD, text_color=COLOR_INK)],
        ],
        size=(250, 110),
        keep_on_top=True,
        element_justification="center",
        background_color=COLOR_BACKGROUND,
    )
    waiting_window.read(timeout=100)
    return waiting_window


# ============================================================
# Safe UI helpers (prevent cascading Element-not-created errors)
# ============================================================

def _safe_update(element, *args, **kwargs):
    """Wrap Element.update() so a missing-key error is swallowed silently.

    PySimpleGUI throws ``ElementNotCreatedError`` when an element's Tk
    widget hasn't been realized yet (e.g. during early window construction
    or after a non-main-thread update).  We catch those and log a one-off
    warning instead of letting the whole turn crash.
    """
    try:
        element.update(*args, **kwargs)
    except Exception:
        pass


def _window_key(window, key):
    """Return the Element for ``key`` if it exists in the window."""
    if window is None:
        return None
    if key not in window.AllKeysDict:
        return None
    return window[key]


def _safe_set_text(window, key, text, text_color=None, background_color=None):
    """Safely update a Text element by key."""
    element = _window_key(window, key)
    if element is None:
        return
    kwargs = {}
    if text_color is not None:
        kwargs["text_color"] = text_color
    if background_color is not None:
        kwargs["background_color"] = background_color
    _safe_update(element, text, **kwargs)


def _safe_set_data(window, key, data, background_color=None):
    """Safely update an Image/Button element's image data."""
    element = _window_key(window, key)
    if element is None:
        return
    kwargs = {"data": data}
    if background_color is not None:
        kwargs["background_color"] = background_color
    _safe_update(element, **kwargs)


def _safe_set_button(window, key, text=None, disabled=None, button_color=None):
    """Safely update a Button element."""
    element = _window_key(window, key)
    if element is None:
        return
    kwargs = {}
    if text is not None:
        kwargs["text"] = text
    if disabled is not None:
        kwargs["disabled"] = disabled
    if button_color is not None:
        kwargs["button_color"] = button_color
    _safe_update(element, **kwargs)


# ============================================================
# Colored combat-log announcements
# ============================================================
def _classify_announce_color(message):
    """Pick a display color for an announcement based on its content."""
    if not message:
        return COLOR_INK
    stripped = message.strip()
    # Chat messages
    if stripped.startswith("[我]"):
        return COLOR_BLUE
    if stripped.startswith("[对方]"):
        return COLOR_MUTED
    # Pure separator lines (only dashes and spaces)
    if "-" in stripped and all(c in "- " for c in stripped):
        return COLOR_MUTED
    # Round markers like "-------------------- ROUND N --------------------"
    if "ROUND" in message:
        return COLOR_GOLD
    # Damage / life loss
    if any(kw in message for kw in (
        "失去", "伤害", "引爆", "炸矛", "心连心", "业力归零",
    )):
        return COLOR_RED
    # Insertions / removals of spears and rods
    if any(kw in message for kw in ("插入", "拔出")):
        return COLOR_RED
    # Warnings / blockers
    if any(kw in message for kw in (
        "无法", "不足", "不能", "不可", "请打出",
    )):
        return COLOR_GOLD
    # Card draw
    if "抽牌" in message:
        return COLOR_GREEN
    # Buffs / positive gains
    if any(kw in message for kw in (
        "获得", "重返雨中", "切换为", "吃下", "释放烟雾", "安稳睡下",
    )):
        return COLOR_GREEN
    # Turn / phase markers
    if any(kw in message for kw in (
        "轮到玩家", "回合结束", "弃牌阶段", "先出牌", "选择了",
    )):
        return COLOR_BLUE
    return COLOR_INK


def colored_announce(game_state, message):
    """Insert a message into the combat log with a type-based color.

    Falls back to ``print`` when the window has not been created yet
    (e.g. during connection setup), so pre-game messages still show up
    on the console.
    """
    window = getattr(game_state, "window", None)
    element = _window_key(window, "-OUTPUT-")
    if element is None:
        print(message)
        return
    color = _classify_announce_color(message)
    text_widget = element.Widget
    text_widget.configure(state="normal")
    text_widget.tag_configure(color, foreground=color)
    text_widget.insert("end", message + "\n", (color,))
    text_widget.configure(state="disabled")
    text_widget.see("end")


# ============================================================
# Refresh helpers
# ============================================================
def refresh_status(game_state):
    """Refresh the two status cards without changing game state."""
    check_game_over(game_state)
    update_defence_totals(game_state)

    local_player = game_state.players[game_state.local_player_id]
    opponent_player = game_state.players[game_state.opponent_player_id]
    _update_player_status(
        game_state.window,
        game_state.local_player_id,
        local_player,
        _format_special_status(game_state, game_state.local_player_id),
    )
    _update_player_status(
        game_state.window,
        game_state.opponent_player_id,
        opponent_player,
        _format_special_status(game_state, game_state.opponent_player_id),
    )

    _flash_changed_values(game_state, game_state.local_player_id, local_player)
    _flash_changed_values(
        game_state, game_state.opponent_player_id, opponent_player
    )

    game_state.window["-DECK-COUNT-"].update(str(len(game_state.draw_pile)))
    # 管虫在场时显示“有效手牌/总手牌”格式
    from card_duel.cards.slugcat import get_displayed_hand_count
    effective, total = get_displayed_hand_count(game_state)
    if effective != total:
        game_state.window["-HAND-COUNT-"].update(f"{effective}/{total}")
    else:
        game_state.window["-HAND-COUNT-"].update(str(total))
    game_state.window.refresh()


def _update_player_status(window, player_id, player, special_status=""):
    prefix = f"-P{player_id}-"
    _safe_set_text(
        window,
        f"{prefix}HP-",
        str(player.health),
        text_color=COLOR_RED if player.health <= 10 else COLOR_INK,
    )
    _safe_set_text(window, f"{prefix}EN-", str(player.energy))
    # Slugcat shows 敏捷/动能 instead of 防御/力量 in the same slots
    is_slugcat = "agility" in player.special
    if is_slugcat:
        _safe_set_text(window, f"{prefix}DEF-LABEL-", "敏捷")
        _safe_set_text(window, f"{prefix}STR-LABEL-", "动能")
        _safe_set_text(window, f"{prefix}DEF-", str(player.special.get("agility", 0)))
        _safe_set_text(window, f"{prefix}STR-", str(player.special.get("momentum", 0)))
    else:
        _safe_set_text(window, f"{prefix}DEF-LABEL-", "防御")
        _safe_set_text(window, f"{prefix}STR-LABEL-", "力量")
        _safe_set_text(window, f"{prefix}DEF-", str(player.defence))
        _safe_set_text(window, f"{prefix}STR-", str(player.strength))
    bar = _window_key(window, f"{prefix}HP-BAR-")
    if bar is not None:
        _safe_update(bar, max(0, player.health))
    _safe_set_text(
        window, f"{prefix}ORB-", _format_energy_orbs(player.energy)
    )
    _safe_set_text(window, f"{prefix}SPECIAL-", special_status)


def _player_value_snapshot(player):
    """Capture the numeric values that should trigger a flash when changed."""
    snapshot = {
        "hp": player.health,
        "energy": player.energy,
        "defence": player.defence,
        "strength": player.strength,
    }
    for key in ("karma", "agility", "momentum", "satiety"):
        if key in player.special:
            snapshot[key] = player.special[key]
    return snapshot


def _flash_changed_values(game_state, player_id, player):
    """Compare current values with the previous snapshot and flash deltas."""
    prefix = f"-P{player_id}-"
    window = game_state.window
    prev = game_state._prev_values.get(player_id, {})
    current = _player_value_snapshot(player)

    is_slugcat = "agility" in player.special
    if is_slugcat:
        field_keys = {
            "hp": f"{prefix}HP-",
            "energy": f"{prefix}EN-",
            "agility": f"{prefix}DEF-",
            "momentum": f"{prefix}STR-",
        }
    else:
        field_keys = {
            "hp": f"{prefix}HP-",
            "energy": f"{prefix}EN-",
            "defence": f"{prefix}DEF-",
            "strength": f"{prefix}STR-",
        }
    for field, key in field_keys.items():
        old_value = prev.get(field)
        new_value = current.get(field)
        if old_value is not None and new_value != old_value:
            color = COLOR_GREEN if new_value > old_value else COLOR_RED
            _flash_text(window, key, color)

    # Only flash SPECIAL- for values shown in that text (业力/饱食 for slugcat).
    # 敏捷/动能 are flashed individually in their own DEF-/STR- slots above.
    if is_slugcat:
        special_keys = ("karma", "satiety")
    else:
        special_keys = ("karma", "agility", "momentum", "satiety")
    special_changed = False
    special_delta = 0
    for key in special_keys:
        if key in current:
            old = prev.get(key)
            if old is not None and old != current[key]:
                special_changed = True
                special_delta += current[key] - old
    if special_changed:
        color = COLOR_GREEN if special_delta > 0 else COLOR_RED
        _flash_text(window, f"{prefix}SPECIAL-", color)

    game_state._prev_values[player_id] = current


def _flash_text(window, key, flash_color, cycles=3):
    """Pulse a Text element's background between ink-paper and the flash color."""
    if key not in window.AllKeysDict:
        return
    base_color = COLOR_PAPER
    try:
        for _ in range(cycles):
            window[key].update(background_color=flash_color)
            window.refresh()
            time.sleep(0.07)
            window[key].update(background_color=base_color)
            window.refresh()
            time.sleep(0.07)
    except Exception:
        pass


def _format_special_status(game_state, player_id):
    if game_state.character_ids.get(player_id) != 4:
        return ""
    from card_duel.cards.slugcat import format_slugcat_status

    return format_slugcat_status(game_state.players[player_id])


def refresh_cards(game_state):
    """Compact removed cards, then redraw every visible hand slot."""
    game_state.hand_cards = [
        card_id for card_id in game_state.hand_cards if card_id != -1
    ]
    if len(game_state.hand_cards) < 999:
        game_state.hand_cards.extend([0] * (999 - len(game_state.hand_cards)))

    # 判断类型直接用 ID 判断：49/50 是插入物（红色边框），16-26 是生物（金色边框）
    from card_duel.cards.slugcat_data import SLUGCAT_CREATURE_IDS, SLUGCAT_INSERTED_IDS, SLUGCAT_SPECS_BY_ID, SLUGCAT_DISCOVERY_IDS
    from card_duel.core.combat import render_creature_card_with_hp, render_card_with_effective_cost
    from card_duel.cards.slugcat import _effective_cost

    # 获取本地玩家生物血量（用于动态渲染卡面）
    local_player = game_state.players[game_state.local_player_id]
    creature_health = local_player.special.get("creature_health", {})

    hand_index = 0
    while (
        hand_index < MAX_HAND_BUTTONS
        and game_state.hand_cards[hand_index] != 0
    ):
        card_id = game_state.hand_cards[hand_index]
        safe_card_id = card_id if 0 <= card_id < len(game_state.card_images) else 0
        element = _window_key(game_state.window, f"-BTN{hand_index}-")
        if element is not None:
            is_inserted = card_id in SLUGCAT_INSERTED_IDS
            is_creature = card_id in SLUGCAT_CREATURE_IDS
            if is_inserted:
                border_color = COLOR_RED
            elif is_creature:
                border_color = COLOR_GOLD
            else:
                border_color = COLOR_PAPER
            # 生物牌：动态生成带血量的卡图
            if is_creature and card_id in SLUGCAT_SPECS_BY_ID:
                hp_list = creature_health.get(card_id, [])
                # 找到当前手牌中第几张同名生物（对应血量列表中的位置）
                same_count_before = sum(
                    1 for i in range(hand_index)
                    if game_state.hand_cards[i] == card_id
                )
                current_hp = hp_list[same_count_before] if same_count_before < len(hp_list) else 0
                image_data = render_creature_card_with_hp(
                    SLUGCAT_SPECS_BY_ID[card_id], current_hp
                )
            # 见闻牌：动态生成带实际耗能的卡面（折扣后数字显示绿色）
            elif card_id in SLUGCAT_DISCOVERY_IDS and card_id in SLUGCAT_SPECS_BY_ID:
                spec = SLUGCAT_SPECS_BY_ID[card_id]
                eff_cost = _effective_cost(
                    game_state, game_state.local_player_id, card_id
                )
                if eff_cost != spec.cost:
                    image_data = render_card_with_effective_cost(spec, eff_cost)
                else:
                    image_data = game_state.card_images[safe_card_id]
            else:
                image_data = game_state.card_images[safe_card_id]
            # NOTE: Button.update() does not support border_width at runtime,
            # so the image/visibility go through update() while the thick
            # colored border is applied directly on the Tk widget below.
            _safe_update(
                element,
                image_data=image_data,
                visible=True,
                button_color=(COLOR_PAPER, border_color),
            )
            _apply_hand_card_border(element, border_color, is_inserted or is_creature)
        hand_index += 1

    game_state.hand_size = hand_index
    for button_index in range(hand_index, MAX_HAND_BUTTONS):
        element = _window_key(game_state.window, f"-BTN{button_index}-")
        if element is not None:
            _safe_update(element, visible=False)
            _apply_hand_card_border(element, COLOR_PAPER, False)


def _apply_hand_card_border(element, color, emphasized):
    """Set a thick solid border on a hand-card button via its Tk widget.

    PySimpleGUI's ``Button.update()`` does not accept ``border_width``, so
    the border is configured directly on the underlying ``tk.Button``:
    ``relief='solid'`` + ``borderwidth`` draws a solid border in the
    button's background color (set via ``button_color``).

    Emphasized cards (inserted spears/rods, creatures) get a 7px border in
    their accent color; normal cards fall back to a 1px paper border.
    """
    try:
        widget = element.Widget
        if emphasized:
            widget.configure(borderwidth=7, relief="solid")
        else:
            widget.configure(borderwidth=1, relief="flat")
    except Exception:
        pass


def set_phase(game_state, phase_text):
    _safe_set_text(game_state.window, "-PHASE-", phase_text)
    tint = DEFAULT_TINT
    active_phase_index = None
    for phase_index, phase_label in enumerate(PHASE_LABELS):
        if phase_label in phase_text:
            tint = PHASE_TINTS[phase_label]
            active_phase_index = phase_index
            break
    _safe_set_text(
        game_state.window, PHASE_BAND_KEY, " ", background_color=tint
    )
    if MODE_HINT_KEY in game_state.window.AllKeysDict:
        _safe_set_text(
            game_state.window, MODE_HINT_KEY, " ", background_color=tint
        )
    for phase_index in range(len(PHASE_LABELS)):
        is_active = phase_index == active_phase_index
        _safe_set_text(
            game_state.window,
            f"-PHASE-STEP-{phase_index}-",
            f"{phase_index + 1:02d}  {PHASE_LABELS[phase_index]}",
            text_color=COLOR_PAPER if is_active else COLOR_MUTED,
            background_color=COLOR_BLUE if is_active else COLOR_PAPER,
        )
    game_state.window.refresh()


def set_cards_enabled(game_state, enabled):
    element = _window_key(game_state.window, "-btn1-")
    if element is not None:
        _safe_update(
            element,
            disabled=not enabled,
            button_color=(
                (COLOR_PAPER, COLOR_GREEN)
                if enabled
                else (COLOR_MUTED, COLOR_DISABLED)
            ),
        )
    hint = "挑一张牌，慢慢想。" if enabled else "等对手落笔……"
    set_mode_hint(
        game_state,
        hint,
        COLOR_GREEN if enabled else COLOR_MUTED,
    )


def set_mode_hint(game_state, text, color=None):
    _safe_set_text(
        game_state.window,
        MODE_HINT_KEY,
        text,
        text_color=color or COLOR_INK,
    )
    game_state.window.refresh()


def _format_energy_orbs(value):
    filled = max(0, min(value, MAX_ENERGY_ORBS))
    return "●" * filled + "○" * (MAX_ENERGY_ORBS - filled)


# ============================================================
# Played-card slot + animations
# ============================================================
def _thumbnail(image_b64, size=SLOT_THUMB_SIZE):
    if not image_b64:
        return None
    raw = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(raw))
    img.thumbnail(size, Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


def _slot_thumbnail(game_state, player_id, card_id):
    if player_id == game_state.local_player_id:
        images = game_state.card_images
        cache_attr = "_local_slot_thumbs"
    else:
        images = getattr(game_state, "peer_card_images", None) or []
        cache_attr = "_peer_slot_thumbs"
    cache = getattr(game_state, cache_attr, None)
    if cache is None:
        cache = {}
        setattr(game_state, cache_attr, cache)
    if card_id in cache:
        return cache[card_id]
    if images and 0 <= card_id < len(images):
        cache[card_id] = _thumbnail(images[card_id])
    else:
        cache[card_id] = None
    return cache[card_id]


def show_played_card(game_state, player_id, card_id):
    """Update one player's played-card slot and flash it as it changes."""
    slot_key = f"-P{player_id}-PLAYED-"
    thumb = _slot_thumbnail(game_state, player_id, card_id)
    _safe_set_data(
        game_state.window, slot_key, thumb, background_color=COLOR_PAPER
    )
    game_state.window.refresh()
    _flash_element(game_state.window, slot_key, COLOR_GOLD, COLOR_PAPER)


def _flash_element(window, key, flash_color, base_color, cycles=3):
    """Pulse an element's background a few times for a transition cue."""
    if key not in window.AllKeysDict:
        return
    try:
        for _ in range(cycles):
            window[key].update(background_color=flash_color)
            window.refresh()
            time.sleep(0.07)
            window[key].update(background_color=base_color)
            window.refresh()
            time.sleep(0.07)
    except Exception:
        pass


def flash_hand_card(game_state, hand_index, color=COLOR_HIGHLIGHT):
    """Briefly highlight one hand button to confirm a selection."""
    key = f"-BTN{hand_index}-"
    if key not in game_state.window.AllKeysDict:
        return
    try:
        for _ in range(2):
            game_state.window[key].update(button_color=(COLOR_INK, color))
            game_state.window.refresh()
            time.sleep(0.08)
            game_state.window[key].update(
                button_color=(COLOR_PAPER, COLOR_PAPER)
            )
            game_state.window.refresh()
            time.sleep(0.08)
    except Exception:
        pass


def mark_hand_card_selected(game_state, hand_index, selected):
    """Keep a hand button visually marked while in a selection mode."""
    key = f"-BTN{hand_index}-"
    if key not in game_state.window.AllKeysDict:
        return
    _safe_update(
        game_state.window[key],
        button_color=(
            (COLOR_INK, COLOR_HIGHLIGHT)
            if selected
            else (COLOR_PAPER, COLOR_PAPER)
        ),
    )
    game_state.window.refresh()


def _set_hand_button_armed(game_state, hand_index, armed):
    key = f"-BTN{hand_index}-"
    if key not in game_state.window.AllKeysDict:
        return
    _safe_update(
        game_state.window[key],
        button_color=(
            (COLOR_INK, COLOR_GOLD)
            if armed
            else (COLOR_PAPER, COLOR_PAPER)
        ),
    )
    game_state.window.refresh()


# ============================================================
# Unified card-click router (left-click arm / right-click preview)
# ============================================================
def arm_card(game_state, hand_index):
    """First left-click: flash the card and mark it as pending a second click."""
    game_state.pending_arm_index = hand_index
    flash_hand_card(game_state, hand_index, COLOR_GOLD)
    _set_hand_button_armed(game_state, hand_index, True)


def disarm_card(game_state):
    """Clear the pending left-click arm and restore the button's normal look."""
    if game_state.pending_arm_index is None:
        return
    idx = game_state.pending_arm_index
    game_state.pending_arm_index = None
    _set_hand_button_armed(game_state, idx, False)


def route_card_event(game_state, event):
    """Route a hand-card event through the unified click model.

    Returns one of: "selected", "armed", "disarmed", "preview_closed", None.
    - "selected": a card was confirmed (callback ran and returned truthy).
    - "armed": first left-click armed a card, waiting for second click.
    - "disarmed": a non-card click cleared the pending arm.
    - "preview_closed": right-click preview was closed without selecting.
    - None: event was not a hand-card click.
    """
    parsed = _parse_hand_event(event)
    if parsed is None:
        # A pure timeout must not reset a pending left-click arm; only an
        # actual click somewhere else (a real event) should disarm it.
        if event in (sg.TIMEOUT_KEY, sg.WIN_CLOSED, None):
            return None
        if game_state.pending_arm_index is not None:
            disarm_card(game_state)
            return "disarmed"
        return None

    hand_index, is_right = parsed
    card_id = game_state.hand_cards[hand_index] if hand_index < len(game_state.hand_cards) else 0
    if card_id in (0, -1):
        return None

    if is_right:
        # Right-click: open preview; clicking the card inside = confirm.
        confirmed = preview_card_popup(game_state, hand_index)
        if confirmed:
            disarm_card(game_state)
            return _confirm_selection(game_state, hand_index)
        return "preview_closed"

    # Left-click.
    if game_state.pending_arm_index is None:
        arm_card(game_state, hand_index)
        return "armed"
    if game_state.pending_arm_index == hand_index:
        disarm_card(game_state)
        return _confirm_selection(game_state, hand_index)
    # Switch the arm to a different card.
    disarm_card(game_state)
    arm_card(game_state, hand_index)
    return "armed"


def _confirm_selection(game_state, hand_index):
    """Invoke the active selection callback; flash even when none is set."""
    callback = game_state.card_selection_callback
    if callback is None:
        # Idle / opponent turn: still give a flash, no real effect.
        flash_hand_card(game_state, hand_index, COLOR_HIGHLIGHT)
        return None
    consumed = bool(callback(hand_index))
    return "selected" if consumed else None


# ============================================================
# Card preview popup
# ============================================================
def preview_card_popup(game_state, hand_index):
    """Show a frameless enlarged card.

    Clicking the card image confirms a selection (if a callback is active);
    clicking anywhere else, pressing Esc, or losing focus closes the popup.
    Returns True only when the card image was clicked.
    """
    card_id = game_state.hand_cards[hand_index]
    safe_card_id = card_id if 0 <= card_id < len(game_state.card_images) else 0
    image_data = game_state.card_images[safe_card_id]

    has_callback = game_state.card_selection_callback is not None
    hint_text = (
        "再次点击卡牌确认 · 点别处或按 Esc 取消"
        if has_callback
        else "预览中 · 点别处或按 Esc 关闭"
    )

    layout = [
        [
            sg.Text(
                hint_text,
                font=FONT_BODY,
                text_color=COLOR_MUTED,
                background_color=COLOR_PAPER,
                justification="center",
                expand_x=True,
            )
        ],
        [
            sg.Button(
                image_data=image_data,
                key="-PREV-CARD-",
                button_color=(COLOR_PAPER, COLOR_PAPER),
                border_width=0,
                pad=(0, 0),
            )
        ],
        [
            sg.Button(
                "关闭",
                key="-PREV-CANCEL-",
                size=(8, 1),
                font=FONT_BODY,
                button_color=(COLOR_INK, COLOR_PAPER_DARK),
                border_width=1,
            )
        ],
    ]
    popup = sg.Window(
        "出牌预览",
        layout,
        no_titlebar=True,
        keep_on_top=True,
        finalize=True,
        background_color=COLOR_PAPER,
        margins=(8, 8),
        element_justification="c",
    )
    popup.bind("<Escape>", "ESCAPE")
    popup.bind("<FocusOut>", "FOCUS_LOST")
    popup.TKroot.focus_force()

    confirmed = False
    while True:
        event, _ = popup.read(timeout=120)
        if event in (
            sg.WIN_CLOSED,
            "ESCAPE",
            "FOCUS_LOST",
            "-PREV-CANCEL-",
        ):
            break
        if event == "-PREV-CARD-":
            confirmed = True
            break
    popup.close()
    return confirmed


# ============================================================
# Draw-pile viewer
# ============================================================
DECK_THUMB_SIZE = (90, 130)
DECK_CARDS_PER_ROW = 5
DECK_TYPE_ORDER = ("技能", "物品", "生物", "见闻", "形态")
DECK_TYPE_COLORS = {
    "技能": "#D6E2D4",
    "物品": "#E8DFC3",
    "生物": "#E8C8BE",
    "见闻": "#DDD5E8",
    "形态": "#D8E0E8",
}


def _card_category(character_id, card_id):
    """Return the grouping category for a card; slugcat uses card_type."""
    if character_id == 4:
        from card_duel.cards.slugcat_data import SLUGCAT_SPECS_BY_ID

        spec = SLUGCAT_SPECS_BY_ID.get(card_id)
        return spec.card_type if spec else "其他"
    return "手牌"


def _card_name(character_id, card_id):
    if character_id == 4:
        from card_duel.cards.slugcat_data import SLUGCAT_SPECS_BY_ID

        spec = SLUGCAT_SPECS_BY_ID.get(card_id)
        return spec.name if spec else f"#{card_id}"
    from card_duel.cards.registry import CARD_REGISTRY

    definition = CARD_REGISTRY.get((character_id, card_id))
    return definition.name if definition else f"#{card_id}"


def _group_draw_pile(game_state):
    """Group the local draw pile by category then by card_id with counts."""
    character_id = game_state.character_ids[game_state.local_player_id]
    groups = {}
    for card_id in game_state.draw_pile:
        if not card_id:
            continue
        category = _card_category(character_id, card_id)
        bucket = groups.setdefault(category, {})
        bucket[card_id] = bucket.get(card_id, 0) + 1
    return groups


def _deck_viewer_card_rows(images, character_id, bucket, drawable):
    """Build the thumbnail rows for one category bucket.

    ``drawable=False`` cards (unlocked creatures) get a gold border to mark
    them as non-drawable.
    """
    rows = []
    card_entries = list(sorted(bucket.items()))
    for chunk_start in range(0, len(card_entries), DECK_CARDS_PER_ROW):
        chunk = card_entries[chunk_start:chunk_start + DECK_CARDS_PER_ROW]
        card_row = []
        for card_id, count in chunk:
            safe_id = card_id if 0 <= card_id < len(images) else 0
            thumb = _thumbnail(images[safe_id], DECK_THUMB_SIZE) if images else None
            border_color = COLOR_PAPER if drawable else COLOR_GOLD
            button = sg.Button(
                image_data=thumb,
                key=f"-DECK-CARD-{card_id}-",
                pad=(6, 4),
                button_color=(COLOR_PAPER, border_color),
                border_width=1,
            )
            card_row.append(
                sg.Column(
                    [
                        [button],
                        [
                            sg.Text(
                                f"{_card_name(character_id, card_id)}  ×{count}",
                                font=("Microsoft YaHei UI", 8),
                                text_color=COLOR_MUTED,
                                background_color=COLOR_PAPER,
                                justification="center",
                                size=(12, 1),
                            )
                        ],
                    ],
                    background_color=COLOR_PAPER,
                    element_justification="c",
                    pad=(2, 2),
                )
            )
        rows.append([
            sg.Column(
                [card_row],
                background_color=COLOR_PAPER,
                expand_x=True,
                pad=(4, 2),
            )
        ])
    return rows


def open_deck_viewer(game_state):
    """Open a read-only window showing the local draw pile, grouped by type."""
    if game_state.deck_viewer_window is not None:
        try:
            game_state.deck_viewer_window.close()
        except Exception:
            pass
        game_state.deck_viewer_window = None

    character_id = game_state.character_ids[game_state.local_player_id]
    images = game_state.card_images
    groups = _group_draw_pile(game_state)

    # 已解锁生物（不进入抽牌堆、不可抽取，仅展示）
    unlocked_creatures = {}
    # 见闻牌堆（discovery_pool，独立于抽牌堆）
    discovery_pool_counts = {}
    if character_id == 4:
        local_player = game_state.players[game_state.local_player_id]
        # JSON反序列化后key可能是字符串，统一转int
        unlocked_creatures = {
            int(k): v for k, v in local_player.special.get("unlocked_creature_counts", {}).items()
        }
        # discovery_pool 是一个 list，统计每张见闻牌的数量
        pool = local_player.special.get("discovery_pool", [])
        for cid in pool:
            cid_int = int(cid)
            discovery_pool_counts[cid_int] = discovery_pool_counts.get(cid_int, 0) + 1

    # Order categories: slugcat type order first, then any extras.
    ordered_categories = [c for c in DECK_TYPE_ORDER if c in groups]
    for category in groups:
        if category not in ordered_categories:
            ordered_categories.append(category)

    rows = [
        [
            sg.Text(
                f"抽牌堆 · 共 {len(game_state.draw_pile)} 张",
                font=FONT_HEADING,
                text_color=COLOR_INK,
                background_color=COLOR_PAPER,
                expand_x=True,
            ),
            sg.Button(
                "刷新",
                key="-DECK-REFRESH-",
                size=(6, 1),
                font=FONT_BODY,
                button_color=(COLOR_INK, COLOR_PAPER_DARK),
            ),
            sg.Button(
                "关闭",
                key="-DECK-CLOSE-",
                size=(6, 1),
                font=FONT_BODY,
                button_color=(COLOR_INK, COLOR_PAPER_DARK),
            ),
        ]
    ]

    if not groups:
        rows.append([
            sg.Text(
                "（牌堆为空）",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
                background_color=COLOR_PAPER,
            )
        ])
    else:
        for category in ordered_categories:
            bucket = groups[category]
            tint = DECK_TYPE_COLORS.get(category, COLOR_PAPER_DARK)
            header = sg.Text(
                f"  {category}  ·  {sum(bucket.values())} 张",
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
                background_color=tint,
                expand_x=True,
                pad=((4, 4), (8, 4)),
            )
            rows.append([header])
            rows.extend(
                _deck_viewer_card_rows(
                    images, character_id, bucket, drawable=True
                )
            )

    # 见闻牌堆区（discovery_pool，独立于抽牌堆，猫跑路从中抽取）
    if discovery_pool_counts:
        rows.append([
            sg.Text(
                f"  见闻牌堆  ·  {sum(discovery_pool_counts.values())} 张"
                f"（猫跑路抽取，打出/弃牌后回到此堆）",
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
                background_color=DECK_TYPE_COLORS.get("见闻", COLOR_PAPER_DARK),
                expand_x=True,
                pad=((4, 4), (12, 4)),
            )
        ])
        rows.extend(
            _deck_viewer_card_rows(
                images, character_id, discovery_pool_counts, drawable=False
            )
        )

    # 已解锁生物区（不可抽取）
    if unlocked_creatures:
        rows.append([
            sg.Text(
                f"  已解锁生物  ·  {sum(unlocked_creatures.values())} 张"
                f"（不可抽取，仅展示）",
                font=FONT_BODY_BOLD,
                text_color=COLOR_GOLD,
                background_color=COLOR_PAPER_DARK,
                expand_x=True,
                pad=((4, 4), (12, 4)),
            )
        ])
        rows.extend(
            _deck_viewer_card_rows(
                images, character_id, unlocked_creatures, drawable=False
            )
        )

    layout = [
        [
            sg.Column(
                rows,
                background_color=COLOR_PAPER,
                expand_x=True,
                expand_y=True,
                pad=(8, 6),
                scrollable=True,
                vertical_scroll_only=True,
                size=(720, 480),
            )
        ]
    ]
    window = sg.Window(
        "抽牌堆",
        layout,
        size=(760, 560),
        finalize=True,
        keep_on_top=True,
        background_color=COLOR_PAPER,
        resizable=True,
    )
    _bind_deck_card_events(window)
    game_state.deck_viewer_window = window
    _poll_deck_viewer(game_state)


def _bind_deck_card_events(window):
    """Bind right-click events to every deck-viewer card button."""
    for key in list(window.AllKeysDict.keys()):
        if isinstance(key, str) and key.startswith("-DECK-CARD-") and key.endswith("-"):
            try:
                window[key].bind("<Button-3>", " RIGHT")
            except Exception:
                pass


def _poll_deck_viewer(game_state):
    """Read once for the deck viewer so right-click previews work.

    The main loop calls this between its own reads; the viewer window is
    non-blocking and only handles its own events.
    """
    window = game_state.deck_viewer_window
    if window is None:
        return
    try:
        if window.was_closed():
            game_state.deck_viewer_window = None
            return
    except Exception:
        game_state.deck_viewer_window = None
        return
    event, _ = window.read(timeout=10)
    if event in (sg.WIN_CLOSED, "-DECK-CLOSE-"):
        window.close()
        game_state.deck_viewer_window = None
        return
    if event == "-DECK-REFRESH-":
        window.close()
        game_state.deck_viewer_window = None
        open_deck_viewer(game_state)
        return
    if isinstance(event, str) and event.startswith("-DECK-CARD-"):
        parsed = _parse_deck_card_event(event)
        if parsed is None:
            return
        card_id, is_right = parsed
        if is_right:
            _preview_static_card(game_state, card_id)


def _parse_deck_card_event(event):
    """Parse a -DECK-CARD-{id}- [RIGHT] event into (card_id, is_right)."""
    if not isinstance(event, str) or not event.startswith("-DECK-CARD-"):
        return None
    is_right = event.endswith(" RIGHT")
    core = event.removesuffix(" RIGHT") if is_right else event
    inner = core.removeprefix("-DECK-CARD-").removesuffix("-")
    if not inner.isdigit():
        return None
    return int(inner), is_right


def _preview_static_card(game_state, card_id):
    """Show a large read-only preview of any card image from the local deck."""
    images = game_state.card_images
    safe_id = card_id if 0 <= card_id < len(images) else 0
    image_data = images[safe_id] if images else None

    layout = [
        [
            sg.Text(
                "点别处或按 Esc 关闭",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
                background_color=COLOR_PAPER,
                justification="center",
                expand_x=True,
            )
        ],
        [sg.Image(data=image_data, background_color=COLOR_PAPER)],
    ]
    popup = sg.Window(
        "卡牌预览",
        layout,
        no_titlebar=True,
        keep_on_top=True,
        finalize=True,
        background_color=COLOR_PAPER,
        margins=(8, 8),
        element_justification="c",
    )
    popup.bind("<Escape>", "ESCAPE")
    popup.bind("<FocusOut>", "FOCUS_LOST")
    popup.TKroot.focus_force()
    while True:
        event, _ = popup.read(timeout=120)
        if event in (sg.WIN_CLOSED, "ESCAPE", "FOCUS_LOST"):
            break
    popup.close()


def poll_deck_viewer(game_state):
    """Public hook for the main loop to drive the deck-viewer window."""
    _poll_deck_viewer(game_state)
