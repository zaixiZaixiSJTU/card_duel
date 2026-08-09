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
        game_state.local_character_id,
        _format_character_status(game_state, game_state.local_player_id, registry),
    )
    _update_player_status(
        window,
        "EN",
        opponent_player,
        game_state.opponent_character_id,
        _format_character_status(game_state, game_state.opponent_player_id, registry),
    )
    window["-DECK-COUNT-"].update(str(len(game_state.draw_pile)))
    hand_count = str(game_state.hand_size)
    if game_state.local_character_id == 4:
        from card_duel.cards.slugcat.hand import effective_hand_size

        effective = effective_hand_size(game_state, game_state.local_player_id)
        if effective != game_state.hand_size:
            hand_count = f"{effective}/{game_state.hand_size}"
    window["-HAND-COUNT-"].update(hand_count)
    window.refresh()


def _update_player_status(
    window, key_prefix, player, character_id, character_status=""
):
    window[f"-{key_prefix}-HP-"].update(
        str(player.health),
        text_color=COLOR_RED if player.health <= 10 else COLOR_INK,
    )
    window[f"-{key_prefix}-EN-"].update(str(player.energy))
    if character_id == 4:
        from card_duel.cards.slugcat.state import slugcat_data

        data = slugcat_data(player)
        defence_label, defence_value = "敏捷", data.agility
        strength_label, strength_value = "动能", data.momentum
    else:
        defence_label, defence_value = "防御", player.defence
        strength_label, strength_value = "力量", player.strength
    window[f"-{key_prefix}-DEF-LABEL-"].update(defence_label)
    window[f"-{key_prefix}-STR-LABEL-"].update(strength_label)
    window[f"-{key_prefix}-DEF-"].update(str(defence_value))
    window[f"-{key_prefix}-STR-"].update(str(strength_value))
    window[f"-{key_prefix}-HP-BAR-"].update(
        max(0, min(MAX_HEALTH_DISPLAY, player.health))
    )
    window[f"-{key_prefix}-ORB-"].update(_format_energy_orbs(player.energy))
    window[f"-{key_prefix}-SPECIAL-"].update(character_status)


def _format_character_status(game_state, player_id, registry):
    character_id = game_state.character_ids.get(player_id)
    if character_id is None:
        return ""
    player = game_state.players[player_id]
    parts = [registry.get_character(character_id).rules.format_status(player)]
    if player.statuses.hand_creatures:
        parts.append(f"携带生物 {len(player.statuses.hand_creatures)}")
    if player.statuses.creature_threats:
        parts.append(f"威胁 {len(player.statuses.creature_threats)}")
    if player.statuses.inserted_cards:
        parts.append(f"插入物 {len(player.statuses.inserted_cards)}")
    return "  ·  ".join(part for part in parts if part)


def refresh_cards(game_state, window, card_images):
    from card_duel.cards.catalog import DEFAULT_REGISTRY
    from card_duel.core.resources import render_card

    visible_count = min(len(game_state.hand_cards), MAX_HAND_BUTTONS)
    creature_offsets = {}
    for hand_index, card_id in enumerate(game_state.hand_cards[:visible_count]):
        safe_card_id = card_id if 0 <= card_id < len(card_images) else 0
        image_data = card_images[safe_card_id]
        definition = DEFAULT_REGISTRY.get_card(game_state.local_character_id, card_id)
        effective_cost = definition.cost
        if game_state.local_character_id == 4 and card_id <= 48:
            from card_duel.cards.slugcat.effects import effective_cost

            effective_cost = effective_cost(
                game_state, game_state.local_player_id, card_id
            )
        matching = [
            item
            for item in game_state.local_player.statuses.hand_creatures
            if item.card_id == card_id
        ]
        offset = creature_offsets.get(card_id, 0)
        creature = matching[offset] if offset < len(matching) else None
        if creature is not None:
            creature_offsets[card_id] = offset + 1
        if effective_cost != definition.cost or creature is not None:
            image_data = render_card(
                definition,
                effective_cost=effective_cost,
                creature_health=creature.health if creature is not None else None,
            )
        window[f"-BTN{hand_index}-"].update(image_data=image_data, visible=True)
        _apply_card_border(
            window[f"-BTN{hand_index}-"],
            "#C86655" if card_id in (49, 50) else "#C39A55",
            card_id in (49, 50) or creature is not None,
        )
    for button_index in range(visible_count, MAX_HAND_BUTTONS):
        window[f"-BTN{button_index}-"].update(visible=False)


def _apply_card_border(element, color, emphasized):
    widget = getattr(element, "Widget", None)
    if widget is None:
        return
    try:
        widget.configure(
            highlightbackground=color,
            highlightcolor=color,
            highlightthickness=5 if emphasized else 0,
            borderwidth=1,
        )
    except Exception:
        return


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
