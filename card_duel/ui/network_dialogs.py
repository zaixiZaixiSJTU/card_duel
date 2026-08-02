"""Modal dialogs used while setting up a network match."""

import FreeSimpleGUI as sg

from card_duel.ui.network_style import (
    COLOR_BACKGROUND,
    COLOR_BLUE,
    COLOR_INK,
    COLOR_MUTED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_TITLE,
)


def character_select_dialog(registry):
    button_colors = ("#E8C8BE", "#D6E2D4", "#DDD5E8", "#E8DFC3")
    character_buttons = []
    for index, character_id in enumerate(registry.character_ids):
        definition = registry.get_character(character_id)
        character_buttons.append(
            sg.Button(
                f"{character_id:02d}\n{definition.name}",
                font=FONT_HEADING,
                button_color=(COLOR_INK, button_colors[index % len(button_colors)]),
                size=(12, 3),
                key=str(character_id),
                pad=(7, 12),
            )
        )
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
        character_buttons,
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
    window = sg.Window(
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
    window.read(timeout=100)
    return window
