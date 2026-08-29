"""Character-aware combat service built on pure domain state."""

from __future__ import annotations

from card_duel.cards.registry import CardRegistry
from card_duel.core.game import TurnPhase
from card_duel.core.models import CombatStatuses, GameState, ScheduledEvent
from card_duel.core.rules import add_defence, draw_cards


class CombatEngine:
    """Resolve combat while delegating character-specific behavior to the catalog."""

    def __init__(self, state: GameState, registry: CardRegistry) -> None:
        self.state = state
        self.registry = registry

    def initialize_players(self) -> None:
        for player_id, character_id in self.state.character_ids.items():
            if character_id is None:
                raise ValueError(f"玩家 {player_id} 尚未选择角色")
            player = self.state.players[player_id]
            player.health = player.max_health = 30
            player.energy = player.strength = player.poison = 0
            player.defences.clear()
            player.statuses = CombatStatuses()
            rules = self.registry.get_character(character_id).rules
            player.character_data = rules.create_data()
            rules.initialize(player)

    def apply_damage(self, damage: int, target_player_id: int, announce=None) -> int:
        target = self.state.players[target_player_id]
        if target.statuses.immune_next_attacks:
            target.statuses.immune_next_attacks -= 1
            if announce:
                announce(f"玩家{target_player_id}免疫了本次攻击")
            return 0

        remaining = max(0, damage)
        effects = target.defences
        while effects and remaining:
            absorbed = min(effects[0].amount, remaining)
            effects[0].amount -= absorbed
            remaining -= absorbed
            if effects[0].amount == 0:
                effects.pop(0)
        remaining = self._modify_incoming_damage(remaining, target_player_id, announce)
        rules = self._rules_for(target_player_id)
        actual_loss = rules.prevent_life_loss(target, remaining)
        return self._apply_life_loss(actual_loss, target_player_id, announce)

    def apply_damage_with_report(
        self, damage: int, target_player_id: int, announce=None
    ) -> tuple[int, int, int]:
        """Apply damage and report (total, agility_consumed, actual_loss)."""
        target = self.state.players[target_player_id]
        data = getattr(target, "character_data", None)
        agility_before = getattr(data, "agility", 0) if data is not None else 0
        actual = self.apply_damage(damage, target_player_id, announce)
        agility_after = getattr(data, "agility", 0) if data is not None else 0
        return damage, max(0, agility_before - agility_after), actual

    def lose_life(self, amount: int, target_player_id: int, announce=None) -> int:
        target = self.state.players[target_player_id]
        rules = self._rules_for(target_player_id)
        actual_loss = self._modify_incoming_damage(
            max(0, amount), target_player_id, announce
        )
        consume = getattr(rules, "consume_on_direct_life_loss", None)
        if consume is not None:
            consume(target, actual_loss)
        return self._apply_life_loss(actual_loss, target_player_id, announce)

    def _apply_life_loss(self, actual_loss, target_player_id, announce) -> int:
        target = self.state.players[target_player_id]
        rules = self._rules_for(target_player_id)
        target.health -= actual_loss
        if announce and actual_loss:
            announce(f"玩家{target_player_id}失去{actual_loss}点生命")
        if target.health <= 0:
            rules.on_life_depleted(self.state, target_player_id, announce=announce)
        return actual_loss

    def _rules_for(self, player_id):
        character_id = self.state.character_ids[player_id]
        if character_id is None:
            raise RuntimeError(f"玩家 {player_id} 尚未选择角色")
        return self.registry.get_character(character_id).rules

    def _modify_incoming_damage(self, damage, target_player_id, announce):
        remaining = damage
        registered = set()
        for character_id in self.state.character_ids.values():
            if character_id is None or character_id in registered:
                continue
            registered.add(character_id)
            rules = self.registry.get_character(character_id).rules
            modifier = getattr(rules, "modify_incoming_damage", None)
            if modifier is not None:
                remaining = modifier(self.state, target_player_id, remaining, announce)
        return remaining

    def resolve_attack(
        self,
        context,
        damage: int,
        card_name: str,
        on_player_penetrate=None,
    ) -> int:
        """Delegate optional non-player targets to an installed character pack."""
        source = self.state.players[context.source_player_id]
        spears = source.statuses.embedded_electric_spears
        if spears:
            penalty = spears * 2
            damage = max(0, damage - penalty)
            context.announce(
                f"玩家{context.source_player_id}受电矛影响，"
                f"本次攻击数值-{penalty}"
            )
        registered = set()
        for character_id in self.state.character_ids.values():
            if character_id is None or character_id in registered:
                continue
            registered.add(character_id)
            rules = self.registry.get_character(character_id).rules
            resolver = getattr(rules, "resolve_attack", None)
            if resolver is not None:
                return resolver(context, damage, card_name, on_player_penetrate)

        # 默认路径（无自定义 resolve_attack 的角色，如战士）：
        # 阵营限制 + 指向性选目标。只能攻击敌方阵营玩家（FFA 互敌，
        # 组队时不同 team 才算敌方）；多个敌方时让玩家选目标，
        # 单个敌方自动选；没有敌方时（如全员同队）不打。
        enemy_targets = self._enemy_player_targets(
            context.state, context.source_player_id
        )
        if not enemy_targets:
            context.announce(
                f"玩家{context.source_player_id}没有可攻击的敌方目标"
            )
            return 0
        if len(enemy_targets) > 1:
            labels = tuple(f"玩家{pid}" for pid in enemy_targets)
            selected = context.choices.choose_option(
                "选择攻击目标",
                "选择本次攻击的敌方玩家",
                labels,
                labels[0],
            )
            target_pid = enemy_targets[labels.index(selected)]
        else:
            target_pid = enemy_targets[0]
        context.announce(
            f"玩家{context.source_player_id}使用{card_name}攻击玩家"
            f"{target_pid}"
        )
        life_loss = self.apply_damage(damage, target_pid, context.announce)
        if life_loss > 0 and on_player_penetrate is not None:
            on_player_penetrate(context)
        return life_loss

    def _enemy_player_targets(
        self, state, source_player_id: int
    ) -> list[int]:
        """返回所有存活敌方玩家座位号（阵营限制）。

        FFA (team_id 为 None) 时所有人互为敌方；组队时 team 不同才算敌方。
        用于指向性攻击目标选择，避免同队互打。
        """
        source_team = state.player_teams.get(source_player_id)
        targets: list[int] = []
        for player_id in state.players:
            if player_id == source_player_id:
                continue
            if not state.players[player_id].is_alive:
                continue
            target_team = state.player_teams.get(player_id)
            if (
                target_team is None
                or source_team is None
                or target_team != source_team
            ):
                targets.append(player_id)
        return targets

    def resolve_scheduled_event(self, event: ScheduledEvent, announce) -> None:
        target = self.state.players[event.target_player_id]
        announce(event.message or "")
        if event.effect_type == 1:
            self.apply_damage(event.amount, event.target_player_id)
        elif event.effect_type == 2:
            target.energy += event.amount
        elif event.effect_type == 3:
            add_defence(target.defences, event.amount)
        elif event.effect_type == 4:
            target.strength += event.amount
        elif event.effect_type == 5:
            target.poison += event.amount
        elif event.effect_type == 6 and event.amount > 0:
            draw_cards(self.state, event.amount)

    def advance_turn_effects(self, player_id: int, announce) -> None:
        player = self.state.players[player_id]
        effects = player.defences
        if not player.statuses.persistent_defence:
            for effect in effects:
                effect.turns_remaining -= 1
            while effects and effects[0].turns_remaining <= 0:
                announce(f"玩家{player_id}的{effects.pop(0).amount}点防御消散")

        due: list[ScheduledEvent] = []
        pending: list[ScheduledEvent] = []
        for event in self.state.timeline:
            event.turns_remaining -= 1
            (due if event.turns_remaining <= 0 else pending).append(event)
        self.state.timeline = pending
        for event in due:
            self.resolve_scheduled_event(event, announce)

    def register_turn_handlers(self, turn) -> None:
        def lock_round1_health_start(context):
            """先手方第一回合开始：锁定对方生命（回合结束统一恢复为满血）。

            多人对局（3+ 人）不再启用此锁定，因为"对方"概念不再单一；
            2 人时保留原行为以维持 1v1 平衡性。
            """
            if (
                self.state.round_number == 1
                and self.state.first_player_id == context.player_id
                and len(self.state.players) == 2
            ):
                self.state.round1_lock_health = self.state.players[
                    context.opponent_id
                ].health

        def restore_round1_health_end(context):
            if (
                self.state.round1_lock_health is not None
                and self.state.first_player_id == context.player_id
                and len(self.state.players) == 2
            ):
                opponent = self.state.players[context.opponent_id]
                locked = self.state.round1_lock_health
                if opponent.health != locked:
                    opponent.health = locked
                    context.announce(
                        f"先手方第一回合：玩家{context.opponent_id}生命锁定为{locked}"
                        "（其它效果保留）"
                    )
                self.state.round1_lock_health = None

        turn.register_phase_handler(
            TurnPhase.TURN_START, lock_round1_health_start, priority=5
        )
        turn.register_phase_handler(
            TurnPhase.TURN_END, restore_round1_health_end, priority=90
        )

        registered: set[int] = set()
        for character_id in self.state.character_ids.values():
            if character_id is None or character_id in registered:
                continue
            self.registry.get_character(character_id).rules.register_turn_handlers(
                turn, self
            )
            registered.add(character_id)

    def is_player_defeated(self, player_id: int) -> bool:
        character_id = self.state.character_ids[player_id]
        if character_id is None:
            return False
        rules = self.registry.get_character(character_id).rules
        defeated = rules.is_defeated(self.state.players[player_id])
        # 同步 is_alive：多人轮转跳过死亡玩家、胜负判定都依赖此字段。
        if defeated:
            self.state.players[player_id].is_alive = False
        return defeated

    def winning_team_id(self) -> int | None:
        """敌方全死算赢：当只剩一个阵营仍有存活玩家时返回该阵营编号。

        - FFA（team_id 全为 None）：每个玩家独立成阵营，只剩一人时该人胜。
        - 组队（team_id 为整数）：同阵营共享胜负，对方阵营全灭时己方胜。
        - 2 人时退化为一方死则对方胜（与原 winning_player_id 语义一致）。
        """
        alive_teams: set[int] = set()
        for player_id in self.state.players:
            if self.is_player_defeated(player_id):
                continue
            team = self.state.player_teams.get(player_id)
            # FFA 时每个玩家独立成阵营，用 player_id 当 team key。
            alive_teams.add(team if team is not None else player_id)
        if len(self.state.players) > 1 and len(alive_teams) <= 1:
            return next(iter(alive_teams)) if alive_teams else None
        return None

    def winning_player_id(self) -> int | None:
        """2 人兼容入口：返回仍存活的玩家 ID（多人时仅返回某一存活者）。

        新代码应使用 winning_team_id；此方法保留以便桌面 TCP 与旧调用方
        继续工作。2 人时一方死则另一方胜，与原行为一致。
        """
        if len(self.state.players) == 2:
            if self.is_player_defeated(1):
                return 2
            if self.is_player_defeated(2):
                return 1
            return None
        alive = [
            pid for pid in self.state.players
            if not self.is_player_defeated(pid)
        ]
        if len(alive) == 1:
            return alive[0]
        return None

    def check_game_over(self) -> int | None:
        # 多人组队严谨结束：只剩一个阵营仍有存活玩家时即结束。
        # 旧逻辑用 winning_player_id（要求"只剩一人"），2v2 中一方全灭、
        # 另一方还有两人存活时不会结束——这里改用 winning_team_id 判定
        # 团队胜利。返回值仍为胜方阵营中某一存活玩家号，兼容旧调用方。
        winning = self.winning_team_id()
        if winning is None:
            return None
        self.state.game_over = True
        for player_id in self.state.players:
            if self.is_player_defeated(player_id):
                continue
            team = self.state.player_teams.get(player_id)
            if (team if team is not None else player_id) == winning:
                return player_id
        return None

    def alive_opponents(self, source_player_id: int) -> list[int]:
        """返回源玩家的所有存活敌方座位号（用于目标选择与默认目标）。

        - FFA：除自己外所有存活玩家。
        - 组队：team_id 不同且存活的玩家。
        """
        source_team = self.state.player_teams.get(source_player_id)
        opponents: list[int] = []
        for player_id in self.state.players:
            if player_id == source_player_id:
                continue
            if not self.state.players[player_id].is_alive:
                continue
            target_team = self.state.player_teams.get(player_id)
            # FFA (None) 时所有人互为敌方；组队时 team 不同才算敌方。
            if target_team is None or source_team is None or target_team != source_team:
                opponents.append(player_id)
        return opponents
