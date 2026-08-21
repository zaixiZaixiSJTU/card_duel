"""Room lobby window shared by host and guest before a match."""

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
)

ROOM_CHAR_KEY = "-ROOM-CHAR-"
ROOM_FIRST_HOST_KEY = "-ROOM-FIRST-HOST-"
ROOM_FIRST_GUEST_KEY = "-ROOM-FIRST-GUEST-"
ROOM_FIRST_RANDOM_KEY = "-ROOM-FIRST-RANDOM-"
ROOM_SEED_KEY = "-ROOM-SEED-"
ROOM_NO_DMG_KEY = "-ROOM-NO-DMG-"
ROOM_RULES_INFO_KEY = "-ROOM-RULES-INFO-"
ROOM_CHAT_LOG_KEY = "-ROOM-CHAT-LOG-"
ROOM_CHAT_INPUT_KEY = "-ROOM-CHAT-INPUT-"
ROOM_CHAT_SEND_KEY = "-ROOM-CHAT-SEND-"
ROOM_START_KEY = "-ROOM-START-"
ROOM_EXIT_KEY = "-ROOM-EXIT-"


def build_room_window(
    registry,
    *,
    is_host: bool,
    first_player: str = "random",
    seed_text: str = "",
    no_damage: bool = True,
) -> sg.Window:
    options = [
        f"{character_id} {registry.get_character(character_id).name}"
        for character_id in registry.get_character_ids()
    ]
    rows = [
        [
            sg.Text(
                "创建房间" if is_host else "加入房间",
                font=FONT_HEADING,
                text_color=COLOR_INK,
            ),
            sg.Text(
                "对局开始前可聊天",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            ),
        ],
        [
            sg.Text("我的角色", size=(9, 1), font=FONT_BODY),
            sg.Combo(
                options,
                default_value=options[0] if options else "",
                key=ROOM_CHAR_KEY,
                size=(18, 1),
                font=FONT_BODY,
                readonly=True,
            ),
        ],
        [sg.HorizontalSeparator(color=COLOR_GOLD)],
    ]
    if is_host:
        rows.extend(
            [
                [sg.Text("规则设置", font=FONT_BODY_BOLD, text_color=COLOR_INK)],
                [
                    sg.Radio(
                        "主机先手",
                        "first",
                        key=ROOM_FIRST_HOST_KEY,
                        default=first_player == "host",
                        font=FONT_BODY,
                        background_color=COLOR_PAPER,
                    ),
                    sg.Radio(
                        "客机先手",
                        "first",
                        key=ROOM_FIRST_GUEST_KEY,
                        default=first_player == "guest",
                        font=FONT_BODY,
                        background_color=COLOR_PAPER,
                    ),
                    sg.Radio(
                        "随机",
                        "first",
                        key=ROOM_FIRST_RANDOM_KEY,
                        default=first_player == "random",
                        font=FONT_BODY,
                        background_color=COLOR_PAPER,
                    ),
                ],
                [
                    sg.Text("随机种子", size=(9, 1), font=FONT_BODY),
                    sg.Input(
                        seed_text,
                        key=ROOM_SEED_KEY,
                        size=(12, 1),
                        font=FONT_BODY,
                    ),
                    sg.Checkbox(
                        "先手方第一回合无法造成血量损失",
                        key=ROOM_NO_DMG_KEY,
                        default=no_damage,
                        font=FONT_BODY,
                        background_color=COLOR_PAPER,
                    ),
                ],
            ]
        )
    else:
        rows.extend(
            [
                [sg.Text("主机规则", font=FONT_BODY_BOLD, text_color=COLOR_INK)],
                [
                    sg.Text(
                        "等待主机开始对战...",
                        key=ROOM_RULES_INFO_KEY,
                        font=FONT_BODY,
                        text_color=COLOR_MUTED,
                        size=(46, 2),
                    )
                ],
            ]
        )
    rows.extend(
        [
            [sg.HorizontalSeparator(color=COLOR_GOLD)],
            [
                sg.Multiline(
                    "",
                    key=ROOM_CHAT_LOG_KEY,
                    size=(48, 6),
                    disabled=True,
                    autoscroll=True,
                    font=FONT_BODY,
                    background_color=COLOR_PAPER,
                )
            ],
            [
                sg.Input(
                    "",
                    key=ROOM_CHAT_INPUT_KEY,
                    size=(32, 1),
                    font=FONT_BODY,
                ),
                sg.Button("发送", key=ROOM_CHAT_SEND_KEY, font=FONT_BODY),
            ],
            [
                sg.Button(
                    "开始对战",
                    key=ROOM_START_KEY,
                    font=FONT_BODY_BOLD,
                    disabled=not is_host,
                ),
                sg.Button("退出房间", key=ROOM_EXIT_KEY, font=FONT_BODY_BOLD),
            ],
        ]
    )
    return sg.Window(
        "创建房间" if is_host else "加入房间",
        rows,
        finalize=True,
        background_color=COLOR_PAPER,
        margins=(16, 12),
        element_justification="left",
        keep_on_top=False,
    )
