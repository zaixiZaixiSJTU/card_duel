"""Playable rules for the Slugcat character."""

import math
import random

import FreeSimpleGUI as sg

from card_duel.cards.slugcat_data import (
    DISCOVERY_ADJACENCY,
    DISCOVERY_CONTENTS,
    FORM_NAMES,
    SLUGCAT_ATTACK_ITEM_IDS,
    SLUGCAT_CARD_SPECS,
    SLUGCAT_CHARACTER_ID,
    SLUGCAT_CREATURE_IDS,
    SLUGCAT_DISCOVERY_IDS,
    SLUGCAT_SPECS_BY_ID,
)
from card_duel.core import combat
from card_duel.core.game import TurnPhase

MAX_KARMA = 5
SLUGCAT_HEALTH = 5


def initialize_slugcat_player(player):
    """Initialize JSON-safe public and runtime fields used by Slugcat."""
    player.health = SLUGCAT_HEALTH
    player.special.update(
        {
            "karma": 3,
            "karma_max": 3,
            "agility": 0,
            "momentum": 0,
            "satiety": 0,
            "last_card_id": 0,
            "jump_followup": 0,
            "form": "普通",
            "seen_discoveries": [],
            "discovery_pool": [27, 27, 27],
            "creature_threats": [],
            "creature_waits": {},
            "embedded_steel_rods": 0,
            "embedded_electric_spears": 0,
            "pending_discards": 0,
            "immune_next_attack": 0,
            "attack_lock": 0,
            "last_dead_creature_health": 0,
            "electric_penalty_this_turn": 0,
        }
    )


def get_slugcat_handler(card_id):
    """Return a registry-compatible handler bound to one card id."""

    def handler(
        game_state,
        source_player_id,
        target_player_id,
        announce,
        ignore_cost=False,
    ):
        return play_slugcat_card(
            card_id,
            game_state,
            source_player_id,
            target_player_id,
            announce,
            ignore_cost,
        )

    return handler


def register_slugcat_phase_handlers(turn):
    """Attach Slugcat statuses and creatures to stable timing points."""
    turn.register_phase_handler(TurnPhase.TURN_START, _on_turn_start, priority=30)
    turn.register_phase_handler(TurnPhase.TURN_END, _on_turn_end, priority=30)


def resolve_slugcat_karma(game_state, player_id, announce=None):
    """Spend one karma when Slugcat reaches zero health."""
    if game_state.character_ids.get(player_id) != SLUGCAT_CHARACTER_ID:
        return False

    player = game_state.players[player_id]
    if player.health > 0:
        return False

    player.special["karma"] = max(0, player.special.get("karma", 0) - 1)
    if player.special["karma"] > 0:
        player.health = SLUGCAT_HEALTH
        if announce:
            announce(
                f"玩家{player_id}消耗1点业力重返雨中"
                f"（业力{player.special['karma']}）"
            )
    else:
        player.health = 0
        if announce:
            announce(f"玩家{player_id}的业力归零")
    return True


def format_slugcat_status(player):
    special = player.special
    return (
        f"业力 {special.get('karma', 0)}/{special.get('karma_max', 0)}  ·  "
        f"敏捷 {special.get('agility', 0)}  ·  "
        f"动能 {special.get('momentum', 0)}  ·  "
        f"饱食 {special.get('satiety', 0)}"
    )


def play_slugcat_card(
    card_id,
    game_state,
    source_player_id,
    target_player_id,
    announce,
    ignore_cost=False,
):
    player = game_state.players[source_player_id]
    _ensure_slugcat_fields(player)

    if card_id in SLUGCAT_ATTACK_ITEM_IDS and player.special.get("attack_lock", 0):
        announce(f"玩家{source_player_id}仍处于致盲状态，不能打出攻击牌")
        return False

    handler = CARD_EFFECTS[card_id]
    was_played = handler(
        game_state,
        source_player_id,
        target_player_id,
        announce,
        ignore_cost,
    )
    if not was_played:
        return False

    _resolve_action_chain(player, card_id, announce, source_player_id)
    player.special["last_card_id"] = card_id
    if card_id not in SLUGCAT_ATTACK_ITEM_IDS and player.special.get("attack_lock", 0):
        player.special["attack_lock"] -= 1
    return True


