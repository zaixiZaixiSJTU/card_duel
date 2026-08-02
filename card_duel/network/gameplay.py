"""Shared active-turn workflow for the network server and client."""

import FreeSimpleGUI as sg

from card_duel.cards.registry import (
    get_card_definition,
    play_registered_card,
)
from card_duel.cards.slugcat import register_slugcat_phase_handlers
from card_duel.core.combat import (
    CHARACTERS,
    advance_turn_effects,
    apply_damage,
    draw_cards,
)
from card_duel.core.game import TurnEngine, TurnPhase
from card_duel.network.protocol import (
    receive_pending_chat,
    send_announcement,
    send_chat_message,
    send_game_state,
    send_played_card,
)
from card_duel.ui.network import (
    CHAT_INPUT_KEY,
    CHAT_SEND_KEY,
    COLOR_GOLD,
    COLOR_GREEN,
    COLOR_HIGHLIGHT,
    COLOR_MUTED,
    COLOR_PAPER,
    REFRESH_HAND_KEY,
    colored_announce,
    disarm_card,
    flash_hand_card,
    mark_hand_card_selected,
    open_deck_viewer,
    poll_deck_viewer,
    refresh_cards,
    refresh_status,
    route_card_event,
    set_cards_enabled,
    set_mode_hint,
    set_phase,
    show_played_card,
)

HAND_LIMIT = 4
BTN_FINISH_TEXT = "完成当前阶段  →"
BTN_CONFIRM_TEXT = "确认弃牌"


def play_active_turn(game_state, player_id, round_number):
    """Run one local turn through all five timing phases."""

    def announce(message):
        send_announcement(game_state, message)

    character_name = CHARACTERS[game_state.character_ids[player_id]]
    announce(f" [轮到玩家{player_id} ({character_name})]")

    turn = TurnEngine(game_state, round_number, player_id, announce)
    turn.register_phase_handler(
        TurnPhase.TURN_START, _resolve_turn_start_effects, priority=10
    )
    turn.register_phase_handler(
        TurnPhase.TURN_START, _apply_heartlink_damage, priority=20
    )
    turn.register_phase_handler(TurnPhase.DRAW, _draw_turn_cards)
    turn.register_phase_handler(
        TurnPhase.TURN_END, _resolve_inserted_items_all, priority=10
    )
    register_slugcat_phase_handlers(turn)

    # 回合开始时：结算持续效果与“回合开始时”能力。
    _enter_phase(turn, TurnPhase.TURN_START)

    # 抽牌阶段：执行标准抽牌及额外抽牌能力。
    _enter_phase(turn, TurnPhase.DRAW)
    refresh_cards(game_state)
    send_game_state(game_state)

    # 出牌阶段：仅在此阶段接受卡牌输入。
    _enter_phase(turn, TurnPhase.PLAY)
    if not _run_card_play_phase(
        game_state, player_id, turn.opponent_id, announce
    ):
        return False

    # 弃牌阶段：将手牌整理至上限后才能继续。
    _enter_phase(turn, TurnPhase.DISCARD)
    if not _run_discard_phase(game_state, announce):
        return False

    # 回合结束时：为结束触发效果保留统一判定点。
    _enter_phase(turn, TurnPhase.TURN_END)
    colored_announce(game_state, " [你的回合结束]")
    refresh_cards(game_state)
    set_cards_enabled(game_state, False)
    return True


def _enter_phase(turn, phase):
    set_phase(
        turn.game_state,
        f"回合 {turn.round_number} - {phase.value}",
    )
    return turn.enter_phase(phase)


def _resolve_turn_start_effects(context):
    advance_turn_effects(
        context.game_state,
        context.player_id,
        context.announce,
    )


def _resolve_inserted_items_all(context):
    """回合结束结算插入物流血——非蛞蝓猫角色由这里处理。

    蛞蝓猫的插入物结算在其自身 ``_on_turn_end`` 中（priority=30），
    这里只处理其他角色（如战士被插入钢筋/电矛后回合结束扣血）。
    """
    game_state = context.game_state
    player_id = context.player_id
    if game_state.character_ids.get(player_id) == 4:
        return  # 蛞蝓猫有自己的 _on_turn_end 处理
    from card_duel.cards.slugcat import _resolve_inserted_items
    _resolve_inserted_items(game_state, player_id, context.announce)


def _draw_turn_cards(context):
    game_state = context.game_state
    player_id = context.player_id
    if game_state.character_ids.get(player_id) == 4:
        _draw_slugcat_cards(game_state, 2, 1, context.announce)
    else:
        draw_cards(game_state, 3)


