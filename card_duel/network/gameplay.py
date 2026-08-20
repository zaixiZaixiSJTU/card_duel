"""Shared active-turn workflow for the network server and client."""

from contextlib import suppress

import FreeSimpleGUI as sg

from card_duel.core.game import TurnEngine, TurnPhase
from card_duel.core.rules import draw_cards
from card_duel.network.protocol import (
    receive_pending_chat,
    send_announcement,
    send_card_played,
    send_chat_message,
    send_game_state,
)
from card_duel.ui.auxiliary_windows import read_primary_window
from card_duel.ui.card_animations import (
    animate_card_action,
    animate_hand_additions,
)
from card_duel.ui.card_interaction import clear_armed_card, route_hand_card_event
from card_duel.ui.choices import GuiChoiceProvider
from card_duel.ui.debug_tool import handle_chat_command
from card_duel.ui.network_log import append_log
from card_duel.ui.network_style import CHAT_INPUT_KEY, CHAT_SEND_KEY
from card_duel.ui.network_view import (
    refresh_cards,
    set_cards_enabled,
    set_phase,
)

HAND_LIMIT = 4


def play_active_turn(session, player_id, round_number):
    """Run one local turn through all five timing phases."""

    game_state = session.state
    window = session.require_window()

    def announce(message):
        send_announcement(session, message)

    character_name = session.registry.get_character(
        game_state.character_ids[player_id]
    ).name
    announce(f" [轮到玩家{player_id} ({character_name})]")

    choices = GuiChoiceProvider(session.card_images)
    turn = TurnEngine(
        game_state,
        round_number,
        player_id,
        announce,
        choices=choices,
        private_announce=lambda message: append_log(session, message),
    )
    turn.register_phase_handler(
        TurnPhase.TURN_START,
        lambda context: session.combat.advance_turn_effects(
            context.player_id, context.announce
        ),
        priority=10,
    )
    turn.register_phase_handler(
        TurnPhase.DRAW,
        lambda context: _draw_turn_cards(
            context, local_announce=lambda message: append_log(session, message)
        ),
    )
    session.combat.register_turn_handlers(turn)

    # 回合开始时：结算持续效果与“回合开始时”能力。
    _enter_phase(session, turn, TurnPhase.TURN_START)

    # 抽牌阶段：执行标准抽牌及额外抽牌能力。
    hand_before_draw = list(game_state.hand_cards)
    _enter_phase(session, turn, TurnPhase.DRAW)
    refresh_cards(game_state, window, session.card_images)
    animate_hand_additions(session, hand_before_draw)
    send_game_state(session)

    # 出牌阶段：仅在此阶段接受卡牌输入。
    _enter_phase(session, turn, TurnPhase.PLAY)
    if not _run_card_play_phase(
        session, player_id, turn.opponent_id, announce, choices
    ):
        return False

    # 弃牌阶段：将手牌整理至上限后才能继续。
    _enter_phase(session, turn, TurnPhase.DISCARD)
    if not _run_discard_phase(session, announce):
        return False

    # 回合结束时：为结束触发效果保留统一判定点。
    _enter_phase(session, turn, TurnPhase.TURN_END)
    append_log(session, " [你的回合结束]")
    refresh_cards(game_state, window, session.card_images)
    set_cards_enabled(window, False)
    # End-phase effects mutate health, agility, creatures, and inserted items.
    # Synchronize those values before handing control to the peer.
    send_game_state(session)
    return True


def _enter_phase(session, turn, phase):
    set_phase(
        session.require_window(),
        f"回合 {turn.round_number} - {phase.value}",
    )
    return turn.enter_phase(phase)


def _draw_turn_cards(context, local_announce=None):
    if context.game_state.character_ids.get(context.player_id) == 4:
        _draw_slugcat_cards(
            context.game_state,
            2,
            1,
            local_announce or context.announce,
        )
    else:
        draw_cards(context.game_state, 3)


def _draw_slugcat_cards(game_state, skill_count, item_count, announce):
    """Draw by type without ever actively drawing creature cards."""
    from card_duel.cards.slugcat.specs import SLUGCAT_SPECS_BY_ID

    drawn = []

    def draw_type(card_type, amount):
        for _ in range(amount):
            index = next(
                (
                    index
                    for index, card_id in enumerate(game_state.draw_pile)
                    if SLUGCAT_SPECS_BY_ID[card_id].card_type == card_type
                ),
                None,
            )
            if index is None:
                break
            drawn.append(game_state.draw_pile.pop(index))

    draw_type("技能", skill_count)
    draw_type("物品", item_count)
    while len(drawn) < skill_count + item_count:
        index = next(
            (
                index
                for index, card_id in enumerate(game_state.draw_pile)
                if SLUGCAT_SPECS_BY_ID[card_id].card_type not in {"生物", "见闻"}
            ),
            None,
        )
        if index is None:
            break
        drawn.append(game_state.draw_pile.pop(index))
    game_state.hand_cards.extend(drawn)
    if drawn:
        names = "、".join(SLUGCAT_SPECS_BY_ID[card_id].name for card_id in drawn)
        announce(f"抽牌：{names}")
    return len(drawn)


