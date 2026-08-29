"""多人回合逻辑核心单元测试。

直接构造 GameState + CombatEngine，验证：
1. 3 人 FFA：敌方全死算赢（杀掉 2 和 3 → 剩 1 胜）
2. 2v2 组队：红队全死 → 蓝队胜
3. alive_opponents / _next_alive_player 的多人语义

不依赖 WebSocket，纯单元测试。回合轮转的端到端流程由 test_web_multiplayer_seats
和 test_web_rooms 覆盖。
"""

import unittest

from card_duel.application.combat import CombatEngine
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.core.models import CharacterState, GameState


def _make_state(seats: list[int], teams: dict[int, int | None] | None = None) -> tuple[GameState, CombatEngine]:
    """构造多人 GameState，所有玩家选战士（character_id=1）。"""
    character_ids = {seat: 1 for seat in seats}
    player_teams = teams or {seat: None for seat in seats}
    players = {seat: CharacterState() for seat in seats}
    state = GameState(
        players=players,
        character_ids=character_ids,
        player_teams=player_teams,
        turn_order=list(seats),
        round_number=1,
        active_player_id=seats[0],
        first_player_id=seats[0],
    )
    combat = CombatEngine(state, DEFAULT_REGISTRY)
    combat.initialize_players()
    return state, combat


