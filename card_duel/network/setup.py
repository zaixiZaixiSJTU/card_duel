"""Shared network-match setup used by host and client roles."""

from __future__ import annotations

import random
import select
from dataclasses import dataclass

import FreeSimpleGUI as sg

from card_duel.application.combat import CombatEngine
from card_duel.core.models import GameState
from card_duel.core.resources import load_character_images
from card_duel.core.rules import build_shuffled_deck
from card_duel.network.transport import receive_json, send_json
from card_duel.ui.card_interaction import bind_hand_card_events
from card_duel.ui.deck_viewer import bind_deck_viewer_events
from card_duel.ui.network import create_main_layout
from card_duel.ui.network_dialogs import character_select_dialog, waiting_dialog
from card_duel.ui.network_style import WINDOW_SIZE, WINDOW_TITLE
from card_duel.ui.network_view import refresh_cards
from card_duel.ui.room_dialog import (
    ROOM_CHAR_KEY,
    ROOM_CHAT_INPUT_KEY,
    ROOM_CHAT_LOG_KEY,
    ROOM_CHAT_SEND_KEY,
    ROOM_EXIT_KEY,
    ROOM_FIRST_GUEST_KEY,
    ROOM_NO_DMG_KEY,
    ROOM_FIRST_RANDOM_KEY,
    ROOM_RULES_INFO_KEY,
    ROOM_SEED_KEY,
    ROOM_START_KEY,
    build_room_window,
)


@dataclass(frozen=True)
class RoomConfig:
    host_character: int
    guest_character: int
    seed: int
    first_player_id: int
    round1_no_damage: bool


def apply_room_config(session, config: RoomConfig, local_player_id: int) -> None:
    session.state.character_ids[1] = config.host_character
    session.state.character_ids[2] = config.guest_character
    session.state.random_seed = config.seed
    session.state.first_player_id = config.first_player_id
    session.state.round1_no_damage = config.round1_no_damage


def exchange_character_choices(
    session, local_player_id: int, preselected: int | None = None
) -> bool:
    if preselected is not None:
        selected = str(preselected)
    else:
        selected = character_select_dialog(session.registry)
        if selected is None:
            return False

    peer_player_id = 2 if local_player_id == 1 else 1
    waiting_window = waiting_dialog("等待对方选择...")
    try:
        session.state.character_ids[local_player_id] = int(selected)
        send_json(
            session.connection,
            {"type": "character_choice", "character_id": int(selected)},
        )
        peer_choice = receive_json(session.connection.recv)
        if peer_choice.get("type") != "character_choice":
            raise ConnectionError("选角阶段收到非预期消息")
        session.state.character_ids[peer_player_id] = int(peer_choice["character_id"])
        return True
    finally:
        waiting_window.close()


def exchange_match_seed(
    session, local_player_id: int, *, is_host: bool, seed: int | None = None
) -> None:
    """Share one random seed so both endpoints deal identical decks."""
    if is_host:
        if seed is None:
            seed = random.randint(0, 2**31 - 1)
        session.state.random_seed = seed
        send_json(session.connection, {"type": "match_seed", "seed": seed})
        return
    message = receive_json(session.connection.recv)
    if message.get("type") != "match_seed":
        raise ConnectionError("选角阶段收到非预期消息")
    session.state.random_seed = int(message["seed"])


def prepare_game_window(session) -> bool:
    state = session.state
    session.combat.initialize_players()
    character_id = state.local_character_id
    if character_id is None:
        raise ValueError("本地角色尚未选择")

    session.card_images, session.max_card_id = load_character_images(
        character_id, session.registry
    )
    if not session.card_images:
        return False
    state.draw_pile = build_shuffled_deck(
        1,
        session.max_card_id,
        session.registry.get_deck_counts(character_id),
        random_seed=state.random_seed,
    )
    layout = create_main_layout(session.card_images, state.hand_cards)
    session.window = sg.Window(
        WINDOW_TITLE,
        layout,
        size=WINDOW_SIZE,
        font=("Microsoft YaHei", 10),
        finalize=True,
        resizable=True,
    )
    bind_hand_card_events(session.require_window())
    bind_deck_viewer_events(session.require_window())
    from card_duel.ui.app_settings import load_settings
    from card_duel.ui.sound import activate

    activate()

    load_settings(session)
    refresh_cards(state, session.require_window(), session.card_images)
    return True