def _run_card_play_phase(session, player_id, opponent_id, announce, choices):
    game_state = session.state
    window = session.require_window()
    clear_armed_card(session)
    set_cards_enabled(window, True)
    while True:
        event, values = read_primary_window(session)
        if event == sg.WIN_CLOSED:
            return False
        if event == CHAT_SEND_KEY:
            text = values.get(CHAT_INPUT_KEY, "")
            if not handle_chat_command(session, text):
                send_chat_message(session, text)
            continue
        receive_pending_chat(session)
        if event == "-btn1-":
            return True
        routed = route_hand_card_event(session, event)
        if routed is None:
            continue
        if routed[0] == "confirmed_creature":
            creatures = [
                item
                for item in game_state.local_player.statuses.hand_creatures
                if item.card_id != 26
            ]
            creature_index = routed[1]
            if creature_index >= len(creatures):
                continue
            card_id = creatures[creature_index].card_id
            character_id = game_state.character_ids[player_id]
            if session.registry.play(
                state=game_state,
                character_id=character_id,
                card_id=card_id,
                source_player_id=player_id,
                target_player_id=opponent_id,
                announce=announce,
                choices=choices,
                combat=session.combat,
                private_announce=lambda message: append_log(session, message),
            ):
                send_card_played(session, player_id, character_id, card_id)
                clear_armed_card(session)
                refresh_cards(game_state, window, session.card_images)
                send_game_state(session)
            continue
        if routed[0] != "confirmed":
            continue
        hand_index = routed[1]
        if hand_index >= len(game_state.hand_cards):
            continue
        card_id = game_state.hand_cards[hand_index]
        character_id = game_state.character_ids[player_id]
        definition = session.registry.get_card(character_id, card_id)
        hand_before_play = list(game_state.hand_cards)
        if session.registry.play(
            state=game_state,
            character_id=character_id,
            card_id=card_id,
            source_player_id=player_id,
            target_player_id=opponent_id,
            announce=announce,
            choices=choices,
            combat=session.combat,
            private_announce=lambda message: append_log(session, message),
        ):
            send_card_played(session, player_id, character_id, card_id)
            clear_armed_card(session)
            animate_card_action(session, hand_index, "play")
            if not definition.exhausted:
                _return_card_after_use(game_state, player_id, card_id)
            _remove_played_card(game_state, hand_index, card_id)
            refresh_cards(game_state, window, session.card_images)
            with suppress(ValueError):
                hand_before_play.remove(card_id)
            animate_hand_additions(session, hand_before_play)
            send_game_state(session)


def _remove_played_card(game_state, original_index, card_id):
    if (
        original_index < len(game_state.hand_cards)
        and game_state.hand_cards[original_index] == card_id
    ):
        game_state.hand_cards.pop(original_index)
        return
    with suppress(ValueError):
        game_state.hand_cards.remove(card_id)


def _return_card_after_use(game_state, player_id, card_id):
    from card_duel.cards.slugcat.specs import SLUGCAT_DISCOVERY_IDS
    from card_duel.cards.slugcat.state import SlugcatData, slugcat_data

    player = game_state.players[player_id]
    if card_id in SLUGCAT_DISCOVERY_IDS and isinstance(
        player.character_data, SlugcatData
    ):
        slugcat_data(player).discovery_pool.append(card_id)
    else:
        game_state.discard_pile.append(card_id)


def _run_discard_phase(session, announce):
    game_state = session.state
    window = session.require_window()
    clear_armed_card(session)
    announce(" ---------------------------------------------------- ")
    announce(" [弃牌阶段]")

    player_id = game_state.local_player_id
    excess_cards = max(0, _effective_hand_size(game_state, player_id) - HAND_LIMIT)
    announce(f"需要弃牌:{excess_cards}" if excess_cards else "无需弃牌")

    while game_state.hand_size > 0:
        event, values = read_primary_window(session)
        if event == sg.WIN_CLOSED:
            return False
        if event == CHAT_SEND_KEY:
            text = values.get(CHAT_INPUT_KEY, "")
            if not handle_chat_command(session, text):
                send_chat_message(session, text)
            continue
        receive_pending_chat(session)
        if (
            event == "-btn1-"
            and _effective_hand_size(game_state, player_id) <= HAND_LIMIT
        ):
            return True
        routed = route_hand_card_event(session, event)
        if routed is None or routed[0] != "confirmed":
            continue
        hand_index = routed[1]
        if hand_index >= len(game_state.hand_cards):
            continue
        card_id = game_state.hand_cards[hand_index]
        if not _can_discard(game_state, player_id, card_id):
            announce("生物牌和插入物不可弃置")
            continue
        clear_armed_card(session)
        animate_card_action(session, hand_index, "discard")
        game_state.hand_cards.pop(hand_index)
        _return_card_after_use(game_state, player_id, card_id)
        refresh_cards(game_state, window, session.card_images)

    return True


def _effective_hand_size(game_state, player_id):
    if game_state.character_ids.get(player_id) != 4:
        return game_state.hand_size
    from card_duel.cards.slugcat.hand import effective_hand_size

    return effective_hand_size(game_state, player_id)


def _can_discard(game_state, player_id, card_id):
    if game_state.character_ids.get(player_id) != 4:
        return card_id not in (49, 50)
    from card_duel.cards.slugcat.specs import SLUGCAT_NO_DISCARD_IDS

    return card_id not in SLUGCAT_NO_DISCARD_IDS