class MultiplayerCombatTests(unittest.TestCase):
    def test_ffa_three_players_killing_two_returns_last_alive(self):
        state, combat = _make_state([1, 2, 3])
        # 没人死时无胜者。
        self.assertIsNone(combat.winning_team_id())
        self.assertIsNone(combat.winning_player_id())
        # 杀掉玩家 2：仍有两个阵营存活，未分胜负。
        state.players[2].health = 0
        self.assertTrue(combat.is_player_defeated(2))
        self.assertFalse(state.players[2].is_alive)
        self.assertIsNone(combat.winning_team_id())
        # 杀掉玩家 3：只剩玩家 1 存活 → 玩家 1 胜（FFA 用 player_id 当 team key）。
        state.players[3].health = 0
        self.assertTrue(combat.is_player_defeated(3))
        winner = combat.winning_team_id()
        self.assertEqual(winner, 1)
        # winning_player_id 兼容入口也返回玩家 1。
        self.assertEqual(combat.winning_player_id(), 1)
        self.assertTrue(state.game_over is True or combat.check_game_over() == 1)

    def test_two_versus_two_team_wipe_returns_winning_team(self):
        # 2v2：玩家 1、3 红队（team 0），玩家 2、4 蓝队（team 1）。
        teams = {1: 0, 2: 1, 3: 0, 4: 1}
        state, combat = _make_state([1, 2, 3, 4], teams)
        # 没人死时无胜者。
        self.assertIsNone(combat.winning_team_id())
        # 杀掉红队的玩家 1：蓝队还没全死，红队还有 3 存活，未分胜负。
        state.players[1].health = 0
        self.assertTrue(combat.is_player_defeated(1))
        self.assertIsNone(combat.winning_team_id())
        # 杀掉红队的玩家 3：红队全死 → 蓝队（team 1）胜。
        state.players[3].health = 0
        self.assertTrue(combat.is_player_defeated(3))
        self.assertEqual(combat.winning_team_id(), 1)
        # 蓝队两个玩家仍存活，is_alive 都是 True。
        self.assertTrue(state.players[2].is_alive)
        self.assertTrue(state.players[4].is_alive)

    def test_check_game_over_ends_two_versus_two_when_team_wiped(self):
        # 回归：旧 check_game_over 走 winning_player_id，要求"只剩一人"才结束，
        # 因此 2v2 一方全灭、另一方还有两人存活时不会结束。改用 winning_team_id
        # 后，一方全灭即应结束并置 game_over。
        teams = {1: 0, 2: 1, 3: 0, 4: 1}
        state, combat = _make_state([1, 2, 3, 4], teams)
        # 未分胜负：不结束。
        self.assertIsNone(combat.check_game_over())
        self.assertFalse(state.game_over)
        # 红队全灭（1、3 死），蓝队两人存活。
        state.players[1].health = 0
        state.players[3].health = 0
        self.assertTrue(combat.is_player_defeated(1))
        self.assertTrue(combat.is_player_defeated(3))
        # 现在应结束：返回胜方蓝队中某一存活玩家号，且 game_over 置 True。
        winner = combat.check_game_over()
        self.assertIn(winner, (2, 4))
        self.assertTrue(state.game_over)

    def test_alive_opponents_ffa_returns_all_others(self):
        state, combat = _make_state([1, 2, 3])
        # FFA：玩家 1 的敌方是 2 和 3。
        self.assertEqual(sorted(combat.alive_opponents(1)), [2, 3])
        self.assertEqual(sorted(combat.alive_opponents(2)), [1, 3])
        # 玩家 3 死后，玩家 1 的敌方只剩 2。
        state.players[3].is_alive = False
        self.assertEqual(sorted(combat.alive_opponents(1)), [2])

    def test_alive_opponents_team_returns_only_enemies(self):
        teams = {1: 0, 2: 1, 3: 0, 4: 1}
        state, combat = _make_state([1, 2, 3, 4], teams)
        # 红队玩家 1 的敌方是蓝队 2 和 4（不含同队 3）。
        self.assertEqual(sorted(combat.alive_opponents(1)), [2, 4])
        # 蓝队玩家 2 的敌方是红队 1 和 3（不含同队 4）。
        self.assertEqual(sorted(combat.alive_opponents(2)), [1, 3])
        # 红队玩家 3 死后，蓝队玩家 2 的敌方只剩 1。
        state.players[3].is_alive = False
        self.assertEqual(sorted(combat.alive_opponents(2)), [1])

    def test_next_alive_player_skips_dead_in_turn_order(self):
        from card_duel.web.gameplay import _next_alive_player

        state, _combat = _make_state([1, 2, 3])
        # 顺序 [1, 2, 3]：玩家 1 的下一个是 2。
        self.assertEqual(_next_alive_player(state, 1), 2)
        # 玩家 2 死后：玩家 1 的下一个跳过 2 直接到 3。
        state.players[2].is_alive = False
        self.assertEqual(_next_alive_player(state, 1), 3)
        # 玩家 3 也死：玩家 1 的下一个只能是自己（仅剩自己存活）。
        state.players[3].is_alive = False
        self.assertEqual(_next_alive_player(state, 1), 1)

    def test_next_alive_player_wraps_to_round_increment(self):
        from card_duel.web.gameplay import _next_alive_player

        state, _combat = _make_state([1, 2, 3])
        # 玩家 3 是 turn_order 末尾，下一个回到 first_player 1。
        self.assertEqual(_next_alive_player(state, 3), 1)
        # 验证：end_turn 用 next_player == first_player_id 判断 +1 round，
        # 这与原 2 人语义一致（first_player 行动完后才进入新轮）。
        state.players[2].is_alive = False
        # 玩家 1 行动完，下个 alive 是 3（跳过死掉的 2）。
        self.assertEqual(_next_alive_player(state, 1), 3)

    def test_default_target_returns_first_enemy(self):
        from card_duel.web.gameplay import _default_target

        state, _combat = _make_state([1, 2, 3])
        # FFA：玩家 1 的默认目标 = 第一个敌方 = 2。
        self.assertEqual(_default_target(state, 1), 2)
        # 2v2：玩家 1（红队）的默认目标 = 第一个蓝队 = 2。
        teams = {1: 0, 2: 1, 3: 0, 4: 1}
        state2, _combat2 = _make_state([1, 2, 3, 4], teams)
        self.assertEqual(_default_target(state2, 1), 2)
        # 玩家 2 死后，玩家 1 的默认目标跳过 2 到 4。
        state2.players[2].is_alive = False
        self.assertEqual(_default_target(state2, 1), 4)


if __name__ == "__main__":
    unittest.main()
