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
)
from card_duel.ui.network import (
    CHAT_INPUT_KEY,
    CHAT_SEND_KEY,
    refresh_cards,
    set_cards_enabled,
    set_phase,
)

HAND_LIMIT = 4


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
    print(" [你的回合结束]")
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


def _draw_turn_cards(context):
    draw_cards(context.game_state, 3)


def _apply_heartlink_damage(context):
    game_state = context.game_state
    player_id = context.player_id
    heartlink_damage = game_state.players[player_id].special["heartlink"]
    if not heartlink_damage:
        return

    context.announce(f"心连心，爱你哦(-{heartlink_damage})")
    apply_damage(game_state, heartlink_damage, player_id)
    sacrifice_layers = game_state.players[player_id].special["sacrifice"]
    if sacrifice_layers:
        draw_cards(game_state, heartlink_damage * sacrifice_layers)
    apply_damage(game_state, heartlink_damage, context.opponent_id)


def _run_card_play_phase(game_state, player_id, opponent_id, announce):
    set_cards_enabled(game_state, True)
    while True:
        event, values = game_state.window.read(timeout=120)
        if event == sg.WIN_CLOSED:
            return False
        if event == CHAT_SEND_KEY:
            send_chat_message(game_state, values.get(CHAT_INPUT_KEY, ""))
            continue

        receive_pending_chat(game_state)
        if event == "-btn1-":
            return True
        if not isinstance(event, str) or not event.startswith("-BTN"):
            continue

        hand_index = int(event.removeprefix("-BTN").removesuffix("-"))
        card_id = game_state.hand_cards[hand_index]
        character_id = game_state.character_ids[player_id]
        definition = get_card_definition(character_id, card_id)
        if play_registered_card(
            game_state,
            character_id,
            card_id,
            player_id,
            opponent_id,
            announce,
        ):
            if not definition.exhausted:
                game_state.draw_pile.append(card_id)
            game_state.hand_cards[hand_index] = -1
            refresh_cards(game_state)
            send_game_state(game_state)


def _run_discard_phase(game_state, announce):
    announce(" ---------------------------------------------------- ")
    announce(" [弃牌阶段]")

    excess_cards = max(0, game_state.hand_size - HAND_LIMIT)
    announce(f"需要弃牌:{excess_cards}" if excess_cards else "无需弃牌")

    while game_state.hand_size > 0:
        event, values = game_state.window.read(timeout=120)
        if event == sg.WIN_CLOSED:
            return False
        if event == CHAT_SEND_KEY:
            send_chat_message(game_state, values.get(CHAT_INPUT_KEY, ""))
            continue

        receive_pending_chat(game_state)
        if event == "-btn1-" and game_state.hand_size <= HAND_LIMIT:
            return True
        if not isinstance(event, str) or not event.startswith("-BTN"):
            continue

        hand_index = int(event.removeprefix("-BTN").removesuffix("-"))
        game_state.draw_pile.append(game_state.hand_cards[hand_index])
        game_state.hand_cards[hand_index] = -1
        game_state.hand_size -= 1
        refresh_cards(game_state)

    return True
