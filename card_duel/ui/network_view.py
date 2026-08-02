"""State-to-widget rendering for the network game."""

from card_duel.ui.network_style import (
    COLOR_BLUE,
    COLOR_DISABLED,
    COLOR_GREEN,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    COLOR_RED,
    MAX_ENERGY_ORBS,
    MAX_HAND_BUTTONS,
    MAX_HEALTH_DISPLAY,
    PHASE_LABELS,
)


def refresh_status(game_state, window, registry):
    local_player = game_state.players[game_state.local_player_id]
    opponent_player = game_state.players[game_state.opponent_player_id]
    _update_player_status(
        window,
        "MY",
        local_player,
        _format_character_status(game_state, game_state.local_player_id, registry),
    )
    _update_player_status(
        window,
        "EN",
        opponent_player,
        _format_character_status(game_state, game_state.opponent_player_id, registry),
    )
    window["-DECK-COUNT-"].update(str(len(game_state.draw_pile)))
    window["-HAND-COUNT-"].update(str(game_state.hand_size))
    window.refresh()


def _update_player_status(window, key_prefix, player, character_status=""):
    window[f"-{key_prefix}-HP-"].update(
        str(player.health),
        text_color=COLOR_RED if player.health <= 10 else COLOR_INK,
    )
    window[f"-{key_prefix}-EN-"].update(str(player.energy))
    window[f"-{key_prefix}-DEF-"].update(str(player.defence))
    window[f"-{key_prefix}-STR-"].update(str(player.strength))
    window[f"-{key_prefix}-HP-BAR-"].update(
        max(0, min(MAX_HEALTH_DISPLAY, player.health))
    )
    window[f"-{key_prefix}-ORB-"].update(_format_energy_orbs(player.energy))
    window[f"-{key_prefix}-SPECIAL-"].update(character_status)


def _format_character_status(game_state, player_id, registry):
    character_id = game_state.character_ids.get(player_id)
    if character_id is None:
        return ""
    return registry.get_character(character_id).rules.format_status(
        game_state.players[player_id]
    )


def refresh_cards(game_state, window, card_images):
    visible_count = min(len(game_state.hand_cards), MAX_HAND_BUTTONS)
    for hand_index, card_id in enumerate(game_state.hand_cards[:visible_count]):
        safe_card_id = card_id if 0 <= card_id < len(card_images) else 0
        window[f"-BTN{hand_index}-"].update(
            image_data=card_images[safe_card_id], visible=True
        )
    for button_index in range(visible_count, MAX_HAND_BUTTONS):
        window[f"-BTN{button_index}-"].update(visible=False)


def set_phase(window, phase_text):
    window["-PHASE-"].update(phase_text)
    active_phase_index = next(
        (
            index
            for index, phase_label in enumerate(PHASE_LABELS)
            if phase_label in phase_text
        ),
        None,
    )
    for phase_index in range(len(PHASE_LABELS)):
        is_active = phase_index == active_phase_index
        window[f"-PHASE-STEP-{phase_index}-"].update(
            text_color=COLOR_PAPER if is_active else COLOR_MUTED,
            background_color=COLOR_BLUE if is_active else COLOR_PAPER,
        )
    window.refresh()


def set_cards_enabled(window, enabled):
    window["-btn1-"].update(
        disabled=not enabled,
        button_color=(
            (COLOR_PAPER, COLOR_GREEN) if enabled else (COLOR_MUTED, COLOR_DISABLED)
        ),
    )
    if "-CARD-HINT-" in window.AllKeysDict:
        window["-CARD-HINT-"].update(
            "挑一张牌，慢慢想。" if enabled else "等对手落笔……",
            text_color=COLOR_GREEN if enabled else COLOR_MUTED,
        )


def _format_energy_orbs(value):
    filled = max(0, min(value, MAX_ENERGY_ORBS))
    return "●" * filled + "○" * (MAX_ENERGY_ORBS - filled)
