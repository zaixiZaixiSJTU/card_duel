"""Button-opened, non-blocking viewer for the opponent's creatures."""

from __future__ import annotations

import FreeSimpleGUI as sg

from card_duel.ui.network_style import (
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    OPPONENT_CREATURE_SLOTS,
)

OPPONENT_VIEW_KEY = "-OPP-VIEW-"
_CARD_PREFIX = "-OPP-CARD-"
_CLOSE_KEY = "-OPP-CLOSE-"
_RIGHT_SUFFIX = " RIGHT"


def open_opponent_viewer(session) -> None:
    """Open a fresh non-blocking window showing the opponent's creatures."""
    close_opponent_viewer(session)
    rows = [
        [
            sg.Text(
                "对方生物",
                font=FONT_HEADING,
                text_color=COLOR_INK,
            )
        ],
        [
            sg.Text(
                "手牌生物 + 威胁生物 · 右键卡片可放大预览",
                font=FONT_BODY,
                text_color=COLOR_MUTED,
            )
        ],
    ]
    for slot in range(OPPONENT_CREATURE_SLOTS):
        rows.append(
            [
                sg.Button(
                    image_data=None,
                    key=f"{_CARD_PREFIX}{slot}-",
                    visible=False,
                    border_width=2,
                    button_color=(COLOR_PAPER, COLOR_PAPER),
                    pad=(6, 3),
                )
            ]
        )
    rows.append(
        [
            sg.Button(
                "关闭",
                key=_CLOSE_KEY,
                font=FONT_BODY_BOLD,
            )
        ]
    )
    window = sg.Window(
        "对方生物",
        rows,
        finalize=True,
        keep_on_top=True,
        modal=False,
        background_color=COLOR_PAPER,
        margins=(10, 8),
        element_justification="center",
    )
    for slot in range(OPPONENT_CREATURE_SLOTS):
        try:
            window[f"{_CARD_PREFIX}{slot}-"].bind("<Button-3>", _RIGHT_SUFFIX)
        except Exception:
            continue
    session.opponent_viewer_window = window
    _refresh_opponent_viewer(session)


def poll_opponent_viewer(session) -> None:
    """Give the viewer one non-blocking event-loop slice."""
    window = getattr(session, "opponent_viewer_window", None)
    if window is None:
        return
    try:
        event, _values = window.read(timeout=50)
    except Exception:
        close_opponent_viewer(session)
        return
    if event in (sg.WIN_CLOSED, _CLOSE_KEY, None):
        close_opponent_viewer(session)
        return
    if isinstance(event, str) and event.startswith(_CARD_PREFIX):
        preview = event.endswith(_RIGHT_SUFFIX)
        key = event[: -len(_RIGHT_SUFFIX)] if preview else event
        try:
            slot = int(key.removeprefix(_CARD_PREFIX).removesuffix("-"))
        except ValueError:
            slot = -1
        if preview and 0 <= slot < OPPONENT_CREATURE_SLOTS:
            _preview_opponent_creature(session, slot)
    _refresh_opponent_viewer(session)


def close_opponent_viewer(session) -> None:
    window = getattr(session, "opponent_viewer_window", None)
    if window is None:
        return
    session.opponent_viewer_window = None
    try:
        window.close()
    except Exception:
        pass


def _refresh_opponent_viewer(session) -> None:
    window = getattr(session, "opponent_viewer_window", None)
    if window is None:
        return
    from card_duel.cards.catalog import DEFAULT_REGISTRY
    from card_duel.core.resources import render_card

    creatures = _opponent_creatures(session)
    opponent_id = session.state.opponent_character_id
    for slot in range(OPPONENT_CREATURE_SLOTS):
        key = f"{_CARD_PREFIX}{slot}-"
        if slot >= len(creatures):
            try:
                window[key].update(visible=False)
            except Exception:
                pass
            continue
        creature = creatures[slot]
        definition = DEFAULT_REGISTRY.get_card(
            opponent_id, creature.card_id
        )
        outline = (
            "#C86655" if creature.card_id == 22 and creature.shell
            else "#000000" if creature.card_id == 22
            else "#C39A55"
        )
        image_data = render_card(
            definition, creature_health=creature.health, outline=outline
        )
        try:
            window[key].update(image_data=image_data, visible=True)
        except Exception:
            pass


def _opponent_creatures(session):
    """Pure data helper: opponent hand creatures followed by threats."""
    state = session.state
    if state.opponent_character_id is None:
        return []
    return (
        list(state.opponent_player.statuses.hand_creatures)
        + list(state.opponent_player.statuses.creature_threats)
    )


def _preview_opponent_creature(session, slot: int) -> None:
    creatures = _opponent_creatures(session)
    if slot >= len(creatures):
        return
    from card_duel.cards.catalog import DEFAULT_REGISTRY
    from card_duel.core.resources import render_card
    from card_duel.ui.card_interaction import open_card_preview

    creature = creatures[slot]
    definition = DEFAULT_REGISTRY.get_card(
        session.state.opponent_character_id, creature.card_id
    )
    outline = (
        "#C86655" if creature.card_id == 22 and creature.shell
        else "#000000" if creature.card_id == 22
        else "#C39A55"
    )
    open_card_preview(
        session,
        render_card(
            definition, creature_health=creature.health, outline=outline
        ),
    )
