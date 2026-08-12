"""Categorized deck, discovery-pool, and creature-pool viewer."""

from __future__ import annotations

from collections import Counter, defaultdict

import FreeSimpleGUI as sg

from card_duel.cards.slugcat.state import SlugcatData, slugcat_data
from card_duel.ui.card_interaction import open_card_preview
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
    """Create or replace the viewer without taking over the event loop."""
    close_deck_viewer(session)
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
        finalize=True,
        resizable=True,
        keep_on_top=True,
        background_color=COLOR_PAPER,
    )
    session.deck_viewer_window = window
    _place_above(window, session.require_window())
    for card_id in {card_id for counts in groups.values() for card_id in counts}:
        window[f"-DECK-CARD-{card_id}-"].bind("<Button-3>", " RIGHT")


def poll_deck_viewer(session) -> None:
    """Process one viewer event and return control to the network loop."""
    window = getattr(session, "deck_viewer_window", None)
    if window is None:
        return
    try:
        event, _values = window.read(timeout=0)
    except Exception:
        close_deck_viewer(session)
        return
    if event == sg.WIN_CLOSED:
        close_deck_viewer(session)
        return
    if isinstance(event, str) and event.startswith("-DECK-CARD-"):
        key = event.removesuffix(" RIGHT")
        card_id = int(key.removeprefix("-DECK-CARD-").removesuffix("-"))
        open_card_preview(session, session.card_images[card_id], window)


def close_deck_viewer(session) -> None:
    window = getattr(session, "deck_viewer_window", None)
    if hasattr(session, "deck_viewer_window"):
        session.deck_viewer_window = None
    if window is not None:
        try:
            window.close()
        except Exception:
            return


def _place_above(window, parent) -> None:
    """Attach a temporary window to its parent and raise it on Windows/Tk."""
    try:
        window.TKroot.transient(parent.TKroot)
        window.TKroot.lift()
        window.TKroot.focus_force()
    except Exception:
        return
