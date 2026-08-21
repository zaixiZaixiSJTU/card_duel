"""Main menu and host room-setup dialogs."""

from __future__ import annotations

import FreeSimpleGUI as sg

from card_duel.ui.network_style import (
    COLOR_GOLD,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_TITLE,
)

MAIN_MENU_CREATE = "create"
MAIN_MENU_JOIN = "join"


def main_menu_dialog() -> str | None:
    """Offer create / join; return the chosen action or None."""
    layout = [
        [
            sg.Text(
                "CARD DUEL",
                font=FONT_TITLE,
                text_color=COLOR_INK,
                justification="center",
            )
        ],
        [
            sg.Text(
                "卡牌对决",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
                justification="center",
            )
        ],
        [sg.HorizontalSeparator(color=COLOR_GOLD)],
        [
            sg.Button(
                "创建房间",
                key=MAIN_MENU_CREATE,
                size=(18, 2),
                font=FONT_BODY_BOLD,
            )
        ],
        [
            sg.Button(
                "加入房间",
                key=MAIN_MENU_JOIN,
                size=(18, 2),
                font=FONT_BODY_BOLD,
            )
        ],
        [
            sg.Button(
                "退出",
                key="-QUIT-",
                size=(18, 1),
                font=FONT_BODY,
            )
        ],
    ]
    window = sg.Window(
        "Card Duel",
        layout,
        finalize=True,
        background_color=COLOR_PAPER,
        element_justification="center",
        margins=(30, 24),
        keep_on_top=False,
    )
    while True:
        event, _values = window.read()
        if event in (sg.WIN_CLOSED, "-QUIT-", None):
            window.close()
            return None
        if event in (MAIN_MENU_CREATE, MAIN_MENU_JOIN):
            window.close()
            return event


def host_setup_dialog(registry) -> tuple[int, int | None] | None:
    """Host room setup: pick a character and an optional random seed."""
    character_ids = registry.get_character_ids()
    options = [
        f"{character_id} {registry.get_character(character_id).name}"
        for character_id in character_ids
    ]
    layout = [
        [
            sg.Text(
                "创建房间",
                font=FONT_HEADING,
                text_color=COLOR_INK,
            )
        ],
        [sg.HorizontalSeparator(color=COLOR_GOLD)],
        [
            sg.Text("我的角色", size=(10, 1), font=FONT_BODY),
            sg.Combo(
                options,
                default_value=options[0] if options else "",
                key="-HOST-CHAR-",
                size=(18, 1),
                font=FONT_BODY,
                readonly=True,
            ),
        ],
        [
            sg.Text("随机种子", size=(10, 1), font=FONT_BODY),
            sg.Input(
                "",
                key="-HOST-SEED-",
                size=(12, 1),
                font=FONT_BODY,
                tooltip="留空则随机生成",
            ),
            sg.Text(
                "留空随机",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            ),
        ],
        [
            sg.Button("开始", key="-HOST-START-", font=FONT_BODY_BOLD),
            sg.Button("取消", key="-HOST-CANCEL-", font=FONT_BODY_BOLD),
        ],
    ]
    window = sg.Window(
        "创建房间",
        layout,
        finalize=True,
        background_color=COLOR_PAPER,
        margins=(16, 14),
        element_justification="left",
        keep_on_top=False,
    )
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, "-HOST-CANCEL-", None):
            window.close()
            return None
        if event != "-HOST-START-":
            continue
        selected = values.get("-HOST-CHAR-", "")
        try:
            character_id = int(selected.split()[0])
        except (ValueError, IndexError):
            window.close()
            return None
        seed_text = (values.get("-HOST-SEED-") or "").strip()
        seed: int | None = None
        if seed_text:
            try:
                seed = int(seed_text)
            except ValueError:
                sg.popup(
                    "种子必须是整数（留空则随机）",
                    keep_on_top=True,
                )
                continue
        window.close()
        return character_id, seed
