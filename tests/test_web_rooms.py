"""Authoritative WebSocket room and private-state tests."""

import unittest
from unittest.mock import patch

from card_duel.core.models import CreatureState
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


class RoomManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = RoomManager()
        self.host = _Sender()
        self.guest = _Sender()
        self.host_id = await self.manager.connect(self.host)
        self.guest_id = await self.manager.connect(self.guest)
        self.host.pop("connected")
        self.guest.pop("connected")

    async def create_and_join(self):
        with patch("card_duel.web.rooms.secrets.randbelow", return_value=123456):
            await self.manager.handle(
                self.host_id, {"action": "create_room", "data": {}}
            )
        created = self.host.pop("room_created")
        code = created["data"]["room_code"]
        self.host.pop("room_state")
        await self.manager.handle(
            self.guest_id,
            {"action": "join_room", "data": {"room_code": code}},
        )
        self.guest.pop("room_joined")
        self.host.pop("room_state")
        self.guest.pop("room_state")
        return code

    async def start_warrior_match(self, host_character=1, guest_character=1):
        code = await self.create_and_join()
        for client_id, character_id in (
            (self.host_id, host_character),
            (self.guest_id, guest_character),
        ):
            await self.manager.handle(
                client_id,
                {
                    "action": "select_character",
                    "data": {"character_id": character_id},
                },
            )
            self.host.clear()
            self.guest.clear()
        await self.manager.handle(
            self.host_id,
            {
                "action": "configure_room",
                "data": {
                    "first_player": "host",
                    "seed": 42,
                    "round1_no_damage": False,
                },
            },
        )
        self.host.clear()
        self.guest.clear()
        await self.manager.handle(
            self.host_id, {"action": "set_ready", "data": {"ready": True}}
        )
        self.host.clear()
        self.guest.clear()
        await self.manager.handle(
            self.guest_id, {"action": "set_ready", "data": {"ready": True}}
        )
        self.host.clear()
        self.guest.clear()
        return self.manager.rooms[code]

    async def test_create_and_join_use_six_digit_room_code(self):
        code = await self.create_and_join()

        self.assertEqual(code, "123456")
        self.assertEqual(set(self.manager.rooms[code].players), {1, 2})

    async def test_only_host_can_configure_room(self):
        await self.create_and_join()

        await self.manager.handle(
            self.guest_id,
            {
                "action": "configure_room",
                "data": {"first_player": "guest"},
            },
        )

        error = self.guest.pop("error")
        self.assertEqual(error["data"]["code"], "host_only")

    async def test_both_ready_start_match_with_private_card_views(self):
        code = await self.create_and_join()
        await self.manager.handle(
            self.host_id,
            {"action": "select_character", "data": {"character_id": 1}},
        )
        self.host.pop("room_state")
        self.guest.pop("room_state")
        await self.manager.handle(
            self.guest_id,
            {"action": "select_character", "data": {"character_id": 4}},
        )
        self.host.pop("room_state")
        self.guest.pop("room_state")
        await self.manager.handle(
            self.host_id,
            {
                "action": "configure_room",
                "data": {
                    "first_player": "guest",
                    "seed": 42,
                    "round1_no_damage": True,
                },
            },
        )
        self.host.pop("room_state")
        self.guest.pop("room_state")
        await self.manager.handle(
            self.host_id, {"action": "set_ready", "data": {"ready": True}}
        )
        self.host.pop("room_state")
        self.guest.pop("room_state")
        await self.manager.handle(
            self.guest_id, {"action": "set_ready", "data": {"ready": True}}
        )

        host_state = self.host.pop("match_started")["data"]["state"]
        guest_state = self.guest.pop("match_started")["data"]["state"]
        room = self.manager.rooms[code]
        self.assertEqual(room.status, "playing")
        self.assertEqual(host_state["first_player_id"], 2)
        self.assertEqual(host_state["random_seed"], 42)
        self.assertEqual(host_state["you"]["hand_cards"], room.card_zones[1].hand)
        self.assertEqual(guest_state["you"]["hand_cards"], room.card_zones[2].hand)
        self.assertNotIn("hand_cards", host_state["opponent"])
        self.assertNotIn("hand_cards", guest_state["opponent"])
        self.assertEqual(host_state["card_catalogs"]["1"][1]["name"], "攻")
        self.assertEqual(host_state["players"]["1"]["health"], 30)
        self.assertEqual(host_state["players"]["1"]["max_health"], 30)
        self.assertEqual(guest_state["players"]["2"]["health"], 5)
        self.assertEqual(guest_state["players"]["2"]["max_health"], 5)
        self.assertEqual(
            len(host_state["you"]["card_costs"]),
            len(host_state["you"]["hand_cards"]),
        )
        self.assertEqual(
            len(host_state["you"]["card_discardable"]),
            len(host_state["you"]["hand_cards"]),
        )
        self.assertEqual(
            host_state["you"]["effective_hand_size"],
            len(host_state["you"]["hand_cards"]),
        )
        self.assertNotIn(
            "pending_hand_additions", host_state["players"]["2"]["statuses"]
        )

    async def test_guest_disconnect_returns_lobby_to_one_player(self):
        code = await self.create_and_join()

        await self.manager.disconnect(self.guest_id)

        room_state = self.host.pop("room_state")["data"]["room"]
        self.assertEqual(room_state["status"], "lobby")
        self.assertEqual(len(room_state["players"]), 1)
        self.assertIn(code, self.manager.rooms)

    async def test_guest_can_leave_lobby_and_return_to_entry(self):
        code = await self.create_and_join()

        await self.manager.handle(
            self.guest_id, {"action": "leave_room", "data": {}}
        )

        self.assertEqual(
            self.guest.pop("room_left")["data"]["room_code"], code
        )
        room_state = self.host.pop("room_state")["data"]["room"]
        self.assertEqual([player["player_id"] for player in room_state["players"]], [1])
        self.assertIsNone(self.manager.connections[self.guest_id].room_code)

    async def test_host_can_leave_and_receives_its_own_acknowledgement(self):
        code = await self.create_and_join()

        await self.manager.handle(
            self.host_id, {"action": "leave_room", "data": {}}
        )

        self.assertEqual(self.host.pop("room_left")["data"]["room_code"], code)
        self.assertEqual(self.guest.pop("room_closed")["data"]["room_code"], code)
        self.assertNotIn(code, self.manager.rooms)
        self.assertIsNone(self.manager.connections[self.host_id].room_code)

    async def test_host_disconnect_closes_room_for_guest(self):
        code = await self.create_and_join()

        await self.manager.disconnect(self.host_id)

        closed = self.guest.pop("room_closed")
        self.assertEqual(closed["data"]["room_code"], code)
        self.assertNotIn(code, self.manager.rooms)

    async def test_invalid_action_returns_structured_error(self):
        await self.manager.handle(
            self.host_id, {"action": "definitely_unknown", "data": {}}
        )

        message = self.host.pop("error")
        self.assertEqual(message["data"]["code"], "unknown_action")
        self.assertEqual(message["protocol_version"], 2)

    async def test_match_starts_in_play_phase_with_server_draw_and_energy(self):
        room = await self.start_warrior_match()

        self.assertEqual(room.state.active_player_id, 1)
        self.assertEqual(room.state.current_phase, "出牌阶段")
        self.assertEqual(len(room.card_zones[1].hand), 5)
        self.assertEqual(len(room.card_zones[2].hand), 2)
        self.assertIn(room.state.players[1].energy, (4, 5, 6))
        self.assertIn(room.state.players[2].energy, (4, 5, 6))

    async def test_active_player_can_play_card_and_state_is_broadcast(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [1]
        room.state.players[1].energy = 1

        await self.manager.handle(
            self.host_id,
            {
                "action": "play_card",
                "data": {"source": "hand", "index": 0},
            },
        )

        self.assertEqual(room.state.players[2].health, 28)
        self.assertEqual(room.card_zones[1].hand, [])
        self.assertEqual(room.card_zones[1].discard_pile[-1], 1)
        self.assertEqual(self.host.pop("card_played")["data"]["card_id"], 1)
        self.assertEqual(self.guest.pop("card_played")["data"]["card_id"], 1)
        self.host.pop("state")
        self.guest.pop("state")

    async def test_non_active_player_action_is_rejected(self):
        await self.start_warrior_match()

        await self.manager.handle(
            self.guest_id,
            {"action": "play_card", "data": {"index": 0}},
        )

        error = self.guest.pop("error")
        self.assertEqual(error["data"]["code"], "not_your_turn")

    async def test_discard_then_end_turn_advances_to_opponent(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [1, 2, 3, 4, 5]

        await self.manager.handle(
            self.host_id,
            {"action": "discard_card", "data": {"index": 0}},
        )
        self.assertEqual(room.state.current_phase, "弃牌阶段")
        self.host.clear()
        self.guest.clear()

        await self.manager.handle(self.host_id, {"action": "end_turn", "data": {}})

        self.assertEqual(room.state.active_player_id, 2)
        self.assertEqual(room.state.current_phase, "出牌阶段")
        self.assertEqual(room.state.round_number, 1)
        self.assertEqual(len(room.card_zones[2].hand), 5)
        self.host.pop("state")
        self.guest.pop("state")

    async def test_staged_cards_are_discarded_atomically_from_play_phase(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [1, 2, 3, 4, 5, 6]
        revision = room.revision

        await self.manager.handle(
            self.host_id,
            {"action": "discard_cards", "data": {"indexes": [1, 4]}},
        )

        self.assertEqual(room.state.current_phase, "弃牌阶段")
        self.assertEqual(room.card_zones[1].hand, [1, 3, 4, 6])
        self.assertEqual(room.card_zones[1].discard_pile[-2:], [2, 5])
        self.assertEqual(room.revision, revision + 1)
        state = self.host.pop("state")["data"]["state"]
        self.assertEqual(state["you"]["effective_hand_size"], 4)

    async def test_invalid_staged_discard_rolls_back_the_whole_selection(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [1, 49, 2]
        revision = room.revision

        await self.manager.handle(
            self.host_id,
            {"action": "discard_cards", "data": {"indexes": [0, 1]}},
        )

        error = self.host.pop("error")
        self.assertEqual(error["data"]["code"], "card_not_discardable")
        self.assertEqual(room.card_zones[1].hand, [1, 49, 2])
        self.assertEqual(room.state.current_phase, "出牌阶段")
        self.assertEqual(room.revision, revision)

    async def test_choice_required_rolls_back_then_resolves_card_atomically(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [8]
        revision = room.revision

        await self.manager.handle(
            self.host_id,
            {"action": "play_card", "data": {"index": 0}},
        )

        required = self.host.pop("choice_required")
        choice_id = required["data"]["choice_id"]
        self.assertEqual(required["data"]["choice"]["kind"], "integer")
        self.assertEqual(room.state.players[1].health, 30)
        self.assertEqual(room.card_zones[1].hand, [8])
        self.assertEqual(room.revision, revision)

        await self.manager.handle(
            self.host_id,
            {
                "action": "resolve_choice",
                "data": {"choice_id": choice_id, "value": 3},
            },
        )

        self.assertEqual(room.state.players[1].health, 27)
        self.assertEqual(room.state.players[1].strength, 3)
        self.assertEqual(room.card_zones[1].hand, [])
        self.assertEqual(room.card_zones[1].discard_pile[-1], 8)
        self.assertIsNone(room.pending_action)
        self.host.pop("state")
        self.guest.pop("state")

    async def test_cancel_choice_restores_action_snapshot_and_clears_pending(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [8]
        revision = room.revision

        await self.manager.handle(
            self.host_id,
            {"action": "play_card", "data": {"index": 0}},
        )
        required = self.host.pop("choice_required")

        await self.manager.handle(
            self.host_id,
            {
                "action": "cancel_choice",
                "data": {"choice_id": required["data"]["choice_id"]},
            },
        )

        self.assertEqual(
            self.host.pop("choice_cancelled")["data"]["choice_id"],
            required["data"]["choice_id"],
        )
        self.assertEqual(room.card_zones[1].hand, [8])
        self.assertEqual(room.state.players[1].health, 30)
        self.assertEqual(room.revision, revision)
        self.assertIsNone(room.pending_action)
        state = self.host.pop("state")["data"]["state"]
        self.assertFalse(state["pending_choice"])

    async def test_multi_step_choice_retries_from_clean_snapshot(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [4, 1, 2]
        room.state.players[1].energy = 4

        await self.manager.handle(
            self.host_id,
            {"action": "play_card", "data": {"index": 0}},
        )
        first = self.host.pop("choice_required")
        await self.manager.handle(
            self.host_id,
            {
                "action": "resolve_choice",
                "data": {"choice_id": first["data"]["choice_id"], "value": 2},
            },
        )
        second = self.host.pop("choice_required")
        self.assertEqual(second["data"]["choice"]["kind"], "card_indexes")
        self.assertEqual(room.card_zones[1].hand, [4, 1, 2])

        await self.manager.handle(
            self.host_id,
            {
                "action": "resolve_choice",
                "data": {
                    "choice_id": second["data"]["choice_id"],
                    "value": [1, 2],
                },
            },
        )

        self.assertEqual(room.card_zones[1].hand, [])
        self.assertEqual(room.card_zones[1].discard_pile[-3:], [1, 2, 4])
        self.assertEqual(room.state.players[1].energy, 5)
        self.assertIsNone(room.pending_action)

    async def test_end_turn_rejects_hand_above_limit(self):
        room = await self.start_warrior_match()
        room.card_zones[1].hand[:] = [1, 1, 1, 1, 1]

        await self.manager.handle(self.host_id, {"action": "end_turn", "data": {}})

        error = self.host.pop("error")
        self.assertEqual(error["data"]["code"], "hand_limit")
        self.assertEqual(room.state.current_phase, "出牌阶段")

    async def test_turn_end_choice_is_resumed_before_next_player_turn(self):
        room = await self.start_warrior_match(host_character=4)
        room.card_zones[1].hand.clear()
        room.state.players[1].energy = 1
        room.state.players[1].statuses.hand_creatures.append(
            CreatureState(card_id=23, health=20, owner_id=1)
        )

        await self.manager.handle(self.host_id, {"action": "end_turn", "data": {}})
        required = self.host.pop("choice_required")
        self.assertEqual(required["data"]["choice"]["kind"], "option")
        self.assertEqual(room.state.active_player_id, 1)
        self.assertEqual(room.state.players[1].energy, 1)

        await self.manager.handle(
            self.host_id,
            {
                "action": "resolve_choice",
                "data": {
                    "choice_id": required["data"]["choice_id"],
                    "value": "支付1点能量",
                },
            },
        )

        self.assertEqual(room.state.players[1].health, 5)
        self.assertEqual(room.state.players[1].energy, 0)
        self.assertEqual(room.state.active_player_id, 2)
        self.assertEqual(room.state.current_phase, "出牌阶段")
