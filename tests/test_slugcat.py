"""Tests for the workbook-defined Slugcat character."""

import unittest

from card_duel.cards.registry import get_card_counts, play_registered_card
from card_duel.cards.slugcat import register_slugcat_phase_handlers
from card_duel.core.combat import (
    NetworkGameState,
    apply_damage,
    initialize_character_states,
    load_character_images,
)
from card_duel.core.game import TurnEngine, TurnPhase


class SlugcatTests(unittest.TestCase):
    def setUp(self):
        self.game = NetworkGameState()
        self.game.character_ids = {1: 4, 2: 1}
        self.game.local_player_id = 1
        initialize_character_states(self.game)
        self.messages = []

    def play(self, card_id):
        return play_registered_card(
            self.game,
            character_id=4,
            card_id=card_id,
            source_player_id=1,
            target_player_id=2,
            announce=self.messages.append,
        )

    def test_initial_deck_contains_only_ten_skill_cards(self):
        counts = get_card_counts(4)

        self.assertEqual(set(counts), set(range(6, 16)))
        self.assertEqual(sum(counts.values()), 49)

    def test_attack_converts_all_momentum_into_damage(self):
        self.game.players[1].special["momentum"] = 4

        self.assertTrue(self.play(2))

        self.assertEqual(self.game.players[2].health, 25)
        self.assertEqual(self.game.players[1].special["momentum"], 0)

    def test_agility_prevents_life_loss_and_karma_revives_slugcat(self):
        self.game.players[1].special["agility"] = 3

        self.assertEqual(apply_damage(self.game, 5, 1), 2)
        self.assertEqual(self.game.players[1].health, 3)
        self.assertEqual(self.game.players[1].special["agility"], 0)

        apply_damage(self.game, 10, 1)
        self.assertEqual(self.game.players[1].health, 5)
        self.assertEqual(self.game.players[1].special["karma"], 2)

    def test_first_discovery_expands_deck_and_karma_cap(self):
        self.game.players[1].energy = 2

        self.assertTrue(self.play(27))

        self.assertEqual(self.game.players[1].special["karma_max"], 4)
        self.assertIn(27, self.game.players[1].special["seen_discoveries"])
        self.assertEqual(len(self.game.draw_pile), 17)
        self.assertTrue(self.game.players[1].special["discovery_pool"])

    def test_turn_start_resets_agility_and_applies_pending_discard(self):
        self.game.hand_cards[:3] = [6, 7, 0]
        self.game.hand_size = 2
        self.game.players[1].special["agility"] = 5
        self.game.players[1].special["pending_discards"] = 1
        turn = TurnEngine(self.game, 1, 1, self.messages.append)
        register_slugcat_phase_handlers(turn)

        turn.enter_phase(TurnPhase.TURN_START)

        self.assertEqual(self.game.players[1].special["agility"], 0)
        self.assertEqual(self.game.players[1].special["pending_discards"], 0)
        self.assertEqual(self.game.hand_cards[:2].count(-1), 1)

    def test_missing_art_pack_uses_registered_placeholder_cards(self):
        images, max_card_id = load_character_images(4)

        self.assertEqual(max_card_id, 48)
        self.assertEqual(len(images), 49)
        self.assertTrue(all(images))


if __name__ == "__main__":
    unittest.main()
