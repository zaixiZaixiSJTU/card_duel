"""Warrior card effects expressed through :class:`CardPlayContext`."""

from card_duel.cards.warrior.state import warrior_data
from card_duel.core.models import ScheduledEvent
from card_duel.core.rules import add_defence, draw_cards, schedule_event


def _spend(context, cost: int) -> bool:
    if not context.ignore_cost and context.source.energy < cost:
        context.announce(f"玩家{context.source_player_id}能量不足（需要{cost}）")
        return False
    if not context.ignore_cost:
        context.source.energy -= cost
    return True


def _discard_cards(context, title: str, count: int, excluded_card_id: int) -> bool:
    indexes = context.choices.choose_card_indexes(
        title,
        context.state.hand_cards,
        count,
        excluded_card_id,
    )
    if indexes is None or len(set(indexes)) != count:
        return False
    if any(index < 0 or index >= len(context.state.hand_cards) for index in indexes):
        return False
    discarded = [context.state.hand_cards[index] for index in indexes]
    for index in sorted(indexes, reverse=True):
        context.state.hand_cards.pop(index)
    context.state.draw_pile.extend(discarded)
    return True


def unavailable(context):
    context.announce("这张牌尚未实现")
    return False


def attack(context):
    if not _spend(context, 1):
        return False
    damage = 2 + context.source.strength
    context.combat.resolve_attack(context, damage, "攻")
    return True


def defend(context):
    if not _spend(context, 2):
        return False
    add_defence(context.source.defences, 3)
    context.announce(f"玩家{context.source_player_id}使用防（防御+3）")
    return True


def shield_bash(context):
    if not _spend(context, 2):
        return False
    damage = 2 + context.source.strength
    add_defence(context.source.defences, 2)
    context.combat.resolve_attack(context, damage, "盾击")
    context.announce(f"玩家{context.source_player_id}通过盾击获得2点防御")
    return True


def pack_god(context):
    maximum = max(0, len(context.state.hand_cards) - 1)
    count = context.choices.choose_integer(
        "背包之神", f"选择弃牌数（0-{maximum}）", 0, maximum, 0
    )
    if count is None or not _discard_cards(context, "背包之神", count, 4):
        return False
    context.source.energy += count - 1
    context.announce(
        f"玩家{context.source_player_id}召唤背包之神（弃{count}牌，能量{count - 1:+d}）"
    )
    return True


def sacrifice(context):
    if not _spend(context, 2):
        return False
    data = warrior_data(context.source)
    data.sacrifice_layers += 1
    context.announce(
        f"玩家{context.source_player_id}使用献祭（{data.sacrifice_layers}层）"
    )
    return True


def heavy_sword(context):
    if not _spend(context, 3):
        return False
    damage = 3 + 2 * context.source.strength
    context.combat.resolve_attack(context, damage, "重剑打击")
    return True


def heavy_hammer(context):
    if not _spend(context, 7):
        return False
    damage = 10 + context.source.strength
    context.combat.resolve_attack(context, damage, "重锤打击")
    return True


def burn(context):
    health_cost = context.choices.choose_integer(
        "燃烧", "选择燃烧的生命（1-3）", 1, 3, 1
    )
    if health_cost is None:
        return False
    data = warrior_data(context.source)
    context.combat.lose_life(health_cost, context.source_player_id, context.announce)
    context.source.strength += health_cost
    if data.sacrifice_layers:
        draw_cards(context.state, health_cost * data.sacrifice_layers)
    schedule_event(
        context.state.timeline,
        ScheduledEvent(
            1,
            4,
            -health_cost,
            context.source_player_id,
            f"玩家{context.source_player_id}燃尽了",
        ),
    )
    context.announce(f"玩家{context.source_player_id}燃烧生命（力量+{health_cost}）")
    return True


def glycogen(context):
    if not _spend(context, 2):
        return False
    schedule_event(
        context.state.timeline,
        ScheduledEvent(1, 4, 2, context.source_player_id, "糖原转化为力量"),
    )
    schedule_event(
        context.state.timeline,
        ScheduledEvent(2, 4, -2, context.source_player_id, "糖原转化为乳酸"),
    )
    context.announce(f"玩家{context.source_player_id}使用糖原堆积")
    return True


def bastion(context):
    if not _spend(context, 4):
        return False
    context.source.statuses.persistent_defence = True
    context.announce(f"玩家{context.source_player_id}建立壁垒，防御不再自然消散")
    return True


def consolidate(context):
    if not _spend(context, 3):
        return False
    for effect in context.source.defences:
        effect.amount = int(effect.amount * 1.5)
    context.announce(f"玩家{context.source_player_id}使用巩固（防御×1.5）")
    return True


def full_body_slam(context):
    if not _spend(context, 4):
        return False
    damage = context.source.defence + context.source.strength
    context.combat.resolve_attack(context, damage, "全身撞击")
    return True


def immovable_mountain(context):
    if not _spend(context, 3):
        return False
    add_defence(context.source.defences, 10)
    context.announce(f"玩家{context.source_player_id}不动如山（防御+10）")
    return True


def heartlink(context):
    if not _spend(context, 2):
        return False
    warrior_data(context.source).heartlink_layers += 1
    context.announce(f"玩家{context.source_player_id}使用心连心")
    return True


def black_flash(context):
    if not context.state.draw_pile or not _spend(context, 2):
        return False
    card_id = context.state.draw_pile.pop(0)
    context.announce("黑闪！")
    context.play_card(card_id, ignore_cost=True)
    if card_id not in (10, 13):
        context.state.draw_pile.append(card_id)
    return True


def burnt_offering(context):
    if not _spend(context, 3):
        return False
    maximum = max(0, len(context.state.hand_cards) - 1)
    count = context.choices.choose_integer(
        "燔祭", f"选择弃牌数（0-{maximum}）", 0, maximum, 0
    )
    if count is None or not _discard_cards(context, "燔祭", count, 16):
        if not context.ignore_cost:
            context.source.energy += 3
        return False
    damage = count + 2 + context.source.strength
    context.combat.resolve_attack(context, damage, "燔祭")
    context.announce(f"玩家{context.source_player_id}为燔祭弃掉{count}张牌")
    return True
