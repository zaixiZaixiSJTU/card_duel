"""Tests for the workbook-defined Slugcat character."""

import unittest

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.slugcat.state import slugcat_data
from card_duel.core.game import TurnEngine, TurnPhase
from card_duel.core.models import GameState
from card_duel.core.resources import load_character_images


class SlugcatTests(unittest.TestCase):
    def setUp(self):
        self.game = GameState()
        self.game.character_ids = {1: 4, 2: 1}
        self.game.local_player_id = 1
        self.combat = CombatEngine(self.game, DEFAULT_REGISTRY)
        self.combat.initialize_players()
        self.messages = []

    def play(self, card_id):
        return DEFAULT_REGISTRY.play(
            state=self.game,
            character_id=4,
            card_id=card_id,
            source_player_id=1,
            target_player_id=2,
            announce=self.messages.append,
            combat=self.combat,
        )

    def test_initial_deck_contains_only_ten_skill_cards(self):
        counts = DEFAULT_REGISTRY.get_deck_counts(4)

        self.assertEqual(set(counts), set(range(6, 16)))
        self.assertEqual(sum(counts.values()), 49)

    def test_attack_converts_all_momentum_into_damage(self):
        slugcat_data(self.game.players[1]).momentum = 4

        self.assertTrue(self.play(2))

        self.assertEqual(self.game.players[2].health, 25)
        self.assertEqual(slugcat_data(self.game.players[1]).momentum, 0)

    def test_agility_prevents_life_loss_and_karma_revives_slugcat(self):
        slugcat_data(self.game.players[1]).agility = 3

        self.assertEqual(self.combat.apply_damage(5, 1), 2)
        self.assertEqual(self.game.players[1].health, 3)
        self.assertEqual(slugcat_data(self.game.players[1]).agility, 0)

        self.combat.apply_damage(10, 1)
        self.assertEqual(self.game.players[1].health, 5)
        self.assertEqual(slugcat_data(self.game.players[1]).karma, 2)

    def test_first_discovery_expands_deck_and_karma_cap(self):
        self.game.players[1].energy = 2

        self.assertTrue(self.play(27))

        self.assertEqual(slugcat_data(self.game.players[1]).karma_max, 4)
        self.assertIn(27, slugcat_data(self.game.players[1]).seen_discoveries)
        self.assertEqual(len(self.game.draw_pile), 17)
        self.assertTrue(slugcat_data(self.game.players[1]).discovery_pool)

    def test_turn_start_resets_agility_and_applies_pending_discard(self):
        self.game.hand_cards[:] = [6, 7]
        slugcat_data(self.game.players[1]).agility = 5
        self.game.players[1].statuses.pending_discards = 1
        turn = TurnEngine(self.game, 1, 1, self.messages.append)
        self.combat.register_turn_handlers(turn)

        turn.enter_phase(TurnPhase.TURN_START)

        self.assertEqual(slugcat_data(self.game.players[1]).agility, 0)
        self.assertEqual(self.game.players[1].statuses.pending_discards, 0)
        self.assertEqual(len(self.game.hand_cards), 1)

    def test_missing_art_pack_uses_registered_placeholder_cards(self):
        images, max_card_id = load_character_images(4, DEFAULT_REGISTRY)

        self.assertEqual(max_card_id, 48)
        self.assertEqual(len(images), 49)
        self.assertTrue(all(images))


if __name__ == "__main__":
    unittest.main()
