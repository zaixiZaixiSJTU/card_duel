"""State-to-widget rendering for the network game."""

import base64
import io

from PIL import Image

from card_duel.ui.network_style import (
    COLOR_BLUE,
    COLOR_DISABLED,
    COLOR_GREEN,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_PAPER,
    COLOR_PAPER_LOCAL,
    COLOR_PAPER_OPPONENT,
    COLOR_RED,
    MAX_HAND_BUTTONS,
    MAX_HEALTH_DISPLAY,
    PHASE_LABELS,
)


def refresh_status(game_state, window, registry, snapshots=None):
    local_player = game_state.players[game_state.local_player_id]
    opponent_player = game_state.players[game_state.opponent_player_id]
    _update_player_status(
        window,
        "MY",
        local_player,
        game_state.local_character_id,
        _format_character_status(game_state, game_state.local_player_id, registry),
    )
    if snapshots is not None:
        _flash_changed_values(
            window,
            "MY",
            snapshots.get(game_state.local_player_id),
            _player_value_snapshot(local_player, game_state.local_character_id),
        )
        snapshots[game_state.local_player_id] = _player_value_snapshot(
            local_player, game_state.local_character_id
        )
    _update_player_status(
        window,
        "EN",
        opponent_player,
        game_state.opponent_character_id,
        _format_character_status(game_state, game_state.opponent_player_id, registry),
    )
    if snapshots is not None:
        _flash_changed_values(
            window,
            "EN",
            snapshots.get(game_state.opponent_player_id),
            _player_value_snapshot(opponent_player, game_state.opponent_character_id),
        )
        snapshots[game_state.opponent_player_id] = _player_value_snapshot(
            opponent_player, game_state.opponent_character_id
        )
    _safe_update(
        window,
        "-DECK-VIEW-DRAW-",
        button_text=f"牌堆\n{len(game_state.draw_pile)}",
    )
    _safe_update(
        window,
        "-DECK-VIEW-DISCARD-",
        button_text=f"弃牌\n{len(game_state.discard_pile)}",
    )
    hand_count = str(game_state.hand_size)
    if game_state.local_character_id == 4:
        from card_duel.cards.slugcat.hand import effective_hand_size

        effective = effective_hand_size(game_state, game_state.local_player_id)
        if effective != game_state.hand_size:
            hand_count = f"{effective}/{game_state.hand_size}"
    _safe_update(window, "-HAND-COUNT-", hand_count)
    _safe_refresh(window)


def _update_player_status(
    window, key_prefix, player, character_id, character_status=""
):
    _safe_update(
        window,
        f"-{key_prefix}-HP-",
        str(player.health),
        text_color=COLOR_RED if player.health <= 10 else COLOR_INK,
    )
    _safe_update(window, f"-{key_prefix}-EN-", str(player.energy))
    if character_id == 4:
        from card_duel.cards.slugcat.state import slugcat_data

        data = slugcat_data(player)
        defence_label, defence_value = "敏捷", data.agility
        strength_label, strength_value = "动能", data.momentum
    else:
        defence_label, defence_value = "防御", player.defence
        strength_label, strength_value = "力量", player.strength
    _safe_update(window, f"-{key_prefix}-DEF-LABEL-", defence_label)
    _safe_update(window, f"-{key_prefix}-STR-LABEL-", strength_label)
    _safe_update(window, f"-{key_prefix}-DEF-", str(defence_value))
    _safe_update(window, f"-{key_prefix}-STR-", str(strength_value))
    _safe_update(
        window, f"-{key_prefix}-HP-BAR-", max(0, min(MAX_HEALTH_DISPLAY, player.health))
    )
    _safe_update(window, f"-{key_prefix}-SPECIAL-", character_status)


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
        _safe_update(
            window,
            f"-BTN{hand_index}-",
            image_data=image_data,
            visible=True,
        )
        _apply_card_border(
            window[f"-BTN{hand_index}-"],
            "#C86655" if card_id in (49, 50) else "#C39A55",
            card_id in (49, 50) or creature is not None,
        )
    for button_index in range(visible_count, MAX_HAND_BUTTONS):
        _safe_update(window, f"-BTN{button_index}-", visible=False)


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
    _safe_update(window, "-PHASE-", phase_text)
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
        _safe_update(
            window,
            f"-PHASE-STEP-{phase_index}-",
            text_color=COLOR_PAPER if is_active else COLOR_MUTED,
            background_color=COLOR_BLUE if is_active else COLOR_PAPER,
        )
    _safe_refresh(window)


def set_cards_enabled(window, enabled):
    _safe_update(
        window,
        "-btn1-",
        disabled=not enabled,
        button_color=(
            (COLOR_PAPER, COLOR_GREEN) if enabled else (COLOR_MUTED, COLOR_DISABLED)
        ),
    )
    if "-CARD-HINT-" in window.AllKeysDict:
        _safe_update(
            window,
            "-CARD-HINT-",
            "挑一张牌，慢慢想。" if enabled else "等对手落笔……",
            text_color=COLOR_GREEN if enabled else COLOR_MUTED,
        )


def show_played_card(session, player_id: int, character_id: int, card_id: int) -> None:
    """Show the latest played card in the shared panel to the right of the log."""
    from card_duel.core.resources import render_card

    definition = session.registry.get_card(character_id, card_id)
    window = session.require_window()
    _safe_update(
        window,
        "-LAST-PLAYED-",
        data=_resized_card(render_card(definition), (200, 300)),
    )
    who = "我方" if player_id == session.state.local_player_id else "对手"
    _safe_update(
        window,
        "-LAST-PLAYED-HINT-",
        f"{who}打出 {definition.name}",
        text_color=COLOR_INK,
    )


def _player_value_snapshot(player, character_id) -> tuple[int, int, int, int]:
    if character_id == 4:
        from card_duel.cards.slugcat.state import slugcat_data

        data = slugcat_data(player)
        return player.health, player.energy, data.agility, data.momentum
    return player.health, player.energy, player.defence, player.strength


def _flash_changed_values(window, prefix, previous, current) -> None:
    """Briefly tint changed values without blocking the network event loop."""
    if previous is None:
        return
    restore_color = (
        COLOR_PAPER_OPPONENT if prefix == "EN"
        else COLOR_PAPER_LOCAL if prefix == "MY"
        else COLOR_PAPER
    )
    for suffix, before, after in zip(
        ("HP", "EN", "DEF", "STR"), previous, current, strict=True
    ):
        if before == after:
            continue
        color = COLOR_GREEN if after > before else COLOR_RED
        try:
            widget = window[f"-{prefix}-{suffix}-"].Widget
            widget.configure(background=color)
            window.TKroot.after(
                420,
                lambda item=widget: item.configure(background=restore_color),
            )
        except Exception:
            continue


def _thumbnail(image_data: bytes, size=(64, 96)) -> bytes:
    raw = base64.b64decode(image_data)
    with Image.open(io.BytesIO(raw)) as image:
        image.thumbnail(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


def _resized_card(image_data: bytes, size=(200, 300)) -> bytes:
    """Resize a card image to the exact target size (also upscales)."""
    raw = base64.b64decode(image_data)
    with Image.open(io.BytesIO(raw)) as image:
        resized = image.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        resized.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


def _safe_update(window, key, *args, **kwargs) -> bool:
    """Avoid crashing when a Tk element disappears during socket shutdown."""
    try:
        window[key].update(*args, **kwargs)
        return True
    except Exception:
        return False


def _safe_refresh(window) -> None:
    try:
        window.refresh()
    except Exception:
        return
