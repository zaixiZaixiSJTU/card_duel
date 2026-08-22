"""Tests for the workbook-defined Slugcat character."""

import unittest
from types import SimpleNamespace

from card_duel.application.choices import (
    DEFAULT_CHOICES,
    AutomaticChoiceProvider,
)
from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.slugcat.creatures import (
    add_hand_creature,
    add_threat,
    attack_targets,
    centipede_health,
    damage_creature,
    hand_creature,
    kill_matching_creature,
    on_creature_death,
)
from card_duel.cards.slugcat.hand import effective_hand_size
from card_duel.cards.slugcat.lifecycle import (
    _resolve_centipede_spread,
    resolve_pending_discards,
)
from card_duel.cards.slugcat.state import slugcat_data
from card_duel.core.game import TurnEngine, TurnPhase
from card_duel.core.models import DefenceEffect, GameState
from card_duel.core.resources import load_character_images


class _PayForLizardChoices(AutomaticChoiceProvider):
    def choose_option(self, title, prompt, options, default):
        return "支付1点能量"


class _TransferFlashChoices(AutomaticChoiceProvider):
    def choose_option(self, title, prompt, options, default):
        return options[1]


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

    def test_hop_followup_includes_stone_and_all_attack_items(self):
        self.game.players[1].energy = 1

        self.assertTrue(self.play(6))
        self.assertEqual(slugcat_data(self.game.players[1]).agility, 1)

        self.assertTrue(self.play(2))

        self.assertEqual(slugcat_data(self.game.players[1]).agility, 2)
        self.assertFalse(slugcat_data(self.game.players[1]).jump_followup)

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

    def test_electric_spear_is_consumed_and_not_returned_to_owner(self):
        self.game.players[1].energy = 2

        self.assertTrue(self.play(5))
        target = self.game.players[2]
        self.assertEqual(target.statuses.pending_hand_additions, [50])
        self.assertEqual(target.statuses.inserted_cards[0].owner_id, 1)
        target.statuses.electric_strength_penalty = 3

        self.game.local_player_id = 2
        self.game.hand_cards[:] = [50]
        target.energy = 1
        self.assertTrue(
            DEFAULT_REGISTRY.play(
                state=self.game,
                character_id=1,
                card_id=50,
                source_player_id=2,
                target_player_id=1,
                announce=self.messages.append,
                combat=self.combat,
            )
        )

        self.assertEqual(self.game.players[1].statuses.pending_draw_returns, [])
        self.assertEqual(target.statuses.embedded_electric_spears, 0)
        self.assertEqual(target.strength, 2)
        self.assertEqual(target.statuses.electric_strength_penalty, 1)

    def test_dead_creature_is_consumed_and_not_returned_to_summon_pool(self):
        data = slugcat_data(self.game.players[1])
        data.unlocked_creature_counts = {20: 2}
        add_hand_creature(self.game, 1, 20, owner_id=1)
        creature = hand_creature(self.game, 1, 20)

        on_creature_death(self.game, 1, creature, self.messages.append)

        self.assertEqual(data.unlocked_creature_counts, {20: 2})
        self.assertTrue(any("绿蜥蜴被击杀" in message for message in self.messages))

    def test_remote_dead_creature_does_not_return_to_owner(self):
        self.game.character_ids = {1: 4, 2: 4}
        self.combat = CombatEngine(self.game, DEFAULT_REGISTRY)
        self.combat.initialize_players()
        data = slugcat_data(self.game.players[2])
        data.unlocked_creature_counts = {20: 1}
        add_hand_creature(self.game, 1, 20, owner_id=2)
        creature = hand_creature(self.game, 1, 20)

        on_creature_death(self.game, 1, creature, self.messages.append)

        self.assertEqual(data.unlocked_creature_counts, {20: 1})
        self.assertEqual(self.game.players[2].statuses.pending_draw_returns, [])

    def test_run_away_returns_living_creatures_to_summon_pool(self):
        data = slugcat_data(self.game.players[1])
        data.unlocked_creature_counts = {20: 1}
        add_hand_creature(self.game, 1, 20, owner_id=1)
        self.game.players[1].energy = 0

        self.assertTrue(self.play(14))

        self.assertEqual(data.unlocked_creature_counts, {20: 2})
        self.assertEqual(self.game.players[1].statuses.hand_creatures, [])

    def _run_turn_end(self, choices):
        turn = TurnEngine(self.game, 1, 1, self.messages.append, choices=choices)
        self.combat.register_turn_handlers(turn)
        turn.enter_phase(TurnPhase.TURN_START)
        turn.enter_phase(TurnPhase.DRAW)
        turn.enter_phase(TurnPhase.PLAY)
        turn.enter_phase(TurnPhase.DISCARD)
        turn.enter_phase(TurnPhase.TURN_END)

    def test_flame_lizard_payment_avoids_damage_but_keeps_creature(self):
        add_hand_creature(self.game, 1, 23, owner_id=1)
        self.game.players[1].energy = 1
        self.game.players[1].health = 20

        self._run_turn_end(_PayForLizardChoices())

        self.assertEqual(self.game.players[1].energy, 0)
        self.assertEqual(self.game.players[1].health, 20)
        self.assertEqual(len(self.game.players[1].statuses.hand_creatures), 1)
        self.assertTrue(any("本回合不攻击" in message for message in self.messages))
        self.assertFalse(any("造成10点伤害" in message for message in self.messages))

    def test_flame_lizard_damages_owner_when_not_paid(self):
        add_hand_creature(self.game, 1, 23, owner_id=1)
        self.game.players[1].energy = 0
        self.game.players[1].health = 20

        self._run_turn_end(DEFAULT_CHOICES)

        self.assertEqual(self.game.players[1].health, 10)
        self.assertEqual(len(self.game.players[1].statuses.hand_creatures), 1)
        self.assertTrue(any("造成10点伤害" in message for message in self.messages))

    def test_newly_added_noodle_fly_does_not_attack_same_turn_end(self):
        add_hand_creature(self.game, 1, 16, owner_id=1)
        self.game.players[1].health = 20

        self._run_turn_end(DEFAULT_CHOICES)

        self.assertEqual(self.game.players[1].health, 20)
        self.assertEqual(
            [item.card_id for item in self.game.players[1].statuses.hand_creatures],
            [17],
        )
        self.assertTrue(any("引来面条蝇" in message for message in self.messages))
        self.assertFalse(any("造成5点伤害" in message for message in self.messages))

    def test_newly_added_vulture_does_not_attack_same_turn_end(self):
        add_hand_creature(self.game, 1, 18, owner_id=1)
        self.game.players[1].health = 20

        self._run_turn_end(DEFAULT_CHOICES)

        self.assertEqual(self.game.players[1].health, 20)
        self.assertEqual(
            [item.card_id for item in self.game.players[1].statuses.creature_threats],
            [19],
        )
        self.assertTrue(any("引来一张秃鹫" in message for message in self.messages))
        self.assertFalse(any("造成10点伤害" in message for message in self.messages))

    def test_creatures_do_not_occupy_hand_slots(self):
        for card_id in (16, 20, 23):
            add_hand_creature(self.game, 1, card_id, owner_id=1)
        self.game.hand_cards[:] = [1, 2, 6, 7]

        self.assertEqual(effective_hand_size(self.game, 1), 4)
        self.assertNotIn(16, self.game.hand_cards)
        self.assertNotIn(20, self.game.hand_cards)
        self.assertNotIn(23, self.game.hand_cards)

    def test_tube_worm_is_held_in_hand_and_exempts_discoveries(self):
        add_hand_creature(self.game, 1, 26, owner_id=1)

        self.assertIn(26, self.game.hand_cards)
        self.assertEqual(len(self.game.players[1].statuses.hand_creatures), 1)
        self.game.hand_cards[:] = [26, 27, 1, 2, 3]
        self.assertEqual(effective_hand_size(self.game, 1), 4)

    def test_vulture_leaves_when_our_creature_dies(self):
        add_hand_creature(self.game, 1, 19, owner_id=1)
        add_hand_creature(self.game, 1, 20, owner_id=1)
        creature = hand_creature(self.game, 1, 20)
        self.game.players[1].statuses.hand_creatures.remove(creature)

        on_creature_death(self.game, 1, creature, self.messages.append)

        self.assertEqual(self.game.players[1].statuses.hand_creatures, [])
        self.assertTrue(any("秃鹫离场" in message for message in self.messages))

    def test_only_one_vulture_leaves_per_death(self):
        add_hand_creature(self.game, 1, 19, owner_id=1)
        add_hand_creature(self.game, 1, 19, owner_id=1)
        add_hand_creature(self.game, 1, 20, owner_id=1)
        creature = hand_creature(self.game, 1, 20)
        self.game.players[1].statuses.hand_creatures.remove(creature)

        on_creature_death(self.game, 1, creature, self.messages.append)

        remaining = [
            item.card_id
            for item in self.game.players[1].statuses.hand_creatures
        ]
        self.assertEqual(remaining, [19])

    def test_vulture_does_not_leave_for_opponent_creature(self):
        self.game.character_ids = {1: 4, 2: 4}
        self.combat = CombatEngine(self.game, DEFAULT_REGISTRY)
        self.combat.initialize_players()
        add_hand_creature(self.game, 1, 19, owner_id=1)
        add_hand_creature(self.game, 2, 20, owner_id=2)
        creature = hand_creature(self.game, 2, 20)

        on_creature_death(self.game, 2, creature, self.messages.append)

        remaining = [
            item.card_id
            for item in self.game.players[1].statuses.hand_creatures
        ]
        self.assertEqual(remaining, [19])

    def test_playing_creature_dodges_and_removes_it(self):
        add_hand_creature(self.game, 1, 20, owner_id=1)
        self.game.players[1].energy = 2

        self.assertTrue(self.play(20))

        self.assertEqual(self.game.players[1].statuses.hand_creatures, [])
        self.assertEqual(self.game.players[1].energy, 0)

    def _damage_context(self):
        return SimpleNamespace(
            state=self.game,
            announce=self.messages.append,
            source_player_id=1,
            private_announce=None,
        )

    def test_centipede_birth_creates_shared_pool(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)

        self.assertEqual(centipede_health(self.game), 20)
        self.assertTrue(self.game.players[1].statuses.hand_creatures[0].shell)
        add_hand_creature(self.game, 2, 22, owner_id=2)
        self.assertEqual(
            self.game.players[2].statuses.hand_creatures[0].health, 20
        )

    def test_centipede_damage_reduces_shared_pool_but_keeps_segments(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)
        add_hand_creature(self.game, 2, 22, owner_id=2)

        self.assertFalse(
            damage_creature(self._damage_context(), 2, 22, 8, threat=False)
        )

        self.assertEqual(centipede_health(self.game), 12)
        self.assertEqual(len(self.game.players[2].statuses.hand_creatures), 1)
        self.assertEqual(
            self.game.players[2].statuses.hand_creatures[0].health, 12
        )

    def test_centipede_dies_when_shared_pool_empty(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)
        add_hand_creature(self.game, 2, 22, owner_id=2)

        self.assertFalse(
            damage_creature(self._damage_context(), 1, 22, 19, threat=False)
        )
        self.assertTrue(
            damage_creature(self._damage_context(), 1, 22, 1, threat=False)
        )

        self.assertEqual(centipede_health(self.game), 0)
        self.assertEqual(self.game.players[1].statuses.hand_creatures, [])
        self.assertEqual(self.game.players[2].statuses.hand_creatures, [])
        self.assertTrue(any("烈焰蜈蚣死亡" in message for message in self.messages))

    def test_centipede_segment_shield_is_consumed_once(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)
        self.game.players[1].health = 20

        self.assertEqual(
            self.combat.apply_damage(6, 1, self.messages.append), 0
        )
        self.assertEqual(self.game.players[1].health, 20)
        segment = hand_creature(self.game, 1, 22)
        self.assertFalse(segment.shell)
        self.assertEqual(centipede_health(self.game), 20)

        self.assertEqual(
            self.combat.apply_damage(6, 1, self.messages.append), 6
        )
        self.assertEqual(self.game.players[1].health, 14)

    def test_threat_zone_segment_also_shields_holder(self):
        add_threat(self.game, 1, 22, owner_id=2)
        self.game.players[1].health = 20

        self.assertEqual(
            self.combat.apply_damage(6, 1, self.messages.append), 0
        )

        self.assertEqual(self.game.players[1].health, 20)
        self.assertFalse(self.game.players[1].statuses.creature_threats[0].shell)

        self.assertEqual(
            self.combat.apply_damage(6, 1, self.messages.append), 6
        )
        self.assertEqual(self.game.players[1].health, 14)

    def test_centipede_spread_prefers_more_side(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)

        _resolve_centipede_spread(self.game, 1, self.messages.append)
        _resolve_centipede_spread(self.game, 2, self.messages.append)

        self.assertEqual(len(self.game.players[1].statuses.hand_creatures), 3)
        self.assertEqual(self.game.players[2].statuses.hand_creatures, [])

    def test_centipede_spread_adds_to_both_when_equal(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)
        add_hand_creature(self.game, 2, 22, owner_id=2)

        _resolve_centipede_spread(self.game, 1, self.messages.append)

        self.assertEqual(len(self.game.players[1].statuses.hand_creatures), 2)
        self.assertEqual(len(self.game.players[2].statuses.hand_creatures), 2)
        self.assertTrue(any("双方各获得" in message for message in self.messages))

    def test_centipede_does_not_spread_when_dead(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)
        self.assertTrue(
            damage_creature(self._damage_context(), 1, 22, 20, threat=False)
        )

        _resolve_centipede_spread(self.game, 1, self.messages.append)

        self.assertEqual(self.game.players[1].statuses.hand_creatures, [])

    def test_smoke_fruit_kills_whole_centipede(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)
        add_hand_creature(self.game, 2, 22, owner_id=2)
        context = SimpleNamespace(
            state=self.game,
            source_player_id=1,
            target_player_id=2,
            announce=self.messages.append,
            private_announce=None,
            choices=DEFAULT_CHOICES,
        )

        self.assertTrue(kill_matching_creature(context, 22))

        self.assertEqual(centipede_health(self.game), 0)
        self.assertEqual(self.game.players[1].statuses.hand_creatures, [])
        self.assertEqual(self.game.players[2].statuses.hand_creatures, [])

    def test_centipede_is_a_single_attack_target(self):
        add_hand_creature(self.game, 1, 22, owner_id=1)
        add_hand_creature(self.game, 1, 22, owner_id=1)
        add_hand_creature(self.game, 1, 20, owner_id=1)

        labels = [target.label for target in attack_targets(self.game, 1, 2)]

        self.assertEqual(labels.count("[己方] 烈焰蜈蚣"), 1)
        self.assertEqual(labels.count("[己方] 绿蜥蜴"), 1)

    def test_flash_fruit_can_target_player_with_creatures_present(self):
        add_hand_creature(self.game, 1, 20, owner_id=1)
        self.game.players[1].energy = 1

        self.assertTrue(self.play(43))

        self.assertEqual(self.game.players[2].statuses.attack_lock, 2)
        self.assertEqual(len(self.game.players[1].statuses.hand_creatures), 1)

    def test_flash_fruit_transfers_creature_to_opponent_hand(self):
        add_hand_creature(self.game, 1, 20, owner_id=1)
        self.game.players[1].energy = 1

        self.assertTrue(
            DEFAULT_REGISTRY.play(
                state=self.game,
                character_id=4,
                card_id=43,
                source_player_id=1,
                target_player_id=2,
                announce=self.messages.append,
                combat=self.combat,
                choices=_TransferFlashChoices(),
            )
        )

        self.assertEqual(self.game.players[1].statuses.hand_creatures, [])
        self.assertEqual(
            [item.card_id for item in self.game.players[2].statuses.hand_creatures],
            [20],
        )

    def test_scavenger_item_is_rolled_at_generation_and_announced(self):
        slugcat_data(self.game.players[1]).unlocked_creature_counts = {25: 1}
        self.game.players[1].energy = 3

        self.assertTrue(self.play(15))

        creature = hand_creature(self.game, 1, 25)
        self.assertIn(creature.held_item, (1, 3, 4, 5))
        self.assertTrue(any("携带物品" in message for message in self.messages))

    def test_scavenger_damage_uses_held_item(self):
        add_hand_creature(self.game, 1, 25, owner_id=1)
        hand_creature(self.game, 1, 25).held_item = 3
        self.game.players[1].health = 20

        self._run_turn_end(DEFAULT_CHOICES)

        self.assertEqual(self.game.players[1].health, 10)
        self.assertTrue(any("携带炸药" in message for message in self.messages))

    def test_white_pearl_gets_scavenger_held_item(self):
        add_hand_creature(self.game, 1, 25, owner_id=1)
        hand_creature(self.game, 1, 25).held_item = 5
        self.game.players[1].energy = 1

        self.assertTrue(self.play(46))

        self.assertIn(5, self.game.hand_cards)
        self.assertEqual(slugcat_data(self.game.players[1]).pearls_given, 1)
        self.assertTrue(any("好感度提升" in m for m in self.messages))

    def test_colored_pearl_hire_increases_scavenger_favor(self):
        add_hand_creature(self.game, 1, 25, owner_id=1)
        self.game.players[1].energy = 1

        self.assertTrue(self.play(47))

        self.assertEqual(slugcat_data(self.game.players[1]).pearls_given, 1)

    def test_scavenger_death_decreases_favor(self):
        add_hand_creature(self.game, 1, 25, owner_id=1)
        creature = hand_creature(self.game, 1, 25)
        self.game.players[1].statuses.hand_creatures.remove(creature)

        on_creature_death(self.game, 1, creature, self.messages.append)

        self.assertEqual(slugcat_data(self.game.players[1]).scavengers_killed, 1)
        self.assertTrue(any("好感度下降" in m for m in self.messages))

    def test_high_favor_scavenger_does_not_attack(self):
        add_hand_creature(self.game, 1, 25, owner_id=1)
        data = slugcat_data(self.game.players[1])
        data.pearls_given = 2
        data.scavengers_killed = 1
        self.game.players[1].health = 20

        self._run_turn_end(DEFAULT_CHOICES)

        self.assertEqual(self.game.players[1].health, 20)
        self.assertTrue(any("高好感度，不会攻击" in m for m in self.messages))

    def test_scavenger_attacks_at_low_favor(self):
        add_hand_creature(self.game, 1, 25, owner_id=1)
        hand_creature(self.game, 1, 25).held_item = 3
        self.game.players[1].health = 20

        self._run_turn_end(DEFAULT_CHOICES)

        self.assertEqual(self.game.players[1].health, 10)
        self.assertTrue(any("低好感度，攻击" in m for m in self.messages))

    def test_explosive_selects_target_and_hits_self(self):
        self.game.players[1].energy = 1
        self.game.players[2].health = 30
        self.game.players[1].health = 20

        self.assertTrue(self.play(3))

        self.assertEqual(self.game.players[2].health, 20)
        self.assertEqual(self.game.players[1].health, 15)
        self.assertTrue(
            any("玩家1使用炸药攻击玩家2" in m for m in self.messages)
        )

    def test_explosive_can_target_creature(self):
        add_hand_creature(self.game, 2, 20, owner_id=2)
        self.game.players[1].energy = 1
        self.game.players[1].health = 20

        self.assertTrue(
            DEFAULT_REGISTRY.play(
                state=self.game,
                character_id=4,
                card_id=3,
                source_player_id=1,
                target_player_id=2,
                announce=self.messages.append,
                combat=self.combat,
                choices=_TransferFlashChoices(),
            )
        )

        self.assertEqual(self.game.players[2].statuses.hand_creatures, [])
        self.assertEqual(self.game.players[1].health, 15)

    def test_creature_attack_respects_agility(self):
        add_hand_creature(self.game, 1, 19, owner_id=1)
        self.game.players[1].health = 20
        turn = TurnEngine(self.game, 1, 1, self.messages.append, choices=DEFAULT_CHOICES)
        self.combat.register_turn_handlers(turn)
        turn.enter_phase(TurnPhase.TURN_START)
        turn.enter_phase(TurnPhase.DRAW)
        turn.enter_phase(TurnPhase.PLAY)
        turn.enter_phase(TurnPhase.DISCARD)
        slugcat_data(self.game.players[1]).agility = 3

        turn.enter_phase(TurnPhase.TURN_END)

        self.assertEqual(self.game.players[1].health, 13)
        self.assertEqual(slugcat_data(self.game.players[1]).agility, 0)

    def test_player_attack_respects_defence(self):
        self.game.players[1].health = 20
        self.game.players[1].defences[:] = [
            DefenceEffect(turns_remaining=1, amount=4)
        ]

        lost = self.combat.apply_damage(10, 1, self.messages.append)

        self.assertEqual(lost, 6)
        self.assertEqual(self.game.players[1].health, 14)

    def test_creature_attack_announce_reflects_actual_damage(self):
        add_hand_creature(self.game, 1, 25, owner_id=1)
        hand_creature(self.game, 1, 25).held_item = 1  # 钢筋 2 伤
        self.game.players[1].health = 20
        turn = TurnEngine(self.game, 1, 1, self.messages.append, choices=DEFAULT_CHOICES)
        self.combat.register_turn_handlers(turn)
        turn.enter_phase(TurnPhase.TURN_START)
        turn.enter_phase(TurnPhase.DRAW)
        turn.enter_phase(TurnPhase.PLAY)
        turn.enter_phase(TurnPhase.DISCARD)
        slugcat_data(self.game.players[1]).agility = 1

        turn.enter_phase(TurnPhase.TURN_END)

        self.assertEqual(self.game.players[1].health, 19)
        self.assertTrue(
            any(
                "拾荒者携带一根钢筋对玩家1造成2点伤害"
                "（总伤害2，扣敏捷1，实际扣血1）" in m
                for m in self.messages
            )
        )

    def test_player_attack_announce_reports_breakdown(self):
        self.game.character_ids = {1: 4, 2: 4}
        self.combat = CombatEngine(self.game, DEFAULT_REGISTRY)
        self.combat.initialize_players()
        self.game.hand_cards[:] = [1]
        self.game.players[1].energy = 2
        self.game.players[2].health = 20
        slugcat_data(self.game.players[2]).agility = 1

        self.assertTrue(self.play(1))

        self.assertEqual(self.game.players[2].health, 19)
        self.assertTrue(
            any(
                "玩家1使用一根钢筋攻击玩家2"
                "（总伤害2，扣敏捷1，实际扣血1）" in m
                for m in self.messages
            )
        )
        self.assertFalse(any("失去1点生命" in m for m in self.messages))

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
