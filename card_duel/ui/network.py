"""Minimalist sketch-style interface for the network game."""

import FreeSimpleGUI as sg

from card_duel.core.combat import check_game_over, update_defence_totals

THEME = "SketchPaper"
WINDOW_SIZE = (1200, 660)
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

FONT_TITLE = ("KaiTi", 24, "bold")
FONT_HEADING = ("KaiTi", 16, "bold")
FONT_BODY = ("Microsoft YaHei UI", 11)
FONT_BODY_BOLD = ("Microsoft YaHei UI", 11, "bold")
FONT_MONO = ("Consolas", 10)

MAX_HAND_BUTTONS = 12
MAX_HEALTH_DISPLAY = 40
MAX_ENERGY_ORBS = 8

PHASE_LABELS = (
    "回合开始时",
    "抽牌阶段",
    "出牌阶段",
    "弃牌阶段",
    "回合结束时",
)

CHAT_INPUT_KEY = "-CHAT-INPUT-"
CHAT_SEND_KEY = "-CHAT-SEND-"


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


def _build_status_card(title, accent, key_prefix):
    """Create one compact player card while preserving update keys."""
    hp_key = f"-{key_prefix}-HP-"
    energy_key = f"-{key_prefix}-EN-"
    defence_key = f"-{key_prefix}-DEF-"
    strength_key = f"-{key_prefix}-STR-"
    orb_key = f"-{key_prefix}-ORB-"
    hp_bar_key = f"-{key_prefix}-HP-BAR-"

    health_bar = sg.ProgressBar(
        MAX_HEALTH_DISPLAY,
        orientation="h",
        size=(24, 9),
        key=hp_bar_key,
        bar_color=(COLOR_RED, COLOR_RED_LIGHT),
        relief=sg.RELIEF_FLAT,
    )
    layout = [
        [
            sg.Text(
                title,
                font=FONT_HEADING,
                text_color=accent,
                background_color=COLOR_PAPER,
                size=(13, 1),
            ),
            sg.Text(
                "HP",
                font=FONT_BODY_BOLD,
                text_color=COLOR_RED,
                background_color=COLOR_PAPER,
            ),
            sg.Text(
                "30",
                key=hp_key,
                font=FONT_TITLE,
                text_color=COLOR_INK,
                background_color=COLOR_PAPER,
                size=(3, 1),
            ),
        ],
        [health_bar],
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
                font=("Segoe UI Symbol", 14),
                text_color=COLOR_BLUE,
                background_color=COLOR_PAPER,
                size=(9, 1),
            ),
            sg.Text(
                "数值",
                key=energy_key,
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
                background_color=COLOR_PAPER,
                size=(6, 1),
            ),
        ],
        [
            sg.Text(
                "防御",
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
                size=(6, 1),
            ),
            sg.Text(
                "力量",
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
                size=(5, 1),
            ),
        ],
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
    card_row = []
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
        card_row.append(
            sg.Button(
                image_data=image_data,
                key=f"-BTN{button_index}-",
                pad=(6, 5),
                button_color=(COLOR_PAPER, COLOR_PAPER),
                border_width=1,
            )
        )

    return sg.Column(
        [card_row],
        scrollable=True,
        size=(WINDOW_SIZE[0] - 70, 205),
        vertical_scroll_only=False,
        background_color=COLOR_PAPER,
        expand_x=True,
        key="-CARD-COL-",
    )


