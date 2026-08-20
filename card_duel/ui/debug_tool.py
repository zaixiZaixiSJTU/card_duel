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
    FONT_HEADING,
)

_DBG_APPLY = "-DBG-APPLY-"
_DBG_ADD = "-DBG-ADD-"
_DBG_CLOSE = "-DBG-CLOSE-"


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
    card_options = [
        f"{card.card_id} {card.name}"
        for card in session.registry.get_catalog(character_id)
    ]
    rows.append(
        [
            sg.Text("加入卡牌", size=(10, 1), font=FONT_BODY),
            sg.Combo(
                card_options,
                default_value=card_options[0] if card_options else "",
                key="-DBG-CARD-",
                size=(28, 1),
                font=FONT_BODY,
                readonly=True,
            ),
            sg.Text("数量", size=(3, 1), font=FONT_BODY),
            sg.Input("1", key="-DBG-COUNT-", size=(4, 1), font=FONT_BODY),
        ]
    )
    rows.append(
        [
            sg.Button("应用修改", key=_DBG_APPLY),
            sg.Button("加入卡牌", key=_DBG_ADD),
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
    if event == _DBG_APPLY:
        _apply_debug_values(session, values)
    elif event == _DBG_ADD:
        _add_debug_card(session, values)


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
    selected = values.get("-DBG-CARD-", "")
    card_id = _parse_int(selected.split()[0]) if selected else None
    if card_id is None:
        return
    count = max(1, min(_parse_int(values.get("-DBG-COUNT-")) or 1, 20))
    character_id = session.state.local_character_id
    definition = session.registry.get_card(character_id, card_id)
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