def _draw_slugcat_cards(game_state, skill_count, item_count, announce):
    """Draw ``skill_count`` skill cards + ``item_count`` item cards for Slugcat.

    Cards are picked from ``game_state.draw_pile`` and removed in-place.  When
    a category is exhausted the remaining quota is filled with whatever comes
    first so the player always receives the maximum cards possible.
    """
    from card_duel.cards.slugcat_data import SLUGCAT_SPECS_BY_ID

    pile = game_state.draw_pile
    drawn = []

    def _pick(predicate, remaining):
        """Pop up to ``remaining`` cards matching ``predicate``."""
        picks = []
        for idx in range(len(pile) - 1, -1, -1):
            if remaining <= 0:
                break
            card_id = pile[idx]
            spec = SLUGCAT_SPECS_BY_ID.get(card_id)
            if spec is not None and predicate(spec):
                picks.append(pile.pop(idx))
                remaining -= 1
        return picks

    drawn.extend(
        _pick(lambda s: s.card_type == "技能", skill_count)
    )
    drawn.extend(
        _pick(lambda s: s.card_type == "物品", item_count)
    )
    # Fill any shortfall with non-creature cards from the top of the deck.
    from card_duel.cards.slugcat_data import SLUGCAT_CREATURE_IDS

    remaining = (skill_count + item_count) - len(drawn)
    skipped = []
    for _ in range(remaining):
        while pile:
            card_id = pile.pop(0)
            if card_id in SLUGCAT_CREATURE_IDS:
                skipped.append(card_id)
                continue
            drawn.append(card_id)
            break
        if not pile and len(drawn) < (skill_count + item_count):
            break
    pile.extend(skipped)

    # Apply drawn cards to hand in the sorted order (skills first, items,
    # then leftovers) so the hand looks consistent.
    from card_duel.core import combat

    names = []
    for card_id in drawn:
        if combat.add_card_to_hand(game_state, card_id):
            spec = SLUGCAT_SPECS_BY_ID.get(card_id)
            names.append(spec.name if spec else f"#{card_id}")
    if names:
        # Drawn card names are private hand info: show only on the owner's
        # log, do NOT broadcast to the peer via announce().
        from card_duel.ui.network import colored_announce

        colored_announce(game_state, "抽牌：" + "、".join(names))


def _apply_heartlink_damage(context):
    game_state = context.game_state
    player_id = context.player_id
    heartlink_damage = game_state.players[player_id].special["heartlink"]
    if not heartlink_damage:
        return

    context.announce(f"心连心，爱你哦(-{heartlink_damage})")
    apply_damage(
        game_state, heartlink_damage, player_id, announce=context.announce
    )
    sacrifice_layers = game_state.players[player_id].special["sacrifice"]
    if sacrifice_layers:
        draw_cards(game_state, heartlink_damage * sacrifice_layers)
    apply_damage(
        game_state,
        heartlink_damage,
        context.opponent_id,
        announce=context.announce,
    )


def _pump_common_events(game_state, event, values):
    """Handle events shared by every active phase loop.

    Returns True when the event was consumed here (chat, deck viewer, etc.).
    """
    if event == CHAT_SEND_KEY:
        send_chat_message(game_state, values.get(CHAT_INPUT_KEY, ""))
        return True
    if event == "-DECK-VIEW-":
        open_deck_viewer(game_state)
        return True
    if event == REFRESH_HAND_KEY:
        refresh_cards(game_state)
        refresh_status(game_state)
        game_state.window.refresh()
        return True
    poll_deck_viewer(game_state)
    receive_pending_chat(game_state)
    return False


def _run_card_play_phase(game_state, player_id, opponent_id, announce):
    set_cards_enabled(game_state, True)
    set_mode_hint(
        game_state,
        "出牌阶段 · 左键双击或右键预览后选牌",
        COLOR_GREEN,
    )

    def on_select(hand_index):
        card_id = game_state.hand_cards[hand_index]
        if card_id in (0, -1):
            return False
        character_id = game_state.character_ids[player_id]
        definition = get_card_definition(character_id, card_id)
        if not play_registered_card(
            game_state,
            character_id,
            card_id,
            player_id,
            opponent_id,
            announce,
        ):
            return False
        if not definition.exhausted:
            game_state.draw_pile.append(card_id)
        game_state.hand_cards[hand_index] = -1
        refresh_cards(game_state)
        show_played_card(game_state, player_id, card_id)
        send_played_card(game_state, player_id, card_id)
        send_game_state(game_state)
        refresh_status(game_state)
        return True

    game_state.card_selection_callback = on_select
    try:
        while True:
            event, values = game_state.window.read(timeout=120)
            if event == sg.WIN_CLOSED:
                return False
            if _pump_common_events(game_state, event, values):
                continue
            if event == "-btn1-":
                disarm_card(game_state)
                return True
            route_card_event(game_state, event)
    finally:
        game_state.card_selection_callback = None
        disarm_card(game_state)