def announce_winner(session, winner: int) -> None:
    """Append the result to the local log on both endpoints."""
    from card_duel.ui.network_log import append_log

    append_log(session, f"对局结束：玩家{winner}获胜！")


def announce_room_config(session) -> None:
    """Announce the applied room settings in the match log on both sides."""
    from card_duel.ui.network_log import append_log

    state = session.state
    registry = session.registry

    def character_name(player_id: int) -> str:
        character_id = state.character_ids.get(player_id)
        if character_id is None:
            return "?"
        return registry.get_character(character_id).name

    first = state.first_player_id or 1
    first_label = f"玩家{first}（{'主机' if first == 1 else '客机'}）"
    append_log(
        session,
        f"房间设置：主机玩家1={character_name(1)} · "
        f"客机玩家2={character_name(2)}",
    )
    append_log(
        session,
        f"先手：{first_label} · 随机种子：{state.random_seed}",
    )
    append_log(
        session,
        "第一回合先手方无法造成血量损失："
        + ("开启" if state.round1_no_damage else "关闭"),
    )


def _room_char_id(values) -> int | None:
    selected = values.get(ROOM_CHAR_KEY, "")
    try:
        return int(selected.split()[0])
    except (ValueError, IndexError):
        return None


def _room_append_chat(window, text: str) -> None:
    try:
        window[ROOM_CHAT_LOG_KEY].update(f"{text}\n", append=True)
    except Exception:
        pass


def _collect_host_rules(values) -> tuple[int, int, bool, str, str] | None:
    if values.get(ROOM_FIRST_GUEST_KEY):
        first_player_id, first_rule = 2, "guest"
    elif values.get(ROOM_FIRST_RANDOM_KEY):
        first_player_id, first_rule = random.choice((1, 2)), "random"
    else:
        first_player_id, first_rule = 1, "host"
    seed_text = (values.get(ROOM_SEED_KEY) or "").strip()
    if seed_text:
        try:
            seed = int(seed_text)
        except ValueError:
            return None
    else:
        seed = random.randint(0, 2**31 - 1)
    no_damage = bool(values.get(ROOM_NO_DMG_KEY, True))
    return seed, first_player_id, no_damage, first_rule, seed_text


def _format_host_rules(message) -> str:
    first = {1: "主机先手", 2: "客机先手"}.get(
        int(message.get("first_player_id", 1)), "随机"
    )
    no_dmg = "开启" if message.get("round1_no_damage") else "关闭"
    return f"先手：{first}\n种子：{message.get('seed')} · 第一回合无伤：{no_dmg}"


