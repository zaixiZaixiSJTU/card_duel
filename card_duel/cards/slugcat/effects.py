"""Slugcat card effects using explicit play context and typed state."""

import math
import random

from card_duel.cards.slugcat.creatures import (
    add_hand_creature,
    add_threat,
    kill_matching_creature,
    remove_all_local_hand_creatures,
    remove_hand_creature,
    return_creature_to_owner_pool,
)
from card_duel.cards.slugcat.hand import draw_non_creatures
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
from card_duel.core.models import InsertedCardState
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
    if card_id in SLUGCAT_DISCOVERY_IDS:
        data.discovery_discount[card_id] = data.discovery_discount.get(card_id, 0) + 1
    if card_id not in SLUGCAT_ATTACK_ITEM_IDS and context.source.statuses.attack_lock:
        context.source.statuses.attack_lock -= 1
    return True


def _resolve_action_chain(context, card_id: int) -> None:
    data = slugcat_data(context.source)
    if card_id == 6 or not data.jump_followup:
        return
    if card_id in SLUGCAT_ATTACK_ITEM_IDS:
        data.agility += 1
        context.announce(
            f"玩家{context.source_player_id}借小跳衔接攻击，额外获得1点敏捷"
        )
    data.jump_followup = False


def effective_cost(state, player_id: int, card_id: int) -> int | None:
    cost = SLUGCAT_SPECS_BY_ID[card_id].cost
    if cost is None:
        return None
    player = state.players[player_id]
    data = slugcat_data(player)
    if card_id == 7 and data.last_card_id in (8, 9):
        cost = max(0, cost - 1)
    if card_id in SLUGCAT_DISCOVERY_IDS:
        cost = max(0, cost - data.discovery_discount.get(card_id, 0))
    if card_id == 16:
        creature = next(
            (item for item in player.statuses.hand_creatures if item.card_id == 16),
            None,
        )
        if creature is not None:
            cost += creature.noodle_cost
    return cost


def _pay_cost(context, card_id: int) -> bool:
    cost = effective_cost(context.state, context.source_player_id, card_id)
    if cost is None:
        return False
    if context.ignore_cost:
        return True
    if context.source.energy < cost:
        context.announce(f"玩家{context.source_player_id}能量不足（需要{cost}）")
        return False
    context.source.energy -= cost
    return True


def _attack_with_momentum(context, base_damage: int) -> int:
    data = slugcat_data(context.source)
    damage = base_damage + context.source.strength + data.momentum
    data.momentum = 0
    return damage


def _attack(card_id: int, base_damage: int, on_penetrate=None):
    def effect(context):
        if not _pay_cost(context, card_id):
            return False
        damage = _attack_with_momentum(context, base_damage)
        context.combat.resolve_attack(
            context,
            damage,
            SLUGCAT_SPECS_BY_ID[card_id].name,
            on_penetrate,
        )
        return True

    return effect


def _insert_steel_rod(context):
    context.target.statuses.embedded_steel_rods += 1
    context.target.statuses.inserted_cards.append(
        InsertedCardState(49, context.source_player_id)
    )
    _queue_hand_card(context, 49)
    context.announce(f"钢筋插入玩家{context.target_player_id}的手牌")


def _insert_explosive_spear(context):
    context.combat.lose_life(10, context.target_player_id, context.announce)
    context.target.statuses.pending_discards += 1
    context.announce(
        f"炸矛穿透：玩家{context.target_player_id}失去10点生命并随机弃1张牌"
    )


def _insert_electric_spear(context):
    context.target.statuses.embedded_electric_spears += 1
    context.target.statuses.inserted_cards.append(
        InsertedCardState(50, context.source_player_id)
    )
    _queue_hand_card(context, 50)
    context.announce(f"电矛插入玩家{context.target_player_id}，其后续回合力量将降低")


def _queue_hand_card(context, card_id: int) -> None:
    if context.target_player_id == context.state.local_player_id:
        add_card_to_hand(context.state, card_id)
    else:
        context.target.statuses.pending_hand_additions.append(card_id)


