"""Minimalist sketch-style interface for the network game."""

import FreeSimpleGUI as sg

from card_duel.ui.deck_viewer import DECK_VIEW_KEY
from card_duel.ui.network_style import (
    CHAT_INPUT_KEY,
    CHAT_SEND_KEY,
    COLOR_BACKGROUND,
    COLOR_BLUE,
    COLOR_DISABLED,
    COLOR_GOLD,
    COLOR_GREEN,
    COLOR_INK,
    COLOR_LINE,
    COLOR_MUTED,
    COLOR_PAPER,
    COLOR_PAPER_DARK,
    COLOR_RED,
    COLOR_RED_LIGHT,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_MONO,
    FONT_TITLE,
    HAND_COLUMNS,
    MAX_HAND_BUTTONS,
    MAX_HEALTH_DISPLAY,
    PHASE_LABELS,
    WINDOW_SIZE,
)


def _build_status_card(title, accent, key_prefix):
    """Create one compact player card while preserving update keys."""
    hp_key = f"-{key_prefix}-HP-"
    energy_key = f"-{key_prefix}-EN-"
    defence_key = f"-{key_prefix}-DEF-"
    strength_key = f"-{key_prefix}-STR-"
    defence_label_key = f"-{key_prefix}-DEF-LABEL-"
    strength_label_key = f"-{key_prefix}-STR-LABEL-"
    orb_key = f"-{key_prefix}-ORB-"
    hp_bar_key = f"-{key_prefix}-HP-BAR-"
    special_key = f"-{key_prefix}-SPECIAL-"

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
                size=(6, 1),
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
                size=(5, 1),
            ),
        ],
        [
            sg.Text(
                "",
                key=special_key,
                font=("Microsoft YaHei UI", 9),
                text_color=COLOR_MUTED,
                background_color=COLOR_PAPER,
                size=(31, 1),
            )
        ],
        [
            sg.Text(
                "最近出牌",
                font=("Microsoft YaHei UI", 9),
                text_color=COLOR_MUTED,
                background_color=COLOR_PAPER,
            ),
            sg.Image(
                key=f"-{key_prefix}-PLAYED-",
                size=(64, 96),
                background_color=COLOR_PAPER_DARK,
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
    card_rows = [[] for _ in range(MAX_HAND_BUTTONS // HAND_COLUMNS)]
    for button_index in range(MAX_HAND_BUTTONS):
        card_id = hand_cards[button_index] if button_index < len(hand_cards) else 0
        image_data = None
        if card_images:
            safe_card_id = card_id if 0 <= card_id < len(card_images) else 0
            image_data = card_images[safe_card_id]
        card_rows[button_index // HAND_COLUMNS].append(
            sg.Button(
                image_data=image_data,
                key=f"-BTN{button_index}-",
                pad=(4, 4),
                button_color=(COLOR_PAPER, COLOR_PAPER),
                border_width=1,
            )
        )

    return sg.Column(
        card_rows,
        scrollable=True,
        size=(WINDOW_SIZE[0] - 70, 430),
        vertical_scroll_only=True,
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
                    reroute_stdout=False,
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
                    "查看牌堆",
                    key=DECK_VIEW_KEY,
                    font=FONT_BODY_BOLD,
                    button_color=(COLOR_INK, COLOR_PAPER_DARK),
                    border_width=1,
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
