"""Regression tests for the refactored domain boundaries."""

import ast
import inspect
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.registry import CardRegistry
from card_duel.cards.slugcat.catalog import register as register_slugcat
from card_duel.core.models import GameState
from card_duel.core.rules import add_defence, draw_cards


class _FixedChoices:
    def choose_integer(self, title, prompt, minimum, maximum, default):
        return 2

    def choose_option(self, title, prompt, options, default):
        return default

    def choose_card_indexes(self, title, hand, count, excluded_card_id=None):
        return [
            index for index, card_id in enumerate(hand) if card_id != excluded_card_id
        ][:count]


class ArchitectureTests(unittest.TestCase):
    def make_warrior_game(self):
        state = GameState(character_ids={1: 1, 2: 1})
        combat = CombatEngine(state, DEFAULT_REGISTRY)
        combat.initialize_players()
        return state, combat

    def test_game_state_contains_no_runtime_ui_or_socket(self):
        state = GameState()

        self.assertFalse(hasattr(state, "window"))
        self.assertFalse(hasattr(state, "connection"))

    def test_hand_is_compact_and_draw_returns_actual_count(self):
        state = GameState(draw_pile=[1, 2])

        self.assertEqual(draw_cards(state, 3), 2)
        self.assertEqual(state.hand_cards, [1, 2])
        self.assertEqual(state.hand_size, 2)
        self.assertEqual(state.draw_pile, [])

    def test_defence_absorbs_damage_and_updates_public_total(self):
        state, combat = self.make_warrior_game()
        add_defence(state.players[1].defences, 3)

        life_lost = combat.apply_damage(5, 1)

        self.assertEqual(life_lost, 2)
        self.assertEqual(state.players[1].health, 28)
        self.assertEqual(state.players[1].defence, 0)

    def test_defence_total_is_derived_from_player_effects(self):
        state, _ = self.make_warrior_game()

        add_defence(state.players[1].defences, 2)
        add_defence(state.players[1].defences, 3, turns_remaining=2)

        self.assertEqual(state.players[1].defence, 5)
        self.assertNotIn("defences", state.__dataclass_fields__)

    def test_card_registry_is_complete_for_every_configured_deck(self):
        DEFAULT_REGISTRY.validate()

        self.assertEqual(DEFAULT_REGISTRY.get_card(2, 5).name, "待实现")

    def test_slugcat_package_registers_itself_into_empty_registry(self):
        registry = CardRegistry()

        register_slugcat(registry)
        registry.freeze()

        self.assertEqual(registry.character_ids, (4,))
        self.assertEqual(len(registry.get_catalog(4)), 51)
        with self.assertRaises(TypeError):
            registry.get_character(4).deck_counts[6] = 999

    def test_failed_character_registration_is_atomic(self):
        registry = CardRegistry()
        warrior = DEFAULT_REGISTRY.get_character(1)
        invalid = replace(warrior, cards=warrior.cards + (warrior.cards[0],))

        with self.assertRaises(ValueError):
            registry.register_character(invalid)

        self.assertEqual(registry.character_ids, ())

    def test_registry_module_has_no_concrete_character_imports(self):
        registry_path = Path("card_duel/cards/registry.py")
        imported_modules = {
            node.module
            for node in ast.walk(ast.parse(registry_path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom)
        }

        self.assertFalse(
            any(
                module and ("warrior" in module or "slugcat" in module)
                for module in imported_modules
            )
        )

    def test_importing_registry_does_not_load_builtin_characters(self):
        script = (
            "import sys; import card_duel.cards.registry; "
            "assert 'card_duel.cards.warrior' not in sys.modules; "
            "assert 'card_duel.cards.slugcat' not in sys.modules"
        )

        subprocess.run([sys.executable, "-c", script], check=True)

    def test_every_card_handler_accepts_only_play_context(self):
        for character_id in DEFAULT_REGISTRY.character_ids:
            for definition in DEFAULT_REGISTRY.get_catalog(character_id):
                parameters = inspect.signature(definition.handler).parameters
                self.assertEqual(
                    len(parameters),
                    1,
                    f"{character_id}:{definition.card_id} handler contract drifted",
                )

    def test_core_rules_do_not_import_cards_ui_or_network(self):
        rules_path = Path("card_duel/core/rules.py")
        imported_modules = {
            node.module
            for node in ast.walk(ast.parse(rules_path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom)
        }

        self.assertFalse(
            any(
                module
                and module.startswith(
                    ("card_duel.cards", "card_duel.ui", "card_duel.network")
                )
                for module in imported_modules
            )
        )

    def test_internal_module_graph_has_no_import_cycles(self):
        module_paths = {
            ".".join(path.with_suffix("").parts): path
            for path in Path("card_duel").rglob("*.py")
        }
        graph = {module: set() for module in module_paths}
        for module, path in module_paths.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in module_paths:
                    graph[module].add(node.module)
                elif isinstance(node, ast.Import):
                    graph[module].update(
                        alias.name for alias in node.names if alias.name in module_paths
                    )

        visited = set()
        active = []

        def visit(module):
            if module in active:
                cycle = " -> ".join(active[active.index(module) :] + [module])
                self.fail(f"检测到内部导入环: {cycle}")
            if module in visited:
                return
            active.append(module)
            for dependency in graph[module]:
                visit(dependency)
            active.pop()
            visited.add(module)

        for module in graph:
            visit(module)

    def test_card_choice_is_injected_and_discards_compactly(self):
        state, combat = self.make_warrior_game()
        state.hand_cards = [16, 1, 2]
        state.players[1].energy = 3
        messages = []

        played = DEFAULT_REGISTRY.play(
            state=state,
            character_id=1,
            card_id=16,
            source_player_id=1,
            target_player_id=2,
            announce=messages.append,
            choices=_FixedChoices(),
            combat=combat,
        )

        self.assertTrue(played)
        self.assertEqual(state.hand_cards, [16])
        self.assertEqual(state.draw_pile, [1, 2])
        self.assertEqual(state.players[2].health, 26)

    def test_ignore_cost_does_not_create_negative_energy(self):
        state, combat = self.make_warrior_game()

        self.assertTrue(
            DEFAULT_REGISTRY.play(
                state=state,
                character_id=1,
                card_id=1,
                source_player_id=1,
                target_player_id=2,
                announce=lambda _: None,
                combat=combat,
                ignore_cost=True,
            )
        )
        self.assertEqual(state.players[1].energy, 0)

    def test_black_flash_with_empty_deck_does_not_spend_energy(self):
        state, combat = self.make_warrior_game()
        state.players[1].energy = 2

        self.assertFalse(
            DEFAULT_REGISTRY.play(
                state=state,
                character_id=1,
                card_id=15,
                source_player_id=1,
                target_player_id=2,
                announce=lambda _: None,
                combat=combat,
            )
        )
        self.assertEqual(state.players[1].energy, 2)


if __name__ == "__main__":
    unittest.main()
