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
DECK_VIEW_KEY_DRAW = "-DECK-VIEW-DRAW-"
DECK_VIEW_KEY_DISCARD = "-DECK-VIEW-DISCARD-"


def grouped_deck_cards(session):
    """Return display groups as pure data so categorization stays testable."""
    state = session.state
    groups = defaultdict(Counter)
    for card_id in state.draw_pile:
        definition = session.registry.get_card(state.local_character_id, card_id)
        groups[definition.card_type][card_id] += 1

    if state.discard_pile:
        discard_groups: Counter = Counter()
        for card_id in state.discard_pile:
            discard_groups[card_id] += 1
        groups["弃牌堆"] = discard_groups

    player = state.local_player
    if isinstance(player.character_data, SlugcatData):
        data = slugcat_data(player)
        groups["见闻牌堆"].update(data.discovery_pool)
        # unlocked_creature_counts 现在是「可召唤计数」语义：召唤-1，死亡/返还+1
        # 生物牌不进抽牌堆/弃牌堆循环，只在此处展示当前可召唤数量
        groups["可召唤生物（不进牌堆）"].update(
            {
                int(card_id): count
                for card_id, count in data.unlocked_creature_counts.items()
            }
        )
    return groups


def open_deck_viewer(session, *, mode: str = "all") -> None:
    """Open the deck viewer window.

    mode:
        "all"     → 显示抽牌堆 + 弃牌堆 + 见闻牌堆 + 可召唤生物
        "draw"    → 只显示抽牌堆相关分组（不含弃牌堆）
        "discard" → 只显示弃牌堆
    """
    groups = grouped_deck_cards(session)
    # 按 mode 过滤分组：固定分组 "弃牌堆" 算弃牌，其他都算抽牌堆相关
    if mode == "draw":
        groups = {k: v for k, v in groups.items() if k != "弃牌堆"}
    elif mode == "discard":
        groups = {k: v for k, v in groups.items() if k == "弃牌堆"}
    rows = []
    bound_keys: list[tuple[str, int]] = []
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
            # Prefix the key with the group title so the same card_id may
            # appear under both the draw pile and the discard pile section
            # without producing duplicate FreeSimpleGUI keys.
            key = f"-DECK-CARD-{title}-{card_id}-"
            bound_keys.append((key, card_id))
            card_row.append(
                sg.Column(
                    [
                        [
                            sg.Button(
                                image_data=session.card_images[card_id],
                                key=key,
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
        empty_text = "弃牌堆为空" if mode == "discard" else "牌堆为空"
        rows = [[sg.Text(empty_text, background_color=COLOR_PAPER)]]
    window_title = "弃牌堆查看" if mode == "discard" else "抽牌堆查看" if mode == "draw" else "牌堆查看"
    window = sg.Window(
        window_title,
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
        keep_on_top=True,
        background_color=COLOR_PAPER,
    )
    from card_duel.ui.card_interaction import _force_visible_centered

    _force_visible_centered(window, session.require_window())
    for key, _card_id in bound_keys:
        window[key].bind("<Button-3>", " RIGHT")
    try:
        while True:
            event, _values = window.read()
            if event == sg.WIN_CLOSED:
                return
            if isinstance(event, str) and event.startswith("-DECK-CARD-"):
                key = event.removesuffix(" RIGHT")
                # Key format: -DECK-CARD-{title}-{card_id}-.  Split on the
                # last dash so titles containing dashes keep working too.
                card_id = int(key.rstrip("-").rsplit("-", 1)[1])
                _preview_static_card(session.card_images[card_id], window)
    finally:
        window.close()


def _preview_static_card(image_data: bytes, parent) -> None:
    from card_duel.ui.card_interaction import _enlarge, show_dismissable_preview

    show_dismissable_preview(_enlarge(image_data), parent)
