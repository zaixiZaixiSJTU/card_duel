"""Explicit catalogs for characters whose mechanics are not implemented yet."""

from dataclasses import dataclass

from card_duel.cards.injected import definitions_for as inserted_definitions
from card_duel.cards.models import CardDefinition, CharacterDefinition


@dataclass(slots=True)
class PlaceholderData:
    label: str = "开发中"


class PlaceholderRules:
    def create_data(self):
        return PlaceholderData()

    def initialize(self, player) -> None:
        player.health = player.max_health = 30

    def register_turn_handlers(self, turn, combat) -> None:
        return None

    def prevent_life_loss(self, player, amount: int) -> int:
        return amount

    def on_life_depleted(self, state, player_id, announce=None) -> None:
        return None

    def is_defeated(self, player) -> bool:
        return player.health <= 0

    def format_status(self, player) -> str:
        return "开发中"


def unavailable(context):
    context.announce("该角色仍在开发中")
    return False


def register(registry) -> None:
    for character_id, name in ((2, "女猎手"), (3, "时间守护者")):
        registry.register_character(
            CharacterDefinition(
                character_id=character_id,
                name=name,
                deck_counts={1: 2, 2: 3, 3: 1, 4: 4, 5: 2},
                cards=tuple(
                    CardDefinition(
                        character_id,
                        card_id,
                        "不可用" if card_id == 0 else "待实现",
                        unavailable,
                        description="该角色仍在开发中",
                    )
                    for card_id in range(6)
                )
                + inserted_definitions(character_id),
                rules=PlaceholderRules(),
            )
        )
