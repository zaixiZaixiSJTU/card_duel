"""多人房间座位扩展回归测试。

覆盖本纵切新增的 lobby 阶段多人动作：add_seat / remove_seat / pick_seat /
shuffle_seats / set_team，以及多人房间开局仍被拒绝（回合逻辑尚未多人化）。
2 人正常开局路径由 test_web_rooms.py 覆盖，这里不重复。
"""

import unittest
from unittest.mock import patch

from card_duel.web.protocol import ActionError
from card_duel.web.rooms import RoomManager


class _Sender:
    def __init__(self):
        self.messages = []

    async def send_json(self, data):
        self.messages.append(data)

    def pop(self, event_type=None):
        if event_type is None:
            return self.messages.pop(0)
        for index, message in enumerate(self.messages):
            if message["type"] == event_type:
                return self.messages.pop(index)
        raise AssertionError(f"未收到事件 {event_type}: {self.messages}")

    def clear(self):
        self.messages.clear()


class MultiplayerSeatTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = RoomManager()
        self.host = _Sender()
        self.guest = _Sender()
        self.host_id = await self.manager.connect(self.host)
        self.guest_id = await self.manager.connect(self.guest)
        self.host.pop("connected")
        self.guest.pop("connected")

    async def _create_room(self) -> str:
        with patch("card_duel.web.rooms.secrets.randbelow", return_value=246810):
            await self.manager.handle(
                self.host_id, {"action": "create_room", "data": {}}
            )
        created = self.host.pop("room_created")
        code = created["data"]["room_code"]
        # 不在这里 pop room_state：交给 _room_state 统一处理累积消息，
        # 各测试可按需调用 _room_state 取最新一条并清空队列。
        return code

    async def _pick_seat(self, client_id: str, code: str, seat: int) -> None:
        await self.manager.handle(
            client_id,
            {"action": "pick_seat", "data": {"room_code": code, "seat": seat}},
        )

    def _room_state(self, client_id: str):
        """取最新一条 room_state，并清空累积的 room_state 消息。"""
        sender = self.manager.connections[client_id].sender
        states = [m for m in sender.messages if m["type"] == "room_state"]
        if not states:
            raise AssertionError(f"未收到事件 room_state: {sender.messages}")
        sender.messages = [
            m for m in sender.messages if m["type"] != "room_state"
        ]
        return states[-1]["data"]["room"]

    def _assert_error(self, client_id: str, code: str) -> None:
        """验证 client 收到指定 code 的 error_event。"""
        sender = self.manager.connections[client_id].sender
        errors = [
            m for m in sender.messages
            if m["type"] == "error" and m["data"].get("code") == code
        ]
        if not errors:
            raise AssertionError(
                f"未收到 error[{code}]: {sender.messages}"
            )
        sender.messages = [
            m for m in sender.messages
            if not (m["type"] == "error" and m["data"].get("code") == code)
        ]

    async def test_host_can_add_and_remove_empty_seats(self):
        code = await self._create_room()
        # 加一个座位：3 → 4 → 5。
        for _ in range(2):
            await self.manager.handle(
                self.host_id, {"action": "add_seat", "data": {}}
            )
        room = self.manager.rooms[code]
        self.assertEqual(room.seat_capacity, 4)
        self.assertEqual(
            [seat["seat_id"] for seat in self._room_state(self.host_id)["seats"]],
            [1, 2, 3, 4],
        )
        # 移除座位 4（空座位）。
        await self.manager.handle(
            self.host_id, {"action": "remove_seat", "data": {"seat": 4}}
        )
        room = self.manager.rooms[code]
        self.assertEqual(room.seat_capacity, 3)
        self._room_state(self.host_id)  # 清空 room_state 队列。

    async def test_remove_seat_rejects_occupied_seat(self):
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        await self.manager.handle(
            self.host_id,
            {"action": "remove_seat", "data": {"seat": 2}},
        )
        self._assert_error(self.host_id, "seat_occupied")

    async def test_pick_seat_lets_guest_choose_specific_seat(self):
        code = await self._create_room()
        await self.manager.handle(
            self.host_id, {"action": "add_seat", "data": {}}
        )
        self.host.pop("room_state")
        # 房客直接坐座位 3（跳过座位 2）。
        await self._pick_seat(self.guest_id, code, 3)
        joined = self.guest.pop("room_joined")
        self.assertEqual(joined["data"]["player_id"], 3)
        self.assertEqual(self.manager.connections[self.guest_id].player_id, 3)

    async def test_pick_seat_allows_relocation_within_lobby(self):
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self.host.pop("room_state")
        self.guest.pop("room_state")
        # 房客从座位 2 换到座位 3（需要先加座位）。
        await self.manager.handle(
            self.host_id, {"action": "add_seat", "data": {}}
        )
        self.host.pop("room_state")
        self.guest.pop("room_state")
        await self.manager.handle(
            self.guest_id, {"action": "pick_seat", "data": {"seat": 3}}
        )
        self.guest.pop("room_state")
        self.host.pop("room_state")
        self.assertEqual(self.manager.connections[self.guest_id].player_id, 3)
        self.assertNotIn(2, self.manager.rooms[code].players)

    async def test_pick_seat_swaps_when_room_full(self):
        """满房换座：两座位都占时，pick_seat 应交换双方而非拒绝。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        # 2 人满房：host 在座位 1，guest 在座位 2。
        # 房主想换到座位 2（被 guest 占用）：应执行交换。
        await self.manager.handle(
            self.host_id, {"action": "pick_seat", "data": {"seat": 2}}
        )
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        # 交换后：host 现在在座位 2，guest 在座位 1。
        self.assertEqual(self.manager.connections[self.host_id].player_id, 2)
        self.assertEqual(self.manager.connections[self.guest_id].player_id, 1)
        room = self.manager.rooms[code]
        self.assertEqual(room.players[1].client_id, self.manager.connections[self.guest_id].client_id)
        self.assertEqual(room.players[2].client_id, self.manager.connections[self.host_id].client_id)
        # 各自的座位号仍占满（无空位）。
        self.assertEqual(set(room.players), {1, 2})

    async def test_pick_seat_swap_preserves_character_and_team(self):
        """满房换座交换后，玩家的角色和阵营应跟随玩家走到新座位。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        # 双方都选角色 + 设阵营。
        await self.manager.handle(
            self.host_id,
            {"action": "select_character", "data": {"character_id": 1}},
        )
        await self.manager.handle(
            self.host_id,
            {"action": "set_team", "data": {"team_id": 0}},
        )
        await self.manager.handle(
            self.guest_id,
            {"action": "select_character", "data": {"character_id": 4}},
        )
        await self.manager.handle(
            self.guest_id,
            {"action": "set_team", "data": {"team_id": 1}},
        )
        for clear_id in (self.host_id, self.guest_id):
            self.manager.connections[clear_id].sender.clear()
        # 交换座位：host(1) ↔ guest(2)。
        await self.manager.handle(
            self.host_id, {"action": "pick_seat", "data": {"seat": 2}}
        )
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        room = self.manager.rooms[code]
        # 房主现在在座位 2，他的角色（战士=1）和阵营（红=0）应跟着他。
        self.assertEqual(room.players[2].character_id, 1)
        self.assertEqual(room.players[2].team_id, 0)
        # 房客现在在座位 1，他的角色（蛞蝓猫=4）和阵营（蓝=1）应跟着他。
        self.assertEqual(room.players[1].character_id, 4)
        self.assertEqual(room.players[1].team_id, 1)

    async def test_shuffle_seats_remaps_player_ids(self):
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        original_host_client = self.manager.rooms[code].players[1].client_id
        original_guest_client = self.manager.rooms[code].players[2].client_id
        await self.manager.handle(
            self.host_id, {"action": "shuffle_seats", "data": {}}
        )
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        room = self.manager.rooms[code]
        # shuffle 后：房间内仍恰好两个座位（1 和 2），两个 client_id 仍在
        # 房间里（可能互换座位号也可能保持，2 人 Fisher-Yates 50% 概率交换）。
        self.assertEqual(set(room.players), {1, 2})
        new_clients = {room.players[1].client_id, room.players[2].client_id}
        self.assertEqual(new_clients, {original_host_client, original_guest_client})
        # connection.player_id 必须与房间里的座位号一致。
        host_seat = self.manager.connections[self.host_id].player_id
        guest_seat = self.manager.connections[self.guest_id].player_id
        self.assertIn(host_seat, {1, 2})
        self.assertIn(guest_seat, {1, 2})
        self.assertNotEqual(host_seat, guest_seat)
        self.assertEqual(
            room.players[host_seat].client_id,
            self.manager.connections[self.host_id].client_id,
        )

    async def test_set_team_records_team_id_on_slot(self):
        code = await self._create_room()
        await self.manager.handle(
            self.host_id,
            {"action": "set_team", "data": {"team_id": 1}},
        )
        self.host.pop("room_state")
        slot = self.manager.rooms[code].players[1]
        self.assertEqual(slot.team_id, 1)
        # 设回 null（FFA）。
        await self.manager.handle(
            self.host_id, {"action": "set_team", "data": {"team_id": None}}
        )
        self.host.pop("room_state")
        self.assertIsNone(self.manager.rooms[code].players[1].team_id)

    async def test_three_player_start_now_supported_with_turn_order(self):
        """3 人开局已放开：start_match 不再拒绝，且生成 turn_order/teams。"""
        code = await self._create_room()
        await self.manager.handle(
            self.host_id, {"action": "add_seat", "data": {}}
        )
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        third = _Sender()
        third_id = await self.manager.connect(third)
        third.pop("connected")
        await self._pick_seat(third_id, code, 3)
        third.pop("room_joined")
        for client_id in (self.host_id, self.guest_id, third_id):
            self._room_state(client_id)
        # 三方都选角色并准备。
        for client_id in (self.host_id, self.guest_id, third_id):
            await self.manager.handle(
                client_id,
                {"action": "select_character", "data": {"character_id": 1}},
            )
            for clear_id in (self.host_id, self.guest_id, third_id):
                self.manager.connections[clear_id].sender.clear()
        for client_id in (self.host_id, self.guest_id, third_id):
            await self.manager.handle(
                client_id, {"action": "set_ready", "data": {"ready": True}}
            )
        # 第三方准备触发开局；start_match 不再拒绝 3 人。
        room = self.manager.rooms[code]
        self.assertEqual(room.status, "playing")
        self.assertEqual(sorted(room.state.turn_order), [1, 2, 3])
        self.assertEqual(
            sorted(room.state.players), [1, 2, 3]
        )
        # FFA 默认：所有 team_id 都是 None，每人独立成阵营。
        self.assertTrue(
            all(team is None for team in room.state.player_teams.values())
        )
        # 房间状态推送里也带 match_started 事件（含 state 数据 + 多人字段）。
        for client_id in (self.host_id, self.guest_id, third_id):
            messages = self.manager.connections[client_id].sender.messages
            self.assertTrue(any(m["type"] == "match_started" for m in messages))
        # 第三方是最后准备的玩家，触发开局；其 sender 应同时收到 turn_order。
        third_state = None
        for m in self.manager.connections[third_id].sender.messages:
            if m["type"] == "match_started":
                third_state = m["data"]["state"]
                break
        self.assertIsNotNone(third_state)
        self.assertEqual(sorted(third_state["turn_order"]), [1, 2, 3])
        self.assertEqual(sorted(third_state["character_ids"]), ["1", "2", "3"])

    async def test_guest_leaving_lobby_keeps_room_open(self):
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self.host.pop("room_state")
        self.guest.pop("room_state")
        # 房客主动离开：房间保留，房主仍在座位 1。
        await self.manager.handle(
            self.guest_id, {"action": "leave_room", "data": {}}
        )
        self.guest.pop("room_left")
        self.host.pop("room_state")
        room = self.manager.rooms[code]
        self.assertEqual(room.status, "lobby")
        self.assertIn(1, room.players)
        self.assertNotIn(2, room.players)

    async def test_room_state_payload_includes_seats_and_capacity(self):
        code = await self._create_room()
        state = self._room_state(self.host_id)
        self.assertEqual(state["seat_capacity"], 2)
        seats = state["seats"]
        self.assertEqual(len(seats), 2)
        # 座位 1 已坐（房主），座位 2 空。
        self.assertTrue(seats[0]["occupied"])
        self.assertEqual(seats[0]["seat_id"], 1)
        self.assertFalse(seats[1]["occupied"])
        self.assertEqual(seats[1]["seat_id"], 2)

    # ---- 房主身份跟随 client_id + 新增动作（swap_seats/move_player/set_name）----

    async def _connect_third(self) -> str:
        third = _Sender()
        third_id = await self.manager.connect(third)
        third.pop("connected")
        return third_id

    async def test_room_state_includes_host_seat_and_is_host_flag(self):
        code = await self._create_room()
        state = self._room_state(self.host_id)
        # 房主默认坐座位 1，host_seat 指向座位 1。
        self.assertEqual(state["host_seat"], 1)
        # 座位 1 的 is_host 标记为 True。
        seat1 = next(s for s in state["seats"] if s["seat_id"] == 1)
        self.assertTrue(seat1["is_host"])

    async def test_set_name_updates_display_name(self):
        code = await self._create_room()
        self._room_state(self.host_id)
        await self.manager.handle(
            self.host_id,
            {"action": "set_name", "data": {"display_name": "  小明  "}},
        )
        state = self._room_state(self.host_id)
        seat1 = next(s for s in state["seats"] if s["seat_id"] == 1)
        # 名称被 strip，存为"小明"。
        self.assertEqual(seat1["display_name"], "小明")

    async def test_set_name_rejects_empty(self):
        await self._create_room()
        self._room_state(self.host_id)
        await self.manager.handle(
            self.host_id,
            {"action": "set_name", "data": {"display_name": "   "}},
        )
        self._assert_error(self.host_id, "invalid_name")

    async def test_swap_seats_action_swaps_two_occupied_seats(self):
        code = await self._create_room()
        # 加一个座位，三人就座：1=host, 2=guest, 3=third。
        await self.manager.handle(self.host_id, {"action": "add_seat", "data": {}})
        await self._pick_seat(self.guest_id, code, 2)
        third_id = await self._connect_third()
        await self._pick_seat(third_id, code, 3)
        self._room_state(self.host_id)
        # 房主强制交换座位 2 与座位 3。
        await self.manager.handle(
            self.host_id,
            {"action": "swap_seats", "data": {"seat_a": 2, "seat_b": 3}},
        )
        state = self._room_state(self.host_id)
        seat2 = next(s for s in state["seats"] if s["seat_id"] == 2)
        seat3 = next(s for s in state["seats"] if s["seat_id"] == 3)
        # 交换后：座位 2 持有原 third 的 client，座位 3 持有原 guest 的 client。
        room = self.manager.rooms[code]
        self.assertEqual(room.players[2].client_id, third_id)
        self.assertEqual(room.players[3].client_id, self.guest_id)
        # connection.player_id 同步更新。
        self.assertEqual(self.manager.connections[third_id].player_id, 2)
        self.assertEqual(self.manager.connections[self.guest_id].player_id, 3)

    async def test_swap_seats_rejects_empty_seat(self):
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self._room_state(self.host_id)
        # 座位 3 不存在（默认容量 2），应报 invalid_seat。
        await self.manager.handle(
            self.host_id,
            {"action": "swap_seats", "data": {"seat_a": 1, "seat_b": 3}},
        )
        self._assert_error(self.host_id, "invalid_seat")

    async def test_move_player_relocates_to_empty_seat(self):
        code = await self._create_room()
        await self.manager.handle(self.host_id, {"action": "add_seat", "data": {}})
        await self._pick_seat(self.guest_id, code, 2)
        self._room_state(self.host_id)
        # 房主把座位 2 的玩家迁移到空座位 3。
        await self.manager.handle(
            self.host_id,
            {"action": "move_player", "data": {"from_seat": 2, "to_seat": 3}},
        )
        state = self._room_state(self.host_id)
        seat2 = next(s for s in state["seats"] if s["seat_id"] == 2)
        seat3 = next(s for s in state["seats"] if s["seat_id"] == 3)
        self.assertFalse(seat2["occupied"])
        self.assertTrue(seat3["occupied"])
        room = self.manager.rooms[code]
        self.assertEqual(room.players[3].client_id, self.guest_id)
        self.assertNotIn(2, room.players)
        self.assertEqual(self.manager.connections[self.guest_id].player_id, 3)

    async def test_move_player_rejects_occupied_target(self):
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self._room_state(self.host_id)
        # 目标座位 1 已被房主占用 → seat_taken。
        await self.manager.handle(
            self.host_id,
            {"action": "move_player", "data": {"from_seat": 2, "to_seat": 1}},
        )
        self._assert_error(self.host_id, "seat_taken")

    async def test_non_host_cannot_swap_seats(self):
        code = await self._create_room()
        await self.manager.handle(self.host_id, {"action": "add_seat", "data": {}})
        await self._pick_seat(self.guest_id, code, 2)
        third_id = await self._connect_third()
        await self._pick_seat(third_id, code, 3)
        self._room_state(self.host_id)
        # 客机尝试交换 → host_only。
        await self.manager.handle(
            self.guest_id,
            {"action": "swap_seats", "data": {"seat_a": 1, "seat_b": 3}},
        )
        self._assert_error(self.guest_id, "host_only")

    async def test_host_retains_permission_after_swapping_own_seat(self):
        """房主身份跟随 client_id：房主用 pick_seat 与客机交换后，
        仍能执行房主专属动作（add_seat），不会因 player_id != 1 失权。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self._room_state(self.host_id)
        # 房主主动与座位 2 交换：房主现在在座位 2。
        await self.manager.handle(
            self.host_id, {"action": "pick_seat", "data": {"seat": 2}}
        )
        state = self._room_state(self.host_id)
        # host_seat 跟随到座位 2，房主位仍在房主手里。
        self.assertEqual(state["host_seat"], 2)
        room = self.manager.rooms[code]
        self.assertTrue(room.is_host(self.manager.connections[self.host_id]))
        # 房主在座位 2 仍能加座位（房主权限未丢）。
        await self.manager.handle(self.host_id, {"action": "add_seat", "data": {}})
        self._room_state(self.host_id)
        self.assertEqual(room.seat_capacity, 3)

    async def test_room_state_includes_your_player_id(self):
        """room_state 事件带 your_player_id，房主换座后该字段跟随更新，
        前端据此同步本地 playerId（修复 isHost/isMine 脱节 bug）。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self.host.clear()
        # 触发一次 room_state 推送（pick_seat 自身座位无操作，用 set_team 触发）。
        await self.manager.handle(
            self.host_id, {"action": "set_team", "data": {"team_id": 0}}
        )
        # host.messages 应包含 room_state 事件，data 里带 your_player_id=1。
        room_state_evts = [m for m in self.host.messages if m.get("type") == "room_state"]
        self.assertTrue(room_state_evts, "未收到 room_state 事件")
        self.assertEqual(room_state_evts[-1]["data"].get("your_player_id"), 1)
        # guest 也应收到 room_state，your_player_id=2。
        guest_state_evts = [m for m in self.guest.messages if m.get("type") == "room_state"]
        self.assertTrue(guest_state_evts, "guest 未收到 room_state 事件")
        self.assertEqual(guest_state_evts[-1]["data"].get("your_player_id"), 2)

    async def test_your_player_id_updates_after_pick_seat_swap(self):
        """房主用 pick_seat 与客机交换座位后，room_state 推送的 your_player_id
        应跟随到新座位号（房主 1→2，客机 2→1），前端不会卡在旧 playerId。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        self.host.clear()
        self.guest.clear()
        # 房主与座位 2 交换：房主现在在座位 2。
        await self.manager.handle(
            self.host_id, {"action": "pick_seat", "data": {"seat": 2}}
        )
        host_state = [m for m in self.host.messages if m.get("type") == "room_state"]
        guest_state = [m for m in self.guest.messages if m.get("type") == "room_state"]
        self.assertTrue(host_state, "host 未收到换座后的 room_state")
        self.assertEqual(host_state[-1]["data"].get("your_player_id"), 2)
        self.assertEqual(guest_state[-1]["data"].get("your_player_id"), 1)

    async def test_pick_seat_carries_display_name_when_joining(self):
        """未入房玩家用 pick_seat 直接选座加入时，display_name 应带到座位上
        （修复 _pick_seat 未入房分支丢失 display_name 的 bug）。"""
        code = await self._create_room()
        await self.manager.handle(
            self.guest_id,
            {
                "action": "pick_seat",
                "data": {"room_code": code, "seat": 2, "display_name": "客人小红"},
            },
        )
        self.guest.pop("room_joined")
        state = self._room_state(self.guest_id)
        seat2 = next(s for s in state["seats"] if s["seat_id"] == 2)
        self.assertEqual(seat2["display_name"], "客人小红")

    async def test_shuffle_seats_preserves_character_and_team(self):
        """shuffle_seats 重排后玩家角色/阵营应跟随玩家，
        不丢失（修复旧实现重建 PlayerSlot 丢数据的问题）。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        # 房主与客机各选角色 1，并各设阵营。
        await self.manager.handle(
            self.host_id,
            {"action": "select_character", "data": {"character_id": 1}},
        )
        await self.manager.handle(
            self.guest_id,
            {"action": "select_character", "data": {"character_id": 1}},
        )
        await self.manager.handle(
            self.guest_id,
            {"action": "set_team", "data": {"team_id": 1}},
        )
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        guest_char_before = self.manager.rooms[code].players[2].character_id
        guest_team_before = self.manager.rooms[code].players[2].team_id
        # 随机重排。
        await self.manager.handle(self.host_id, {"action": "shuffle_seats", "data": {}})
        self._room_state(self.host_id)
        # 找到 guest 现在所在的座位，验证数据跟随。
        room = self.manager.rooms[code]
        guest_seat_now = next(
            seat for seat, slot in room.players.items()
            if slot.client_id == self.guest_id
        )
        self.assertEqual(
            room.players[guest_seat_now].character_id, guest_char_before
        )
        self.assertEqual(
            room.players[guest_seat_now].team_id, guest_team_before
        )

    async def test_start_match_rejects_everyone_same_team(self):
        """阵营多样性校验：全员同一非空阵营（都选红队）应拒绝开局；
        FFA（全员不选阵营）仍允许，由 3 人用例覆盖。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        for client_id in (self.host_id, self.guest_id):
            await self.manager.handle(
                client_id,
                {"action": "select_character", "data": {"character_id": 1}},
            )
            await self.manager.handle(
                client_id, {"action": "set_team", "data": {"team_id": 0}}
            )
            self._room_state(client_id)
        # host 先准备。
        await self.manager.handle(
            self.host_id, {"action": "set_ready", "data": {"ready": True}}
        )
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        # guest 准备触发开局：全员红队 → team_diversity 拒绝，房间留在 lobby。
        await self.manager.handle(
            self.guest_id, {"action": "set_ready", "data": {"ready": True}}
        )
        self._assert_error(self.guest_id, "team_diversity")
        room = self.manager.rooms[code]
        self.assertEqual(room.status, "lobby")
        self.assertIsNone(room.state)

    async def test_return_to_room_resets_to_lobby_after_game_over(self):
        """对局结束后 return_to_room 应清算对局、切回 lobby，
        保留座位/角色/阵营，仅重置准备状态。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        for client_id in (self.host_id, self.guest_id):
            await self.manager.handle(
                client_id,
                {"action": "select_character", "data": {"character_id": 1}},
            )
            await self.manager.handle(
                client_id,
                {
                    "action": "set_team",
                    "data": {"team_id": 0 if client_id is self.host_id else 1},
                },
            )
            self._room_state(client_id)
        for client_id in (self.host_id, self.guest_id):
            await self.manager.handle(
                client_id, {"action": "set_ready", "data": {"ready": True}}
            )
        room = self.manager.rooms[code]
        self.assertEqual(room.status, "playing")
        # 模拟对局结束（避免驱动完整战斗流程）。
        assert room.state is not None
        room.state.game_over = True
        # 回到房间。
        await self.manager.handle(
            self.host_id, {"action": "return_to_room", "data": {}}
        )
        self._room_state(self.host_id)
        self._room_state(self.guest_id)
        room = self.manager.rooms[code]
        self.assertEqual(room.status, "lobby")
        self.assertIsNone(room.state)
        self.assertIsNone(room.combat)
        self.assertEqual(room.card_zones, {})
        # 座位/角色/阵营保留，准备状态被重置。
        self.assertEqual(set(room.players), {1, 2})
        self.assertEqual(room.players[1].character_id, 1)
        self.assertEqual(room.players[2].character_id, 1)
        self.assertEqual(room.players[1].team_id, 0)
        self.assertEqual(room.players[2].team_id, 1)
        self.assertFalse(room.players[1].ready)
        self.assertFalse(room.players[2].ready)

    async def test_return_to_room_rejected_before_game_over(self):
        """对局未结束时 return_to_room 应被拒绝（game_not_over）。"""
        code = await self._create_room()
        await self._pick_seat(self.guest_id, code, 2)
        self.guest.pop("room_joined")
        for client_id in (self.host_id, self.guest_id):
            await self.manager.handle(
                client_id,
                {"action": "select_character", "data": {"character_id": 1}},
            )
            await self.manager.handle(
                client_id,
                {
                    "action": "set_team",
                    "data": {"team_id": 0 if client_id is self.host_id else 1},
                },
            )
            self._room_state(client_id)
        for client_id in (self.host_id, self.guest_id):
            await self.manager.handle(
                client_id, {"action": "set_ready", "data": {"ready": True}}
            )
        room = self.manager.rooms[code]
        assert room.state is not None and not room.state.game_over
        await self.manager.handle(
            self.host_id, {"action": "return_to_room", "data": {}}
        )
        self._assert_error(self.host_id, "game_not_over")
        self.assertEqual(self.manager.rooms[code].status, "playing")


if __name__ == "__main__":
    unittest.main()
