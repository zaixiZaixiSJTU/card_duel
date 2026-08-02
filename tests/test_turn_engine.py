"""Tests for the strict five-phase turn engine."""

import unittest
from types import SimpleNamespace

from card_duel.core.game import PHASE_SEQUENCE, TurnEngine, TurnPhase


class TurnEngineTests(unittest.TestCase):
    def setUp(self):
        self.state = SimpleNamespace(
            round_number=0,
            active_player_id=None,
            current_phase=None,
        )
        self.engine = TurnEngine(
            self.state,
            round_number=3,
            player_id=1,
            announce=lambda _message: None,
        )

    def test_all_five_phases_run_in_order(self):
        visited_phases = []
        for phase in PHASE_SEQUENCE:
            self.engine.register_phase_handler(
                phase,
                lambda context, phases=visited_phases: phases.append(context.phase),
            )

        for phase in PHASE_SEQUENCE:
            self.engine.enter_phase(phase)

        self.assertEqual(visited_phases, list(PHASE_SEQUENCE))
        self.assertTrue(self.engine.is_complete)
        self.assertEqual(self.state.round_number, 3)
        self.assertEqual(self.state.current_phase, "回合结束时")

    def test_lower_priority_handler_runs_first(self):
        calls = []
        self.engine.register_phase_handler(
            TurnPhase.TURN_START,
            lambda _context: calls.append("later"),
            priority=20,
        )
        self.engine.register_phase_handler(
            TurnPhase.TURN_START,
            lambda _context: calls.append("earlier"),
            priority=10,
        )

        self.engine.enter_phase(TurnPhase.TURN_START)

        self.assertEqual(calls, ["earlier", "later"])

    def test_skipping_a_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.enter_phase(TurnPhase.PLAY)


if __name__ == "__main__":
    unittest.main()
