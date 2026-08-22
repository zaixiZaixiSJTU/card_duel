"""In-memory authoritative rooms shared by WebSocket connections."""

from __future__ import annotations

import asyncio
import copy
import random
import secrets
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Protocol
from uuid import uuid4

from card_duel.application.combat import CombatEngine
from card_duel.application.turns import HAND_LIMIT, can_discard, effective_hand_size
from card_duel.cards.catalog import DEFAULT_REGISTRY
from card_duel.cards.registry import CardRegistry
from card_duel.core.models import CharacterState, GameState
from card_duel.core.rules import build_shuffled_deck
from card_duel.web.gameplay import (
    ActionLog,
    ChoiceRequired,
    PendingAction,
    SubmittedChoiceProvider,
    begin_turn,
    discard_card,
    discard_cards,
    end_turn,
    play_card,
)
from card_duel.web.protocol import (
    MAX_CHAT_LENGTH,
    ActionError,
    ClientAction,
    error_event,
    event,
)


class JsonSender(Protocol):
    async def send_json(self, data: object) -> None: ...


@dataclass(slots=True)
class CardZone:
    """Private card locations owned by one player on the authoritative server."""

    hand: list[int] = field(default_factory=list)
    draw_pile: list[int] = field(default_factory=list)
    discard_pile: list[int] = field(default_factory=list)


@dataclass(slots=True)
class PlayerSlot:
    player_id: int
    client_id: str
    character_id: int | None = None
    ready: bool = False


@dataclass(slots=True)
class RoomSettings:
    first_player: str = "random"
    seed: int | None = None
    round1_no_damage: bool = True


@dataclass(slots=True)
class Room:
    code: str
    players: dict[int, PlayerSlot] = field(default_factory=dict)
    settings: RoomSettings = field(default_factory=RoomSettings)
    status: str = "lobby"
    state: GameState | None = None
    combat: CombatEngine | None = None
    card_zones: dict[int, CardZone] = field(default_factory=dict)
    revision: int = 0
    pending_action: PendingAction | None = None

    def start_match(self, registry: CardRegistry) -> ActionLog:
        if self.status != "lobby":
            raise ActionError("match_started", "对局已经开始")
        if set(self.players) != {1, 2}:
            raise ActionError("room_not_ready", "需要两名玩家才能开始")
        if any(slot.character_id is None for slot in self.players.values()):
            raise ActionError("character_required", "双方必须先选择角色")
        if not all(slot.ready for slot in self.players.values()):
            raise ActionError("room_not_ready", "双方尚未准备")

        seed = self.settings.seed
        if seed is None:
            seed = secrets.randbelow(2**31)
        if self.settings.first_player == "host":
            first_player_id = 1
        elif self.settings.first_player == "guest":
            first_player_id = 2
        else:
            first_player_id = secrets.choice((1, 2))

        character_ids = {
            player_id: slot.character_id for player_id, slot in self.players.items()
        }
        state = GameState(
            character_ids=character_ids,
            random_seed=seed,
            first_player_id=first_player_id,
            round1_no_damage=self.settings.round1_no_damage,
            round_number=1,
            active_player_id=first_player_id,
        )
        combat = CombatEngine(state, registry)
        combat.initialize_players()

        zones: dict[int, CardZone] = {}
        for player_id, character_id in character_ids.items():
            if character_id is None:  # Narrowed by validation above.
                raise RuntimeError("角色状态在开局时意外丢失")
            deck_counts = registry.get_deck_counts(character_id)
            last_card_id = max(deck_counts, default=0)
            deck = build_shuffled_deck(
                1,
                last_card_id,
                deck_counts,
                random_seed=seed,
            )
            zones[player_id] = CardZone(hand=deck[:2], draw_pile=deck[2:])

        self.settings.seed = seed
        self.state = state
        self.combat = combat
        self.card_zones = zones
        self.status = "playing"
        log = begin_turn(self, first_player_id, registry)
        self.revision += 1
        return log


@dataclass(slots=True)
class ClientConnection:
    client_id: str
    sender: JsonSender
    room_code: str | None = None
    player_id: int | None = None


Delivery = tuple[ClientConnection, dict[str, object]]


