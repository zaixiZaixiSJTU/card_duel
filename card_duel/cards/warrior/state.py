"""Typed runtime data owned by the Warrior character."""

from dataclasses import dataclass


@dataclass(slots=True)
class WarriorData:
    sacrifice_layers: int = 0
    heartlink_layers: int = 0


def warrior_data(player) -> WarriorData:
    if not isinstance(player.character_data, WarriorData):
        raise TypeError("当前玩家不是战士或尚未初始化")
    return player.character_data