def _run_discard_phase(game_state, announce):
    announce(" ---------------------------------------------------- ")
    announce(" [弃牌阶段]")

    excess_cards = max(0, game_state.hand_size - HAND_LIMIT)
    announce(f"需要弃牌:{excess_cards}" if excess_cards else "无需弃牌")

    game_state.window["-btn1-"].update(
        disabled=False,
        button_color=(COLOR_PAPER, COLOR_GREEN),
    )
    _refresh_discard_hint(game_state)

    def on_select(hand_index):
        card_id = game_state.hand_cards[hand_index]
        if card_id in (0, -1):
            return False
        # 生物牌和插入物不能弃牌
        from card_duel.cards.slugcat_data import SLUGCAT_NO_DISCARD_IDS, SLUGCAT_INSERTED_IDS, SLUGCAT_CREATURE_IDS
        if card_id in SLUGCAT_NO_DISCARD_IDS:
            if card_id in SLUGCAT_INSERTED_IDS:
                announce("插入物无法弃牌——请打出它来拔出")
            elif card_id in SLUGCAT_CREATURE_IDS:
                announce("生物牌无法弃牌——请打出它或用其他方式处理")
            else:
                announce("此牌无法弃牌")
            return False
        flash_hand_card(game_state, hand_index, COLOR_HIGHLIGHT)
        game_state.draw_pile.append(card_id)
        game_state.hand_cards[hand_index] = -1
        game_state.hand_size -= 1
        refresh_cards(game_state)
        _refresh_discard_hint(game_state)
        return True

    game_state.card_selection_callback = on_select
    try:
        while game_state.hand_size > 0:
            event, values = game_state.window.read(timeout=120)
            if event == sg.WIN_CLOSED:
                return False
            if _pump_common_events(game_state, event, values):
                continue
            if event == "-btn1-" and game_state.hand_size <= HAND_LIMIT:
                disarm_card(game_state)
                set_mode_hint(game_state, "弃牌完成", COLOR_MUTED)
                return True
            route_card_event(game_state, event)
    finally:
        game_state.card_selection_callback = None
        disarm_card(game_state)
    return True


def _refresh_discard_hint(game_state):
    """Update the mode banner to show how many cards still need discarding."""
    excess = max(0, game_state.hand_size - HAND_LIMIT)
    if excess:
        set_mode_hint(
            game_state,
            f"弃牌阶段 · 还需弃 {excess} 张 · 左键双击或右键预览后弃置",
            COLOR_GOLD,
        )
    else:
        set_mode_hint(
            game_state,
            "弃牌阶段 · 手牌已达标 · 点击「完成当前阶段」继续",
            COLOR_GREEN,
        )


def select_hand_cards_in_place(game_state, prompt, exclude_id=None, max_count=None):
    """Let the user pick any number of hand cards in the main window.

    Used by card effects (e.g. 背包之神/燔祭) that previously opened a popup.
    Each card uses the unified gesture: left-click twice or right-click preview
    to toggle it in/out of the selected set. Returns the list of selected hand
    indexes, or None if cancelled.
    """
    selected = set()

    button = game_state.window["-btn1-"]
    button.update(
        text=BTN_CONFIRM_TEXT,
        disabled=False,
        button_color=(COLOR_PAPER, COLOR_GREEN),
    )

    def on_select(hand_index):
        card_id = game_state.hand_cards[hand_index]
        if card_id in (0, -1):
            return False
        if exclude_id is not None and card_id == exclude_id:
            return False
        if hand_index in selected:
            selected.discard(hand_index)
            mark_hand_card_selected(game_state, hand_index, False)
        else:
            if max_count is not None and len(selected) >= max_count:
                return False
            selected.add(hand_index)
            flash_hand_card(game_state, hand_index, COLOR_HIGHLIGHT)
            mark_hand_card_selected(game_state, hand_index, True)
        _refresh_effect_hint(game_state, prompt, len(selected), max_count)
        return True

    saved_callback = game_state.card_selection_callback
    game_state.card_selection_callback = on_select
    try:
        _refresh_effect_hint(game_state, prompt, 0, max_count)
        while True:
            event, values = game_state.window.read(timeout=120)
            if event == sg.WIN_CLOSED:
                return None
            if _pump_common_events(game_state, event, values):
                continue
            if event == "-btn1-":
                disarm_card(game_state)
                return sorted(selected)
            route_card_event(game_state, event)
    finally:
        game_state.card_selection_callback = saved_callback
        disarm_card(game_state)
        for index in list(selected):
            mark_hand_card_selected(game_state, index, False)
        button.update(text=BTN_FINISH_TEXT)


def _refresh_effect_hint(game_state, prompt, count, max_count):
    count_text = f"已选 {count}"
    if max_count is not None:
        count_text += f"/{max_count}"
    set_mode_hint(
        game_state,
        f"{prompt} · {count_text} · 左键双击或右键预览切换 / 点「确认弃牌」提交",
        COLOR_GOLD,
    )
