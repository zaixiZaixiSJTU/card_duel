"""Creature zones, targeting, damage, and death effects for Slugcat cards."""

from __future__ import annotations

import random
from contextlib import suppress
from dataclasses import dataclass

from card_duel.cards.slugcat.specs import (
    CREATURE_BASE_HEALTH,
    SLUGCAT_CHARACTER_ID,
    SLUGCAT_SPECS_BY_ID,
)
from card_duel.core.models import CreatureState
from card_duel.core.rules import add_card_to_hand


@dataclass(frozen=True, slots=True)
class AttackTarget:
    zone: str
    player_id: int
    card_id: int = 0
    label: str = ""


def add_hand_creature(
    state,
    player_id: int,
    card_id: int,
    *,
    owner_id: int | None = None,
    noodle_cost: int = 0,
) -> CreatureState:
    """Add a creature and queue its physical card for the owning endpoint."""
    owner_id = player_id if owner_id is None else owner_id
    creature = CreatureState(
        card_id=card_id,
        health=CREATURE_BASE_HEALTH[card_id],
        owner_id=owner_id,
        noodle_cost=noodle_cost,
    )
    state.players[player_id].statuses.hand_creatures.append(creature)

    if card_id == 25 and creature.held_item == 0:
        creature.held_item = _roll_scavenger_item()

    if card_id == 22:
        # 烈焰蜈蚣只有一只：第一张体节出生时建立共享 20 血池，
        # 后续加入的体节同步显示当前剩余血量。
        if centipede_health(state) <= 0:
            state.players[owner_id].statuses.centipede_health = 20
        else:
            creature.health = centipede_health(state)

    # 生物不占手牌卡槽：只进入生物区。管虫（26）是唯一拿在手里的生物，
    # 因此只有它会作为实体卡加入手牌。
    if card_id == 26 and state.character_ids.get(player_id) == SLUGCAT_CHARACTER_ID:
        if player_id == state.local_player_id:
            add_card_to_hand(state, card_id)
        else:
            state.players[player_id].statuses.pending_hand_additions.append(card_id)
    return creature


def add_threat(
    state,
    player_id: int,
    card_id: int,
    *,
    owner_id: int | None = None,
) -> CreatureState:
    owner_id = player_id if owner_id is None else owner_id
    creature = CreatureState(
        card_id=card_id,
        health=CREATURE_BASE_HEALTH[card_id],
        owner_id=owner_id,
    )
    state.players[player_id].statuses.creature_threats.append(creature)
    if card_id == 25 and creature.held_item == 0:
        creature.held_item = _roll_scavenger_item()
    return creature


def remove_hand_creature(
    state,
    player_id: int,
    card_id: int,
    *,
    remove_physical: bool = True,
) -> CreatureState | None:
    statuses = state.players[player_id].statuses
    creature = next(
        (item for item in statuses.hand_creatures if item.card_id == card_id), None
    )
    if creature is None:
        return None
    statuses.hand_creatures.remove(creature)

    if (
        remove_physical
        and card_id == 26
        and state.character_ids.get(player_id) == SLUGCAT_CHARACTER_ID
    ):
        if player_id == state.local_player_id:
            with suppress(ValueError):
                state.hand_cards.remove(card_id)
        else:
            statuses.pending_hand_removals.append(card_id)
    return creature


def remove_all_local_hand_creatures(
    state, player_id: int
) -> list[CreatureState]:
    """Remove every hand creature and return the removed creatures."""
    statuses = state.players[player_id].statuses
    creatures = list(statuses.hand_creatures)
    statuses.hand_creatures.clear()
    if player_id != state.local_player_id:
        statuses.pending_hand_removals.extend(
            item.card_id for item in creatures if item.card_id == 26
        )
        return creatures
    for creature in creatures:
        if creature.card_id == 26:
            with suppress(ValueError):
                state.hand_cards.remove(26)
    return creatures


