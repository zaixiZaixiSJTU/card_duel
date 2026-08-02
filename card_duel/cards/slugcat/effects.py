"""Slugcat card effects using explicit play context and typed state."""

import math
import random

from card_duel.cards.slugcat.hand import (
    add_creature_threat,
    count_card,
    pop_first_creature,
    remove_all_creatures,
    remove_first,
)
from card_duel.cards.slugcat.specs import (
    DISCOVERY_ADJACENCY,
    DISCOVERY_CONTENTS,
    FORM_NAMES,
    SLUGCAT_ATTACK_ITEM_IDS,
    SLUGCAT_CREATURE_IDS,
    SLUGCAT_DISCOVERY_IDS,
    SLUGCAT_SPECS_BY_ID,
)
from card_duel.cards.slugcat.state import MAX_KARMA, slugcat_data
from card_duel.core.rules import add_card_to_hand


def make_handler(card_id: int):
    def handler(context):
        return play_card(card_id, context)

    return handler


def play_card(card_id: int, context):
    data = slugcat_data(context.source)
    if card_id in SLUGCAT_ATTACK_ITEM_IDS and context.source.statuses.attack_lock:
        context.announce(
            f"玩家{context.source_player_id}仍处于致盲状态，不能打出攻击牌"
        )
        return False

    played = CARD_EFFECTS[card_id](context)
    if not played:
        return False
    _resolve_action_chain(context, card_id)
    data.last_card_id = card_id
    if card_id not in SLUGCAT_ATTACK_ITEM_IDS and context.source.statuses.attack_lock:
        context.source.statuses.attack_lock -= 1
    return True


def _resolve_action_chain(context, card_id: int) -> None:
    data = slugcat_data(context.source)
    if card_id == 6 or not data.jump_followup:
        return
    if card_id in (2, 4, 5):
        data.agility += 1
        context.announce(
            f"玩家{context.source_player_id}借小跳衔接攻击，额外获得1点敏捷"
        )
    data.jump_followup = False


def _effective_cost(context, card_id: int) -> int | None:
    cost = SLUGCAT_SPECS_BY_ID[card_id].cost
    if cost is None:
        return None
    data = slugcat_data(context.source)
    if card_id == 7 and data.last_card_id in (8, 9):
        cost = max(0, cost - 1)
    if card_id in SLUGCAT_DISCOVERY_IDS and count_card(context.state, 26):
        cost = max(0, cost - 1)
    return cost


def _pay_cost(context, card_id: int) -> bool:
    cost = _effective_cost(context, card_id)
    if cost is None:
        return False
    if context.ignore_cost:
        return True
    if context.source.energy < cost:
        context.announce(f"玩家{context.source_player_id}能量不足（需要{cost}）")
        return False
    context.source.energy -= cost
    return True


def _attack_with_momentum(context, base_damage: int) -> tuple[int, int]:
    data = slugcat_data(context.source)
    damage = base_damage + context.source.strength + data.momentum
    data.momentum = 0
    life_loss = context.combat.apply_damage(damage, context.target_player_id)
    return damage, life_loss


def _attack(card_id: int, base_damage: int, on_penetrate=None):
    def effect(context):
        if not _pay_cost(context, card_id):
            return False
        damage, life_loss = _attack_with_momentum(context, base_damage)
        context.announce(
            f"玩家{context.source_player_id}使用{SLUGCAT_SPECS_BY_ID[card_id].name}"
            f"（造成{damage}点伤害）"
        )
        if life_loss > 0 and on_penetrate:
            on_penetrate(context)
        return True

    return effect


def _insert_steel_rod(context):
    context.target.statuses.embedded_steel_rods += 1
    context.announce(f"钢筋插入玩家{context.target_player_id}的手牌区")


def _insert_explosive_spear(context):
    context.combat.lose_life(10, context.target_player_id, context.announce)
    context.target.statuses.pending_discards += 1
    context.announce(
        f"炸矛穿透：玩家{context.target_player_id}失去10点生命并需随机弃1张牌"
    )


def _insert_electric_spear(context):
    context.target.statuses.embedded_electric_spears += 1
    context.announce(f"电矛插入玩家{context.target_player_id}，其后续回合力量将降低")


def explosive(context):
    if not _pay_cost(context, 3):
        return False
    context.combat.apply_damage(10, context.target_player_id)
    context.combat.apply_damage(5, context.source_player_id)
    context.announce(f"玩家{context.source_player_id}引爆炸药（对目标10伤，自身5伤）")
    return True


def hop(context):
    if not _pay_cost(context, 6):
        return False
    data = slugcat_data(context.source)
    data.agility += 1
    data.jump_followup = True
    context.announce(f"玩家{context.source_player_id}小跳，获得1点敏捷")
    return True


