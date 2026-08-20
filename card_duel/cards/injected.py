"""Cross-character cards inserted into a player's hand by another card."""

from card_duel.cards.models import CardDefinition

INSERTED_CARD_IDS = (49, 50)


def handler_for(card_id: int):
    def play_inserted_card(context):
        """Pay one energy to remove one matching inserted item."""
        if not context.ignore_cost and context.source.energy < 1:
            context.announce("能量不足，拔出插入物需要1点能量")
            return False
        item = next(
            (
                item
                for item in context.source.statuses.inserted_cards
                if item.card_id == card_id
            ),
            None,
        )
        if item is None:
            context.announce("没有对应的插入物可以拔出")
            return False
        if not context.ignore_cost:
            context.source.energy -= 1

        context.source.statuses.inserted_cards.remove(item)
        if card_id == 49:
            context.source.statuses.embedded_steel_rods = max(
                0, context.source.statuses.embedded_steel_rods - 1
            )
            normal_card_id = 1
            item_name = "钢筋"
        else:
            context.source.statuses.embedded_electric_spears = max(
                0, context.source.statuses.embedded_electric_spears - 1
            )
            restored = min(2, context.source.statuses.electric_strength_penalty)
            context.source.strength += restored
            context.source.statuses.electric_strength_penalty -= restored
            normal_card_id = None
            item_name = "电矛"

        if normal_card_id is not None:
            if item.owner_id == context.state.local_player_id:
                context.state.discard_pile.append(normal_card_id)
            else:
                context.state.players[
                    item.owner_id
                ].statuses.pending_draw_returns.append(normal_card_id)
        context.announce(f"玩家{context.source_player_id}拔出1根{item_name}")
        return True

    return play_inserted_card


def definitions_for(character_id: int) -> tuple[CardDefinition, ...]:
    descriptions = {
        49: "耗能1拔出体内钢筋；普通钢筋返回原主人的牌堆。不可弃牌。",
        50: "耗能1拔出电矛并恢复对应力量；电矛消耗，不返还。不可弃牌。",
    }
    return tuple(
        CardDefinition(
            character_id,
            card_id,
            "钢筋【插入】" if card_id == 49 else "电矛【插入】",
            handler_for(card_id),
            exhausted=True,
            card_type="物品",
            cost=1,
            description=descriptions[card_id],
        )
        for card_id in INSERTED_CARD_IDS
    )