def _ensure_slugcat_fields(player):
    if "karma" in player.special:
        return
    initialize_slugcat_player(player)


def _resolve_action_chain(player, card_id, announce, player_id):
    if card_id == 6:
        return
    if not player.special.get("jump_followup", 0):
        return
    if card_id in (2, 4, 5):
        player.special["agility"] += 1
        announce(f"玩家{player_id}借小跳衔接攻击，额外获得1点敏捷")
    player.special["jump_followup"] = 0


def _effective_cost(game_state, player_id, card_id):
    spec = SLUGCAT_SPECS_BY_ID[card_id]
    cost = spec.cost
    if cost is None:
        return None
    player = game_state.players[player_id]
    if card_id == 7 and player.special.get("last_card_id") in (8, 9):
        cost = max(0, cost - 1)
    if card_id in SLUGCAT_DISCOVERY_IDS and _hand_count(game_state, 26):
        cost = max(0, cost - 1)
    return cost


def _pay_cost(game_state, player_id, card_id, announce, ignore_cost=False):
    cost = _effective_cost(game_state, player_id, card_id)
    if cost is None:
        return False
    player = game_state.players[player_id]
    if ignore_cost:
        return True
    if player.energy < cost:
        announce(f"玩家{player_id}能量不足（需要{cost}）")
        return False
    player.energy -= cost
    return True


def _attack_with_momentum(game_state, source_id, target_id, base_damage):
    source = game_state.players[source_id]
    damage = base_damage + source.strength + source.special.get("momentum", 0)
    source.special["momentum"] = 0
    health_loss = combat.apply_damage(game_state, damage, target_id)
    return damage, health_loss


def _play_attack(card_id, base_damage, inserted_effect=None):
    def effect(game_state, source_id, target_id, announce, ignore_cost):
        if not _pay_cost(game_state, source_id, card_id, announce, ignore_cost):
            return False
        damage, health_loss = _attack_with_momentum(
            game_state, source_id, target_id, base_damage
        )
        announce(
            f"玩家{source_id}使用{SLUGCAT_SPECS_BY_ID[card_id].name}"
            f"（造成{damage}点伤害）"
        )
        if health_loss > 0 and inserted_effect:
            inserted_effect(game_state, source_id, target_id, announce)
        return True

    return effect


def _insert_steel_rod(game_state, _source_id, target_id, announce):
    target = game_state.players[target_id]
    target.special["embedded_steel_rods"] = (
        target.special.get("embedded_steel_rods", 0) + 1
    )
    announce(f"钢筋插入玩家{target_id}的手牌区")


def _insert_explosive_spear(game_state, _source_id, target_id, announce):
    combat.lose_life(game_state, 10, target_id)
    game_state.players[target_id].special["pending_discards"] = (
        game_state.players[target_id].special.get("pending_discards", 0) + 1
    )
    announce(f"炸矛穿透：玩家{target_id}失去10点生命并需随机弃1张牌")


def _insert_electric_spear(game_state, _source_id, target_id, announce):
    target = game_state.players[target_id]
    target.special["embedded_electric_spears"] = (
        target.special.get("embedded_electric_spears", 0) + 1
    )
    announce(f"电矛插入玩家{target_id}，其后续回合力量将降低")


def _play_explosive(game_state, source_id, target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 3, announce, ignore_cost):
        return False
    combat.apply_damage(game_state, 10, target_id)
    combat.apply_damage(game_state, 5, source_id)
    announce(f"玩家{source_id}引爆炸药（对目标10伤，自身5伤）")
    return True


def _play_hop(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 6, announce, ignore_cost):
        return False
    player = game_state.players[source_id]
    player.special["agility"] += 1
    player.special["jump_followup"] = 1
    announce(f"玩家{source_id}小跳，获得1点敏捷")
    return True


def _play_ridge_jump(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 7, announce, ignore_cost):
        return False
    game_state.players[source_id].special["agility"] += 3
    announce(f"玩家{source_id}脊背大跳，获得3点敏捷")
    return True