def hand_creature(state, player_id: int, card_id: int) -> CreatureState | None:
    return next(
        (
            item
            for item in state.players[player_id].statuses.hand_creatures
            if item.card_id == card_id
        ),
        None,
    )


def centipede_health(state) -> int:
    """Shared flame-centipede body pool; 0 means no live centipede."""
    return max(
        (player.statuses.centipede_health for player in state.players.values()),
        default=0,
    )


def _roll_scavenger_item() -> int:
    """Random held item for a generated scavenger (3/5 钢筋 1/10 炸药 1/5 炸矛 1/10 电矛)."""
    return random.choices((1, 3, 4, 5), weights=(6, 1, 2, 1), k=1)[0]


def _reduce_centipede_health(state, damage: int) -> int:
    """Reduce the shared centipede pool and return the actual damage dealt."""
    pool_owner = next(
        (
            player
            for player in state.players.values()
            if player.statuses.centipede_health
        ),
        None,
    )
    if pool_owner is None:
        return 0
    clamped = max(0, damage)
    remaining = max(0, pool_owner.statuses.centipede_health - clamped)
    actual = pool_owner.statuses.centipede_health - remaining
    pool_owner.statuses.centipede_health = remaining
    _sync_centipede_health(state, remaining)
    return actual


def _sync_centipede_health(state, health: int) -> None:
    """Keep every segment's displayed health in sync with the shared pool."""
    for player in state.players.values():
        for zone in (
            player.statuses.hand_creatures,
            player.statuses.creature_threats,
        ):
            for creature in zone:
                if creature.card_id == 22:
                    creature.health = health


def _remove_all_centipede_segments(state) -> list[CreatureState]:
    """Remove every centipede segment on both sides and reset the pool."""
    removed = []
    for player in state.players.values():
        statuses = player.statuses
        for zone in (statuses.hand_creatures, statuses.creature_threats):
            kept = []
            for creature in zone:
                if creature.card_id == 22:
                    removed.append(creature)
                else:
                    kept.append(creature)
            zone[:] = kept
        statuses.centipede_health = 0
    return removed


def attack_targets(state, source_player_id: int, target_player_id: int):
    targets = [
        AttackTarget("player", target_player_id, label=f"玩家{target_player_id}")
    ]
    for player_id in (source_player_id, target_player_id):
        creatures = state.players[player_id].statuses.hand_creatures
        for card_id in dict.fromkeys(item.card_id for item in creatures):
            count = sum(item.card_id == card_id for item in creatures)
            side = "己方" if player_id == source_player_id else "敌方"
            suffix = "" if card_id == 22 else (f" ×{count}" if count > 1 else "")
            targets.append(
                AttackTarget(
                    "hand",
                    player_id,
                    card_id,
                    f"[{side}] {SLUGCAT_SPECS_BY_ID[card_id].name}{suffix}",
                )
            )
    threats = state.players[target_player_id].statuses.creature_threats
    for card_id in dict.fromkeys(item.card_id for item in threats):
        count = sum(item.card_id == card_id for item in threats)
        suffix = "" if card_id == 22 else (f" ×{count}" if count > 1 else "")
        targets.append(
            AttackTarget(
                "threat",
                target_player_id,
                card_id,
                f"[敌方威胁] {SLUGCAT_SPECS_BY_ID[card_id].name}{suffix}",
            )
        )
    return targets


def resolve_attack(
    context,
    damage: int,
    card_name: str,
    on_player_penetrate=None,
) -> int:
    """Choose a player or creature target and apply one attack."""
    targets = attack_targets(
        context.state, context.source_player_id, context.target_player_id
    )
    labels = tuple(target.label for target in targets)
    selected = context.choices.choose_option(
        "选择攻击目标",
        "选择本次攻击的目标",
        labels,
        labels[0],
    )
    target = next((item for item in targets if item.label == selected), targets[0])
    if target.zone == "player":
        total, agility_consumed, life_loss = context.combat.apply_damage_with_report(
            damage, target.player_id, None
        )
        context.announce(
            f"玩家{context.source_player_id}使用{card_name}攻击{target.label}"
            f"（总伤害{total}，扣敏捷{agility_consumed}，实际扣血{life_loss}）"
        )
        if life_loss > 0 and on_player_penetrate is not None:
            on_player_penetrate(context)
        return life_loss
    context.announce(f"玩家{context.source_player_id}使用{card_name}攻击{target.label}")
    damage_creature(
        context,
        target.player_id,
        target.card_id,
        damage,
        threat=target.zone == "threat",
    )
    return 0