def ridge_jump(context):
    if not _pay_cost(context, 7):
        return False
    slugcat_data(context.source).agility += 3
    context.announce(f"玩家{context.source_player_id}脊背大跳，获得3点敏捷")
    return True


def slide(context):
    if not _pay_cost(context, 8):
        return False
    slugcat_data(context.source).momentum += 4
    context.announce(f"玩家{context.source_player_id}滑铲，获得4点动能")
    return True


def roll(context):
    data = slugcat_data(context.source)
    if data.agility < 2:
        context.announce("翻滚需要至少2点敏捷")
        return False
    if not _pay_cost(context, 9):
        return False
    converted = data.agility + 2
    data.agility = 0
    data.momentum += converted
    context.announce(
        f"玩家{context.source_player_id}翻滚，将{converted}点敏捷势能转为动能"
    )
    return True


def crouch(context):
    if not _pay_cost(context, 10):
        return False
    data = slugcat_data(context.source)
    data.agility = data.momentum = 0
    creature_id = random.choice(SLUGCAT_CREATURE_IDS)
    add_creature_threat(context.state, context.target_player_id, creature_id)
    context.announce(
        f"玩家{context.source_player_id}趴下，"
        f"{SLUGCAT_SPECS_BY_ID[creature_id].name}转向玩家{context.target_player_id}"
    )
    return True


def backflip(context):
    if not _pay_cost(context, 11):
        return False
    data = slugcat_data(context.source)
    data.momentum += 4
    data.agility += 2
    context.announce(f"玩家{context.source_player_id}后空翻，获得4动能和2敏捷")
    return True


def sleep(context):
    data = slugcat_data(context.source)
    if data.satiety < 3:
        context.announce("饱食度不足，无法睡觉")
        return False
    if not _pay_cost(context, 12):
        return False
    data.satiety -= 3
    data.karma = min(data.karma_max, data.karma + 1)
    context.announce(f"玩家{context.source_player_id}安稳睡下，业力+1")
    return True


def forage(context):
    if not _pay_cost(context, 13):
        return False
    gained = math.ceil(context.source.statuses.last_dead_creature_health / 5)
    slugcat_data(context.source).satiety += gained
    context.announce(f"玩家{context.source_player_id}觅食，获得{gained}点饱食度")
    return True


def run_away(context):
    data = slugcat_data(context.source)
    if data.next_x_cost is not None:
        amount = max(0, min(context.source.energy, data.next_x_cost))
        data.next_x_cost = None
    elif context.ignore_cost:
        amount = 0
    else:
        maximum = max(0, context.source.energy)
        amount = context.choices.choose_integer(
            "猫跑路了", f"投入能量（0-{maximum}）", 0, maximum, maximum
        )
    if amount is None:
        return False
    if not context.ignore_cost:
        context.source.energy -= amount
    remove_all_creatures(context.state)
    obtained = 0
    for _ in range(amount):
        if not data.discovery_pool:
            break
        add_card_to_hand(context.state, data.discovery_pool.pop(0))
        obtained += 1
    for _ in range(amount - obtained):
        add_card_to_hand(context.state, random.choice(SLUGCAT_CREATURE_IDS))
    context.announce(f"玩家{context.source_player_id}跑路，获得{obtained}张见闻牌")
    return True


def trouble(context):
    if not _pay_cost(context, 15):
        return False
    creature_id = random.choice(SLUGCAT_CREATURE_IDS)
    add_card_to_hand(context.state, creature_id)
    context.announce(
        f"玩家{context.source_player_id}闯祸，引来了"
        f"{SLUGCAT_SPECS_BY_ID[creature_id].name}"
    )
    return True


def _creature(card_id: int):
    def effect(context):
        spec = SLUGCAT_SPECS_BY_ID[card_id]
        if spec.cost is None:
            context.announce(f"{spec.name}不可主动打出")
            return False
        if not _pay_cost(context, card_id):
            return False
        if card_id in (16, 18, 24):
            add_creature_threat(context.state, context.target_player_id, card_id)
        if card_id == 18:
            add_creature_threat(context.state, context.target_player_id, 19)
        if card_id == 19:
            context.combat.apply_damage(10, context.target_player_id)
        context.announce(f"玩家{context.source_player_id}处理了{spec.name}")
        return True

    return effect


def _discovery(card_id: int):
    def effect(context):
        if not _pay_cost(context, card_id):
            return False
        data = slugcat_data(context.source)
        if card_id not in data.seen_discoveries:
            data.seen_discoveries.append(card_id)
            data.karma_max = min(MAX_KARMA, data.karma_max + 1)
        for new_card_id, count in DISCOVERY_CONTENTS[card_id].items():
            context.state.draw_pile.extend([new_card_id] * count)
        random.shuffle(context.state.draw_pile)
        _unlock_adjacent_discovery(data, card_id)
        context.announce(
            f"玩家{context.source_player_id}探索"
            f"{SLUGCAT_SPECS_BY_ID[card_id].name}，牌组获得新的物品与生物"
        )
        return True

    return effect