def create_main_layout(card_images, hand_cards):
    """Build a compact top-to-bottom workspace for network play."""
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

    opponent_status = _build_status_card("对手", COLOR_RED, "EN")
    local_status = _build_status_card("我方", COLOR_GREEN, "MY")

    log_panel = sg.Frame(
        " 战斗记录 / NOTES ",
        [
            [
                sg.Multiline(
                    size=(55, 10),
                    key="-OUTPUT-",
                    autoscroll=True,
                    reroute_stdout=True,
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
            [
                sg.Text(
                    "聊天消息和卡牌结算共用记录区。",
                    key="-LOG-HINT-",
                    font=FONT_BODY,
                    text_color=COLOR_MUTED,
                    background_color=COLOR_PAPER,
                )
            ],
        ],
        font=FONT_BODY_BOLD,
        title_color=COLOR_INK,
        background_color=COLOR_PAPER,
        relief=sg.RELIEF_SOLID,
        border_width=1,
        expand_x=True,
    )

    card_panel = sg.Frame(
        " 手牌 / HAND ",
        [
            [
                sg.Text(
                    "等待开始",
                    key="-CARD-HINT-",
                    font=FONT_BODY,
                    text_color=COLOR_MUTED,
                    background_color=COLOR_PAPER,
                    expand_x=True,
                ),
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

    content = [
        title_row,
        [phase_tracker],
        [
            sg.Column(
                [[opponent_status]],
                background_color=COLOR_BACKGROUND,
                vertical_alignment="top",
                pad=(0, 0),
            ),
            sg.Column(
                [[log_panel]],
                background_color=COLOR_BACKGROUND,
                expand_x=True,
                vertical_alignment="top",
                pad=(8, 0),
            ),
            sg.Column(
                [[local_status]],
                background_color=COLOR_BACKGROUND,
                vertical_alignment="top",
                pad=(0, 0),
            ),
        ],
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


def refresh_status(game_state):
    """Refresh the two status cards without changing game state."""
    check_game_over(game_state)
    update_defence_totals(game_state)

    local_player = game_state.players[game_state.local_player_id]
    opponent_player = game_state.players[game_state.opponent_player_id]
    _update_player_status(game_state.window, "MY", local_player)
    _update_player_status(game_state.window, "EN", opponent_player)

    game_state.window["-DECK-COUNT-"].update(str(len(game_state.draw_pile)))
    game_state.window["-HAND-COUNT-"].update(str(game_state.hand_size))
    game_state.window.refresh()


def _update_player_status(window, key_prefix, player):
    window[f"-{key_prefix}-HP-"].update(
        str(player.health),
        text_color=COLOR_RED if player.health <= 10 else COLOR_INK,
    )
    window[f"-{key_prefix}-EN-"].update(str(player.energy))
    window[f"-{key_prefix}-DEF-"].update(str(player.defence))
    window[f"-{key_prefix}-STR-"].update(str(player.strength))
    window[f"-{key_prefix}-HP-BAR-"].update(
        max(0, min(MAX_HEALTH_DISPLAY, player.health))
    )
    window[f"-{key_prefix}-ORB-"].update(
        _format_energy_orbs(player.energy)
    )


def refresh_cards(game_state):
    """Compact removed cards, then redraw every visible hand slot."""
    game_state.hand_cards = [
        card_id for card_id in game_state.hand_cards if card_id != -1
    ]
    if len(game_state.hand_cards) < 999:
        game_state.hand_cards.extend([0] * (999 - len(game_state.hand_cards)))

    hand_index = 0
    while (
        hand_index < MAX_HAND_BUTTONS
        and game_state.hand_cards[hand_index] != 0
    ):
        card_id = game_state.hand_cards[hand_index]
        safe_card_id = card_id if 0 <= card_id < len(game_state.card_images) else 0
        game_state.window[f"-BTN{hand_index}-"].update(
            image_data=game_state.card_images[safe_card_id],
            visible=True,
        )
        hand_index += 1

    game_state.hand_size = hand_index
    for button_index in range(hand_index, MAX_HAND_BUTTONS):
        game_state.window[f"-BTN{button_index}-"].update(visible=False)


def set_phase(game_state, phase_text):
    game_state.window["-PHASE-"].update(phase_text)
    active_phase_index = next(
        (
            phase_index
            for phase_index, phase_label in enumerate(PHASE_LABELS)
            if phase_label in phase_text
        ),
        None,
    )
    for phase_index in range(len(PHASE_LABELS)):
        is_active = phase_index == active_phase_index
        game_state.window[f"-PHASE-STEP-{phase_index}-"].update(
            text_color=COLOR_PAPER if is_active else COLOR_MUTED,
            background_color=COLOR_BLUE if is_active else COLOR_PAPER,
        )
    game_state.window.refresh()


def set_cards_enabled(game_state, enabled):
    game_state.window["-btn1-"].update(
        disabled=not enabled,
        button_color=(
            (COLOR_PAPER, COLOR_GREEN)
            if enabled
            else (COLOR_MUTED, COLOR_DISABLED)
        ),
    )
    hint = "挑一张牌，慢慢想。" if enabled else "等对手落笔……"
    if "-CARD-HINT-" in game_state.window.AllKeysDict:
        game_state.window["-CARD-HINT-"].update(
            hint,
            text_color=COLOR_GREEN if enabled else COLOR_MUTED,
        )


def _format_energy_orbs(value):
    filled = max(0, min(value, MAX_ENERGY_ORBS))
    return "●" * filled + "○" * (MAX_ENERGY_ORBS - filled)
