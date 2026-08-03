"""Legacy API facade.

Internal modules must use ``CombatEngine``, ``CardRegistry``, core models, and
core rules directly. This module only protects older launchers and integrations.
"""

# ruff: noqa: F401 -- re-exported names are the compatibility surface.

from card_duel.application.combat import CombatEngine
from card_duel.cards import DEFAULT_REGISTRY, play_registered_card
from card_duel.core.models import (
    CharacterState,
    CombatStatuses,
    DefenceEffect,
    GameState,
    NetworkGameState,
    ScheduledEvent,
)
from card_duel.core.resources import (
    BUTTON_PAD,
    IMAGE_SIZE,
    encode_image,
    resolve_resource_path,
)
from card_duel.core.rules import (
    add_card_to_hand,
    add_defence,
    build_shuffled_deck,
    draw_cards,
    schedule_event,
)

CHARACTERS = [
    "未选择",
    *(
        DEFAULT_REGISTRY.get_character(index).name
        for index in DEFAULT_REGISTRY.character_ids
    ),
]


def _engine(game_state):
    return CombatEngine(game_state, DEFAULT_REGISTRY)


def initialize_character_states(game_state):
    return _engine(game_state).initialize_players()


def apply_damage(game_state, damage, target_player_id, announce=None):
    return _engine(game_state).apply_damage(damage, target_player_id, announce)


def lose_life(game_state, amount, target_player_id):
    return _engine(game_state).lose_life(amount, target_player_id)


def advance_turn_effects(game_state, player_id, announce):
    return _engine(game_state).advance_turn_effects(player_id, announce)


def resolve_scheduled_event(game_state, event, announce):
    return _engine(game_state).resolve_scheduled_event(event, announce)


def check_game_over(game_state):
    return _engine(game_state).check_game_over()


def is_player_defeated(game_state, player_id):
    return _engine(game_state).is_player_defeated(player_id)


def winning_player_id(game_state):
    return _engine(game_state).winning_player_id()


def update_defence_totals(game_state):
    """Compatibility no-op; defence is now a derived player property."""
    return None


def load_character_images(character_id):
    from card_duel.core.resources import load_character_images as load_images

    return load_images(character_id, DEFAULT_REGISTRY)


def _legacy_card(card_id):
    def play(
        game_state,
        source_player_id,
        target_player_id,
        announce,
        ignore_cost=False,
        choices=None,
    ):
        return play_registered_card(
            game_state,
            1,
            card_id,
            source_player_id,
            target_player_id,
            announce,
            ignore_cost,
            choices,
        )

    return play


play_unavailable_card = _legacy_card(0)
play_attack_card = _legacy_card(1)
play_defend_card = _legacy_card(2)
play_shield_bash_card = _legacy_card(3)
play_pack_god_card = _legacy_card(4)
play_sacrifice_card = _legacy_card(5)
play_heavy_sword_card = _legacy_card(6)
play_heavy_hammer_card = _legacy_card(7)
play_burn_card = _legacy_card(8)
play_glycogen_card = _legacy_card(9)
play_bastion_card = _legacy_card(10)
play_consolidate_card = _legacy_card(11)
play_full_body_slam_card = _legacy_card(12)
play_immovable_mountain_card = _legacy_card(13)
play_heartlink_card = _legacy_card(14)
play_black_flash_card = _legacy_card(15)
play_burnt_offering_card = _legacy_card(16)

__all__ = [name for name in globals() if not name.startswith("_")]
