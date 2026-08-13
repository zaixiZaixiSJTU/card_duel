"""In-window deck browser that never competes with the game window."""

from __future__ import annotations

from collections import Counter, defaultdict

import FreeSimpleGUI as sg

from card_duel.cards.slugcat.state import SlugcatData, slugcat_data
from card_duel.ui.card_interaction import open_card_preview
from card_duel.ui.network_style import (
    COLOR_BACKGROUND,
    COLOR_GOLD,
    COLOR_GREEN,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    COLOR_PAPER_DARK,
    COLOR_RED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    WINDOW_SIZE,
)

DECK_VIEW_KEY = "-DECK-VIEW-"
DECK_CLOSE_KEY = "-DECK-CLOSE-"
DECK_REFRESH_KEY = "-DECK-REFRESH-"
DECK_PREVIOUS_KEY = "-DECK-PREVIOUS-"
DECK_NEXT_KEY = "-DECK-NEXT-"
DECK_PANEL_KEY = "-DECK-PANEL-"
DECK_GRID_KEY = "-DECK-GRID-"
GAME_PANEL_KEY = "-ROOT-COL-"
DECK_CARD_PREFIX = "-DECK-CARD-"
DECK_VIEW_COLUMNS = 5
DECK_VIEW_SLOTS = 10

CATEGORY_ORDER = (
    "技能",
    "物品",
    "形态",
    "见闻",
    "见闻牌堆",
    "生物",
    "已解锁生物（不可抽取）",
)


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


def build_deck_viewer_panel(card_images):
    """Build a hidden browser inside the main window's own stacking context."""
    placeholder = card_images[0] if card_images else None
    rows = []
    for row_start in range(0, DECK_VIEW_SLOTS, DECK_VIEW_COLUMNS):
        row = []
        for slot in range(row_start, row_start + DECK_VIEW_COLUMNS):
            row.append(
                sg.Column(
                    [
                        [
                            sg.Button(
                                image_data=placeholder,
                                key=f"{DECK_CARD_PREFIX}{slot}-",
                                visible=False,
                                border_width=2,
                                button_color=(COLOR_PAPER, COLOR_PAPER),
                                pad=(7, 4),
                                tooltip="右键放大预览",
                            )
                        ],
                        [
                            sg.Text(
                                "",
                                key=f"-DECK-CARD-LABEL-{slot}-",
                                visible=False,
                                size=(22, 2),
                                justification="center",
                                font=FONT_BODY,
                                text_color=COLOR_INK,
                                background_color=COLOR_PAPER,
                            )
                        ],
                    ],
                    key=f"-DECK-SLOT-{slot}-",
                    visible=False,
                    background_color=COLOR_PAPER,
                    element_justification="center",
                    pad=(2, 3),
                )
            )
        rows.append(row)

    toolbar = [
        sg.Text(
            "牌堆档案",
            font=FONT_HEADING,
            text_color=COLOR_INK,
            background_color=COLOR_BACKGROUND,
        ),
        sg.Text(
            "抽牌堆、见闻池和已解锁生物会实时更新",
            font=FONT_BODY,
            text_color=COLOR_MUTED,
            background_color=COLOR_BACKGROUND,
            expand_x=True,
        ),
        sg.Button(
            "刷新",
            key=DECK_REFRESH_KEY,
            font=FONT_BODY_BOLD,
            button_color=(COLOR_INK, COLOR_PAPER_DARK),
            border_width=1,
        ),
        sg.Button(
            "上一页",
            key=DECK_PREVIOUS_KEY,
            font=FONT_BODY_BOLD,
            button_color=(COLOR_INK, COLOR_PAPER_DARK),
            border_width=1,
        ),
        sg.Text(
            "1 / 1",
            key="-DECK-PAGE-",
            size=(7, 1),
            justification="center",
            font=FONT_BODY_BOLD,
            text_color=COLOR_INK,
            background_color=COLOR_BACKGROUND,
        ),
        sg.Button(
            "下一页",
            key=DECK_NEXT_KEY,
            font=FONT_BODY_BOLD,
            button_color=(COLOR_INK, COLOR_PAPER_DARK),
            border_width=1,
        ),
        sg.Button(
            "返回对局  ←",
            key=DECK_CLOSE_KEY,
            font=FONT_BODY_BOLD,
            button_color=(COLOR_PAPER, COLOR_GREEN),
            border_width=1,
        ),
    ]
    summary = [
        sg.Text(
            "",
            key="-DECK-SUMMARY-",
            font=FONT_BODY_BOLD,
            text_color=COLOR_GOLD,
            background_color=COLOR_PAPER,
            expand_x=True,
            pad=(8, 8),
        )
    ]
    browser = sg.Column(
        rows,
        key=DECK_GRID_KEY,
        size=(WINDOW_SIZE[0] - 55, WINDOW_SIZE[1] - 155),
        background_color=COLOR_PAPER,
        expand_x=True,
        expand_y=True,
        element_justification="center",
    )
    return sg.Column(
        [toolbar, summary, [sg.HorizontalSeparator(color=COLOR_GOLD)], [browser]],
        key=DECK_PANEL_KEY,
        visible=False,
        background_color=COLOR_BACKGROUND,
        expand_x=True,
        expand_y=True,
        pad=(10, 6),
    )


def bind_deck_viewer_events(window) -> None:
    """Only right-click previews cards; left-click is deliberately inert."""
    for slot in range(DECK_VIEW_SLOTS):
        try:
            window[f"{DECK_CARD_PREFIX}{slot}-"].bind("<Button-3>", " RIGHT")
        except Exception:
            continue


