"""Tests for the UI-independent local game model."""

import unittest
from unittest.mock import patch

from card_duel.core.demo import LocalGame


class LocalGameTests(unittest.TestCase):
    def setUp(self):
        with patch("card_duel.core.demo.random.randint", return_value=1):
            self.game = LocalGame(1, 2)

    def test_start_round_assigns_energy(self):
        with patch("card_duel.core.demo.random.randint", side_effect=[4, 5]):
            messages = self.game.start_round()

        self.assertEqual(self.game.players[1].energy, 4)
        self.assertEqual(self.game.players[2].energy, 5)
        self.assertIn("玩家1 先手", messages)

    def test_play_card_spends_energy_and_deals_damage(self):
        self.game.players[1].energy = 4
        with patch("card_duel.core.demo.random.randint", return_value=6):
            was_played, damage = self.game.play_card()

        self.assertTrue(was_played)
        self.assertEqual(damage, 6)
        self.assertEqual(self.game.players[1].energy, 2)
        self.assertEqual(self.game.players[2].health, 32)

    def test_end_turn_advances_after_both_players(self):
        self.assertEqual(self.game.end_turn(), "switch")
        self.assertEqual(self.game.active_player_id, 2)
        self.assertEqual(self.game.end_turn(), "new_round")
        self.assertEqual(self.game.round_number, 2)
        self.assertEqual(self.game.starting_player_id, 2)


if __name__ == "__main__":
    unittest.main()
