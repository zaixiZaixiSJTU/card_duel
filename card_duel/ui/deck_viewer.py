"""Categorized deck, discovery-pool, and creature-pool viewer."""

from __future__ import annotations

from collections import Counter, defaultdict

import FreeSimpleGUI as sg

from card_duel.cards.slugcat.state import SlugcatData, slugcat_data
from card_duel.ui.network_style import (
    COLOR_GOLD,
    COLOR_INK,
    COLOR_PAPER,
    COLOR_RED,
    FONT_BODY_BOLD,
)

DECK_VIEW_KEY = "-DECK-VIEW-"


def grouped_deck_cards(session):
    """Return display groups as pure data so categorization stays testable."""
    state = session.state
    groups = defaultdict(Counter)
    for card_id in state.draw_pile:
        definition = session.registry.get_card(state.local_character_id, card_id)
        groups[definition.card_type][card_id] += 1

    player = state.local_player
    if isinstance(player.character_data, SlugcatData):
        data = slugcat_data(player)
        groups["见闻牌堆"].update(data.discovery_pool)
        groups["已解锁生物（不可抽取）"].update(
            {
                int(card_id): count
                for card_id, count in data.unlocked_creature_counts.items()
            }
        )
    return groups


def open_deck_viewer(session) -> None:
    groups = grouped_deck_cards(session)
    rows = []
    for title, counts in groups.items():
        if not counts:
            continue
        rows.append(
            [
                sg.Text(
                    title,
                    font=FONT_BODY_BOLD,
                    text_color=COLOR_INK,
                    background_color=COLOR_PAPER,
                )
            ]
        )
        card_row = []
        for card_id, count in sorted(counts.items()):
            border = (
                COLOR_GOLD
                if 16 <= card_id <= 26
                else COLOR_RED
                if card_id in (49, 50)
                else COLOR_PAPER
            )
            card_row.append(
                sg.Column(
                    [
                        [
                            sg.Button(
                                image_data=session.card_images[card_id],
                                key=f"-DECK-CARD-{card_id}-",
                                border_width=3,
                                button_color=(border, border),
                            )
                        ],
                        [
                            sg.Text(
                                f"× {count}",
                                justification="center",
                                expand_x=True,
                                background_color=COLOR_PAPER,
                            )
                        ],
                    ],
                    background_color=COLOR_PAPER,
                )
            )
            if len(card_row) == 5:
                rows.append(card_row)
                card_row = []
        if card_row:
            rows.append(card_row)
    if not rows:
        rows = [[sg.Text("牌堆为空", background_color=COLOR_PAPER)]]
    window = sg.Window(
        "牌堆查看",
        [
            [
                sg.Column(
                    rows,
                    scrollable=True,
                    vertical_scroll_only=True,
                    size=(940, 680),
                    background_color=COLOR_PAPER,
                )
            ]
        ],
        modal=True,
        finalize=True,
        resizable=True,
        background_color=COLOR_PAPER,
    )
    for card_id in {card_id for counts in groups.values() for card_id in counts}:
        window[f"-DECK-CARD-{card_id}-"].bind("<Button-3>", " RIGHT")
    try:
        while True:
            event, _values = window.read()
            if event == sg.WIN_CLOSED:
                return
            if isinstance(event, str) and event.startswith("-DECK-CARD-"):
                key = event.removesuffix(" RIGHT")
                card_id = int(key.removeprefix("-DECK-CARD-").removesuffix("-"))
                _preview_static_card(session.card_images[card_id])
    finally:
        window.close()


def _preview_static_card(image_data: bytes) -> None:
    window = sg.Window(
        "卡牌预览",
        [[sg.Image(data=image_data)], [sg.Button("关闭", key="-CLOSE-")]],
        modal=True,
        finalize=True,
        background_color=COLOR_PAPER,
    )
    try:
        while True:
            event, _values = window.read()
            if event in (sg.WIN_CLOSED, "-CLOSE-"):
                return
    finally:
        window.close()