def _play_slide(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 8, announce, ignore_cost):
        return False
    game_state.players[source_id].special["momentum"] += 4
    announce(f"玩家{source_id}滑铲，获得4点动能")
    return True


def _play_roll(game_state, source_id, _target_id, announce, ignore_cost):
    player = game_state.players[source_id]
    if player.special.get("agility", 0) < 2:
        announce("翻滚需要至少2点敏捷")
        return False
    if not _pay_cost(game_state, source_id, 9, announce, ignore_cost):
        return False
    converted = player.special["agility"] + 2
    player.special["agility"] = 0
    player.special["momentum"] += converted
    announce(f"玩家{source_id}翻滚，将{converted}点敏捷势能转为动能")
    return True


def _play_crouch(game_state, source_id, target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 10, announce, ignore_cost):
        return False
    player = game_state.players[source_id]
    player.special["agility"] = 0
    player.special["momentum"] = 0
    creature_id = random.choice(SLUGCAT_CREATURE_IDS)
    _add_creature_threat(game_state, target_id, creature_id)
    announce(
        f"玩家{source_id}趴下，{SLUGCAT_SPECS_BY_ID[creature_id].name}"
        f"转向玩家{target_id}"
    )
    return True


def _play_backflip(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 11, announce, ignore_cost):
        return False
    player = game_state.players[source_id]
    player.special["momentum"] += 4
    player.special["agility"] += 2
    announce(f"玩家{source_id}后空翻，获得4动能和2敏捷")
    return True


def _play_sleep(game_state, source_id, _target_id, announce, ignore_cost):
    player = game_state.players[source_id]
    if player.special.get("satiety", 0) < 3:
        announce("饱食度不足，无法睡觉")
        return False
    if not _pay_cost(game_state, source_id, 12, announce, ignore_cost):
        return False
    player.special["satiety"] -= 3
    player.special["karma"] = min(
        player.special.get("karma_max", 3), player.special.get("karma", 0) + 1
    )
    announce(f"玩家{source_id}安稳睡下，业力+1")
    return True


def _play_forage(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 13, announce, ignore_cost):
        return False
    player = game_state.players[source_id]
    gained = math.ceil(player.special.get("last_dead_creature_health", 0) / 5)
    player.special["satiety"] += gained
    announce(f"玩家{source_id}觅食，获得{gained}点饱食度")
    return True


def _play_run_away(game_state, source_id, _target_id, announce, ignore_cost):
    player = game_state.players[source_id]
    amount = _choose_x_cost(player, ignore_cost)
    if amount is None:
        return False
    player.energy -= amount if not ignore_cost else 0
    _remove_all_creatures_from_hand(game_state)
    discovery_pool = player.special.setdefault("discovery_pool", [27, 27, 27])
    obtained = 0
    for _ in range(amount):
        if not discovery_pool:
            break
        card_id = discovery_pool.pop(0)
        if combat.add_card_to_hand(game_state, card_id):
            obtained += 1
    for _ in range(amount - obtained):
        combat.add_card_to_hand(game_state, random.choice(SLUGCAT_CREATURE_IDS))
    announce(f"玩家{source_id}跑路，获得{obtained}张见闻牌")
    return True


def _choose_x_cost(player, ignore_cost):
    if "next_x_cost" in player.special:
        return max(0, min(player.energy, int(player.special.pop("next_x_cost"))))
    if ignore_cost:
        return 0
    maximum = max(0, player.energy)
    value = sg.popup_get_text(
        f"投入能量（0-{maximum}）",
        default_text=str(maximum),
        title="猫跑路了",
        keep_on_top=True,
    )
    if value is None:
        return None
    try:
        return max(0, min(maximum, int(value)))
    except ValueError:
        return None


def _play_trouble(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 15, announce, ignore_cost):
        return False
    creature_id = random.choice(SLUGCAT_CREATURE_IDS)
    combat.add_card_to_hand(game_state, creature_id)
    announce(f"玩家{source_id}闯祸，引来了{SLUGCAT_SPECS_BY_ID[creature_id].name}")
    return True


