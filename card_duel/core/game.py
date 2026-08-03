"""Five-phase turn engine used by the network game."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class TurnPhase(Enum):
    """Stable timing points available to cards, abilities, and rules."""

    TURN_START = "回合开始时"
    DRAW = "抽牌阶段"
    PLAY = "出牌阶段"
    DISCARD = "弃牌阶段"
    TURN_END = "回合结束时"


PHASE_SEQUENCE = (
    TurnPhase.TURN_START,
    TurnPhase.DRAW,
    TurnPhase.PLAY,
    TurnPhase.DISCARD,
    TurnPhase.TURN_END,
)


@dataclass(frozen=True)
class TurnContext:
    """Information supplied to every phase handler."""

    game_state: object
    round_number: int
    player_id: int
    opponent_id: int
    phase: TurnPhase
    announce: Callable[[str], None]
    choices: object | None = None


class TurnEngine:
    """Advance one player's turn and dispatch registered phase handlers."""

    def __init__(self, game_state, round_number, player_id, announce, choices=None):
        self.game_state = game_state
        self.round_number = round_number
        self.player_id = player_id
        self.opponent_id = 2 if player_id == 1 else 1
        self.announce = announce
        self.choices = choices
        self.current_phase = None
        self._phase_index = -1
        self._handlers = {phase: [] for phase in PHASE_SEQUENCE}

    def register_phase_handler(self, phase, handler, priority=100):
        """Register a phase callback; lower priority values run first."""
        self._handlers[phase].append((priority, handler))
        self._handlers[phase].sort(key=lambda item: item[0])

    def enter_phase(self, phase):
        """Enter the next phase and run its handlers in priority order."""
        expected_index = self._phase_index + 1
        if expected_index >= len(PHASE_SEQUENCE):
            raise RuntimeError("当前回合已经结束")

        expected_phase = PHASE_SEQUENCE[expected_index]
        if phase is not expected_phase:
            raise ValueError(
                f"阶段顺序错误：期望 {expected_phase.value}，收到 {phase.value}"
            )

        self._phase_index = expected_index
        self.current_phase = phase
        self.game_state.round_number = self.round_number
        self.game_state.active_player_id = self.player_id
        self.game_state.current_phase = phase.value

        context = TurnContext(
            game_state=self.game_state,
            round_number=self.round_number,
            player_id=self.player_id,
            opponent_id=self.opponent_id,
            phase=phase,
            announce=self.announce,
            choices=self.choices,
        )
        for _, handler in self._handlers[phase]:
            handler(context)
        return context

    @property
    def is_complete(self):
        return self.current_phase is TurnPhase.TURN_END
