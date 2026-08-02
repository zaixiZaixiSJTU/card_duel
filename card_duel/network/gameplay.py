"""Shared active-turn workflow for the network server and client."""

import FreeSimpleGUI as sg

from card_duel.core.game import TurnEngine, TurnPhase
from card_duel.core.rules import draw_cards
from card_duel.network.protocol import (
    receive_pending_chat,
    send_announcement,
    send_chat_message,
    send_game_state,
)
from card_duel.ui.choices import GuiChoiceProvider
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

    turn = TurnEngine(game_state, round_number, player_id, announce)
    turn.register_phase_handler(
        TurnPhase.TURN_START,
        lambda context: session.combat.advance_turn_effects(
            context.player_id, context.announce
        ),
        priority=10,
    )
    turn.register_phase_handler(TurnPhase.DRAW, _draw_turn_cards)
    session.combat.register_turn_handlers(turn)

    # 回合开始时：结算持续效果与“回合开始时”能力。
    _enter_phase(session, turn, TurnPhase.TURN_START)

    # 抽牌阶段：执行标准抽牌及额外抽牌能力。
    _enter_phase(session, turn, TurnPhase.DRAW)
    refresh_cards(game_state, window, session.card_images)
    send_game_state(session)

    # 出牌阶段：仅在此阶段接受卡牌输入。
    _enter_phase(session, turn, TurnPhase.PLAY)
    if not _run_card_play_phase(session, player_id, turn.opponent_id, announce):
        return False

    # 弃牌阶段：将手牌整理至上限后才能继续。
    _enter_phase(session, turn, TurnPhase.DISCARD)
    if not _run_discard_phase(session, announce):
        return False

    # 回合结束时：为结束触发效果保留统一判定点。
    _enter_phase(session, turn, TurnPhase.TURN_END)
    print(" [你的回合结束]")
    refresh_cards(game_state, window, session.card_images)
    set_cards_enabled(window, False)
    return True


def _enter_phase(session, turn, phase):
    set_phase(
        session.require_window(),
        f"回合 {turn.round_number} - {phase.value}",
    )
    return turn.enter_phase(phase)


def _draw_turn_cards(context):
    draw_cards(context.game_state, 3)


def _run_card_play_phase(session, player_id, opponent_id, announce):
    game_state = session.state
    window = session.require_window()
    set_cards_enabled(window, True)
    choices = GuiChoiceProvider(session.card_images)
    while True:
        event, values = window.read(timeout=120)
        if event == sg.WIN_CLOSED:
            return False
        if event == CHAT_SEND_KEY:
            send_chat_message(session, values.get(CHAT_INPUT_KEY, ""))
            continue

        receive_pending_chat(session)
        if event == "-btn1-":
            return True
        if not isinstance(event, str) or not event.startswith("-BTN"):
            continue

        hand_index = int(event.removeprefix("-BTN").removesuffix("-"))
        if hand_index >= len(game_state.hand_cards):
            continue
        card_id = game_state.hand_cards[hand_index]
        character_id = game_state.character_ids[player_id]
        definition = session.registry.get_card(character_id, card_id)
        if session.registry.play(
            state=game_state,
            character_id=character_id,
            card_id=card_id,
            source_player_id=player_id,
            target_player_id=opponent_id,
            announce=announce,
            choices=choices,
            combat=session.combat,
        ):
            if not definition.exhausted:
                game_state.draw_pile.append(card_id)
            game_state.hand_cards.pop(hand_index)
            refresh_cards(game_state, window, session.card_images)
            send_game_state(session)


def _run_discard_phase(session, announce):
    game_state = session.state
    window = session.require_window()
    announce(" ---------------------------------------------------- ")
    announce(" [弃牌阶段]")

    excess_cards = max(0, game_state.hand_size - HAND_LIMIT)
    announce(f"需要弃牌:{excess_cards}" if excess_cards else "无需弃牌")

    while game_state.hand_size > 0:
        event, values = window.read(timeout=120)
        if event == sg.WIN_CLOSED:
            return False
        if event == CHAT_SEND_KEY:
            send_chat_message(session, values.get(CHAT_INPUT_KEY, ""))
            continue

        receive_pending_chat(session)
        if event == "-btn1-" and game_state.hand_size <= HAND_LIMIT:
            return True
        if not isinstance(event, str) or not event.startswith("-BTN"):
            continue

        hand_index = int(event.removeprefix("-BTN").removesuffix("-"))
        if hand_index >= len(game_state.hand_cards):
            continue
        game_state.draw_pile.append(game_state.hand_cards.pop(hand_index))
        refresh_cards(game_state, window, session.card_images)

    return True
