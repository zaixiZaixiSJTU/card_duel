"""Playable rules for the Slugcat character."""

import math
import random

import FreeSimpleGUI as sg

from card_duel.cards.slugcat_data import (
    CREATURE_BASE_HEALTH,
    DISCOVERY_ADJACENCY,
    DISCOVERY_CONTENTS,
    FORM_NAMES,
    LIZARD_IDS,
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
            "discovery_pool": [27],
            # creature_threats stores dicts: {"card_id", "health", "owner"}
            "creature_threats": [],
            # creature_health tracks HP for hand creatures: card_id -> [hp, ...]
            "creature_health": {},
            # hand_creature_owners: card_id -> [owner_id, ...]
            "hand_creature_owners": {},
            # creature_waits: card_id -> wait_turns (for green lizard)
            "creature_waits": {},
            "embedded_steel_rods": 0,
            "embedded_electric_spears": 0,
            "pending_discards": 0,
            "immune_next_attack": 0,
            "attack_lock": 0,
            "last_dead_creature_health": 0,
            "electric_penalty_this_turn": 0,
            "pending_insertions": [],
            # noodle_cost_stacks: per-instance cost increase for 小面条 in hand,
            # parallel to creature_health[16]. Each transfer adds +1.
            "noodle_cost_stacks": [],
            # 已解锁生物数量：开局含基础生物（source_count>0），见闻解锁时累加。
            # 不在抽牌堆中（不可抽取），仅供查看器展示。
            "unlocked_creature_counts": {
                spec.card_id: spec.source_count
                for spec in SLUGCAT_CARD_SPECS
                if 16 <= spec.card_id <= 26 and spec.source_count > 0
            },
            # 趴下标记：本回合随机生物优先加入对方手牌
            "redirect_creatures_to_opponent": False,
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
    # 敏捷/动能已在主面板显示，这里只展示业力和饱食
    return (
        f"业力 {special.get('karma', 0)}/{special.get('karma_max', 0)}  ·  "
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
    # 小跳后接矛(1钢筋/4炸矛/5电矛)或石子(2)获得额外1敏捷
    if card_id in (1, 2, 4, 5):
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
    if card_id == 16:
        stacks = player.special.get("noodle_cost_stacks", [])
        if stacks:
            cost += stacks[0]
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


def _attack_with_momentum(game_state, source_id, target_id, base_damage, announce=None):
    source = game_state.players[source_id]
    damage = base_damage + source.strength + source.special.get("momentum", 0)
    source.special["momentum"] = 0
    health_loss = combat.apply_damage(
        game_state, damage, target_id, announce=announce
    )
    return damage, health_loss


def _play_attack(card_id, base_damage, inserted_effect=None):
    def effect(game_state, source_id, target_id, announce, ignore_cost):
        source = game_state.players[source_id]
        from card_duel.cards.slugcat_data import SLUGCAT_INSERTED_IDS

        # 强制将攻击目标设为对手（避免UI误传目标为自己导致无弹窗）
        opponent_id = 2 if source_id == 1 else 1
        target_id = opponent_id

        # 插入物卡（49/50）：打出时耗能1执行"拔出"，返回普通版本（1/5）到牌堆
        if card_id in SLUGCAT_INSERTED_IDS:
            if not _pay_cost(game_state, source_id, card_id, announce, ignore_cost):
                return False
            normal_id = 1 if card_id == 49 else 5
            embedded_key = (
                "embedded_steel_rods" if card_id == 49 else "embedded_electric_spears"
            )
            source.special[embedded_key] = max(
                0, source.special.get(embedded_key, 0) - 1
            )
            game_state.draw_pile.append(normal_id)
            announce(
                f"玩家{source_id}拔出1根{'钢筋' if card_id == 49 else '电矛'}"
                f"（返回牌堆，体内剩{source.special[embedded_key]}根）"
            )
            return True

        if not _pay_cost(game_state, source_id, card_id, announce, ignore_cost):
            return False
        damage = base_damage + source.strength + source.special.get("momentum", 0)
        source.special["momentum"] = 0
        spec_name = SLUGCAT_SPECS_BY_ID[card_id].name

        # Let attacker choose target if any creature exists
        target_obj = choose_attack_target(game_state, source_id, target_id, announce)
        if target_obj is None or target_obj["type"] == "player":
            health_loss = combat.apply_damage(
                game_state, damage, target_id, announce=announce
            )
            announce(
                f"玩家{source_id}使用{spec_name}"
                f"（造成{damage}点伤害）"
            )
            if health_loss > 0 and inserted_effect:
                inserted_effect(game_state, source_id, target_id, announce)
        else:
            target_name = target_obj["name"]
            creature_owner = target_obj.get("player_id", target_id)
            if target_obj["type"] == "hand":
                _damage_hand_creature(
                    game_state, creature_owner, target_obj["card_id"],
                    damage, announce, attacker_id=source_id,
                )
            else:
                threats = game_state.players[creature_owner].special.get("creature_threats", [])
                idx = next(
                    (i for i, t in enumerate(threats)
                     if int(t["card_id"]) == target_obj["card_id"]),
                    -1,
                )
                if idx >= 0:
                    _damage_threat_creature(
                        game_state, creature_owner, idx, damage, announce,
                        attacker_id=source_id,
                    )
            announce(f"玩家{source_id}使用{spec_name}攻击{target_name}")
        return True

    return effect


def _insert_steel_rod(game_state, source_id, target_id, announce):
    target = game_state.players[target_id]
    target.special["embedded_steel_rods"] = (
        target.special.get("embedded_steel_rods", 0) + 1
    )
    # Insert as a real card into target's hand (use 49 = 钢筋【插入】)
    if target_id == game_state.local_player_id:
        combat.add_card_to_hand(game_state, 49)
        _refresh_local_hand(game_state)
    else:
        target.special.setdefault("pending_insertions", []).append(49)
    announce(f"钢筋插入玩家{target_id}的手牌")


def _insert_explosive_spear(game_state, _source_id, target_id, announce):
    combat.lose_life(game_state, 10, target_id, announce=announce)
    game_state.players[target_id].special["pending_discards"] = (
        game_state.players[target_id].special.get("pending_discards", 0) + 1
    )
    announce(f"炸矛穿透：玩家{target_id}失去10点生命并需随机弃1张牌")


def _insert_electric_spear(game_state, source_id, target_id, announce):
    target = game_state.players[target_id]
    target.special["embedded_electric_spears"] = (
        target.special.get("embedded_electric_spears", 0) + 1
    )
    # Insert as a real card into target's hand (use 50 = 电矛【插入】)
    if target_id == game_state.local_player_id:
        combat.add_card_to_hand(game_state, 50)
        _refresh_local_hand(game_state)
    else:
        target.special.setdefault("pending_insertions", []).append(50)
    announce(f"电矛插入玩家{target_id}的手牌")


def _play_explosive(game_state, source_id, target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 3, announce, ignore_cost):
        return False
    combat.apply_damage(game_state, 10, target_id, announce=announce)
    combat.apply_damage(game_state, 5, source_id, announce=announce)
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
    # 趴下不生成生物，而是设置标记：本回合随机生物优先加入对方手牌
    player.special["redirect_creatures_to_opponent"] = True
    announce(
        f"玩家{source_id}趴下，取消全部敏捷和动能，"
        f"本回合随机加入的生物将优先加入玩家{target_id}手牌"
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
    combat.draw_cards(game_state, 1)
    announce(f"玩家{source_id}觅食，获得{gained}点饱食度并抽1张牌")
    return True


def _play_run_away(game_state, source_id, target_id, announce, ignore_cost):
    player = game_state.players[source_id]
    amount = _choose_x_cost(player, ignore_cost)
    if amount is None:
        return False
    player.energy -= amount if not ignore_cost else 0
    _remove_all_creatures_from_hand(game_state)
    discovery_pool = player.special.setdefault("discovery_pool", [27])
    seen = set(player.special.get("seen_discoveries", []))
    obtained = 0
    for _ in range(amount):
        if not discovery_pool:
            break
        # 优先抽未打出过的见闻牌，其次才抽已打出过的
        unseen_idx = next(
            (i for i, c in enumerate(discovery_pool) if c not in seen), None
        )
        idx = unseen_idx if unseen_idx is not None else 0
        card_id = discovery_pool.pop(idx)
        if combat.add_card_to_hand(game_state, card_id):
            obtained += 1
    # Wasted energy (discovery pool exhausted) is simply lost — no creatures.
    wasted = amount - obtained
    combat.draw_cards(game_state, 1)
    if wasted:
        announce(
            f"玩家{source_id}跑路，获得{obtained}张见闻牌"
            f"（{wasted}点能量因见闻池耗尽而浪费，额外抽1张牌）"
        )
    else:
        announce(
            f"玩家{source_id}跑路，获得{obtained}张见闻牌，额外抽1张牌"
        )
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


def _play_trouble(game_state, source_id, target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 15, announce, ignore_cost):
        return False
    creature_id = random.choice(SLUGCAT_CREATURE_IDS)
    # 趴下标记：随机生物优先加入对方手牌
    player = game_state.players[source_id]
    dest_id = target_id if player.special.get("redirect_creatures_to_opponent") else source_id
    _add_creature_to_hand(game_state, dest_id, creature_id, owner_id=source_id)
    combat.draw_cards(game_state, 1)
    announce(f"玩家{source_id}闯祸，{SLUGCAT_SPECS_BY_ID[creature_id].name}加入了玩家{dest_id}手牌，抽1张牌")
    return True


def _play_creature(card_id):
    def effect(game_state, source_id, target_id, announce, ignore_cost):
        spec = SLUGCAT_SPECS_BY_ID[card_id]
        if spec.cost is None:
            announce(f"{spec.name}不可主动打出")
            return False
        if not _pay_cost(game_state, source_id, card_id, announce, ignore_cost):
            return False
        # Transfer creatures move from self hand to opponent hand
        if card_id in (16, 18, 24):
            # Capture noodle cost stack before removal so we can escalate it.
            noodle_cost = 0
            if card_id == 16:
                source_player = game_state.players[source_id]
                stacks = source_player.special.get("noodle_cost_stacks", [])
                if stacks:
                    noodle_cost = stacks[0]
            _remove_hand_creature(game_state, card_id)
            _add_creature_to_hand(
                game_state, target_id, card_id, owner_id=source_id,
                noodle_cost=noodle_cost + 1 if card_id == 16 else 0,
            )
            announce(
                f"玩家{source_id}将{spec.name}转移到玩家{target_id}手牌"
            )
        else:
            announce(f"玩家{source_id}打出了{spec.name}")
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
        # 生物牌（16-26）不进入抽牌堆（不可被抽取），但记入 unlocked_creature_counts
        # 供抽牌堆查看器展示为"已解锁"状态。
        unlocked_creatures = player.special.setdefault(
            "unlocked_creature_counts", {}
        )
        for new_card_id, count in DISCOVERY_CONTENTS[card_id].items():
            if 16 <= new_card_id <= 26:
                unlocked_creatures[new_card_id] = (
                    unlocked_creatures.get(new_card_id, 0) + count
                )
            else:
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
    announce(f"玩家{source_id}释放烟雾，将免疫下一次攻击")
    # 搜索所有可见位置的烈焰蜈蚣(22)并让玩家选择秒杀
    target = choose_creature_target(game_state, card_id_filter=22)
    if target is not None:
        _kill_creature_at(game_state, target, announce)
        announce("烟雾秒杀了烈焰蜈蚣")
    return True


def _play_batfly_grass(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 42, announce, ignore_cost):
        return False
    announce(f"玩家{source_id}打出了蝠蝇草")
    return True


def _play_flash_fruit(game_state, source_id, target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 43, announce, ignore_cost):
        return False
    # 让玩家选择要转移的手牌生物，无生物时致盲对手
    creature_id = _choose_own_hand_creature(game_state)
    if creature_id is not None:
        _remove_hand_creature(game_state, creature_id)
        _add_creature_threat(
            game_state, target_id, creature_id, owner_id=source_id
        )
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
    # 当石子使用时，走和普通攻击牌一样的目标选择逻辑
    source = game_state.players[source_id]
    damage = 1 + source.strength + source.special.get("momentum", 0)
    source.special["momentum"] = 0
    spec_name = "泡水果(石子)"

    target_obj = choose_attack_target(game_state, source_id, target_id, announce)
    if target_obj is None or target_obj["type"] == "player":
        health_loss = combat.apply_damage(
            game_state, damage, target_id, announce=announce
        )
        announce(f"玩家{source_id}把泡水果当作石子（造成{damage}点伤害）")
    else:
        target_name = target_obj["name"]
        creature_owner = target_obj.get("player_id", target_id)
        if target_obj["type"] == "hand":
            _damage_hand_creature(
                game_state, creature_owner, target_obj["card_id"],
                damage, announce, attacker_id=source_id,
            )
        else:
            threats = game_state.players[creature_owner].special.get("creature_threats", [])
            idx = next(
                (i for i, t in enumerate(threats)
                 if int(t["card_id"]) == target_obj["card_id"]),
                -1,
            )
            if idx >= 0:
                _damage_threat_creature(
                    game_state, creature_owner, idx, damage, announce,
                    attacker_id=source_id,
                )
        announce(f"玩家{source_id}把泡水果当作石子攻击{target_name}")
    return True


def _play_white_pearl(game_state, source_id, _target_id, announce, ignore_cost):
    if not _pay_cost(game_state, source_id, 46, announce, ignore_cost):
        return False
    if _remove_hand_creature(game_state, 25) is not None:
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
    if _remove_hand_creature(game_state, 25) is not None:
        _add_creature_threat(game_state, target_id, 25, owner_id=source_id)
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
        # 回合开始兜底清零：若上回合因为任何原因没清零（例如跳转流程），这里强制清零
        player.special["agility"] = 0
        player.special["momentum"] = 0
        player.special["redirect_creatures_to_opponent"] = False
        grass_count = _hand_count(game_state, 42)
        if grass_count:
            player.special["satiety"] += grass_count * 2
            context.announce(f"蝠蝇草提供{grass_count * 2}点饱食度")
        # Reset noodle fly immunity (negative HP = used immunity)
        fly_health = player.special.get("creature_health", {}).get(17, [])
        player.special["creature_health"][17] = [abs(h) for h in fly_health]
        # Also reset in threats
        for t in player.special.get("creature_threats", []):
            if t["card_id"] == 17:
                t["health"] = abs(t["health"])

    _resolve_pending_discards(game_state, player)


def _on_turn_end(context):
    game_state = context.game_state
    player_id = context.player_id
    player = game_state.players[player_id]
    # 回合结束结算插入物流血效果（钢筋扣血、电矛扣力量）
    _resolve_inserted_items(game_state, player_id, context.announce)
    _resolve_creatures(game_state, player_id, context.announce)
    penalty = player.special.get("electric_penalty_this_turn", 0)
    if penalty:
        player.strength += penalty
        player.special["electric_penalty_this_turn"] = 0
    # 回合结束清零动能（攻击资源已用完），但保留敏捷——敏捷是防御资源，
    # 需要留存到对手回合才能减伤，在下一回合开始时清零。
    if game_state.character_ids.get(player_id) == SLUGCAT_CHARACTER_ID:
        player.special["momentum"] = 0


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
    """回合结束时结算插入物的流血效果（钢筋扣血、电矛扣力量）。

    拔出不再自动执行——被插入的钢筋/电矛在手牌中像普通卡一样占据位置，
    玩家可以在出牌阶段主动打出它们来"拔出"（花1能量，返回牌堆，体内减1）。
    """
    player = game_state.players[player_id]

    rods = player.special.get("embedded_steel_rods", 0)
    if rods:
        combat.lose_life(game_state, rods, player_id, announce=announce)
        announce(f"{rods}根钢筋使玩家{player_id}失去{rods}点生命")

    spears = player.special.get("embedded_electric_spears", 0)
    if spears:
        penalty = spears * 2
        player.strength -= penalty
        player.special["electric_penalty_this_turn"] = penalty
        announce(f"电矛使玩家{player_id}本回合力量-{penalty}")


def _resolve_creatures(game_state, player_id, announce):
    """Resolve all creature effects at turn end."""
    if game_state.local_player_id != player_id:
        return
    player = game_state.players[player_id]

    # Collect hand creatures (card_id list) and threat dicts
    hand_creatures = [
        game_state.hand_cards[index]
        for index in _occupied_hand_indexes(game_state)
        if game_state.hand_cards[index] in SLUGCAT_CREATURE_IDS
    ]
    threats = list(player.special.get("creature_threats", []))
    all_creature_ids = hand_creatures + [t["card_id"] for t in threats]
    if not all_creature_ids:
        return

    # --- Noodle/lizard mutual exclusion ---
    # Lizards eat noodles: remove all noodles if any lizard present
    has_lizard = any(cid in LIZARD_IDS for cid in all_creature_ids)
    if has_lizard:
        while _hand_count(game_state, 16) > 0:
            owner = _remove_hand_creature(game_state, 16)
            announce("蜥蜴吃掉了小面条")
            # Noodle eaten → spawn noodle fly
            _add_creature_to_hand(game_state, player_id, 17, owner_id=player_id)
        # Remove noodle threats
        threats = [t for t in threats if t["card_id"] != 16]

    # Recompile after noodle removal
    hand_creatures = [
        game_state.hand_cards[index]
        for index in _occupied_hand_indexes(game_state)
        if game_state.hand_cards[index] in SLUGCAT_CREATURE_IDS
    ]
    all_creature_ids = hand_creatures + [t["card_id"] for t in threats]

    # --- Noodle death: any 小面条 still in hand at turn end dies ---
    # (it was not transferred this turn) and spawns a 面条蝇.
    while _hand_count(game_state, 16) > 0:
        _remove_hand_creature(game_state, 16)
        _add_creature_to_hand(game_state, player_id, 17, owner_id=player_id)
        announce("小面条未转移，死亡并变为面条蝇")

    # Recompile after noodle death
    hand_creatures = [
        game_state.hand_cards[index]
        for index in _occupied_hand_indexes(game_state)
        if game_state.hand_cards[index] in SLUGCAT_CREATURE_IDS
    ]
    all_creature_ids = hand_creatures + [t["card_id"] for t in threats]

    centipede_count = all_creature_ids.count(22)

    # --- 烈焰蜥蜴: optionally pay 1 energy to avoid its 10 damage ---
    # Each lizard in hand can be "played" for 1 energy: it returns to the
    # draw pile (will be drawn again later) and deals no damage this turn.
    lizard_count = _hand_count(game_state, 23)
    for _ in range(lizard_count):
        if player.energy < 1:
            break
        choice = sg.popup_yes_no(
            "支付1能量避免烈焰蜥蜴的10点伤害？\n（烈焰蜥蜴返回牌堆，之后还会抽到）",
            title="烈焰蜥蜴",
            keep_on_top=True,
        )
        if choice != "Yes":
            break
        player.energy -= 1
        _remove_hand_creature(game_state, 23)
        game_state.draw_pile.append(23)
        announce(f"玩家{player_id}支付1能量，烈焰蜥蜴返回牌堆")

    # Recompile after lizard avoidance
    hand_creatures = [
        game_state.hand_cards[index]
        for index in _occupied_hand_indexes(game_state)
        if game_state.hand_cards[index] in SLUGCAT_CREATURE_IDS
    ]
    all_creature_ids = hand_creatures + [t["card_id"] for t in threats]

    # --- Damage phase ---
    for creature_id in hand_creatures:
        damage = _creature_damage(player, creature_id, centipede_count)
        if damage:
            combat.apply_damage(
                game_state, damage, player_id, announce=announce
            )
            announce(
                f"{SLUGCAT_SPECS_BY_ID[creature_id].name}"
                f"对玩家{player_id}造成{damage}点伤害"
            )
        _on_creature_turn_end_hand(game_state, player_id, creature_id, announce)

    for i in range(len(threats) - 1, -1, -1):
        threat = threats[i]
        creature_id = threat["card_id"]
        damage = _creature_damage(player, creature_id, centipede_count)
        if damage:
            combat.apply_damage(
                game_state, damage, player_id, announce=announce
            )
            announce(
                f"{SLUGCAT_SPECS_BY_ID[creature_id].name}"
                f"对玩家{player_id}造成{damage}点伤害"
            )
        _on_creature_turn_end_threat(game_state, player_id, threat, announce)

    # --- Centipede proliferation ---
    _resolve_centipede_spread(game_state, player_id, announce)


def _on_creature_turn_end_hand(game_state, player_id, creature_id, announce):
    """Per-turn effects for hand creatures (non-damage)."""
    if creature_id == 18:
        # 射线虫: summon vulture at turn end
        _add_creature_threat(game_state, player_id, 19, owner_id=player_id)
        announce(f"射线虫引来秃鹫")


def _on_creature_turn_end_threat(game_state, player_id, threat, announce):
    """Per-turn effects for threat creatures (non-damage)."""
    pass


def _resolve_centipede_spread(game_state, player_id, announce):
    """烈焰蜈蚣增殖：每整轮（round）只在 server 侧判定一次。

    为避免 client/server 双方各自判定导致重复增殖或双方各加一张，只有
    当本机器的 ``local_player_id == 1``（server 端）时才真正执行增殖。
    若需要加给 client（玩家 2），通过 ``pending_insertions`` 同步。
    手蜈蚣数从**双方公开的** ``player.special.creature_health`` 读取，
    这样 server 能看到双方完整的手牌蜈蚣数，而不依赖本地 ``hand_cards``。
    """
    if game_state.local_player_id != 1:
        return
    # 同一 round 内即使 server 自己先后结束两个回合（理论上不会）也只增殖一次
    marker = (game_state.round_number, "centipede_proliferation_done")
    if game_state.players[1].special.get("last_centipede_round") == marker:
        return
    game_state.players[1].special["last_centipede_round"] = marker

    p1 = game_state.players[1]
    p2 = game_state.players[2]
    p1_hand = len(p1.special.get("creature_health", {}).get(22, []))
    p2_hand = len(p2.special.get("creature_health", {}).get(22, []))
    p1_threat = sum(
        1 for t in p1.special.get("creature_threats", []) if t["card_id"] == 22
    )
    p2_threat = sum(
        1 for t in p2.special.get("creature_threats", []) if t["card_id"] == 22
    )
    p1_count = p1_hand + p1_threat
    p2_count = p2_hand + p2_threat

    if p1_count == 0 and p2_count == 0:
        target = player_id if player_id in (1, 2) else 1
        _add_creature_to_hand(game_state, target, 22, owner_id=target)
        announce("烈焰蜈蚣出现在你手牌中")
        return
    if p1_count == p2_count:
        return  # 相等不增殖
    target = 1 if p1_count > p2_count else 2
    _add_creature_to_hand(game_state, target, 22, owner_id=target)
    announce(
        f"玩家{target}场上烈焰蜈蚣较多（{max(p1_count, p2_count)} vs {min(p1_count, p2_count)}），增殖了一张"
    )


def check_centipede_immunity(game_state, target_player_id, amount, announce=None):
    """烈焰蜈蚣免伤：消耗一张蜈蚣免受一次伤害。返回减免后的伤害。"""
    if amount <= 0:
        return amount
    if game_state.character_ids.get(target_player_id) != SLUGCAT_CHARACTER_ID:
        return amount
    player = game_state.players[target_player_id]
    # Check hand first
    if _hand_count(game_state, 22) > 0:
        _remove_hand_creature(game_state, 22)
        if announce:
            announce(f"玩家{target_player_id}的烈焰蜈蚣消耗一张免受伤害")
        return 0
    # Check threats
    threats = player.special.get("creature_threats", [])
    for i, t in enumerate(threats):
        if t["card_id"] == 22:
            threats.pop(i)
            if announce:
                announce(f"玩家{target_player_id}的烈焰蜈蚣消耗一张免受伤害")
            return 0
    return amount


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


def _add_creature_threat(game_state, player_id, creature_id, owner_id=None):
    """Add a creature as a threat (no hand slot) with HP and owner tracking."""
    if owner_id is None:
        owner_id = player_id
    player = game_state.players[player_id]
    player.special.setdefault("creature_threats", []).append(
        {
            "card_id": creature_id,
            "health": CREATURE_BASE_HEALTH.get(creature_id, 1),
            "owner": owner_id,
        }
    )


def _add_creature_to_hand(game_state, player_id, card_id, owner_id=None, noodle_cost=0):
    """Add a creature card to hand and initialise its HP tracking.

    For remote players the card is queued via ``pending_insertions`` so the
    peer's client inserts it into its own hand on the next state sync.
    """
    if owner_id is None:
        owner_id = player_id
    player = game_state.players[player_id]
    if player_id == game_state.local_player_id:
        combat.add_card_to_hand(game_state, card_id)
        _refresh_local_hand(game_state)
    else:
        player.special.setdefault("pending_insertions", []).append(card_id)
    health_list = player.special.setdefault("creature_health", {}).setdefault(card_id, [])
    health_list.append(CREATURE_BASE_HEALTH.get(card_id, 1))
    owner_list = player.special.setdefault("hand_creature_owners", {}).setdefault(card_id, [])
    owner_list.append(owner_id)
    if card_id == 16:
        player.special.setdefault("noodle_cost_stacks", []).append(noodle_cost)


def _refresh_local_hand(game_state):
    """Refresh the local player's hand display in real time."""
    if game_state.window is not None:
        from card_duel.ui.network import refresh_cards
        refresh_cards(game_state)
        game_state.window.refresh()


def _remove_hand_creature(game_state, card_id, player_id=None):
    """Remove the first matching creature from hand and its HP/owner entries.

    player_id=None时默认为local_player_id（本地玩家手牌）。
    player_id != local_player_id时只清除creature_health等数据，
    不操作hand_cards（对手手牌通过pending_insertions同步）。
    """
    if player_id is None:
        player_id = game_state.local_player_id
    player = game_state.players[player_id]

    # 只从本地玩家的hand_cards中移除卡牌
    if player_id == game_state.local_player_id:
        for index in _occupied_hand_indexes(game_state):
            if game_state.hand_cards[index] == card_id:
                game_state.hand_cards[index] = -1
                _refresh_local_hand(game_state)
                break

    # 无论哪个玩家，都从其creature_health中移除记录
    health_list = player.special.get("creature_health", {}).get(card_id, [])
    if health_list:
        health_list.pop(0)
    owner_list = player.special.get("hand_creature_owners", {}).get(card_id, [])
    if card_id == 16:
        stacks = player.special.get("noodle_cost_stacks", [])
        if stacks:
            stacks.pop(0)
    if owner_list:
        return owner_list.pop(0)
    return player_id


def _damage_hand_creature(game_state, target_player_id, card_id, damage, announce, attacker_id=None):
    """Deal damage to the first hand creature of given type. Return True if killed."""
    player = game_state.players[target_player_id]
    health_list = player.special.get("creature_health", {}).get(card_id, [])
    if not health_list:
        return False
    # Noodle fly (17) is immune to first attack each turn.
    if card_id == 17 and health_list[0] > 0:
        health_list[0] = -abs(health_list[0])  # mark as used immunity
        announce(f"面条蝇免疫了本次攻击")
        return False
    health_list[0] -= damage
    announce(f"对{SLUGCAT_SPECS_BY_ID[card_id].name}造成{damage}点伤害（剩余{max(0, health_list[0])}）")
    # 烈焰蜥蜴反伤3
    if card_id == 23 and attacker_id is not None:
        combat.apply_damage(game_state, 3, attacker_id, announce=announce)
        announce(f"烈焰蜥蜴反伤玩家{attacker_id}3点伤害")
    if health_list[0] <= 0:
        owner_id = _remove_hand_creature(game_state, card_id, player_id=target_player_id)
        if owner_id is None:
            owner_id = target_player_id
        _on_creature_death(game_state, target_player_id, card_id, owner_id, announce)
        return True
    return False


def _damage_threat_creature(game_state, target_player_id, index, damage, announce, attacker_id=None):
    """Deal damage to a threat creature by index. Return True if killed."""
    player = game_state.players[target_player_id]
    threats = player.special.get("creature_threats", [])
    if index < 0 or index >= len(threats):
        return False
    threat = threats[index]
    card_id = threat["card_id"]
    if card_id == 17 and threat["health"] > 0:
        threat["health"] = -abs(threat["health"])
        announce(f"面条蝇免疫了本次攻击")
        return False
    threat["health"] -= damage
    announce(f"对{SLUGCAT_SPECS_BY_ID[card_id].name}造成{damage}点伤害（剩余{max(0, threat['health'])}）")
    # 烈焰蜥蜴反伤3
    if card_id == 23 and attacker_id is not None:
        combat.apply_damage(game_state, 3, attacker_id, announce=announce)
        announce(f"烈焰蜥蜴反伤玩家{attacker_id}3点伤害")
    if threat["health"] <= 0:
        owner_id = threat.get("owner", target_player_id)
        threats.pop(index)
        _on_creature_death(game_state, target_player_id, card_id, owner_id, announce)
        return True
    return False


def _on_creature_death(game_state, player_id, card_id, owner_id, announce):
    """Trigger death effects and return the creature card to owner's draw pile."""
    base_health = CREATURE_BASE_HEALTH.get(card_id, 0)
    game_state.players[player_id].special["last_dead_creature_health"] = base_health
    announce(f"{SLUGCAT_SPECS_BY_ID[card_id].name}被击杀（{base_health}血）")
    # Death effects
    if card_id == 16:
        # 小面条死亡 → 加入面条蝇
        _add_creature_to_hand(game_state, player_id, 17, owner_id=player_id)
        announce(f"小面条死亡，引来面条蝇")
    elif card_id == 18:
        # 射线虫死亡 → 加入秃鹫
        _add_creature_threat(game_state, player_id, 19, owner_id=player_id)
        announce(f"射线虫死亡，引来秃鹫")
    elif card_id == 25:
        # 拾荒者死亡 → 获得其物品
        carried_item = random.choices((1, 3, 4, 5), weights=(6, 1, 2, 1), k=1)[0]
        combat.add_card_to_hand(game_state, carried_item)
        announce(
            f"拾荒者被击杀，掉落{SLUGCAT_SPECS_BY_ID[carried_item].name}"
        )
    # Return card to owner's draw pile.  Creature cards are Slugcat-specific:
    # only add to the local draw_pile when the local player IS the owner and
    # is a Slugcat.  If the owner is the remote player, queue the card via
    # ``pending_draw_returns`` so the peer adds it to their own draw_pile on
    # the next state sync.
    if not (1 <= owner_id <= 2):
        return
    local_id = game_state.local_player_id
    if owner_id == local_id and game_state.character_ids.get(local_id) == SLUGCAT_CHARACTER_ID:
        game_state.draw_pile.append(card_id)
    else:
        owner = game_state.players[owner_id]
        owner.special.setdefault("pending_draw_returns", []).append(card_id)


def get_attack_targets(game_state, source_player_id, target_player_id):
    """Return attackable targets: opponent player + both sides' hand creatures
    + opponent's threat creatures.

    Hand creatures are read from ``player.special["creature_health"]``.  We
    scan **both** the attacker and the defender so a creature is always
    selectable even when network sync only populated one side's data.  Each
    creature target carries ``player_id`` so the caller knows whose
    ``creature_health`` to damage.
    """
    targets = [{
        "type": "player", "card_id": 0,
        "name": f"玩家{target_player_id}",
        "player_id": target_player_id,
    }]

    # Hand creatures from BOTH sides.
    for pid in (source_player_id, target_player_id):
        player = game_state.players[pid]
        hand_creature_health = player.special.get("creature_health", {})
        for raw_id, health_list in hand_creature_health.items():
            count = len(health_list) if health_list else 0
            if count <= 0:
                continue
            # JSON反序列化后key可能是字符串，统一转int
            card_id = int(raw_id)
            name = SLUGCAT_SPECS_BY_ID[card_id].name
            if count > 1:
                name += f" ×{count}"
            side = "己方" if pid == source_player_id else "敌方"
            targets.append({
                "type": "hand", "card_id": card_id,
                "name": f"[{side}] {name}", "player_id": pid,
            })

    # Threat creatures — opponent's, always public
    opp = game_state.players[target_player_id]
    threats = opp.special.get("creature_threats", [])
    seen_threat = set()
    for threat in threats:
        card_id = int(threat["card_id"])
        if card_id not in seen_threat:
            seen_threat.add(card_id)
            count = sum(1 for t in threats if int(t["card_id"]) == card_id)
            name = SLUGCAT_SPECS_BY_ID[card_id].name
            if count > 1:
                name += f" ×{count}"
            targets.append({
                "type": "threat", "card_id": card_id, "name": name,
                "player_id": target_player_id,
            })
    return targets


def choose_attack_target(game_state, source_player_id, target_player_id, announce):
    """Always pop up target selection, even if only one target exists.

    Returns the chosen target dict.  Returns None only if the user cancels
    the popup (caller treats None as "default to player").
    """
    targets = get_attack_targets(game_state, source_player_id, target_player_id)
    choices = [t["name"] for t in targets]
    choice = sg.popup_get_text(
        f"选择攻击目标（输入序号）：\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(choices)),
        title="选择攻击目标",
        keep_on_top=True,
    )
    if choice is None:
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(targets):
            return targets[idx]
    except ValueError:
        pass
    return targets[0]  # default to first target


def _kill_creature_at(game_state, target, announce):
    """秒杀指定位置的生物（不造伤害，直接移除并触发死亡效果）。"""
    local_id = game_state.local_player_id
    opponent_id = 2 if local_id == 1 else 1
    card_id = target["card_id"]
    location = target["location"]

    if location == "own_hand":
        owner_id = _remove_hand_creature(game_state, card_id)
        if owner_id is None:
            owner_id = local_id
        _on_creature_death(game_state, local_id, card_id, owner_id, announce)
    elif location == "own_threat":
        threats = game_state.players[local_id].special.get("creature_threats", [])
        idx = next((i for i, t in enumerate(threats) if int(t["card_id"]) == card_id), -1)
        if idx >= 0:
            threat = threats.pop(idx)
            owner_id = threat.get("owner", local_id)
            _on_creature_death(game_state, local_id, card_id, owner_id, announce)
    elif location == "opp_threat":
        threats = game_state.players[opponent_id].special.get("creature_threats", [])
        idx = next((i for i, t in enumerate(threats) if int(t["card_id"]) == card_id), -1)
        if idx >= 0:
            threat = threats.pop(idx)
            owner_id = threat.get("owner", opponent_id)
            _on_creature_death(game_state, opponent_id, card_id, owner_id, announce)


def choose_creature_target(game_state, card_id_filter=None):
    """从所有可见位置收集生物目标并让玩家选择。

    card_id_filter 指定时只搜索该类型生物。
    返回 {"location": "own_hand"/"own_threat"/"opp_threat", "card_id": X, "name": ...}
    或 None（无目标）。
    """
    local_id = game_state.local_player_id
    opponent_id = 2 if local_id == 1 else 1
    targets = []

    # 己方手牌生物
    seen = set()
    for index in _occupied_hand_indexes(game_state):
        cid = game_state.hand_cards[index]
        if cid not in SLUGCAT_CREATURE_IDS or cid in seen:
            continue
        if card_id_filter is not None and cid != card_id_filter:
            continue
        seen.add(cid)
        count = _hand_count(game_state, cid)
        name = SLUGCAT_SPECS_BY_ID[cid].name
        if count > 1:
            name += f" ×{count}"
        targets.append({"location": "own_hand", "card_id": cid,
                        "name": f"己方手牌: {name}"})

    # 己方威胁生物
    own_threats = game_state.players[local_id].special.get("creature_threats", [])
    seen_own = set()
    for threat in own_threats:
        cid = int(threat["card_id"])
        if card_id_filter is not None and cid != card_id_filter:
            continue
        if cid not in seen_own:
            seen_own.add(cid)
            count = sum(1 for t in own_threats if int(t["card_id"]) == cid)
            name = SLUGCAT_SPECS_BY_ID[cid].name
            if count > 1:
                name += f" ×{count}"
            targets.append({"location": "own_threat", "card_id": cid,
                            "name": f"己方威胁: {name}"})

    # 敌方威胁生物
    opp_threats = game_state.players[opponent_id].special.get("creature_threats", [])
    seen_opp = set()
    for threat in opp_threats:
        cid = int(threat["card_id"])
        if card_id_filter is not None and cid != card_id_filter:
            continue
        if cid not in seen_opp:
            seen_opp.add(cid)
            count = sum(1 for t in opp_threats if int(t["card_id"]) == cid)
            name = SLUGCAT_SPECS_BY_ID[cid].name
            if count > 1:
                name += f" ×{count}"
            targets.append({"location": "opp_threat", "card_id": cid,
                            "name": f"敌方威胁: {name}"})

    if not targets:
        return None
    if len(targets) == 1:
        return targets[0]

    choices = [t["name"] for t in targets]
    choice = sg.popup_get_text(
        f"选择目标（输入序号）：\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(choices)),
        title="选择生物目标",
        keep_on_top=True,
    )
    if choice is None:
        return targets[0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(targets):
            return targets[idx]
    except ValueError:
        pass
    return targets[0]


def _choose_own_hand_creature(game_state):
    """让玩家从自己手牌中选择一种生物类型。返回 card_id 或 None。"""
    seen = set()
    creatures = []
    for index in _occupied_hand_indexes(game_state):
        cid = game_state.hand_cards[index]
        if cid in SLUGCAT_CREATURE_IDS and cid not in seen:
            seen.add(cid)
            count = _hand_count(game_state, cid)
            name = SLUGCAT_SPECS_BY_ID[cid].name
            if count > 1:
                name += f" ×{count}"
            creatures.append((cid, name))

    if not creatures:
        return None
    if len(creatures) == 1:
        return creatures[0][0]

    choices = [name for _, name in creatures]
    choice = sg.popup_get_text(
        "选择要转移的生物（输入序号）：\n"
        + "\n".join(f"{i+1}. {c}" for i, c in enumerate(choices)),
        title="闪光果",
        keep_on_top=True,
    )
    if choice is None:
        return creatures[0][0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(creatures):
            return creatures[idx][0]
    except ValueError:
        pass
    return creatures[0][0]



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
            _refresh_local_hand(game_state)
            return True
    return False


def _pop_first_creature_from_hand(game_state):
    for index in _occupied_hand_indexes(game_state):
        card_id = game_state.hand_cards[index]
        if card_id in SLUGCAT_CREATURE_IDS:
            game_state.hand_cards[index] = -1
            _refresh_local_hand(game_state)
            player = game_state.players[game_state.local_player_id]
            health_list = player.special.get("creature_health", {}).get(card_id, [])
            if health_list:
                health_list.pop(0)
            owner_list = player.special.get("hand_creature_owners", {}).get(card_id, [])
            if owner_list:
                owner_list.pop(0)
            if card_id == 16:
                stacks = player.special.get("noodle_cost_stacks", [])
                if stacks:
                    stacks.pop(0)
            return card_id
    return None


def _remove_all_creatures_from_hand(game_state):
    for index in _occupied_hand_indexes(game_state):
        if game_state.hand_cards[index] in SLUGCAT_CREATURE_IDS:
            game_state.hand_cards[index] = -1
    _refresh_local_hand(game_state)
    player = game_state.players[game_state.local_player_id]
    player.special["creature_health"] = {}
    player.special["hand_creature_owners"] = {}
    player.special["noodle_cost_stacks"] = []


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
    # 插入物：_play_attack 开头已判定 card_id in SLUGCAT_INSERTED_IDS 时走拔出分支
    49: _play_attack(49, 0),
    50: _play_attack(50, 0),
}

assert len(CARD_EFFECTS) == len(SLUGCAT_CARD_SPECS)