def _unlock_adjacent_discovery(data, card_id: int) -> None:
    adjacent = DISCOVERY_ADJACENCY[card_id]
    unseen = [item for item in adjacent if item not in data.seen_discoveries]
    candidates = unseen or list(adjacent)
    data.discovery_pool.append(
        min(candidates, key=lambda item: data.discovery_pool.count(item))
    )


def _form(card_id: int):
    def effect(context):
        if not _pay_cost(context, card_id):
            return False
        form_name = FORM_NAMES[card_id]
        slugcat_data(context.source).form = form_name
        context.announce(f"玩家{context.source_player_id}切换为{form_name}形态")
        return True

    return effect


def smoke_fruit(context):
    if not _pay_cost(context, 41):
        return False
    context.source.statuses.immune_next_attacks += 1
    remove_first(context.state, 22)
    context.announce(f"玩家{context.source_player_id}释放烟雾，将免疫下一次攻击")
    return True


def batfly_grass(context):
    if not _pay_cost(context, 42):
        return False
    context.announce(f"玩家{context.source_player_id}打出了蝠蝇草")
    return True


def flash_fruit(context):
    if not _pay_cost(context, 43):
        return False
    creature_id = pop_first_creature(context.state)
    if creature_id is not None:
        add_creature_threat(context.state, context.target_player_id, creature_id)
        context.announce(f"闪光果将{SLUGCAT_SPECS_BY_ID[creature_id].name}赶向对手")
    else:
        context.target.statuses.attack_lock = 2
        context.announce(f"玩家{context.target_player_id}被致盲，需先打出两张非攻击牌")
    return True


def blue_fruit(context):
    if not _pay_cost(context, 44):
        return False
    slugcat_data(context.source).satiety += 1
    context.announce(f"玩家{context.source_player_id}吃下蓝果，饱食度+1")
    return True


def bubble_fruit(context):
    data = slugcat_data(context.source)
    mode = data.next_bubble_mode
    data.next_bubble_mode = None
    if mode is None:
        mode = context.choices.choose_option(
            "泡水果", "选择泡水果的使用方式", ("fruit", "stone"), "fruit"
        )
    if mode is None:
        return False
    if mode == "fruit":
        data.satiety += 1
        context.announce(f"玩家{context.source_player_id}把泡水果当作蓝果")
        return True
    damage, _ = _attack_with_momentum(context, 1)
    context.announce(
        f"玩家{context.source_player_id}把泡水果当作石子（造成{damage}点伤害）"
    )
    return True


def white_pearl(context):
    if not _pay_cost(context, 46):
        return False
    if remove_first(context.state, 25):
        item = random.choices((1, 3, 4, 5), weights=(6, 1, 2, 1), k=1)[0]
        add_card_to_hand(context.state, item)
        context.source.statuses.last_dead_creature_health = 5
        context.announce("白珍珠换来了拾荒者携带的物品")
    else:
        context.source.statuses.scavenger_attraction = True
        context.announce("白珍珠正在吸引拾荒者")
    return True


def colored_pearl(context):
    if not _pay_cost(context, 47):
        return False
    if remove_first(context.state, 25):
        add_creature_threat(context.state, context.target_player_id, 25)
        context.announce(
            f"玩家{context.source_player_id}雇佣拾荒者对付玩家"
            f"{context.target_player_id}"
        )
    else:
        context.source.statuses.scavenger_attraction = True
        context.announce("有色珍珠正在吸引拾荒者")
    return True


def mass_battery(context):
    if not _pay_cost(context, 48):
        return False
    slugcat_data(context.source).agility += 99
    context.announce(f"玩家{context.source_player_id}启动质量稀释电池，敏捷+99")
    return True


CARD_EFFECTS = {
    1: _attack(1, 2, _insert_steel_rod),
    2: _attack(2, 1),
    3: explosive,
    4: _attack(4, 3, _insert_explosive_spear),
    5: _attack(5, 3, _insert_electric_spear),
    6: hop,
    7: ridge_jump,
    8: slide,
    9: roll,
    10: crouch,
    11: backflip,
    12: sleep,
    13: forage,
    14: run_away,
    15: trouble,
    **{card_id: _creature(card_id) for card_id in range(16, 27)},
    **{card_id: _discovery(card_id) for card_id in range(27, 36)},
    **{card_id: _form(card_id) for card_id in range(36, 41)},
    41: smoke_fruit,
    42: batfly_grass,
    43: flash_fruit,
    44: blue_fruit,
    45: bubble_fruit,
    46: white_pearl,
    47: colored_pearl,
    48: mass_battery,
}