def damage_creature(
    context,
    player_id: int,
    card_id: int,
    damage: int,
    *,
    threat: bool,
) -> bool:
    statuses = context.state.players[player_id].statuses
    zone = statuses.creature_threats if threat else statuses.hand_creatures
    creature = next((item for item in zone if item.card_id == card_id), None)
    if creature is None:
        return False
    if card_id == 17 and not statuses.noodle_fly_immunity_used:
        statuses.noodle_fly_immunity_used = True
        context.announce("面条蝇免疫了本次攻击")
        return False

    if card_id == 22:
        lost = _reduce_centipede_health(context.state, damage)
        context.announce(
            f"对烈焰蜈蚣造成{lost}点伤害"
            f"（剩余{centipede_health(context.state)}）"
        )
        if centipede_health(context.state) > 0:
            return False
        zone.remove(creature)
        _kill_centipede(context, player_id, creature)
        return True

    creature.health -= max(0, damage)
    context.announce(
        f"对{SLUGCAT_SPECS_BY_ID[card_id].name}造成{damage}点伤害"
        f"（剩余{max(0, creature.health)}）"
    )
    if card_id == 23:
        context.combat.apply_damage(3, context.source_player_id, context.announce)
        context.announce(f"烈焰蜥蜴反伤玩家{context.source_player_id}3点伤害")
    if creature.health > 0:
        return False

    zone.remove(creature)
    if not threat and state_has_physical_creature(context.state, player_id):
        _remove_physical_or_queue(context.state, player_id, card_id)
    on_creature_death(
        context.state,
        player_id,
        creature,
        context.announce,
        private_announce=context.private_announce,
    )
    return True


def _kill_centipede(context, player_id: int, creature: CreatureState) -> None:
    """Remove every centipede segment and settle the killed segment's death."""
    _remove_all_centipede_segments(context.state)
    if context.announce:
        context.announce("烈焰蜈蚣死亡，所有体节消失")
    on_creature_death(
        context.state,
        player_id,
        creature,
        context.announce,
        cause="被击杀",
        private_announce=context.private_announce,
    )


def state_has_physical_creature(state, player_id: int) -> bool:
    return state.character_ids.get(player_id) == SLUGCAT_CHARACTER_ID


def _remove_physical_or_queue(state, player_id: int, card_id: int) -> None:
    if card_id != 26:
        return
    if player_id == state.local_player_id:
        with suppress(ValueError):
            state.hand_cards.remove(card_id)
    else:
        state.players[player_id].statuses.pending_hand_removals.append(card_id)


def on_creature_death(
    state,
    player_id: int,
    creature: CreatureState,
    announce,
    *,
    cause: str = "被击杀",
    private_announce=None,
) -> None:
    card_id = creature.card_id
    statuses = state.players[player_id].statuses
    statuses.last_dead_creature_health += CREATURE_BASE_HEALTH[card_id]
    announce(
        f"{SLUGCAT_SPECS_BY_ID[card_id].name}{cause}"
        f"（{CREATURE_BASE_HEALTH[card_id]}血）"
    )
    if card_id == 16:
        add_hand_creature(state, player_id, 17, owner_id=player_id)
        announce("小面条死亡，引来面条蝇")
    elif card_id == 25 and state.character_ids.get(player_id) == SLUGCAT_CHARACTER_ID:
        item = creature.held_item or _roll_scavenger_item()
        if player_id == state.local_player_id:
            add_card_to_hand(state, item)
        else:
            statuses.pending_hand_additions.append(item)
        announce("拾荒者掉落了携带的物品")
        (private_announce or announce)(
            f"获得物品：{SLUGCAT_SPECS_BY_ID[item].name}（仅自己可见）"
        )

    if creature.owner_id == player_id:
        _vulture_leaves_on_creature_death(state, player_id, announce)