def room_phase(session, registry, *, is_host: bool) -> RoomConfig | None:
    """Room lobby: choose characters, chat, and apply host rules."""
    window = build_room_window(
        registry,
        is_host=is_host,
        first_player=getattr(session, "room_first_player", "random"),
        seed_text=getattr(session, "room_seed_text", ""),
        no_damage=getattr(session, "room_round1_no_damage", True),
    )
    host_config: dict | None = None
    original_timeout = session.connection.gettimeout()
    session.connection.settimeout(0.2)
    try:
        while True:
            event, values = window.read(timeout=50)
            # 每个 UI 轮询周期最多读一条房间消息；Windows 上 select 偶发
            # 重复可读，配合短超时避免 recv 永久阻塞。
            if select.select([session.connection], [], [], 0)[0]:
                try:
                    message = receive_json(session.connection.recv)
                except TimeoutError:
                    message = None
                if message is not None:
                    mtype = message.get("type")
                    if mtype == "room_chat":
                        _room_append_chat(
                            window, f"[对方] {message.get('message', '')}"
                        )
                    elif mtype == "room_start" and not is_host:
                        host_config = message
                        window[ROOM_START_KEY].update(disabled=False)
                        window[ROOM_RULES_INFO_KEY].update(
                            _format_host_rules(message)
                        )
                    elif mtype == "room_ready" and is_host:
                        if host_config is None:
                            continue
                        window.close()
                        return RoomConfig(
                            host_character=int(host_config["host_character"]),
                            guest_character=int(
                                message.get("guest_character", 0)
                            ),
                            seed=int(host_config["seed"]),
                            first_player_id=int(
                                host_config["first_player_id"]
                            ),
                            round1_no_damage=bool(
                                host_config.get("round1_no_damage", False)
                            ),
                        )
                    elif mtype == "room_exit":
                        window.close()
                        return None
            if event in (sg.WIN_CLOSED, ROOM_EXIT_KEY, None):
                try:
                    send_json(
                        session.connection, {"type": "room_exit"}
                    )
                except Exception:
                    pass
                window.close()
                return None
            if event == ROOM_CHAT_SEND_KEY:
                text = (values.get(ROOM_CHAT_INPUT_KEY) or "").strip()
                if text:
                    send_json(
                        session.connection,
                        {"type": "room_chat", "message": text},
                    )
                    _room_append_chat(window, f"[我] {text}")
                    window[ROOM_CHAT_INPUT_KEY].update("")
            if event == ROOM_START_KEY:
                if is_host:
                    character_id = _room_char_id(values)
                    if character_id is None:
                        continue
                    rules = _collect_host_rules(values)
                    if rules is None:
                        sg.popup("种子必须是整数（留空随机）", keep_on_top=True)
                        continue
                    seed, first_player_id, no_damage, first_rule, seed_text = rules
                    session.room_first_player = first_rule
                    session.room_seed_text = seed_text
                    session.room_round1_no_damage = no_damage
                    from card_duel.ui.app_settings import save_settings

                    save_settings(session)
                    host_config = {
                        "type": "room_start",
                        "host_character": character_id,
                        "seed": seed,
                        "first_player_id": first_player_id,
                        "round1_no_damage": no_damage,
                    }
                    send_json(session.connection, host_config)
                    window[ROOM_START_KEY].update(disabled=True)
                else:
                    if host_config is None:
                        continue
                    guest_character = _room_char_id(values)
                    if guest_character is None:
                        continue
                    send_json(
                        session.connection,
                        {
                            "type": "room_ready",
                            "guest_character": guest_character,
                        },
                    )
                    window[ROOM_START_KEY].update(disabled=True)
                    window.close()
                    return RoomConfig(
                        host_character=int(host_config["host_character"]),
                        guest_character=guest_character,
                        seed=int(host_config["seed"]),
                        first_player_id=int(host_config["first_player_id"]),
                        round1_no_damage=bool(
                            host_config.get("round1_no_damage", False)
                        ),
                    )
    finally:
        session.connection.settimeout(original_timeout)
        try:
            window.close()
        except Exception:
            pass


def ask_rematch(session, *, is_host: bool) -> bool:
    """Both players agree on a rematch before restarting."""
    if is_host:
        choice = sg.popup_yes_no(
            "再来一场？", title="对局结束", keep_on_top=True
        )
        if choice != "Yes":
            send_json(session.connection, {"type": "rematch", "choice": "no"})
            return False
        send_json(session.connection, {"type": "rematch", "choice": "yes"})
        message = receive_json(session.connection.recv)
        peer_yes = (
            message.get("type") == "rematch"
            and message.get("choice") == "yes"
        )
        if not peer_yes:
            sg.popup("对方选择退出", keep_on_top=True)
        return peer_yes

    message = receive_json(session.connection.recv)
    if message.get("type") != "rematch":
        raise ConnectionError("对局结束收到非预期消息")
    if message.get("choice") != "yes":
        sg.popup("对方选择退出", keep_on_top=True)
        return False
    choice = sg.popup_yes_no(
        "再来一场？", title="对局结束", keep_on_top=True
    )
    send_json(
        session.connection,
        {"type": "rematch", "choice": "yes" if choice == "Yes" else "no"},
    )
    return choice == "Yes"


def reset_for_rematch(session, local_player_id: int) -> None:
    """Reset the match state and window for a fresh game."""
    from card_duel.ui.auxiliary_windows import close_auxiliary_windows

    close_auxiliary_windows(session)
    if session.window is not None:
        try:
            session.window.close()
        except Exception:
            pass
    session.state = GameState(local_player_id=local_player_id)
    session.combat = CombatEngine(session.state, session.registry)
    session.window = None
    session.card_images = []
    session.max_card_id = 0
    session.armed_hand_index = None
    session.armed_creature_index = None
    session.deck_viewer_open = False
    session.deck_viewer_page = 0
    session.deck_viewer_signature = None
    session.deck_viewer_card_ids = []
    session.preview_window = None
    session.debug_tool_window = None
    session.opponent_viewer_window = None
    session.settings_window = None
    session.settings_color_snapshot = {}
    session.animation_windows = []
    session.animation_callbacks = []
    session.status_snapshots = {}
    session.log_history = []