class RoomManager:
    """Own rooms, validate client actions, and fan out personalized snapshots."""

    def __init__(self, registry: CardRegistry = DEFAULT_REGISTRY) -> None:
        self.registry = registry
        self.rooms: dict[str, Room] = {}
        self.connections: dict[str, ClientConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(self, sender: JsonSender) -> str:
        client_id = uuid4().hex
        connection = ClientConnection(client_id=client_id, sender=sender)
        async with self._lock:
            self.connections[client_id] = connection
        await self._deliver(
            [
                (
                    connection,
                    event("connected", client_id=client_id),
                )
            ]
        )
        return client_id

    async def handle(self, client_id: str, payload: object) -> None:
        try:
            action = ClientAction.parse(payload)
            async with self._lock:
                connection = self._connection(client_id)
                deliveries = self._handle_locked(connection, action)
        except ActionError as exc:
            connection = self.connections.get(client_id)
            deliveries = [] if connection is None else [(connection, error_event(exc))]
        await self._deliver(deliveries)

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            connection = self.connections.pop(client_id, None)
            if connection is None:
                return
            deliveries = self._leave_locked(connection, disconnected=True)
        await self._deliver(deliveries)

    def _handle_locked(
        self, connection: ClientConnection, action: ClientAction
    ) -> list[Delivery]:
        handlers = {
            "create_room": self._create_room,
            "join_room": self._join_room,
            "select_character": self._select_character,
            "configure_room": self._configure_room,
            "set_ready": self._set_ready,
            "chat": self._chat,
            "request_state": self._request_state,
            "leave_room": self._leave_room,
            "play_card": self._play_card,
            "discard_card": self._discard_card,
            "discard_cards": self._discard_cards,
            "end_turn": self._end_turn,
            "resolve_choice": self._resolve_choice,
            "cancel_choice": self._cancel_choice,
        }
        room = (
            self.rooms.get(connection.room_code)
            if connection.room_code is not None
            else None
        )
        if (
            room is not None
            and room.pending_action is not None
            and action.action
            not in {"resolve_choice", "cancel_choice", "chat", "request_state"}
        ):
            raise ActionError("choice_pending", "请先完成或取消当前卡牌选择")
        handler = handlers.get(action.action)
        if handler is None:
            raise ActionError("unknown_action", f"未知 action: {action.action}")
        return handler(connection, action.data)

    def _create_room(
        self, connection: ClientConnection, _data: dict[str, Any]
    ) -> list[Delivery]:
        self._require_outside_room(connection)
        code = self._new_room_code()
        room = Room(code=code)
        room.players[1] = PlayerSlot(player_id=1, client_id=connection.client_id)
        self.rooms[code] = room
        connection.room_code = code
        connection.player_id = 1
        return [
            (connection, event("room_created", room_code=code, player_id=1)),
            *self._room_state_deliveries(room),
        ]

    def _join_room(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        self._require_outside_room(connection)
        code = str(data.get("room_code", "")).strip()
        room = self.rooms.get(code)
        if room is None:
            raise ActionError("room_not_found", "房间不存在")
        if room.status != "lobby":
            raise ActionError("match_started", "该房间的对局已经开始")
        if len(room.players) >= 2:
            raise ActionError("room_full", "房间已满")
        room.players[2] = PlayerSlot(player_id=2, client_id=connection.client_id)
        connection.room_code = code
        connection.player_id = 2
        return [
            (connection, event("room_joined", room_code=code, player_id=2)),
            *self._room_state_deliveries(room),
        ]

    def _select_character(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, slot = self._require_lobby_player(connection)
        character_id = _required_int(data, "character_id")
        if character_id not in self.registry.character_ids:
            raise ActionError("invalid_character", "角色不存在")
        slot.character_id = character_id
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _configure_room(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_lobby_player(connection)
        if connection.player_id != 1:
            raise ActionError("host_only", "只有房主可以修改房间规则")
        first_player = data.get("first_player", room.settings.first_player)
        if first_player not in {"host", "guest", "random"}:
            raise ActionError(
                "invalid_settings", "first_player 必须是 host、guest 或 random"
            )
        seed_value = data.get("seed", room.settings.seed)
        if seed_value is not None:
            if isinstance(seed_value, bool) or not isinstance(seed_value, int):
                raise ActionError("invalid_settings", "seed 必须是整数或 null")
            if not 0 <= seed_value < 2**31:
                raise ActionError("invalid_settings", "seed 超出允许范围")
        no_damage = data.get("round1_no_damage", room.settings.round1_no_damage)
        if not isinstance(no_damage, bool):
            raise ActionError("invalid_settings", "round1_no_damage 必须是布尔值")
        room.settings = RoomSettings(
            first_player=first_player,
            seed=seed_value,
            round1_no_damage=no_damage,
        )
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _set_ready(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, slot = self._require_lobby_player(connection)
        ready = data.get("ready")
        if not isinstance(ready, bool):
            raise ActionError("invalid_ready", "ready 必须是布尔值")
        if ready and slot.character_id is None:
            raise ActionError("character_required", "请先选择角色")
        slot.ready = ready
        if len(room.players) == 2 and all(item.ready for item in room.players.values()):
            log = room.start_match(self.registry)
            return [
                *self._match_started_deliveries(room),
                *self._log_deliveries(room, log),
            ]
        return self._room_state_deliveries(room)

    def _chat(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_room_player(connection)
        raw_message = data.get("message")
        if not isinstance(raw_message, str):
            raise ActionError("invalid_chat", "message 必须是字符串")
        message = " ".join(raw_message.strip().splitlines())[:MAX_CHAT_LENGTH]
        if not message:
            raise ActionError("invalid_chat", "聊天内容不能为空")
        return [
            (
                target,
                event("chat", player_id=connection.player_id, message=message),
            )
            for target in self._room_connections(room)
        ]

    def _request_state(
        self, connection: ClientConnection, _data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_room_player(connection)
        if room.status == "playing":
            return [
                (connection, event("state", state=self._match_view(room, connection)))
            ]
        return [(connection, event("room_state", room=self._room_view(room)))]

    def _leave_room(
        self, connection: ClientConnection, _data: dict[str, Any]
    ) -> list[Delivery]:
        return self._leave_locked(connection, disconnected=False)

    def _play_card(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        return self._run_match_action(connection, "play_card", data, [])

    def _discard_card(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        return self._run_discard_action(connection, data, multiple=False)

    def _discard_cards(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        return self._run_discard_action(connection, data, multiple=True)

    def _run_discard_action(
        self,
        connection: ClientConnection,
        data: dict[str, Any],
        *,
        multiple: bool,
    ) -> list[Delivery]:
        room, _slot = self._require_playing_player(connection)
        snapshot = self._snapshot(room)
        try:
            handler = discard_cards if multiple else discard_card
            log = handler(room, connection.player_id, data)
        except Exception:
            self._restore(room, snapshot)
            raise
        room.revision += 1
        return [
            *self._log_deliveries(room, log),
            *self._state_deliveries(room),
        ]

    def _end_turn(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        if data:
            raise ActionError("invalid_message", "end_turn 的 data 必须为空")
        return self._run_match_action(connection, "end_turn", data, [])

    def _resolve_choice(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_playing_player(connection)
        pending = room.pending_action
        if pending is None:
            raise ActionError("no_choice_pending", "当前没有待处理选择")
        if pending.player_id != connection.player_id:
            raise ActionError("not_your_choice", "该选择属于另一名玩家")
        if data.get("choice_id") != pending.choice_id:
            raise ActionError("stale_choice", "选择编号已失效")
        if "value" not in data:
            raise ActionError("invalid_choice", "选择消息缺少 value")
        return self._run_match_action(
            connection,
            pending.action,
            pending.data,
            [*pending.answers, data["value"]],
        )

    def _cancel_choice(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_playing_player(connection)
        pending = room.pending_action
        if pending is None:
            raise ActionError("no_choice_pending", "当前没有待处理选择")
        if pending.player_id != connection.player_id:
            raise ActionError("not_your_choice", "该选择属于另一名玩家")
        choice_id = data.get("choice_id")
        if choice_id is not None and choice_id != pending.choice_id:
            raise ActionError("stale_choice", "选择编号已失效")
        room.pending_action = None
        return [
            (connection, event("choice_cancelled", choice_id=pending.choice_id)),
            *self._state_deliveries(room),
        ]

    def _run_match_action(
        self,
        connection: ClientConnection,
        action: str,
        data: dict[str, Any],
        answers: list[object],
    ) -> list[Delivery]:
        room, _slot = self._require_playing_player(connection)
        player_id = connection.player_id
        if player_id is None:
            raise ActionError("not_in_room", "当前不在房间中")
        snapshot = self._snapshot(room)
        provider = SubmittedChoiceProvider(answers)
        try:
            if action == "play_card":
                log = play_card(room, player_id, data, self.registry, provider)
            elif action == "end_turn":
                log = end_turn(room, player_id, self.registry, provider)
            else:
                raise ActionError("unknown_action", f"未知对局动作: {action}")
        except ChoiceRequired as required:
            self._restore(room, snapshot)
            choice_id = uuid4().hex
            room.pending_action = PendingAction(
                player_id=player_id,
                action=action,
                data=dict(data),
                answers=list(answers),
                choice_id=choice_id,
            )
            return [
                (
                    connection,
                    event(
                        "choice_required",
                        choice_id=choice_id,
                        choice=required.choice.payload(),
                    ),
                )
            ]
        except Exception:
            self._restore(room, snapshot)
            raise

        room.pending_action = None
        room.revision += 1
        return [
            *self._log_deliveries(room, log),
            *self._state_deliveries(room),
        ]

    def _leave_locked(
        self, connection: ClientConnection, *, disconnected: bool
    ) -> list[Delivery]:
        if connection.room_code is None or connection.player_id is None:
            if disconnected:
                return []
            raise ActionError("not_in_room", "当前不在房间中")
        room = self.rooms.get(connection.room_code)
        player_id = connection.player_id
        room_code = connection.room_code
        connection.room_code = None
        connection.player_id = None
        left_delivery = (
            []
            if disconnected
            else [(connection, event("room_left", room_code=room_code))]
        )
        if room is None:
            return left_delivery

        room.players.pop(player_id, None)
        if player_id == 1 or room.status == "playing":
            self.rooms.pop(room.code, None)
            deliveries = []
            for target in self._room_connections(room):
                target.room_code = None
                target.player_id = None
                deliveries.append(
                    (
                        target,
                        event(
                            "room_closed",
                            room_code=room.code,
                            reason="player_disconnected"
                            if disconnected
                            else "player_left",
                        ),
                    )
                )
            return [*left_delivery, *deliveries]

        self._reset_readiness(room)
        return [*left_delivery, *self._room_state_deliveries(room)]

    def _new_room_code(self) -> str:
        for _ in range(100):
            code = f"{secrets.randbelow(1_000_000):06d}"
            if code not in self.rooms:
                return code
        raise RuntimeError("暂时无法生成唯一房间号")

    def _connection(self, client_id: str) -> ClientConnection:
        try:
            return self.connections[client_id]
        except KeyError as exc:
            raise ActionError("not_connected", "连接不存在") from exc

    def _require_outside_room(self, connection: ClientConnection) -> None:
        if connection.room_code is not None:
            raise ActionError("already_in_room", "请先离开当前房间")

    def _require_room_player(
        self, connection: ClientConnection
    ) -> tuple[Room, PlayerSlot]:
        if connection.room_code is None or connection.player_id is None:
            raise ActionError("not_in_room", "当前不在房间中")
        room = self.rooms.get(connection.room_code)
        if room is None:
            raise ActionError("room_not_found", "房间不存在")
        slot = room.players.get(connection.player_id)
        if slot is None or slot.client_id != connection.client_id:
            raise ActionError("not_in_room", "当前不在房间中")
        return room, slot

    def _require_lobby_player(
        self, connection: ClientConnection
    ) -> tuple[Room, PlayerSlot]:
        room, slot = self._require_room_player(connection)
        if room.status != "lobby":
            raise ActionError("match_started", "对局已经开始")
        return room, slot

    def _require_playing_player(
        self, connection: ClientConnection
    ) -> tuple[Room, PlayerSlot]:
        room, slot = self._require_room_player(connection)
        if room.status != "playing":
            raise ActionError("match_not_started", "对局尚未开始")
        return room, slot

    def _reset_readiness(self, room: Room) -> None:
        for slot in room.players.values():
            slot.ready = False

    def _room_connections(self, room: Room) -> list[ClientConnection]:
        return [
            connection
            for slot in room.players.values()
            if (connection := self.connections.get(slot.client_id)) is not None
        ]

    def _room_state_deliveries(self, room: Room) -> list[Delivery]:
        room_view = self._room_view(room)
        return [
            (connection, event("room_state", room=room_view))
            for connection in self._room_connections(room)
        ]

    def _match_started_deliveries(self, room: Room) -> list[Delivery]:
        return [
            (
                connection,
                event("match_started", state=self._match_view(room, connection)),
            )
            for connection in self._room_connections(room)
        ]

    def _state_deliveries(self, room: Room) -> list[Delivery]:
        return [
            (
                connection,
                event("state", state=self._match_view(room, connection)),
            )
            for connection in self._room_connections(room)
        ]

    def _log_deliveries(self, room: Room, log: ActionLog) -> list[Delivery]:
        deliveries = [
            (target, event("announcement", message=message))
            for message in log.announcements
            for target in self._room_connections(room)
        ]
        for player_id, message in log.private_announcements:
            slot = room.players.get(player_id)
            target = self.connections.get(slot.client_id) if slot is not None else None
            if target is not None:
                deliveries.append(
                    (target, event("private_announcement", message=message))
                )
        if log.played_card is not None:
            player_id, character_id, card_id = log.played_card
            deliveries.extend(
                (
                    target,
                    event(
                        "card_played",
                        player_id=player_id,
                        character_id=character_id,
                        card_id=card_id,
                    ),
                )
                for target in self._room_connections(room)
            )
        return deliveries

    def _snapshot(self, room: Room):
        return (
            copy.deepcopy(room.state),
            copy.deepcopy(room.card_zones),
            room.revision,
            random.getstate(),
        )

    def _restore(self, room: Room, snapshot) -> None:
        state, card_zones, revision, random_state = snapshot
        room.state = state
        room.card_zones = card_zones
        room.revision = revision
        random.setstate(random_state)
        if state is not None:
            room.combat = CombatEngine(state, self.registry)

    def _room_view(self, room: Room) -> dict[str, object]:
        characters = [
            {
                "character_id": character_id,
                "name": self.registry.get_character(character_id).name,
            }
            for character_id in self.registry.character_ids
        ]
        return {
            "room_code": room.code,
            "status": room.status,
            "settings": asdict(room.settings),
            "players": [
                {
                    "player_id": slot.player_id,
                    "character_id": slot.character_id,
                    "ready": slot.ready,
                }
                for slot in room.players.values()
            ],
            "characters": characters,
        }

    def _match_view(
        self, room: Room, connection: ClientConnection
    ) -> dict[str, object]:
        state = room.state
        player_id = connection.player_id
        if state is None or player_id is None:
            raise RuntimeError("对局状态尚未初始化")
        opponent_id = 2 if player_id == 1 else 1
        own_zone = room.card_zones[player_id]
        opponent_zone = room.card_zones[opponent_id]
        catalogs = {
            str(character_id): [
                {
                    "card_id": definition.card_id,
                    "name": definition.name,
                    "card_type": definition.card_type,
                    "cost": definition.cost,
                    "description": definition.description,
                    "exhausted": definition.exhausted,
                }
                for definition in self.registry.get_catalog(character_id)
            ]
            for character_id in set(state.character_ids.values())
            if character_id is not None
        }
        return {
            "room_code": room.code,
            "revision": room.revision,
            "player_id": player_id,
            "character_ids": {
                str(key): value for key, value in state.character_ids.items()
            },
            "players": {
                str(key): _public_player_payload(value)
                for key, value in state.players.items()
            },
            "card_catalogs": catalogs,
            "random_seed": state.random_seed,
            "first_player_id": state.first_player_id,
            "round1_no_damage": state.round1_no_damage,
            "round_number": state.round_number,
            "active_player_id": state.active_player_id,
            "current_phase": state.current_phase,
            "game_over": state.game_over,
            "hand_limit": HAND_LIMIT,
            "pending_choice": room.pending_action is not None,
            "you": {
                "hand_cards": list(own_zone.hand),
                "card_costs": self._card_costs(state, player_id, own_zone.hand),
                "card_discardable": [
                    can_discard(state, player_id, card_id)
                    for card_id in own_zone.hand
                ],
                "effective_hand_size": effective_hand_size(
                    state, player_id, own_zone.hand
                ),
                "draw_count": len(own_zone.draw_pile),
                "discard_count": len(own_zone.discard_pile),
            },
            "opponent": {
                "hand_count": len(opponent_zone.hand),
                "draw_count": len(opponent_zone.draw_pile),
                "discard_count": len(opponent_zone.discard_pile),
            },
        }

    def _card_costs(
        self, state: GameState, player_id: int, hand: list[int]
    ) -> list[int | None]:
        character_id = state.character_ids[player_id]
        if character_id is None:
            return [None for _card_id in hand]
        if character_id == 4:
            from card_duel.cards.slugcat.effects import effective_cost

            return [effective_cost(state, player_id, card_id) for card_id in hand]
        return [
            self.registry.get_card(character_id, card_id).cost for card_id in hand
        ]

    async def _deliver(self, deliveries: list[Delivery]) -> None:
        for connection, payload in deliveries:
            try:
                await connection.sender.send_json(payload)
            except Exception:
                # The ASGI endpoint observes the disconnect and performs cleanup.
                continue


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActionError("invalid_message", f"{key} 必须是整数")
    return value


def _public_player_payload(player: CharacterState) -> dict[str, object]:
    payload: dict[str, object] = {}
    for item in fields(player):
        if item.name == "statuses":
            statuses = getattr(player, item.name)
            status_payload = asdict(statuses)
            for private_name in (
                "pending_hand_additions",
                "pending_hand_removals",
                "pending_draw_returns",
            ):
                status_payload.pop(private_name, None)
            payload[item.name] = _json_value(status_payload)
        else:
            payload[item.name] = _json_value(getattr(player, item.name))
    payload["defence"] = player.defence
    return payload


def _json_value(value: object) -> object:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