def open_deck_viewer(session) -> None:
    """Switch the main window to its embedded, non-blocking deck browser."""
    session.deck_viewer_open = True
    session.deck_viewer_page = 0
    refresh_deck_viewer(session, force=True)
    window = session.require_window()
    window[GAME_PANEL_KEY].update(visible=False)
    window[DECK_PANEL_KEY].update(visible=True)
    window.refresh()


def refresh_deck_viewer(session, *, force=False) -> bool:
    """Update changed deck contents in place and leave the socket loop alone."""
    if not getattr(session, "deck_viewer_open", False) and not force:
        return False
    entries, summary = _deck_entries(session)
    page_count = max(1, (len(entries) + DECK_VIEW_SLOTS - 1) // DECK_VIEW_SLOTS)
    page = min(max(0, getattr(session, "deck_viewer_page", 0)), page_count - 1)
    session.deck_viewer_page = page
    page_start = page * DECK_VIEW_SLOTS
    page_entries = entries[page_start : page_start + DECK_VIEW_SLOTS]
    signature = (tuple(entries), summary, page)
    if not force and signature == getattr(session, "deck_viewer_signature", None):
        return False

    window = session.require_window()
    session.deck_viewer_signature = signature
    session.deck_viewer_card_ids = [card_id for _, card_id, _ in page_entries]
    window["-DECK-SUMMARY-"].update(summary)
    window["-DECK-PAGE-"].update(f"{page + 1} / {page_count}")
    window[DECK_PREVIOUS_KEY].update(disabled=page == 0)
    window[DECK_NEXT_KEY].update(disabled=page == page_count - 1)
    for slot in range(DECK_VIEW_SLOTS):
        slot_element = window[f"-DECK-SLOT-{slot}-"]
        button = window[f"{DECK_CARD_PREFIX}{slot}-"]
        label = window[f"-DECK-CARD-LABEL-{slot}-"]
        if slot >= len(page_entries):
            slot_element.update(visible=False)
            button.update(visible=False)
            label.update(visible=False)
            continue
        category, card_id, count = page_entries[slot]
        definition = session.registry.get_card(session.state.local_character_id, card_id)
        button.update(image_data=session.card_images[card_id], visible=True)
        label.update(
            f"{category}\n{definition.name} × {count}",
            visible=True,
            text_color=_category_color(category),
        )
        slot_element.update(visible=True)
        _apply_slot_border(button, category, card_id)
    window.refresh()
    return True


def handle_deck_viewer_event(session, event) -> bool:
    """Handle one main-window deck event; return whether it was consumed."""
    if event == DECK_VIEW_KEY:
        open_deck_viewer(session)
        return True
    if event == DECK_CLOSE_KEY:
        close_deck_viewer(session)
        return True
    if event == DECK_REFRESH_KEY:
        refresh_deck_viewer(session, force=True)
        return True
    if event == DECK_PREVIOUS_KEY:
        session.deck_viewer_page = max(0, session.deck_viewer_page - 1)
        refresh_deck_viewer(session, force=True)
        return True
    if event == DECK_NEXT_KEY:
        session.deck_viewer_page += 1
        refresh_deck_viewer(session, force=True)
        return True
    if not isinstance(event, str) or not event.startswith(DECK_CARD_PREFIX):
        return False
    # A normal left click is consumed but does not open a preview.
    if not event.endswith(" RIGHT"):
        return True
    key = event.removesuffix(" RIGHT")
    try:
        slot = int(key.removeprefix(DECK_CARD_PREFIX).removesuffix("-"))
        card_id = session.deck_viewer_card_ids[slot]
    except (ValueError, IndexError, AttributeError):
        return True
    open_card_preview(session, session.card_images[card_id])
    return True


def poll_deck_viewer(session) -> None:
    """Keep the embedded snapshot current while the browser is visible."""
    refresh_deck_viewer(session)


def close_deck_viewer(session) -> None:
    if not getattr(session, "deck_viewer_open", False):
        return
    session.deck_viewer_open = False
    try:
        window = session.require_window()
        window[DECK_PANEL_KEY].update(visible=False)
        window[GAME_PANEL_KEY].update(visible=True)
        window.refresh()
    except Exception:
        return


def _deck_entries(session):
    groups = grouped_deck_cards(session)
    categories = [category for category in CATEGORY_ORDER if groups.get(category)]
    categories.extend(
        category
        for category in groups
        if category not in categories and groups[category]
    )
    entries = [
        (category, card_id, count)
        for category in categories
        for card_id, count in sorted(groups[category].items())
    ]
    data = (
        slugcat_data(session.state.local_player)
        if isinstance(session.state.local_player.character_data, SlugcatData)
        else None
    )
    discovery_count = len(data.discovery_pool) if data is not None else 0
    creature_count = (
        sum(data.unlocked_creature_counts.values()) if data is not None else 0
    )
    summary = (
        f"可抽取 {len(session.state.draw_pile)} 张"
        f"   ·   见闻池 {discovery_count} 张"
        f"   ·   已解锁生物 {creature_count} 张"
        f"   ·   共 {len(entries)} 种"
        "   ·   右键卡牌可放大"
    )
    return entries, summary


def _category_color(category):
    if "生物" in category:
        return COLOR_GOLD
    if "见闻" in category:
        return COLOR_GREEN
    return COLOR_INK


def _apply_slot_border(button, category, card_id) -> None:
    color = (
        COLOR_RED
        if card_id in (49, 50)
        else COLOR_GOLD
        if "生物" in category
        else COLOR_GREEN
        if "见闻" in category
        else COLOR_PAPER_DARK
    )
    try:
        button.Widget.configure(
            highlightbackground=color,
            highlightcolor=color,
            highlightthickness=4,
            borderwidth=1,
        )
    except Exception:
        return
