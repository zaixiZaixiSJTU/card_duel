"""Tests for the workbook-defined Slugcat character."""

import unittest

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.slugcat.creatures import add_hand_creature
from card_duel.cards.slugcat.lifecycle import resolve_pending_discards
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

    def test_initial_deck_keeps_source_cards_but_excludes_special_pools(self):
        counts = DEFAULT_REGISTRY.get_deck_counts(4)

        self.assertEqual(
            set(counts),
            {
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                36,
                37,
                38,
                39,
                40,
                42,
                44,
                46,
            },
        )
        self.assertEqual(sum(counts.values()), 107)
        self.assertTrue(set(counts).isdisjoint(range(16, 36)))
        self.assertTrue(set(counts).isdisjoint((49, 50)))

    def test_attack_converts_all_momentum_into_damage(self):
        slugcat_data(self.game.players[1]).momentum = 4

        self.assertTrue(self.play(2))

        self.assertEqual(self.game.players[2].health, 25)
        self.assertEqual(slugcat_data(self.game.players[1]).momentum, 0)

    def test_agility_prevents_life_loss_and_karma_revives_slugcat(self):
        slugcat_data(self.game.players[1]).agility = 3

        self.assertEqual(self.combat.apply_damage(5, 1), 2)
        self.assertEqual(self.game.players[1].health, 3)
        self.assertEqual(slugcat_data(self.game.players[1]).agility, 1)

        self.combat.apply_damage(10, 1)
        self.assertEqual(self.game.players[1].health, 5)
        self.assertEqual(slugcat_data(self.game.players[1]).karma, 2)

    def test_fully_blocked_damage_does_not_consume_agility(self):
        data = slugcat_data(self.game.players[1])
        data.agility = 2

        self.assertEqual(self.combat.apply_damage(2, 1), 0)
        self.assertEqual(data.agility, 2)

    def test_first_discovery_expands_deck_and_karma_cap(self):
        self.game.players[1].energy = 2

        self.assertTrue(self.play(27))

        self.assertEqual(slugcat_data(self.game.players[1]).karma_max, 4)
        self.assertIn(27, slugcat_data(self.game.players[1]).seen_discoveries)
        self.assertEqual(len(self.game.draw_pile), 8)
        self.assertEqual(
            slugcat_data(self.game.players[1]).unlocked_creature_counts,
            {25: 5, 18: 3, 19: 1},
        )
        self.assertTrue(slugcat_data(self.game.players[1]).discovery_pool)

    def test_pending_discard_resolves_immediately_instead_of_at_turn_start(self):
        self.game.hand_cards[:] = [6, 7]
        slugcat_data(self.game.players[1]).agility = 5
        self.game.players[1].statuses.pending_discards = 1
        discard_events = []
        turn = TurnEngine(self.game, 1, 1, self.messages.append)
        self.combat.register_turn_handlers(turn)

        turn.enter_phase(TurnPhase.TURN_START)

        self.assertEqual(slugcat_data(self.game.players[1]).agility, 0)
        self.assertEqual(self.game.players[1].statuses.pending_discards, 1)
        resolve_pending_discards(
            self.game,
            1,
            self.messages.append,
            on_discard=lambda index, card_id: discard_events.append((index, card_id)),
        )
        self.assertEqual(self.game.players[1].statuses.pending_discards, 0)
        self.assertEqual(len(self.game.hand_cards), 1)
        self.assertEqual(len(discard_events), 1)
        self.assertIn(discard_events[0][1], (6, 7))
        self.assertTrue(any("随机弃掉" in message for message in self.messages))

    def test_missing_art_pack_uses_registered_placeholder_cards(self):
        images, max_card_id = load_character_images(4, DEFAULT_REGISTRY)

        self.assertEqual(max_card_id, 50)
        self.assertEqual(len(images), 51)
        self.assertTrue(all(images))

    def test_direct_life_loss_ignores_agility_but_consumes_it(self):
        data = slugcat_data(self.game.players[1])
        data.agility = 3

        self.assertEqual(self.combat.lose_life(2, 1, self.messages.append), 2)
        self.assertEqual(self.game.players[1].health, 3)
        self.assertEqual(data.agility, 1)

    def test_discovery_unlocks_all_neighbors_and_replaces_scene(self):
        self.game.players[1].energy = 2
        self.game.draw_pile[:] = [1, 6, 44]

        self.assertTrue(self.play(27))

        data = slugcat_data(self.game.players[1])
        self.assertTrue({28, 29, 32}.issubset(data.discovery_pool))
        self.assertNotIn(1, self.game.draw_pile)
        self.assertNotIn(44, self.game.draw_pile)
        self.assertIn(6, self.game.draw_pile)

    def test_crouch_redirects_trouble_creature_to_opponent(self):
        self.game.players[1].energy = 2
        self.game.draw_pile[:] = [6, 7]

        self.assertTrue(self.play(10))
        self.assertTrue(self.play(15))

        self.assertFalse(self.game.players[1].statuses.hand_creatures)
        self.assertEqual(len(self.game.players[2].statuses.hand_creatures), 1)
        self.assertEqual(self.game.hand_cards, [6, 7])

    def test_run_away_exhausts_energy_and_draws_x_minus_one(self):
        data = slugcat_data(self.game.players[1])
        data.discovery_pool[:] = [27, 28]
        self.game.players[1].energy = 3

        self.assertTrue(self.play(14))

        self.assertEqual(self.game.players[1].energy, 0)
        self.assertEqual(self.game.hand_cards, [27, 28])

    def test_attack_can_target_creature_and_noodle_fly_immunity_is_per_turn(self):
        class CreatureChoices:
            def choose_option(self, title, prompt, options, default):
                return next(option for option in options if "面条蝇" in option)

            def choose_integer(self, title, prompt, minimum, maximum, default):
                return default

            def choose_card_indexes(self, title, hand, count, excluded_card_id=None):
                return []

        creature = add_hand_creature(self.game, 2, 17, owner_id=2)
        self.game.players[1].energy = 0
        for _ in range(2):
            self.assertTrue(
                DEFAULT_REGISTRY.play(
                    state=self.game,
                    character_id=4,
                    card_id=2,
                    source_player_id=1,
                    target_player_id=2,
                    announce=self.messages.append,
                    choices=CreatureChoices(),
                    combat=self.combat,
                )
            )

        self.assertEqual(creature.health, 4)
        self.assertEqual(self.game.players[2].health, 30)

    def test_inserted_card_uses_unique_id_and_returns_to_original_owner(self):
        self.game.players[1].energy = 1

        self.assertTrue(self.play(1))
        target = self.game.players[2]
        self.assertEqual(target.statuses.pending_hand_additions, [49])
        self.assertEqual(target.statuses.inserted_cards[0].owner_id, 1)

        self.game.local_player_id = 2
        self.game.hand_cards[:] = [49]
        target.energy = 1
        self.assertTrue(
            DEFAULT_REGISTRY.play(
                state=self.game,
                character_id=1,
                card_id=49,
                source_player_id=2,
                target_player_id=1,
                announce=self.messages.append,
                combat=self.combat,
            )
        )
        self.assertEqual(self.game.players[1].statuses.pending_draw_returns, [1])

    def test_scavenger_item_name_is_reported_only_to_its_owner(self):
        private_messages = []
        add_hand_creature(self.game, 1, 25, owner_id=1)

        self.assertTrue(
            DEFAULT_REGISTRY.play(
                state=self.game,
                character_id=4,
                card_id=46,
                source_player_id=1,
                target_player_id=2,
                announce=self.messages.append,
                private_announce=private_messages.append,
                combat=self.combat,
            )
        )

        self.assertTrue(any("携带的物品" in message for message in self.messages))
        self.assertFalse(any("仅自己可见" in message for message in self.messages))
        self.assertTrue(any("仅自己可见" in message for message in private_messages))


if __name__ == "__main__":
    unittest.main()
