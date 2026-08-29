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
from card_duel.application.turns import (
    can_discard,
    effective_hand_size,
    hand_limit_for,
)
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
    MAX_NAME_LENGTH,
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
    # player_id 在多人扩展中即"座位号 seat_id"（1..N），同时承担协议层
    # 玩家标识。user_id 是持久玩家身份，目前用 client_id 占位，未来从认证
    # 系统取；display_name 用于公告和聊天，避免再写"玩家{player_id}"。
    player_id: int
    client_id: str
    user_id: str = ""
    display_name: str = ""
    character_id: int | None = None
    ready: bool = False
    team_id: int | None = None
    deck_counts: dict[int, dict[int, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.user_id:
            self.user_id = self.client_id
        if not self.display_name:
            self.display_name = f"玩家{self.player_id}"


@dataclass(slots=True)
class RoomSettings:
    # 兼容字段：旧客户端仍可发送 first_player="host"/"guest"/"random"。
    # 新客户端改用 first_seat（座位号）+ random_seat_order（开局时随机
    # 打乱座位顺序，即"随机顺序"按钮）。
    first_player: str = "random"
    first_seat: int | None = None
    random_seat_order: bool = False
    seed: int | None = None
    round1_no_damage: bool = True


@dataclass(slots=True)
class Room:
    code: str
    players: dict[int, PlayerSlot] = field(default_factory=dict)
    seat_capacity: int = 2
    # 房主身份跟随 client_id（创建房间的连接），不跟随座位号。
    # 这样房主用 pick_seat 换到其他座位后仍保留房主权限；房主也能被
    # swap_seats / move_player 调整位置而不丢失权限。
    host_client_id: str = ""
    settings: RoomSettings = field(default_factory=RoomSettings)
    status: str = "lobby"
    state: GameState | None = None
    combat: CombatEngine | None = None
    card_zones: dict[int, CardZone] = field(default_factory=dict)
    revision: int = 0
    pending_action: PendingAction | None = None

    def is_host(self, connection: "ClientConnection") -> bool:
        """房主判断：以创建房间的 client_id 为准，不依赖座位号。"""
        return connection.client_id == self.host_client_id

    def start_match(self, registry: CardRegistry) -> ActionLog:
        if self.status != "lobby":
            raise ActionError("match_started", "对局已经开始")
        # 多人扩展：放开 2 人限制，支持 2..N 人开局。
        # 回合轮转按 turn_order 跳过死亡玩家，胜负按"敌方全死算赢"。
        occupied_seats = sorted(self.players)
        if len(occupied_seats) < 2:
            raise ActionError("room_not_ready", "需要至少两名玩家才能开始")
        if any(slot.character_id is None for slot in self.players.values()):
            raise ActionError("character_required", "双方必须先选择角色")
        if not all(slot.ready for slot in self.players.values()):
            raise ActionError("room_not_ready", "双方尚未准备")
        # 阵营多样性校验：避免全员同色无法交战。
        # FFA（team_id 全为 None）允许——所有人互为敌方；全员同一非空
        # 阵营时拒绝（否则没有可攻击目标，对局无法进行）。
        team_ids = {slot.team_id for slot in self.players.values()}
        if (
            len(self.players) > 1
            and len(team_ids) == 1
            and None not in team_ids
        ):
            raise ActionError(
                "team_diversity", "至少需要两种不同阵营才能开始"
            )

        seed = self.settings.seed
        if seed is None:
            seed = secrets.randbelow(2**31)
        # 座位顺序：默认按座位号升序；房主开启随机顺序时打乱后再开局。
        seats = list(occupied_seats)
        if self.settings.random_seat_order:
            rng = random.Random(seed ^ 0x5EED_0DE1)
            rng.shuffle(seats)
        # 先手座位：first_seat 优先，否则回退到旧 first_player 语义。
        first_player_id: int
        if self.settings.first_seat is not None:
            if self.settings.first_seat not in seats:
                raise ActionError("invalid_settings", "指定的先手座位不存在")
            first_player_id = self.settings.first_seat
        elif self.settings.first_player == "host":
            first_player_id = seats[0]
        elif self.settings.first_player == "guest":
            first_player_id = seats[-1]
        else:
            first_player_id = secrets.choice(seats)
        turn_order = seats
        # 把先手座位排到 turn_order 首位，保持后续轮转语义简单。
        while turn_order and turn_order[0] != first_player_id:
            turn_order.append(turn_order.pop(0))

        character_ids = {
            player_id: slot.character_id for player_id, slot in self.players.items()
        }
        player_teams = {
            player_id: slot.team_id for player_id, slot in self.players.items()
        }
        # 多人扩展：显式构造 players dict，每个就座座位一个 CharacterState。
        # GameState 默认只有 {1, 2}，3+ 人时必须显式传入避免 KeyError。
        players = {seat: CharacterState() for seat in character_ids}
        state = GameState(
            players=players,
            character_ids=character_ids,
            player_teams=player_teams,
            turn_order=list(turn_order),
            random_seed=seed,
            first_player_id=first_player_id,
            round1_no_damage=self.settings.round1_no_damage,
            round_number=1,
            active_player_id=first_player_id,
        )
        combat = CombatEngine(state, registry)
        combat.initialize_players()
        self._apply_configured_slugcat_pools(state, character_ids)

        zones: dict[int, CardZone] = {}
        for player_id, character_id in character_ids.items():
            if character_id is None:  # Narrowed by validation above.
                raise RuntimeError("角色状态在开局时意外丢失")
            deck_counts = self._deck_counts_for_slot(
                self.players[player_id], character_id, registry
            )
            last_card_id = max(deck_counts, default=0)
            player_seed = (seed ^ ((player_id * 0x9E3779B1) & 0x7FFFFFFF)) % (2**31)
            deck = build_shuffled_deck(
                1,
                last_card_id,
                deck_counts,
                random_seed=player_seed,
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

    def _deck_counts_for_slot(
        self, slot: PlayerSlot, character_id: int, registry: CardRegistry
    ) -> dict[int, int]:
        configured = slot.deck_counts.get(character_id)
        if configured is None:
            return registry.get_deck_counts(character_id)
        if character_id == 4:
            from card_duel.cards.slugcat.specs import SLUGCAT_SPECS_BY_ID

            defaults = registry.get_deck_counts(character_id)
            skill_counts = (
                {
                    card_id: count
                    for card_id, count in configured.items()
                    if SLUGCAT_SPECS_BY_ID.get(card_id) is not None
                    and SLUGCAT_SPECS_BY_ID[card_id].card_type == "技能"
                }
                if configured is not None
                else {
                    card_id: count
                    for card_id, count in defaults.items()
                    if SLUGCAT_SPECS_BY_ID.get(card_id) is not None
                    and SLUGCAT_SPECS_BY_ID[card_id].card_type == "技能"
                }
            )
            item_counts = {
                card_id: count
                for card_id, count in defaults.items()
                if SLUGCAT_SPECS_BY_ID.get(card_id) is not None
                and SLUGCAT_SPECS_BY_ID[card_id].card_type == "物品"
            }
            return {**skill_counts, **item_counts}
        return configured

    def _apply_configured_slugcat_pools(
        self, state: GameState, character_ids: dict[int, int | None]
    ) -> None:
        """把构建牌组中的见闻/形态数量写入各自的堆（生物保持默认）。"""
        from card_duel.cards.slugcat.specs import (
            SLUGCAT_DISCOVERY_IDS,
            SLUGCAT_FORM_IDS,
        )
        from card_duel.cards.slugcat.state import slugcat_data

        for player_id, character_id in character_ids.items():
            if character_id != 4:
                continue
            configured = self.players[player_id].deck_counts.get(character_id)
            if configured is None:
                continue
            data = slugcat_data(state.players[player_id])
            data.discovery_pool = [
                card_id
                for card_id, count in configured.items()
                if card_id in SLUGCAT_DISCOVERY_IDS
                for _ in range(max(0, count))
            ]
            data.form_copies = {
                card_id: count
                for card_id, count in configured.items()
                if card_id in SLUGCAT_FORM_IDS and count > 0
            }


@dataclass(slots=True)
class ClientConnection:
    client_id: str
    sender: JsonSender
    room_code: str | None = None
    player_id: int | None = None


Delivery = tuple[ClientConnection, dict[str, object]]


class RoomManager:
    """Own rooms, validate client actions, and fan out personalized snapshots."""

    # 房间允许的最大座位数。多人扩展已放开 2..8 人开局。
    MAX_SEATS = 8

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
            "configure_character_deck": self._configure_character_deck,
            "create_room": self._create_room,
            "join_room": self._join_room,
            "pick_seat": self._pick_seat,
            "add_seat": self._add_seat,
            "remove_seat": self._remove_seat,
            "shuffle_seats": self._shuffle_seats,
            "swap_seats": self._swap_seats_action,
            "move_player": self._move_player,
            "set_team": self._set_team,
            "set_name": self._set_name,
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
            "return_to_room": self._return_to_room,
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
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        self._require_outside_room(connection)
        code = self._new_room_code()
        room = Room(code=code, seat_capacity=2, host_client_id=connection.client_id)
        # 房主默认坐座位 1；座位 2..N 默认为空，等客机选座。
        # 房主身份保存在 host_client_id，房主换座位后权限不变。
        room.players[1] = PlayerSlot(
            player_id=1,
            client_id=connection.client_id,
            display_name=str(data.get("display_name") or "").strip() or "",
        )
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
        """兼容旧客户端：不带 seat 时自动坐到最小空座位。"""
        self._require_outside_room(connection)
        code = str(data.get("room_code", "")).strip()
        room = self.rooms.get(code)
        if room is None:
            raise ActionError("room_not_found", "房间不存在")
        if room.status != "lobby":
            raise ActionError("match_started", "该房间的对局已经开始")
        seat = data.get("seat")
        if seat is None:
            seat = self._first_free_seat(room)
        else:
            seat = _required_int({"seat": seat}, "seat")
        if seat not in self._all_seats(room):
            raise ActionError("invalid_seat", "座位号不存在")
        if seat in room.players:
            raise ActionError("seat_taken", "该座位已被占用")
        room.players[seat] = PlayerSlot(
            player_id=seat,
            client_id=connection.client_id,
            display_name=str(data.get("display_name") or "").strip() or "",
        )
        connection.room_code = code
        connection.player_id = seat
        return [
            (connection, event("room_joined", room_code=code, player_id=seat)),
            *self._room_state_deliveries(room),
        ]

    def _pick_seat(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        """已加入房间的玩家换座，或未入房玩家直接选座加入。

        满房换座支持：目标座位被其他玩家占用时，执行双方座位交换
        （各自的角色/阵营/准备/牌库配置跟随玩家走到对方座位），
        而不是拒绝。这样玩家即使前面进满了也能调整座位顺序。
        """
        seat = _required_int(data, "seat")
        if connection.room_code is None:
            # 未入房：走 join 逻辑但指定 seat，并带上 display_name 等字段。
            code = str(data.get("room_code", "")).strip()
            join_data: dict[str, Any] = {"room_code": code, "seat": seat}
            if "display_name" in data:
                join_data["display_name"] = data["display_name"]
            if "team_id" in data:
                join_data["team_id"] = data["team_id"]
            return self._join_room(connection, join_data)
        room = self.rooms.get(connection.room_code)
        if room is None:
            raise ActionError("room_not_found", "房间不存在")
        if room.status != "lobby":
            raise ActionError("match_started", "该房间的对局已经开始")
        if seat not in self._all_seats(room):
            raise ActionError("invalid_seat", "座位号不存在")
        my_old_seat = connection.player_id
        if my_old_seat is None:
            # 已在房间但没有座位（理论上不该发生）：直接占目标座位。
            if seat in room.players:
                raise ActionError("seat_taken", "该座位已被占用")
            room.players[seat] = PlayerSlot(
                player_id=seat,
                client_id=connection.client_id,
                team_id=data.get("team_id"),
            )
            connection.player_id = seat
            self._reset_readiness(room)
            return self._room_state_deliveries(room)
        if seat == my_old_seat:
            # 点击自己当前座位：无操作，仅刷新。
            return self._room_state_deliveries(room)
        if seat not in room.players:
            # 目标座位空：释放原座位，迁入新座位。
            old_slot = room.players.pop(my_old_seat, None)
            # 自定义名称跟随玩家：默认名(玩家{旧座位号})随座位号更新，
            # 自定义名保留不动。
            old_display_name = old_slot.display_name if old_slot else ""
            if old_display_name == f"玩家{my_old_seat}":
                new_display_name = f"玩家{seat}"
            else:
                new_display_name = old_display_name
            old_user_id = old_slot.user_id if old_slot else connection.client_id
            room.players[seat] = PlayerSlot(
                player_id=seat,
                client_id=connection.client_id,
                user_id=old_user_id,
                display_name=new_display_name,
                team_id=data.get("team_id"),
                deck_counts=old_slot.deck_counts if old_slot else {},
            )
            connection.player_id = seat
            self._reset_readiness(room)
            return self._room_state_deliveries(room)
        # 目标座位被其他玩家占用：执行双方交换。
        occupant_client_id = room.players[seat].client_id
        if occupant_client_id == connection.client_id:
            return self._room_state_deliveries(room)
        self._swap_seats(room, my_old_seat, seat)
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _swap_seats(self, room: Room, seat_a: int, seat_b: int) -> None:
        """交换两个座位的玩家身份（client_id、角色、阵营、准备、牌库配置）。

        座位号本身不变（slot.player_id 跟随座位号），玩家带着自己的数据
        换到对方座位；两个 connection.player_id 也同步更新。这样满房后
        也能调整座位顺序，避免"前面进满了很难改"。
        """
        slot_a = room.players[seat_a]
        slot_b = room.players[seat_b]
        # 记录交换前 display_name 是否为默认格式（玩家{座位号}）。
        # 交换后 slot_a 持有原 b 的名字、slot_b 持有原 a 的名字；
        # 默认名应跟随当前座位号，自定义名跟随玩家（保持交换后的值）。
        a_name_default = slot_a.display_name == f"玩家{seat_a}"
        b_name_default = slot_b.display_name == f"玩家{seat_b}"
        # 交换所有玩家相关字段（保留 player_id 即座位号不变）。
        for field_name in (
            "client_id",
            "user_id",
            "display_name",
            "character_id",
            "ready",
            "team_id",
            "deck_counts",
        ):
            a_val = getattr(slot_a, field_name)
            b_val = getattr(slot_b, field_name)
            setattr(slot_a, field_name, b_val)
            setattr(slot_b, field_name, a_val)
        # 修正默认名：原 b 是默认名 → slot_a 现在持默认名，跟随座位 a；
        # 原 a 是默认名 → slot_b 现在持默认名，跟随座位 b。
        if b_name_default:
            slot_a.display_name = f"玩家{seat_a}"
        if a_name_default:
            slot_b.display_name = f"玩家{seat_b}"
        # player_id 保持不变（=座位号）。
        slot_a.player_id = seat_a
        slot_b.player_id = seat_b
        # 同步两个 connection 的 player_id。
        # 交换后 slot_a 持有原 slot_b 的 client_id，所以那位玩家现在在座位 a。
        conn_for_a = self.connections.get(slot_a.client_id)
        conn_for_b = self.connections.get(slot_b.client_id)
        if conn_for_a is not None:
            conn_for_a.player_id = seat_a
        if conn_for_b is not None:
            conn_for_b.player_id = seat_b

    def _add_seat(
        self, connection: ClientConnection, _data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_lobby_player(connection)
        if not room.is_host(connection):
            raise ActionError("host_only", "只有房主可以加座位")
        if room.seat_capacity >= self.MAX_SEATS:
            raise ActionError("seat_limit", f"房间最多 {self.MAX_SEATS} 个座位")
        room.seat_capacity += 1
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _remove_seat(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_lobby_player(connection)
        if not room.is_host(connection):
            raise ActionError("host_only", "只有房主可以移除座位")
        seat = _required_int(data, "seat")
        if seat not in self._all_seats(room):
            raise ActionError("invalid_seat", "座位号不存在")
        if seat in room.players:
            raise ActionError("seat_occupied", "已坐人的座位不能移除（请用踢人或换座）")
        if room.seat_capacity <= 2:
            raise ActionError("seat_limit", "至少保留 2 个座位")
        # 收缩 seat_capacity 并重新编号最大座位。
        room.seat_capacity -= 1
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _shuffle_seats(
        self, connection: ClientConnection, _data: dict[str, Any]
    ) -> list[Delivery]:
        """房主随机重排座位顺序：玩家带着自己的数据换到新座位号。"""
        room, _slot = self._require_lobby_player(connection)
        if not room.is_host(connection):
            raise ActionError("host_only", "只有房主可以随机座位")
        old_seats = sorted(room.players)
        slots = [room.players[seat] for seat in old_seats]
        # 记录每个 slot 是否为默认名（玩家{原座位号}），便于跟随新座位号。
        is_default_name = [
            slot.display_name == f"玩家{seat}"
            for seat, slot in zip(old_seats, slots, strict=True)
        ]
        # Fisher-Yates 用一个独立的房间级 RNG，避免与开局种子混淆。
        rng = random.Random(secrets.randbelow(2**31))
        rng.shuffle(slots)
        room.players.clear()
        for seat, slot, was_default in zip(
            old_seats, slots, is_default_name, strict=True
        ):
            # 保留玩家全部数据（角色/阵营/准备/牌库/名称），只换座位号。
            slot.player_id = seat
            # 默认名跟随新座位号；自定义名保留不动。
            if was_default:
                slot.display_name = f"玩家{seat}"
            room.players[seat] = slot
            # 同步 connection.player_id 到新座位。
            conn = self.connections.get(slot.client_id)
            if conn is not None:
                conn.player_id = seat
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _swap_seats_action(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        """房主强制交换两个已占用座位的玩家。

        参数：seat_a, seat_b（两个已占用座位号）。
        调用现有 _swap_seats：双方角色/阵营/准备/牌库/名称跟随玩家走到对方座位。
        """
        room, _slot = self._require_lobby_player(connection)
        if not room.is_host(connection):
            raise ActionError("host_only", "只有房主可以交换座位")
        seat_a = _required_int(data, "seat_a")
        seat_b = _required_int(data, "seat_b")
        if seat_a == seat_b:
            raise ActionError("invalid_seat", "两个座位不能相同")
        for seat in (seat_a, seat_b):
            if seat not in self._all_seats(room):
                raise ActionError("invalid_seat", "座位号不存在")
            if seat not in room.players:
                raise ActionError("seat_empty", "只能交换已坐人的座位")
        self._swap_seats(room, seat_a, seat_b)
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _move_player(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        """房主把某个已坐人的玩家强制迁移到指定的空座位。

        参数：from_seat（已占用座位）、to_seat（空座位）。
        单方面迁移：玩家带着自己的数据（角色/阵营/准备/牌库/名称）搬到空座位，
        原座位腾空。不同于 swap_seats 的双向交换。
        """
        room, _slot = self._require_lobby_player(connection)
        if not room.is_host(connection):
            raise ActionError("host_only", "只有房主可以迁移玩家")
        from_seat = _required_int(data, "from_seat")
        to_seat = _required_int(data, "to_seat")
        if from_seat == to_seat:
            raise ActionError("invalid_seat", "起始座位与目标座位不能相同")
        for seat in (from_seat, to_seat):
            if seat not in self._all_seats(room):
                raise ActionError("invalid_seat", "座位号不存在")
        if from_seat not in room.players:
            raise ActionError("seat_empty", "起始座位没有玩家")
        if to_seat in room.players:
            raise ActionError("seat_taken", "目标座位已被占用")
        # 迁移：复用 _pick_seat 的迁移分支逻辑（保留自定义名）。
        old_slot = room.players.pop(from_seat)
        old_display_name = old_slot.display_name
        if old_display_name == f"玩家{from_seat}":
            new_display_name = f"玩家{to_seat}"
        else:
            new_display_name = old_display_name
        old_slot.player_id = to_seat
        old_slot.display_name = new_display_name
        room.players[to_seat] = old_slot
        # 同步 connection.player_id 到新座位。
        conn = self.connections.get(old_slot.client_id)
        if conn is not None:
            conn.player_id = to_seat
        self._reset_readiness(room)
        return self._room_state_deliveries(room)

    def _set_name(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        """玩家设置自己的 display_name，方便在座位和公告中辨识。"""
        room, slot = self._require_lobby_player(connection)
        if slot.ready:
            raise ActionError("ready_locked", "已准备，请先取消准备再改名")
        raw_name = data.get("display_name")
        if not isinstance(raw_name, str):
            raise ActionError("invalid_name", "display_name 必须是字符串")
        name = " ".join(raw_name.strip().splitlines())[:MAX_NAME_LENGTH]
        if not name:
            raise ActionError("invalid_name", "名称不能为空")
        slot.display_name = name
        # 改名不影响游戏公平，不重置任何人准备。
        return self._room_state_deliveries(room)

    def _set_team(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, slot = self._require_lobby_player(connection)
        if slot.ready:
            raise ActionError("ready_locked", "已准备，请先取消准备再改阵营")
        team_id = data.get("team_id")
        if team_id is not None:
            if isinstance(team_id, bool) or not isinstance(team_id, int):
                raise ActionError("invalid_team", "team_id 必须是整数或 null")
            if not 0 <= team_id < 100:
                raise ActionError("invalid_team", "team_id 超出允许范围")
        slot.team_id = team_id
        return self._room_state_deliveries(room)

    def _configure_character_deck(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, slot = self._require_lobby_player(connection)
        if slot.ready:
            raise ActionError("ready_locked", "已准备，请先取消准备再修改牌组")
        character_id = _required_int(data, "character_id")
        if character_id not in self.registry.character_ids:
            raise ActionError("invalid_character", "角色不存在")
        raw_counts = data.get("deck_counts")
        if not isinstance(raw_counts, dict):
            raise ActionError("invalid_deck", "deck_counts 必须是对象")
        catalog_ids = {
            definition.card_id for definition in self.registry.get_catalog(character_id)
        }
        counts = {}
        for raw_card_id, raw_count in raw_counts.items():
            try:
                card_id = int(raw_card_id)
            except (TypeError, ValueError):
                raise ActionError("invalid_deck", "卡牌编号必须是整数")
            if isinstance(card_id, bool):
                raise ActionError("invalid_deck", "卡牌编号必须是整数")
            if (
                isinstance(raw_count, bool)
                or not isinstance(raw_count, int)
                or not 0 <= raw_count <= 99
            ):
                raise ActionError("invalid_deck", "卡牌数量必须是 0 到 99 的整数")
            if card_id not in catalog_ids:
                raise ActionError("invalid_deck", f"卡牌 {card_id} 不属于该角色")
            counts[card_id] = raw_count
        if character_id == 4:
            # 蛞蝓猫物品/生物由默认牌组与区域机制决定，不参与构建。
            from card_duel.cards.slugcat.specs import SLUGCAT_SPECS_BY_ID

            counts = {
                card_id: count
                for card_id, count in counts.items()
                if SLUGCAT_SPECS_BY_ID.get(card_id) is not None
                and SLUGCAT_SPECS_BY_ID[card_id].card_type
                not in {"物品", "生物"}
            }
        if not any(counts.get(card_id) for card_id in catalog_ids):
            raise ActionError("invalid_deck", "牌组至少需要一张可抽的卡牌")
        slot.deck_counts[character_id] = counts
        # 准备是纯玩家自己的行为：改牌组不取消任何人的准备。
        return self._room_state_deliveries(room)

    def _select_character(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, slot = self._require_lobby_player(connection)
        if slot.ready:
            raise ActionError("ready_locked", "已准备，请先取消准备再更换角色")
        character_id = _required_int(data, "character_id")
        if character_id not in self.registry.character_ids:
            raise ActionError("invalid_character", "角色不存在")
        slot.character_id = character_id
        # 准备是纯玩家自己的行为：选角不取消任何人的准备。
        return self._room_state_deliveries(room)

    def _configure_room(
        self, connection: ClientConnection, data: dict[str, Any]
    ) -> list[Delivery]:
        room, _slot = self._require_lobby_player(connection)
        if not room.is_host(connection):
            raise ActionError("host_only", "只有房主可以修改房间规则")
        first_player = data.get("first_player", room.settings.first_player)
        if first_player not in {"host", "guest", "random"}:
            raise ActionError(
                "invalid_settings", "first_player 必须是 host、guest 或 random"
            )
        # 多人扩展：first_seat 与 random_seat_order。新客户端用这两个字段
        # 替代旧 host/guest/random 三选一。
        first_seat = data.get("first_seat", room.settings.first_seat)
        if first_seat is not None:
            if isinstance(first_seat, bool) or not isinstance(first_seat, int):
                raise ActionError("invalid_settings", "first_seat 必须是整数或 null")
            if first_seat not in self._all_seats(room):
                raise ActionError("invalid_settings", "first_seat 不在合法座位范围")
        random_seat_order = data.get("random_seat_order", room.settings.random_seat_order)
        if not isinstance(random_seat_order, bool):
            raise ActionError("invalid_settings", "random_seat_order 必须是布尔值")
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
            first_seat=first_seat,
            random_seat_order=random_seat_order,
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
        # 多人扩展：所有就座的玩家都准备才开局（2..N 人）。
        all_ready = bool(room.players) and all(
            item.ready for item in room.players.values()
        )
        if all_ready:
            log = room.start_match(self.registry)
            return [
                *self._match_started_deliveries(room),
                *self._log_deliveries(room, log),
            ]
        return self._room_state_deliveries(room)

    def _return_to_room(
        self, connection: ClientConnection, _data: dict[str, Any]
    ) -> list[Delivery]:
        # 对局结束后回到房间：清算对局状态，房间切回 lobby。
        # 保留座位/角色/阵营/名称，仅重置准备状态，方便同一批人再开一局。
        # 前端收到 room_state 会自动 setMatch(null) 切回房间界面。
        room, _slot = self._require_room_player(connection)
        if room.status != "playing":
            raise ActionError("match_not_started", "当前不在对局中")
        if room.state is None or not room.state.game_over:
            raise ActionError("game_not_over", "对局尚未结束，无法回到房间")
        room.state = None
        room.combat = None
        room.card_zones = {}
        room.pending_action = None
        room.status = "lobby"
        self._reset_readiness(room)
        room.revision += 1
        return self._room_state_deliveries(room)

    def _all_seats(self, room: Room) -> list[int]:
        """返回当前房间所有合法座位号（1..seat_capacity）。"""
        return list(range(1, room.seat_capacity + 1))

    def _first_free_seat(self, room: Room) -> int:
        for seat in self._all_seats(room):
            if seat not in room.players:
                return seat
        raise ActionError("room_full", "房间已满")

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
            log = handler(room, connection.player_id, data, self.registry)
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
        # 房主离开 → 关房（无论 lobby 还是 playing）。
        # 对局中任一玩家离开 → 关房（断线重连尚未实现，无法继续）。
        # 多人 lobby 阶段客机离开 → 只清自己的座位，房间继续。
        # 房主身份跟随 client_id，所以用 host_client_id 判断。
        if connection.client_id == room.host_client_id or room.status == "playing":
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
        # 每个连接带上自己的 player_id（座位号），前端据此同步本地 playerId。
        # 这样房主/玩家换座后前端 playerId 不会脱节，isHost/isMine 判断始终正确。
        return [
            (
                connection,
                event(
                    "room_state",
                    room=room_view,
                    your_player_id=connection.player_id,
                ),
            )
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
                if definition.card_id != 0
            ]
            for character_id in self.registry.character_ids
        }
        default_deck_counts = {}
        for character_id in self.registry.character_ids:
            counts = dict(self.registry.get_deck_counts(character_id))
            if character_id == 4:
                from card_duel.cards.slugcat.specs import (
                    SLUGCAT_CARD_SPECS,
                    SLUGCAT_CREATURE_IDS,
                )

                counts[27] = 1  # 见闻堆默认初始一张工业郊区
                for spec in SLUGCAT_CARD_SPECS:
                    if (
                        spec.card_id in SLUGCAT_CREATURE_IDS
                        and spec.source_count > 0
                    ):
                        counts[spec.card_id] = spec.source_count
            default_deck_counts[str(character_id)] = counts
        # 多人扩展：seats 列表覆盖所有座位（含空座位），方便前端渲染
        # 选座位 UI；players 字段保留以兼容只读取已坐玩家列表的旧前端。
        # 房主身份跟随 client_id：返回 host_seat（房主当前所在座位号），
        # 前端用 (playerId === host_seat) 判断房主，无需感知 client_id。
        host_seat: int | None = None
        for seat, slot in room.players.items():
            if slot.client_id == room.host_client_id:
                host_seat = seat
                break
        seats_payload = []
        for seat in self._all_seats(room):
            slot = room.players.get(seat)
            if slot is None:
                seats_payload.append({"seat_id": seat, "occupied": False})
            else:
                seats_payload.append(
                    {
                        "seat_id": seat,
                        "occupied": True,
                        "player_id": slot.player_id,
                        "display_name": slot.display_name,
                        "is_host": slot.client_id == room.host_client_id,
                        "character_id": slot.character_id,
                        "ready": slot.ready,
                        "team_id": slot.team_id,
                        "deck_counts": {
                            str(key): value
                            for key, value in slot.deck_counts.items()
                        },
                    }
                )
        return {
            "room_code": room.code,
            "status": room.status,
            "seat_capacity": room.seat_capacity,
            "host_seat": host_seat,
            "seats": seats_payload,
            "settings": asdict(room.settings),
            "players": [
                {
                    "player_id": slot.player_id,
                    "character_id": slot.character_id,
                    "ready": slot.ready,
                    "team_id": slot.team_id,
                    "display_name": slot.display_name,
                    "deck_counts": {
                        str(key): value for key, value in slot.deck_counts.items()
                    },
                }
                for slot in room.players.values()
            ],
            "characters": characters,
            "catalogs": catalogs,
            "default_deck_counts": default_deck_counts,
        }

    def _match_view(
        self, room: Room, connection: ClientConnection
    ) -> dict[str, object]:
        state = room.state
        player_id = connection.player_id
        if state is None or player_id is None:
            raise RuntimeError("对局状态尚未初始化")
        # 多人扩展：opponent 字段保留以兼容旧前端（2 人时仍按 1↔2 取），
        # 3+ 人时回退为 turn_order 中除自己外的第一个座位。新前端应使用
        # others 列表渲染所有对手的牌区计数。
        turn_order = list(state.turn_order) or sorted(state.players)
        if player_id in turn_order:
            others_order = [
                seat for seat in turn_order if seat != player_id
            ]
        else:
            others_order = [seat for seat in turn_order if seat != player_id]
        opponent_id = others_order[0] if others_order else player_id
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
                    "unlock_condition": self.registry_ability_condition(
                        character_id, definition.card_id
                    ),
                }
                for definition in self.registry.get_catalog(character_id)
            ]
            for character_id in set(state.character_ids.values())
            if character_id is not None
        }
        # 公开玩家 payload 合并 PlayerSlot 的 team_id/display_name。
        players_payload: dict[str, object] = {}
        for pid, character in state.players.items():
            slot = room.players.get(pid)
            payload = _public_player_payload(character)
            payload["team_id"] = slot.team_id if slot is not None else None
            payload["display_name"] = (
                slot.display_name if slot is not None else f"玩家{pid}"
            )
            payload["seat_id"] = pid
            players_payload[str(pid)] = payload
        others_zones = []
        for seat in others_order:
            zone = room.card_zones.get(seat)
            if zone is None:
                continue
            others_zones.append(
                {
                    "player_id": seat,
                    "hand_count": len(zone.hand),
                    "draw_count": len(zone.draw_pile),
                    "discard_count": len(zone.discard_pile),
                }
            )
        return {
            "room_code": room.code,
            "revision": room.revision,
            "player_id": player_id,
            "character_ids": {
                str(key): value for key, value in state.character_ids.items()
            },
            "player_teams": {
                str(key): value for key, value in state.player_teams.items()
            },
            "turn_order": list(turn_order),
            "players": players_payload,
            "card_catalogs": catalogs,
            "random_seed": state.random_seed,
            "first_player_id": state.first_player_id,
            "round1_no_damage": state.round1_no_damage,
            "round_number": state.round_number,
            "active_player_id": state.active_player_id,
            "current_phase": state.current_phase,
            "game_over": state.game_over,
            "hand_limit": hand_limit_for(state, player_id),
            "pending_choice": room.pending_action is not None,
            "you": {
                "hand_cards": list(own_zone.hand),
                "draw_pile": list(own_zone.draw_pile),
                "discard_pile": list(own_zone.discard_pile),
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
                "forced_discards": state.players[player_id].statuses.forced_discards,
            },
            # 兼容字段：2 人时即对手；3+ 人时仅返回轮转中的下一个对手。
            "opponent": {
                "hand_count": len(opponent_zone.hand),
                "draw_count": len(opponent_zone.draw_pile),
                "discard_count": len(opponent_zone.discard_pile),
            },
            # 多人扩展：所有非自己的玩家牌区计数，3+ 人前端据此渲染。
            "others": others_zones,
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

    def registry_ability_condition(self, character_id: int, card_id: int) -> str | None:
        if character_id != 4:
            return None
        from card_duel.cards.slugcat.specs import ABILITY_UNLOCK_CONDITIONS
        return ABILITY_UNLOCK_CONDITIONS.get(card_id)

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
                "pending_draw_additions",
            ):
                status_payload.pop(private_name, None)
            character_data = player.character_data
            if character_data is not None:
                character_data = player.character_data
                unlocked = getattr(character_data, "unlocked_creature_counts", None)
                discoveries = getattr(character_data, "discovery_pool", None)
                if unlocked is not None:
                    status_payload["unlocked_creature_counts"] = {
                        str(card_id): count for card_id, count in unlocked.items()
                    }
                if discoveries is not None:
                    status_payload["discovery_pool"] = list(discoveries)
            payload[item.name] = _json_value(status_payload)
        else:
            converted = _json_value(getattr(player, item.name))
            if item.name == "character_data" and isinstance(converted, dict):
                # 私有牌堆不向对方展示：见闻弃牌堆、生物弃牌堆。
                converted.pop("discovery_discard", None)
                converted.pop("creature_discard", None)
            payload[item.name] = converted
    payload["defence"] = player.defence
    return payload


def _json_value(value: object) -> object:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        # Sets are not JSON serializable; game data (e.g. SlugcatData.ability_unlocks)
        # uses them internally, so normalize them to arrays at the protocol boundary.
        return [_json_value(item) for item in sorted(value, key=str)]
    return value