def explosive(context):
    if not _pay_cost(context, 3):
        return False
    context.combat.resolve_attack(
        context, 10, SLUGCAT_SPECS_BY_ID[3].name
    )
    context.announce(f"玩家{context.source_player_id}引爆炸药")
    context.combat.apply_damage(5, context.source_player_id, context.announce)
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
    data.redirect_creatures_to_opponent = True
    context.announce(
        f"玩家{context.source_player_id}趴下，取消全部敏捷和动能；"
        f"本回合猫闯祸生成的生物将进入玩家{context.target_player_id}手牌"
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
    context.source.statuses.last_dead_creature_health = 0
    draw_non_creatures(context.state, 1)
    context.announce(
        f"玩家{context.source_player_id}觅食，获得{gained}点饱食度并抽1张牌"
    )
    return True


def run_away(context):
    data = slugcat_data(context.source)
    amount = 0 if context.ignore_cost else context.source.energy
    context.source.energy = 0
    draw_count = max(0, amount - 1)
    removed = remove_all_local_hand_creatures(
        context.state, context.source_player_id
    )
    # 跑路的生物没有死亡，离场后回到主人的可召唤池，之后仍可被猫闯祸召唤。
    for creature in removed:
        return_creature_to_owner_pool(context.state, creature)
    obtained = 0
    seen = set(data.seen_discoveries)
    for _ in range(draw_count):
        if data.discovery_pool:
            index = next(
                (
                    index
                    for index, candidate in enumerate(data.discovery_pool)
                    if candidate not in seen
                ),
                0,
            )
            add_card_to_hand(context.state, data.discovery_pool.pop(index))
            obtained += 1
        else:
            obtained += draw_non_creatures(context.state, 1)
    context.announce(
        f"玩家{context.source_player_id}跑路，耗尽{amount}点能量，获得{obtained}张牌"
    )
    return True


def trouble(context):
    if not _pay_cost(context, 15):
        return False
    data = slugcat_data(context.source)
    # 按 unlocked_creature_counts 加权随机：count 即为可召唤数量，召唤后 -1，减到 0 删除
    if data.unlocked_creature_counts:
        pool_ids = list(data.unlocked_creature_counts.keys())
        weights = [data.unlocked_creature_counts[cid] for cid in pool_ids]
        creature_id = random.choices(pool_ids, weights=weights, k=1)[0]
        data.unlocked_creature_counts[creature_id] -= 1
        if data.unlocked_creature_counts[creature_id] <= 0:
            del data.unlocked_creature_counts[creature_id]
    else:
        # 空池 fallback：仍按场景默认生物种类随机一次（不计入 unlocked_creature_counts）
        creature_id = random.choice([16, 20, 25])
    destination = (
        context.target_player_id
        if data.redirect_creatures_to_opponent
        else context.source_player_id
    )
    creature = add_hand_creature(
        context.state,
        destination,
        creature_id,
        owner_id=context.source_player_id,
    )
    draw_non_creatures(context.state, 2)
    context.announce(
        f"玩家{context.source_player_id}闯祸，"
        f"{SLUGCAT_SPECS_BY_ID[creature_id].name}加入玩家{destination}手牌，并抽2张牌"
    )
    if creature_id == 25:
        context.announce_private(
            f"拾荒者携带物品：{SLUGCAT_SPECS_BY_ID[creature.held_item].name}"
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
            creature = remove_hand_creature(
                context.state,
                context.source_player_id,
                card_id,
                remove_physical=False,
            )
            noodle_cost = (creature.noodle_cost + 1) if creature else 0
            add_hand_creature(
                context.state,
                context.target_player_id,
                card_id,
                owner_id=context.source_player_id,
                noodle_cost=noodle_cost,
            )
            context.announce(
                f"玩家{context.source_player_id}将{spec.name}转移到"
                f"玩家{context.target_player_id}手牌"
            )
        else:
            # 打出生物 = 躲避：消耗能量后生物离开手牌，回合结束不再造成伤害。
            remove_hand_creature(context.state, context.source_player_id, card_id)
            context.announce(f"玩家{context.source_player_id}打出了{spec.name}")
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
        context.state.draw_pile[:] = [
            item
            for item in context.state.draw_pile
            if SLUGCAT_SPECS_BY_ID[item].card_type != "物品"
        ]
        # Scene change also retires non-item cards sitting in the discard pile
        # so they cannot cycle back into the new scene on the next reshuffle.
        context.state.discard_pile[:] = [
            item
            for item in context.state.discard_pile
            if SLUGCAT_SPECS_BY_ID[item].card_type == "物品"
        ]
        data.unlocked_creature_counts.clear()
        for new_card_id, count in DISCOVERY_CONTENTS[card_id].items():
            if new_card_id in SLUGCAT_CREATURE_IDS:
                data.unlocked_creature_counts[new_card_id] = count
            else:
                context.state.draw_pile.extend([new_card_id] * count)
        random.shuffle(context.state.draw_pile)
        _unlock_adjacent_discovery(data, card_id)
        context.announce(
            f"玩家{context.source_player_id}探索"
            f"{SLUGCAT_SPECS_BY_ID[card_id].name}，切换到新的物品与生物场景"
        )
        return True

    return effect


def _unlock_adjacent_discovery(data, card_id: int) -> None:
    adjacent = DISCOVERY_ADJACENCY[card_id]
    unseen = [
        item
        for item in adjacent
        if item not in data.seen_discoveries and item not in data.discovery_pool
    ]
    for candidate in reversed(unseen):
        data.discovery_pool.insert(0, candidate)


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
    kill_matching_creature(context, 22)
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
    creatures = context.source.statuses.hand_creatures
    player_label = f"玩家{context.target_player_id}"
    creature_labels = [
        f"{SLUGCAT_SPECS_BY_ID[item.card_id].name} #{index + 1}"
        for index, item in enumerate(creatures)
    ]
    labels = [player_label] + creature_labels
    selected = context.choices.choose_option(
        "闪光果", "选择目标：转移生物或致盲玩家", labels, labels[0]
    )
    if selected in creature_labels:
        index = creature_labels.index(selected)
        creature = creatures[index]
        held_item = creature.held_item
        remove_hand_creature(context.state, context.source_player_id, creature.card_id)
        transferred = add_hand_creature(
            context.state,
            context.target_player_id,
            creature.card_id,
            owner_id=creature.owner_id,
        )
        transferred.held_item = held_item
        context.announce(
            f"闪光果将{SLUGCAT_SPECS_BY_ID[creature.card_id].name}转移到"
            f"玩家{context.target_player_id}手牌"
        )
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
    if not _pay_cost(context, 45):
        return False
    damage = _attack_with_momentum(context, 1)
    context.combat.resolve_attack(context, damage, "泡水果（石子）")
    return True


def white_pearl(context):
    if not _pay_cost(context, 46):
        return False
    scavenger = remove_hand_creature(context.state, context.source_player_id, 25)
    if scavenger is not None:
        item = scavenger.held_item
        add_card_to_hand(context.state, item)
        context.source.statuses.last_dead_creature_health += 5
        slugcat_data(context.source).pearls_given += 1
        context.announce(f"玩家{context.source_player_id}给拾荒者珍珠，好感度提升")
        context.announce("白珍珠换来了拾荒者携带的物品")
        context.announce_private(
            f"获得物品：{SLUGCAT_SPECS_BY_ID[item].name}（仅自己可见）"
        )
    else:
        context.source.statuses.scavenger_attraction = True
        context.announce("白珍珠正在吸引拾荒者")
    return True


def colored_pearl(context):
    if not _pay_cost(context, 47):
        return False
    scavenger = remove_hand_creature(context.state, context.source_player_id, 25)
    if scavenger is not None:
        hired = add_threat(
            context.state,
            context.target_player_id,
            25,
            owner_id=scavenger.owner_id,
        )
        hired.held_item = scavenger.held_item
        slugcat_data(context.source).pearls_given += 1
        context.announce(f"玩家{context.source_player_id}给拾荒者珍珠，好感度提升")
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
