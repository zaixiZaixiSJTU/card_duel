"""Runtime resources for one network game endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field
from socket import socket
from typing import Any

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.registry import CardRegistry
from card_duel.core.models import GameState


@dataclass
class GameSession:
    """Bind transport and presentation resources to serializable game state."""

    state: GameState
    connection: socket
    window: Any | None = None
    card_images: list[bytes] = field(default_factory=list)
    max_card_id: int = 0
    armed_hand_index: int | None = None
    deck_viewer_open: bool = False
    deck_viewer_page: int = 0
    deck_viewer_signature: object | None = None
    deck_viewer_card_ids: list[int] = field(default_factory=list)
    preview_window: Any | None = None
    animation_windows: list[Any] = field(default_factory=list)
    animation_callbacks: list[tuple[Any, str]] = field(default_factory=list)
    status_snapshots: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)
    registry: CardRegistry = field(default_factory=lambda: DEFAULT_REGISTRY)
    combat: CombatEngine = field(init=False)

    def __post_init__(self) -> None:
        self.combat = CombatEngine(self.state, self.registry)

    def require_window(self):
        if self.window is None:
            raise RuntimeError("游戏窗口尚未创建")
        return self.window
