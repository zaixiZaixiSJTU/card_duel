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
DECK_VIEW_KEY_DRAW = "-DECK-VIEW-DRAW-"
DECK_VIEW_KEY_DISCARD = "-DECK-VIEW-DISCARD-"
DECK_CLOSE_KEY = "-DECK-CLOSE-"
DECK_REFRESH_KEY = "-DECK-REFRESH-"
DECK_PANEL_KEY = "-DECK-PANEL-"
DECK_GRID_KEY = "-DECK-GRID-"
GAME_PANEL_KEY = "-ROOT-COL-"
DECK_CARD_PREFIX = "-DECK-CARD-"
DECK_VIEW_COLUMNS = 5
DECK_SECTIONS = 8  # 对应 CATEGORY_ORDER 的8个分类
DECK_SLOTS_PER_SECTION = 10  # 每个分类最多10个卡槽（2行×5列）
DECK_VIEW_SLOTS = DECK_SECTIONS * DECK_SLOTS_PER_SECTION  # 80

CATEGORY_ORDER = (
    "技能",
    "物品",
    "形态",
    "见闻",
    "见闻牌堆",
    "弃牌堆",
    "生物",
    "可召唤生物（不进牌堆）",
)


def grouped_deck_cards(session):
    """Return display groups as pure data so categorization stays testable."""
    state = session.state
    groups = defaultdict(Counter)
    for card_id in state.draw_pile:
        definition = session.registry.get_card(state.local_character_id, card_id)
        groups[definition.card_type][card_id] += 1

    # 弃牌堆分组：展示当前弃牌堆内容
    if state.discard_pile:
        discard_group = Counter()
        for card_id in state.discard_pile:
            discard_group[card_id] += 1
        groups["弃牌堆"] = discard_group

    player = state.local_player
    if isinstance(player.character_data, SlugcatData):
        data = slugcat_data(player)
        groups["见闻牌堆"].update(data.discovery_pool)
        groups["可召唤生物（不进牌堆）"].update(
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
    slot = 0
    for section in range(DECK_SECTIONS):
        # 分类标题行
        rows.append([
            sg.Text(
                "",
                key=f"-DECK-HEADER-{section}-",
                visible=False,
                font=FONT_BODY_BOLD,
                text_color=COLOR_GOLD,
                background_color=COLOR_PAPER_DARK,
                expand_x=True,
                pad=(10, 6),
            )
        ])
        # 卡牌行（DECK_SLOTS_PER_SECTION // DECK_VIEW_COLUMNS 行 × DECK_VIEW_COLUMNS 列）
        for _ in range(DECK_SLOTS_PER_SECTION // DECK_VIEW_COLUMNS):
            row = []
            for _ in range(DECK_VIEW_COLUMNS):
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
                slot += 1
            rows.append(row)

    toolbar = [
        sg.Text(
            "牌堆档案",
            font=FONT_HEADING,
            text_color=COLOR_INK,
            background_color=COLOR_BACKGROUND,
        ),
        sg.Text(
            "抽牌堆、见闻池和已解锁生物会实时更新 · 滚轮浏览",
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
        scrollable=True,
        vertical_scroll_only=True,
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


def open_deck_viewer(session, *, mode: str = "all") -> None:
    """Switch the main window to its embedded, non-blocking deck browser.

    mode:
        "all"     → 显示抽牌堆 + 弃牌堆 + 见闻牌堆 + 可召唤生物
        "draw"    → 只显示抽牌堆相关分组（不含弃牌堆）
        "discard" → 只显示弃牌堆
    """
    session.deck_viewer_open = True
    session.deck_viewer_mode = mode
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
    signature = (tuple(entries), summary, getattr(session, "deck_viewer_mode", "all"))
    if not force and signature == getattr(session, "deck_viewer_signature", None):
        return False

    window = session.require_window()
    session.deck_viewer_signature = signature

    # 按分类分组 entries（entries 已按 CATEGORY_ORDER 排序）
    grouped = []
    current_cat = None
    current_cards = []
    for category, card_id, count in entries:
        if category != current_cat:
            if current_cards:
                grouped.append((current_cat, current_cards))
            current_cat = category
            current_cards = [(card_id, count)]
        else:
            current_cards.append((card_id, count))
    if current_cards:
        grouped.append((current_cat, current_cards))

    session.deck_viewer_card_ids = []
    slot = 0
    for section in range(DECK_SECTIONS):
        header = window[f"-DECK-HEADER-{section}-"]
        if section < len(grouped):
            category, cards = grouped[section]
            header.update(
                f"  {category}  ({len(cards)} 种)",
                visible=True,
            )
            # 填充该分类的卡牌
            for i in range(DECK_SLOTS_PER_SECTION):
                slot_element = window[f"-DECK-SLOT-{slot}-"]
                button = window[f"{DECK_CARD_PREFIX}{slot}-"]
                label = window[f"-DECK-CARD-LABEL-{slot}-"]
                if i < len(cards):
                    card_id, count = cards[i]
                    definition = session.registry.get_card(
                        session.state.local_character_id, card_id
                    )
                    session.deck_viewer_card_ids.append(card_id)
                    button.update(
                        image_data=session.card_images[card_id], visible=True
                    )
                    label.update(
                        f"{definition.name} × {count}",
                        visible=True,
                        text_color=_category_color(category),
                    )
                    slot_element.update(visible=True)
                    _apply_slot_border(button, category, card_id)
                else:
                    # 隐藏槽位也占位，保证列表按全局槽位对齐。
                    session.deck_viewer_card_ids.append(None)
                    slot_element.update(visible=False)
                    button.update(visible=False)
                    label.update(visible=False)
                slot += 1
        else:
            # 隐藏未使用的分类
            header.update(visible=False)
            for _ in range(DECK_SLOTS_PER_SECTION):
                session.deck_viewer_card_ids.append(None)
                window[f"-DECK-SLOT-{slot}-"].update(visible=False)
                window[f"{DECK_CARD_PREFIX}{slot}-"].update(visible=False)
                window[f"-DECK-CARD-LABEL-{slot}-"].update(visible=False)
                slot += 1

    window["-DECK-SUMMARY-"].update(summary)
    window.refresh()
    return True


def handle_deck_viewer_event(session, event) -> bool:
    """Handle one main-window deck event; return whether it was consumed."""
    if event == DECK_VIEW_KEY:
        open_deck_viewer(session)
        return True
    if event == DECK_VIEW_KEY_DRAW:
        open_deck_viewer(session, mode="draw")
        return True
    if event == DECK_VIEW_KEY_DISCARD:
        open_deck_viewer(session, mode="discard")
        return True
    if event == DECK_CLOSE_KEY:
        close_deck_viewer(session)
        return True
    if event == DECK_REFRESH_KEY:
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
    if card_id is None:
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
    mode = getattr(session, "deck_viewer_mode", "all")
    # 按 mode 过滤分组：固定分组 "弃牌堆" 算弃牌，其他都算抽牌堆相关
    if mode == "draw":
        groups = {k: v for k, v in groups.items() if k != "弃牌堆"}
    elif mode == "discard":
        groups = {k: v for k, v in groups.items() if k == "弃牌堆"}
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
    discard_count = len(session.state.discard_pile)
    if mode == "discard":
        summary = (
            f"弃牌堆 {discard_count} 张   ·   共 {len(entries)} 种"
            "   ·   右键卡牌可放大"
        )
    elif mode == "draw":
        summary = (
            f"可抽取 {len(session.state.draw_pile)} 张"
            f"   ·   见闻池 {discovery_count} 张"
            f"   ·   已解锁生物 {creature_count} 张"
            f"   ·   共 {len(entries)} 种"
            "   ·   右键卡牌可放大"
        )
    else:
        summary = (
            f"可抽取 {len(session.state.draw_pile)} 张"
            f"   ·   弃牌 {discard_count} 张"
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
