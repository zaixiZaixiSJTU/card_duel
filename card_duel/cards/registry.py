"""Generic card and character registry.

This module intentionally imports no concrete character package.
"""

from __future__ import annotations

from dataclasses import replace
from inspect import signature
from types import MappingProxyType

from card_duel.application.choices import DEFAULT_CHOICES, ChoiceProvider
from card_duel.cards.models import (
    CardDefinition,
    CardPlayContext,
    CharacterDefinition,
)
from card_duel.core.models import GameState


class CardRegistry:
    """Validated runtime catalog assembled by the application composition root."""

    def __init__(self) -> None:
        self._characters: dict[int, CharacterDefinition] = {}
        self._cards: dict[tuple[int, int], CardDefinition] = {}
        self._frozen = False

    def register_character(self, definition: CharacterDefinition) -> None:
        if self._frozen:
            raise RuntimeError("注册表已冻结")
        if definition.character_id in self._characters:
            raise ValueError(f"角色 {definition.character_id} 重复注册")

        card_ids = {card.card_id for card in definition.cards}
        if 0 not in card_ids:
            raise ValueError(f"角色 {definition.character_id} 缺少 0 号占位卡")
        missing = set(definition.deck_counts) - card_ids
        if missing:
            raise ValueError(
                f"角色 {definition.character_id} 的牌组引用未注册卡牌: {sorted(missing)}"
            )
        if any(count < 0 for count in definition.deck_counts.values()):
            raise ValueError(f"角色 {definition.character_id} 的卡牌数量不能为负")

        pending_cards = {}
        for card in definition.cards:
            if card.character_id != definition.character_id:
                raise ValueError(f"卡牌 {card.card_id} 的角色编号与角色目录不一致")
            key = (card.character_id, card.card_id)
            if key in self._cards or key in pending_cards:
                raise ValueError(f"卡牌 {key} 重复注册")
            if len(signature(card.handler).parameters) != 1:
                raise TypeError(f"卡牌 {key} 的处理器必须只接收 CardPlayContext")
            pending_cards[key] = card
        self._cards.update(pending_cards)
        self._characters[definition.character_id] = replace(
            definition,
            deck_counts=MappingProxyType(dict(definition.deck_counts)),
            cards=tuple(definition.cards),
        )

    def freeze(self) -> CardRegistry:
        self.validate()
        self._frozen = True
        return self

    def validate(self) -> None:
        if not self._characters:
            raise ValueError("注册表没有可用角色")
        for character_id, definition in self._characters.items():
            for card_id in definition.deck_counts:
                self.get_card(character_id, card_id)

    def get_character(self, character_id: int) -> CharacterDefinition:
        try:
            return self._characters[character_id]
        except KeyError as error:
            raise KeyError(f"角色 {character_id} 未注册") from error

    def get_card(self, character_id: int, card_id: int) -> CardDefinition:
        try:
            return self._cards[(character_id, card_id)]
        except KeyError as error:
            raise KeyError(f"角色 {character_id} 未注册卡牌 {card_id}") from error

    def get_deck_counts(self, character_id: int) -> dict[int, int]:
        return dict(self.get_character(character_id).deck_counts)

    def get_catalog(self, character_id: int) -> tuple[CardDefinition, ...]:
        return tuple(
            sorted(
                self.get_character(character_id).cards,
                key=lambda definition: definition.card_id,
            )
        )

    def play(
        self,
        *,
        state: GameState,
        character_id: int,
        card_id: int,
        source_player_id: int,
        target_player_id: int,
        announce,
        combat,
        choices: ChoiceProvider | None = None,
        ignore_cost: bool = False,
    ) -> bool | int:
        context = CardPlayContext(
            state=state,
            source_player_id=source_player_id,
            target_player_id=target_player_id,
            announce=announce,
            choices=choices or DEFAULT_CHOICES,
            combat=combat,
            registry=self,
            ignore_cost=ignore_cost,
        )
        return self.get_card(character_id, card_id).handler(context)

    @property
    def character_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._characters))
