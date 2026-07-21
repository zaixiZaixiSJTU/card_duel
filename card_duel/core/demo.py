"""UI-independent rules for the lightweight local demo."""

import random
from dataclasses import dataclass

from card_duel.core.characters import LOCAL_CHARACTER_PROFILES


@dataclass
class LocalPlayer:
    """Runtime values for one local-demo player."""

    name: str
    icon: str
    color: str
    max_health: int
    energy_range: tuple[int, int]
    health: int
    energy: int = 0

    @classmethod
    def from_character(cls, character_id):
        profile = LOCAL_CHARACTER_PROFILES[character_id]
        return cls(
            name=profile["name"],
            icon=profile["icon"],
            color=profile["color"],
            max_health=profile["health"],
            energy_range=profile["energy_range"],
            health=profile["health"],
        )


class LocalGame:
    """Manage the state and simple rules of a two-player local match."""

    def __init__(self, player_one_character_id, player_two_character_id):
        self.players = {
            1: LocalPlayer.from_character(player_one_character_id),
            2: LocalPlayer.from_character(player_two_character_id),
        }
        self.round_number = 1
        self.starting_player_id = random.randint(1, 2)
        self.active_player_id = self.starting_player_id
        self.is_over = False
        self.winner_id = None

    @property
    def current_player(self):
        return self.players[self.active_player_id]

    @property
    def defending_player(self):
        opponent_id = 2 if self.active_player_id == 1 else 1
        return self.players[opponent_id]

    def start_round(self):
        """Allocate energy and return messages describing the new round."""
        for player in self.players.values():
            player.energy = random.randint(*player.energy_range)

        self.active_player_id = self.starting_player_id
        return [
            f"\n═══  第 {self.round_number} 回合  ═══",
            f"玩家{self.starting_player_id} 先手",
        ]

    def play_card(self):
        """Spend two energy and apply random damage."""
        attacking_player = self.current_player
        defending_player = self.defending_player
        if attacking_player.energy < 2:
            return False, 0

        damage = random.randint(3, 8)
        attacking_player.energy -= 2
        defending_player.health -= damage
        if defending_player.health <= 0:
            self.is_over = True
            self.winner_id = self.active_player_id
        return True, damage

    def end_turn(self):
        """Switch players, or advance the round after both have acted."""
        if self.active_player_id == self.starting_player_id:
            self.active_player_id = 2 if self.starting_player_id == 1 else 1
            return "switch"

        self.round_number += 1
        self.starting_player_id = 2 if self.starting_player_id == 1 else 1
        return "new_round"

    def format_status(self):
        """Return a compact text representation of both players."""
        player_one = self.players[1]
        player_two = self.players[2]
        return [
            "┌" + "─" * 24 + "┐",
            f"│ P1 {player_one.name:<6}"
            f" HP {player_one.health:<3}"
            f" EP {player_one.energy:<2} │",
            f"│ P2 {player_two.name:<6}"
            f" HP {player_two.health:<3}"
            f" EP {player_two.energy:<2} │",
            "└" + "─" * 24 + "┘",
        ]

    def format_chat(self, message):
        player = self.current_player
        return f"  ··· [玩家{self.active_player_id} {player.name}]: {message}"