def _vulture_leaves_on_creature_death(state, player_id: int, announce) -> None:
    """One vulture in the player's hand leaves when one of their creatures dies.

    The leave is equivalent to playing the vulture for 2 energy, except it
    happens automatically and costs nothing.
    """
    statuses = state.players[player_id].statuses
    vulture = next(
        (item for item in statuses.hand_creatures if item.card_id == 19), None
    )
    if vulture is None:
        return
    statuses.hand_creatures.remove(vulture)
    if announce:
        announce("我方生物死亡，手牌中的秃鹫离场（相当于打出）")


def return_creature_to_owner_pool(state, creature: CreatureState) -> None:
    """Return a still-living creature to its owner's summon pool.

    Death is final and never calls this helper; only creatures that left
    play while alive (猫跑路了) come back for re-summoning.
    """
    if state.character_ids.get(creature.owner_id) != SLUGCAT_CHARACTER_ID:
        return
    from card_duel.cards.slugcat.state import slugcat_data

    if creature.owner_id == state.local_player_id:
        data = slugcat_data(state.players[creature.owner_id])
        data.unlocked_creature_counts[creature.card_id] = (
            data.unlocked_creature_counts.get(creature.card_id, 0) + 1
        )
    else:
        state.players[creature.owner_id].statuses.pending_draw_returns.append(
            creature.card_id
        )


def kill_matching_creature(context, card_id: int) -> bool:
    """Let the player choose and instantly kill one matching visible creature."""
    candidates = []
    for player_id in (context.source_player_id, context.target_player_id):
        side = "己方" if player_id == context.source_player_id else "敌方"
        if any(
            item.card_id == card_id
            for item in context.state.players[player_id].statuses.hand_creatures
        ):
            candidates.append(
                AttackTarget(
                    "hand",
                    player_id,
                    card_id,
                    f"[{side}手牌] {SLUGCAT_SPECS_BY_ID[card_id].name}",
                )
            )
        if any(
            item.card_id == card_id
            for item in context.state.players[player_id].statuses.creature_threats
        ):
            candidates.append(
                AttackTarget(
                    "threat",
                    player_id,
                    card_id,
                    f"[{side}威胁] {SLUGCAT_SPECS_BY_ID[card_id].name}",
                )
            )
    if not candidates:
        return False
    labels = tuple(item.label for item in candidates)
    selected = context.choices.choose_option(
        "选择生物目标", "选择要秒杀的生物", labels, labels[0]
    )
    target = next(
        (item for item in candidates if item.label == selected), candidates[0]
    )
    statuses = context.state.players[target.player_id].statuses
    zone = (
        statuses.creature_threats
        if target.zone == "threat"
        else statuses.hand_creatures
    )
    creature = next(item for item in zone if item.card_id == card_id)
    zone.remove(creature)
    if card_id == 22:
        _remove_all_centipede_segments(context.state)
        if context.announce:
            context.announce("烟雾果秒杀了烈焰蜈蚣，所有体节消失")
        on_creature_death(
            context.state,
            target.player_id,
            creature,
            context.announce,
            cause="被秒杀",
            private_announce=context.private_announce,
        )
        return True
    if target.zone == "hand" and state_has_physical_creature(
        context.state, target.player_id
    ):
        _remove_physical_or_queue(context.state, target.player_id, card_id)
    on_creature_death(
        context.state,
        target.player_id,
        creature,
        context.announce,
        cause="被秒杀",
        private_announce=context.private_announce,
    )
    return True