def _play_creature(card_id):
    def effect(game_state, source_id, target_id, announce, ignore_cost):
        spec = SLUGCAT_SPECS_BY_ID[card_id]
        if spec.cost is None:
            announce(f"{spec.name}不可主动打出")
            return False
        if not _pay_cost(game_state, source_id, card_id, announce, ignore_cost):
            return False
        if card_id in (16, 18, 24):
            _add_creature_threat(game_state, target_id, card_id)
        if card_id == 18:
            _add_creature_threat(game_state, target_id, 19)
        if card_id == 19:
            combat.apply_damage(game_state, 10, target_id)
        announce(f"玩家{source_id}处理了{spec.name}")
        return True

    return effect


def _play_discovery(card_id):
    def effect(game_state, source_id, _target_id, announce, ignore_cost):
        if not _pay_cost(game_state, source_id, card_id, announce, ignore_cost):
            return False
        player = game_state.players[source_id]
        seen = player.special.setdefault("seen_discoveries", [])
        if card_id not in seen:
            seen.append(card_id)
            player.special["karma_max"] = min(
                MAX_KARMA, player.special.get("karma_max", 3) + 1
            )
        for new_card_id, count in DISCOVERY_CONTENTS[card_id].items():
            game_state.draw_pile.extend([new_card_id] * count)
        random.shuffle(game_state.draw_pile)
        _unlock_adjacent_discovery(player, card_id)
        announce(
            f"玩家{source_id}探索{SLUGCAT_SPECS_BY_ID[card_id].name}，"
            "牌组获得新的物品与生物"
        )
        return True

    return effect


def _unlock_adjacent_discovery(player, card_id):
    pool = player.special.setdefault("discovery_pool", [])
    seen = set(player.special.setdefault("seen_discoveries", []))
    adjacent = DISCOVERY_ADJACENCY[card_id]
    unseen = [candidate for candidate in adjacent if candidate not in seen]
    candidates = unseen or list(adjacent)
    selected = min(candidates, key=lambda candidate: pool.count(candidate))
    pool.append(selected)


def _play_form(card_id):
    def effect(game_state, source_id, _target_id, announce, ignore_cost):
        if not _pay_cost(game_state, source_id, card_id, announce, ignore_cost):
            return False
        form_name = FORM_NAMES[card_id]
        game_state.players[source_id].special["form"] = form_name
        announce(f"玩家{source_id}切换为{form_name}形态")
        return True

    return effect


def _play_smoke_fruit(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 41, announce, ignore_cost):
        return False
    game_state.players[source_id].special["immune_next_attack"] += 1
    _remove_first_hand_card(game_state, 22)
    announce(f"玩家{source_id}释放烟雾，将免疫下一次攻击")
    return True


def _play_batfly_grass(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 42, announce, ignore_cost):
        return False
    announce(f"玩家{source_id}打出了蝠蝇草")
    return True


def _play_flash_fruit(game_state, source_id, target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 43, announce, ignore_cost):
        return False
    creature_id = _pop_first_creature_from_hand(game_state)
    if creature_id is not None:
        _add_creature_threat(game_state, target_id, creature_id)
        announce(f"闪光果将{SLUGCAT_SPECS_BY_ID[creature_id].name}赶向对手")
    else:
        game_state.players[target_id].special["attack_lock"] = 2
        announce(f"玩家{target_id}被致盲，需先打出两张非攻击牌")
    return True


def _play_blue_fruit(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 44, announce, ignore_cost):
        return False
    game_state.players[source_id].special["satiety"] += 1
    announce(f"玩家{source_id}吃下蓝果，饱食度+1")
    return True


def _play_bubble_fruit(game_state, source_id, target_id, announce, ignore_cost):
    player = game_state.players[source_id]
    mode = player.special.pop("next_bubble_mode", None)
    if mode is None:
        answer = sg.popup_yes_no(
            "将泡水果视为蓝果？\n选择“否”则视为石子。",
            title="泡水果",
            keep_on_top=True,
        )
        mode = "fruit" if answer == "Yes" else "stone"
    if mode == "fruit":
        return _play_blue_fruit(game_state, source_id, target_id, announce, True)
    damage, _ = _attack_with_momentum(game_state, source_id, target_id, 1)
    announce(f"玩家{source_id}把泡水果当作石子（造成{damage}点伤害）")
    return True


