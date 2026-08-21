"""Non-blocking debug console opened from the chat input via ``/tool``.

The console edits the local player's numeric parameters and injects cards into
the local hand. Every change is written to the match log and broadcast to the
peer as an announcement; the window never blocks the network event loop.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields

import FreeSimpleGUI as sg

from card_duel.core.models import DefenceEffect
from card_duel.ui.network_log import append_log
from card_duel.ui.network_style import (
    CHAT_INPUT_KEY,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
)

_DBG_APPLY = "-DBG-APPLY-"
_DBG_ADD = "-DBG-ADD-"
_DBG_CLOSE = "-DBG-CLOSE-"
_DBG_TREE_KEY = "-DBG-TREE-"
_DBG_CARD_INFO_KEY = "-DBG-CARD-INFO-"
_CARD_ID_PREFIX = "-DBG-CARD-"
_CATEGORY_ORDER = ("技能", "物品", "形态", "见闻", "生物", "插入物", "其他")


def handle_chat_command(session, text: str) -> bool:
    """Return True when the chat input is a console command."""
    command = " ".join((text or "").strip().split()).lower()
    if command != "/tool":
        return False
    open_debug_tool(session)
    try:
        session.require_window()[CHAT_INPUT_KEY].update("")
    except Exception:
        pass
    return True


def open_debug_tool(session) -> None:
    """Open a fresh non-blocking console bound to the local player."""
    close_debug_tool(session)
    state = session.state
    player = state.local_player
    character_id = state.local_character_id
    definition = session.registry.get_character(character_id)
    data = player.character_data

    rows = [
        [
            sg.Text(
                f"调试控制台 · {definition.name}（角色{character_id}）",
                font=FONT_HEADING,
                text_color=COLOR_INK,
            )
        ],
        [
            sg.Text(
                "修改本地玩家参数 / 加入卡牌 · 修改会播报给双方",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            )
        ],
    ]
    for label, value in (
        ("生命", player.health),
        ("能量", player.energy),
        ("力量", player.strength),
        ("毒", player.poison),
    ):
        rows.append(
            [
                sg.Text(label, size=(10, 1), font=FONT_BODY),
                sg.Input(
                    str(value),
                    key=f"-DBG-{label}-",
                    size=(10, 1),
                    font=FONT_BODY,
                ),
            ]
        )
    rows.append(
        [
            sg.Text("防御", size=(10, 1), font=FONT_BODY),
            sg.Input(
                str(player.defence),
                key="-DBG-防御-",
                size=(10, 1),
                font=FONT_BODY,
            ),
        ]
    )
    if data is not None:
        for field in dataclass_fields(data):
            value = getattr(data, field.name)
            if isinstance(value, int) and not isinstance(value, bool):
                rows.append(
                    [
                        sg.Text(field.name, size=(10, 1), font=FONT_BODY),
                        sg.Input(
                            str(value),
                            key=f"-DBG-{field.name}-",
                            size=(10, 1),
                            font=FONT_BODY,
                        ),
                    ]
                )

    rows.append([sg.HorizontalSeparator()])
    rows.append(
        [
            sg.Text(
                "加入卡牌（按分类选择）",
                font=FONT_BODY_BOLD,
                text_color=COLOR_INK,
            )
        ]
    )
    tree_data = sg.TreeData()
    _populate_card_tree(
        tree_data, session.registry.get_catalog(character_id)
    )
    rows.append(
        [
            sg.Tree(
                tree_data,
                headings=["类型", "费用"],
                key=_DBG_TREE_KEY,
                num_rows=10,
                col0_width=18,
                def_col_width=8,
                auto_size_columns=False,
                justification="left",
                enable_events=True,
                font=FONT_BODY,
            )
        ]
    )
    rows.append(
        [
            sg.Text(
                "选中卡牌：",
                key=_DBG_CARD_INFO_KEY,
                font=FONT_BODY,
                text_color=COLOR_MUTED,
                size=(50, 2),
            )
        ]
    )
    rows.append(
        [
            sg.Text("数量", font=FONT_BODY),
            sg.Input("1", key="-DBG-COUNT-", size=(4, 1), font=FONT_BODY),
            sg.Button("加入卡牌", key=_DBG_ADD, font=FONT_BODY_BOLD),
        ]
    )
    rows.append(
        [
            sg.Button("应用修改", key=_DBG_APPLY),
            sg.Button("关闭", key=_DBG_CLOSE),
        ]
    )

    window = sg.Window(
        "调试控制台",
        rows,
        finalize=True,
        keep_on_top=True,
        modal=False,
        background_color=COLOR_PAPER,
        margins=(12, 10),
        element_justification="left",
    )
    session.debug_tool_window = window
    append_log(session, "调试控制台已打开（/tool）")


def poll_debug_tool(session) -> None:
    """Give the console one non-blocking event-loop slice."""
    window = getattr(session, "debug_tool_window", None)
    if window is None:
        return
    try:
        event, values = window.read(timeout=50)
    except Exception:
        close_debug_tool(session)
        return
    if event in (sg.WIN_CLOSED, _DBG_CLOSE, None):
        close_debug_tool(session)
        return
    if event == _DBG_TREE_KEY:
        _update_debug_card_info(session, values)
    elif event == _DBG_APPLY:
        _apply_debug_values(session, values)
    elif event == _DBG_ADD:
        _add_debug_card(session, values)


def _populate_card_tree(tree_data, cards) -> None:
    """Group cards by category and insert them under category nodes."""
    grouped: dict[str, list] = {}
    for card in cards:
        if card.card_id == 0:
            continue
        card_type = (
            "插入物"
            if card.card_id in (49, 50)
            else (card.card_type or "其他")
        )
        grouped.setdefault(card_type, []).append(card)

    def insert_category(category: str, items) -> None:
        cat_key = f"-DBG-CAT-{category}-"
        tree_data.Insert("", cat_key, category, ["", ""])
        for card in sorted(items, key=lambda item: item.card_id):
            cost = "X" if card.cost is None else str(card.cost)
            tree_data.Insert(
                cat_key,
                f"{_CARD_ID_PREFIX}{card.card_id}-",
                card.name,
                [category, cost],
            )

    for category in _CATEGORY_ORDER:
        items = grouped.pop(category, None)
        if items:
            insert_category(category, items)
    for category, items in grouped.items():
        insert_category(category, items)


def _selected_card_id(session, values) -> int | None:
    selected = values.get(_DBG_TREE_KEY, "")
    if isinstance(selected, (list, tuple)):
        selected = selected[0] if selected else ""
    if not isinstance(selected, str) or not selected.startswith(_CARD_ID_PREFIX):
        # FreeSimpleGUI 5.1 的 Tree 不把选中项写入 values，兜底读组件选中行。
        try:
            element = session.debug_tool_window[_DBG_TREE_KEY]
            rows = getattr(element, "SelectedRows", None)
            selected = rows[0] if rows else ""
        except Exception:
            selected = ""
    if not isinstance(selected, str) or not selected.startswith(_CARD_ID_PREFIX):
        return None
    try:
        return int(selected.removeprefix(_CARD_ID_PREFIX).removesuffix("-"))
    except ValueError:
        return None


def _update_debug_card_info(session, values) -> None:
    card_id = _selected_card_id(session, values)
    if card_id is None:
        return
    definition = session.registry.get_card(
        session.state.local_character_id, card_id
    )
    cost = "X" if definition.cost is None else str(definition.cost)
    text = (
        f"{definition.name} · {definition.card_type} · 费用{cost}\n"
        f"{definition.description}"
    )
    try:
        session.debug_tool_window[_DBG_CARD_INFO_KEY].update(text)
    except Exception:
        pass


def close_debug_tool(session) -> None:
    window = getattr(session, "debug_tool_window", None)
    if window is None:
        return
    session.debug_tool_window = None
    try:
        window.close()
    except Exception:
        pass


def _apply_debug_values(session, values) -> None:
    player = session.state.local_player
    data = player.character_data
    changes = []
    for label, attr in (
        ("生命", "health"),
        ("能量", "energy"),
        ("力量", "strength"),
        ("毒", "poison"),
    ):
        new = _parse_int(values.get(f"-DBG-{label}-"))
        if new is not None and new != getattr(player, attr):
            setattr(player, attr, new)
            changes.append(f"{label}={new}")

    defence_value = _parse_int(values.get("-DBG-防御-"))
    if defence_value is not None:
        player.defences[:] = (
            [DefenceEffect(turns_remaining=1, amount=max(0, defence_value))]
            if defence_value
            else []
        )
        changes.append(f"防御={defence_value}")

    if data is not None:
        for field in dataclass_fields(data):
            value = getattr(data, field.name)
            if isinstance(value, int) and not isinstance(value, bool):
                new = _parse_int(values.get(f"-DBG-{field.name}-"))
                if new is not None and new != value:
                    setattr(data, field.name, new)
                    changes.append(f"{field.name}={new}")

    if changes:
        _broadcast_debug(
            session,
            f"调试：玩家{session.state.local_player_id}修改参数 "
            + "、".join(changes),
        )
    _refresh_after_debug(session)
    _refresh_tool_values(session)


def _add_debug_card(session, values) -> None:
    card_id = _selected_card_id(session, values)
    if card_id is None:
        return
    count = max(1, min(_parse_int(values.get("-DBG-COUNT-")) or 1, 20))
    character_id = session.state.local_character_id
    definition = session.registry.get_card(character_id, card_id)
    player_id = session.state.local_player_id
    if definition.card_type == "生物":
        # 与真实生成一致：生物进入生物区（hand_creatures），不占手牌卡槽。
        from card_duel.cards.slugcat.creatures import add_hand_creature

        for _ in range(count):
            add_hand_creature(
                session.state, player_id, card_id, owner_id=player_id
            )
    else:
        for _ in range(count):
            session.state.hand_cards.append(card_id)
    _broadcast_debug(
        session,
        f"调试：玩家{session.state.local_player_id}加入卡牌 "
        f"{definition.name} ×{count}",
    )
    _refresh_after_debug(session)


def _refresh_after_debug(session) -> None:
    from card_duel.ui.network_view import refresh_cards, refresh_status

    window = session.require_window()
    refresh_status(
        session.state,
        window,
        session.registry,
        getattr(session, "status_snapshots", None),
    )
    refresh_cards(session.state, window, session.card_images)
    try:
        window.refresh()
    except Exception:
        pass


def _refresh_tool_values(session) -> None:
    window = getattr(session, "debug_tool_window", None)
    if window is None:
        return
    player = session.state.local_player
    updates = {
        "-DBG-生命-": player.health,
        "-DBG-能量-": player.energy,
        "-DBG-力量-": player.strength,
        "-DBG-毒-": player.poison,
        "-DBG-防御-": player.defence,
    }
    data = player.character_data
    if data is not None:
        for field in dataclass_fields(data):
            value = getattr(data, field.name)
            if isinstance(value, int) and not isinstance(value, bool):
                updates[f"-DBG-{field.name}-"] = value
    for key, value in updates.items():
        try:
            window[key].update(str(value))
        except Exception:
            continue


def _broadcast_debug(session, message: str) -> None:
    append_log(session, message)
    connection = getattr(session, "connection", None)
    if connection is None:
        return
    try:
        # 与 protocol.send_announcement 使用相同的公告消息类型。
        from card_duel.network.transport import send_json

        send_json(session.connection, {"type": "announcement", "message": message})
    except Exception:
        pass


def _parse_int(text) -> int | None:
    if text is None:
        return None
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None