def _play_white_pearl(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 46, announce, ignore_cost):
        return False
    if _remove_first_hand_card(game_state, 25):
        carried_item = random.choices((1, 3, 4, 5), weights=(6, 1, 2, 1), k=1)[0]
        combat.add_card_to_hand(game_state, carried_item)
        game_state.players[source_id].special["last_dead_creature_health"] = 5
        announce("白珍珠换来了拾荒者携带的物品")
    else:
        game_state.players[source_id].special["scavenger_attraction"] = 1
        announce("白珍珠正在吸引拾荒者")
    return True


def _play_colored_pearl(game_state, source_id, target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 47, announce, ignore_cost):
        return False
    if _remove_first_hand_card(game_state, 25):
        _add_creature_threat(game_state, target_id, 25)
        announce(f"玩家{source_id}雇佣拾荒者对付玩家{target_id}")
    else:
        game_state.players[source_id].special["scavenger_attraction"] = 1
        announce("有色珍珠正在吸引拾荒者")
    return True


def _play_mass_battery(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 48, announce, ignore_cost):
        return False
    game_state.players[source_id].special["agility"] += 99
    announce(f"玩家{source_id}启动质量稀释电池，敏捷+99")
    return True


def _on_turn_start(context):
    game_state = context.game_state
    player_id = context.player_id
    player = game_state.players[player_id]
    if game_state.character_ids.get(player_id) == SLUGCAT_CHARACTER_ID:
        _ensure_slugcat_fields(player)
        player.special["agility"] = 0
        grass_count = _hand_count(game_state, 42)
        if grass_count:
            player.special["satiety"] += grass_count * 2
            context.announce(f"蝠蝇草提供{grass_count * 2}点饱食度")

    _resolve_pending_discards(game_state, player)
    _resolve_inserted_items(game_state, player_id, context.announce)


def _on_turn_end(context):
    game_state = context.game_state
    player_id = context.player_id
    player = game_state.players[player_id]
    _resolve_creatures(game_state, player_id, context.announce)
    penalty = player.special.get("electric_penalty_this_turn", 0)
    if penalty:
        player.strength += penalty
        player.special["electric_penalty_this_turn"] = 0


def _resolve_pending_discards(game_state, player):
    pending = player.special.get("pending_discards", 0)
    while pending > 0 and game_state.hand_size > 0:
        indexes = _occupied_hand_indexes(game_state)
        if not indexes:
            break
        hand_index = random.choice(indexes)
        game_state.draw_pile.append(game_state.hand_cards[hand_index])
        game_state.hand_cards[hand_index] = -1
        pending -= 1
    player.special["pending_discards"] = pending


def _resolve_inserted_items(game_state, player_id, announce):
    player = game_state.players[player_id]
    rods = player.special.get("embedded_steel_rods", 0)
    if rods:
        combat.lose_life(game_state, rods, player_id)
        announce(f"{rods}根钢筋使玩家{player_id}失去{rods}点生命")
        if player.energy >= 1:
            player.energy -= 1
            player.special["embedded_steel_rods"] -= 1
            announce(f"玩家{player_id}支付1点能量拔出1根钢筋")

    spears = player.special.get("embedded_electric_spears", 0)
    if spears:
        penalty = spears * 2
        player.strength -= penalty
        player.special["electric_penalty_this_turn"] = penalty
        announce(f"电矛使玩家{player_id}本回合力量-{penalty}")
        if player.energy >= 1:
            player.energy -= 1
            player.special["embedded_electric_spears"] -= 1
            announce(f"玩家{player_id}支付1点能量拔出1根电矛")


def _resolve_creatures(game_state, player_id, announce):
    if game_state.local_player_id != player_id:
        return
    player = game_state.players[player_id]
    hand_creatures = [
        game_state.hand_cards[index]
        for index in _occupied_hand_indexes(game_state)
        if game_state.hand_cards[index] in SLUGCAT_CREATURE_IDS
    ]
    threats = list(player.special.get("creature_threats", []))
    creatures = hand_creatures + threats
    if not creatures:
        return

    centipede_count = creatures.count(22)
    for creature_id in creatures:
        damage = _creature_damage(player, creature_id, centipede_count)
        if damage:
            combat.apply_damage(game_state, damage, player_id)
            announce(
                f"{SLUGCAT_SPECS_BY_ID[creature_id].name}"
                f"对玩家{player_id}造成{damage}点伤害"
            )
        if creature_id == 18:
            player.special.setdefault("creature_threats", []).append(19)
        if creature_id == 16:
            _remove_first_hand_card(game_state, 16)
            combat.add_card_to_hand(game_state, 17)
            player.special["last_dead_creature_health"] = 1


def _creature_damage(player, creature_id, centipede_count):
    if creature_id == 17:
        return 5
    if creature_id == 19:
        return 10
    if creature_id == 20:
        waits = player.special.setdefault("creature_waits", {})
        key = str(creature_id)
        if waits.get(key, 0) == 0:
            waits[key] = 1
            return 0
        return 5
    if creature_id == 21:
        return 3
    if creature_id == 22:
        return 15 if centipede_count >= 3 else 0
    if creature_id == 23:
        return 10
    if creature_id == 24:
        return 15
    if creature_id == 25:
        return random.choices((2, 10, 3, 3), weights=(6, 1, 2, 1), k=1)[0]
    return 0


def _add_creature_threat(game_state, player_id, creature_id):
    game_state.players[player_id].special.setdefault("creature_threats", []).append(
        creature_id
    )


def _occupied_hand_indexes(game_state):
    indexes = []
    for index, card_id in enumerate(game_state.hand_cards):
        if card_id == 0:
            break
        if card_id != -1:
            indexes.append(index)
    return indexes


def _hand_count(game_state, card_id):
    return sum(
        game_state.hand_cards[index] == card_id
        for index in _occupied_hand_indexes(game_state)
    )


def _remove_first_hand_card(game_state, card_id):
    for index in _occupied_hand_indexes(game_state):
        if game_state.hand_cards[index] == card_id:
            game_state.hand_cards[index] = -1
            return True
    return False


def _pop_first_creature_from_hand(game_state):
    for index in _occupied_hand_indexes(game_state):
        card_id = game_state.hand_cards[index]
        if card_id in SLUGCAT_CREATURE_IDS:
            game_state.hand_cards[index] = -1
            return card_id
    return None


def _remove_all_creatures_from_hand(game_state):
    for index in _occupied_hand_indexes(game_state):
        if game_state.hand_cards[index] in SLUGCAT_CREATURE_IDS:
            game_state.hand_cards[index] = -1


CARD_EFFECTS = {
    1: _play_attack(1, 2, _insert_steel_rod),
    2: _play_attack(2, 1),
    3: _play_explosive,
    4: _play_attack(4, 3, _insert_explosive_spear),
    5: _play_attack(5, 3, _insert_electric_spear),
    6: _play_hop,
    7: _play_ridge_jump,
    8: _play_slide,
    9: _play_roll,
    10: _play_crouch,
    11: _play_backflip,
    12: _play_sleep,
    13: _play_forage,
    14: _play_run_away,
    15: _play_trouble,
    **{card_id: _play_creature(card_id) for card_id in SLUGCAT_CREATURE_IDS},
    **{card_id: _play_discovery(card_id) for card_id in SLUGCAT_DISCOVERY_IDS},
    **{card_id: _play_form(card_id) for card_id in FORM_NAMES},
    41: _play_smoke_fruit,
    42: _play_batfly_grass,
    43: _play_flash_fruit,
    44: _play_blue_fruit,
    45: _play_bubble_fruit,
    46: _play_white_pearl,
    47: _play_colored_pearl,
    48: _play_mass_battery,
}

assert len(CARD_EFFECTS) == len(SLUGCAT_CARD_SPECS)
