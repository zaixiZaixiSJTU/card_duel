# Web 后端协议（阶段一）

Web 后端是 `docs/ARCHITECTURE_AND_MIGRATION_PLAN.md` 阶段一的首个可运行纵切。
服务端负责房间和开局状态，浏览器只发送动作并渲染服务端事件。

## 启动

```bash
python -m pip install -e ".[dev]"
card-duel-web
```

- 服务说明首页：`GET /`
- 健康检查：`GET /health`
- WebSocket：`WS /ws`
- 当前 Web 协议版本：`2`

客户端消息统一使用动作信封：

```json
{"action": "create_room", "data": {}}
```

服务端消息统一使用事件信封：

```json
{"type": "room_created", "protocol_version": 2, "data": {"room_code": "123456", "player_id": 1}}
```

校验失败不会主动关闭连接，而是返回结构化错误：

```json
{"type": "error", "protocol_version": 2, "data": {"code": "room_not_found", "message": "房间不存在"}}
```

## 客户端动作

| action | data | 说明 |
| --- | --- | --- |
| `create_room` | `{}` | 创建房间并成为玩家 1（房主） |
| `join_room` | `{"room_code":"123456"}` 或 `{"room_code":"...","seat":2}` | 加入房间；不带 `seat` 时自动坐到最小空座位，带 `seat` 则坐指定座位 |
| `pick_seat` | `{"seat":3}` 或 `{"room_code":"...","seat":3}` | 已入房玩家换座；未入房玩家等价于 `join_room` 带指定 `seat`。会取消所有人准备 |
| `add_seat` | `{}` | 仅房主；新增一个空座位，房间座位上限最多 8 个 |
| `remove_seat` | `{"seat":4}` | 仅房主；移除一个空座位（已坐人的座位拒绝移除，至少保留 2 个座位） |
| `shuffle_seats` | `{}` | 仅房主；Fisher-Yates 随机重排已就座玩家的座位号；`connection.player_id` 同步更新 |
| `set_team` | `{"team_id":1}` 或 `{"team_id":null}` | 设置自己的阵营编号；`null` 表示自由阵营（FFA）。已准备时拒绝 |
| `select_character` | `{"character_id":1}` | 选择已注册角色；会取消双方准备状态 |
| `configure_room` | 见下文 | 仅房主可修改；会取消双方准备状态 |
| `set_ready` | `{"ready":true}` | 所有就座玩家准备后由服务端初始化对局；3+ 人开局会返回 `multiplayer_not_supported` |
| `chat` | `{"message":"..."}` | 房间/对局聊天，最多 200 字符 |
| `request_state` | `{}` | 请求当前房间或个性化对局快照 |
| `leave_room` | `{}` | 主动离开房间；房主离开或对局中离开会关闭房间，lobby 阶段客机离开只清自己的座位 |
| `play_card` | `{"source":"hand","index":0}` | 当前玩家在出牌阶段打出手牌或生物 |
| `discard_card` | `{"index":0}` | 进入/停留在弃牌阶段并弃一张牌 |
| `discard_cards` | `{"indexes":[0,2]}` | 从出牌/弃牌阶段原子弃置预选的多张牌 |
| `end_turn` | `{}` | 手牌不超过上限时结算回合结束并切换玩家 |
| `resolve_choice` | 见下文 | 回答当前挂起的卡牌或阶段选择 |
| `cancel_choice` | `{"choice_id":"..."}` | 取消选择并保留动作前状态 |

房主规则格式：

```json
{
  "action": "configure_room",
  "data": {
    "first_player": "random",
    "first_seat": null,
    "random_seat_order": false,
    "seed": null,
    "round1_no_damage": true
  }
}
```

`first_player` 可取 `host`、`guest` 或 `random`（旧字段，保留兼容）；
`first_seat` 为整数时指定先手座位号，`null` 表示按 `first_player` 回退；
`random_seat_order` 为 `true` 时开局按 `seed` 打乱座位号再确定先手；
`seed` 可为 0 至 `2^31-1` 的整数，或用 `null` 让服务端开局时生成。

## 多人房间扩展

`PlayerSlot` 拓展了多人所需的玩家元数据：`user_id`（持久身份，暂用
`client_id` 占位）、`display_name`（公告/聊天显示，默认"玩家N"）、
`team_id`（阵营编号，`null` 表示 FFA）、`seat_id` 即 `player_id`。
`GameState` 新增 `player_teams: dict[PlayerId, int | None]` 和
`turn_order: list[int]`，`CharacterState` 新增 `is_alive: bool`；
2 人模式下保持默认值即可，桌面 TCP 与现有协议不读写这些字段。

`room_state` 事件扩展字段：
- `seat_capacity`：房间当前座位总数（2..8）
- `seats`：所有座位的列表，每项含 `seat_id`、`occupied`；
  `occupied=true` 时附带 `player_id`、`display_name`、`character_id`、
  `ready`、`team_id`、`deck_counts`

`state` 事件扩展字段（3+ 人纵切完成后才真正多人化，当前 3+ 人开局会被拒绝）：
- `player_teams`：座位号 -> 阵营编号
- `turn_order`：本局回合轮转顺序（座位号列表）
- `others`：除自己外所有玩家的牌区计数列表，3+ 人前端据此渲染
- `players[id]` 每个玩家附带 `team_id`、`display_name`、`seat_id`、`is_alive`
- `opponent` 字段保留以兼容旧前端（2 人时即对手，3+ 人时仅返回轮转中的下一个对手）

当前 2 人纵切已支持多人房间建模与 lobby 选座位 UI，但 `start_match` 仍显式
拒绝 3+ 人开局（返回 `multiplayer_not_supported`），因为回合轮转、卡牌目标
选择和胜负判定尚未多人化。

## 多人对局回合逻辑

多人对局已全面放开（2..8 人），核心规则：

- **回合轮转**：按 `turn_order` 顺序切换；`end_turn` 用 `_next_alive_player`
  跳过 `is_alive=False` 的玩家；回到 `first_player_id` 时 `round_number += 1`。
- **胜负判定**：`winning_team_id` 返回"敌方全死算赢"的阵营编号——
  - FFA（`team_id` 全为 None）：每个玩家独立成阵营，只剩一人时该人胜；
  - 组队（`team_id` 为整数）：同阵营共享胜负，对方阵营全灭时己方胜；
  - 2 人时退化为一方死则对方胜，与原 `winning_player_id` 语义一致。
- **目标选择**：`play_card` 默认目标为"第一个存活敌方"
  （`_default_target`），1v1 时自动选用，3+ 人时也回退到第一个敌方。
  未来如需"多敌方时让玩家选目标"，可在 play_card 入口增加 `choose_player`
  步骤，卡牌 effects 不变（`context.target_player_id` 仍是单一 int）。
- **首回合保护**：`round1_lock_health` 仅在 2 人时启用；3+ 人时跳过此
  锁定（"对方"概念不再单一，且多人本身有先手劣势平衡）。
- **死亡玩家处理**：`is_player_defeated` 返回 True 时同步设置 `is_alive=False`；
  `_apply_pending_zones` 遍历所有座位时跳过死亡玩家。

### 满房换座

`pick_seat` 支持满房交换：目标座位被其他玩家占用时，`_swap_seats` 执行
双方座位交换（各自的角色/阵营/准备/牌库配置跟随玩家走到对方座位），
而不是拒绝。这样玩家即使前面进满了也能调整座位顺序。`display_name`
如果是默认格式（`玩家N`），交换后跟随新座位号更新。

### 阵营颜色

`PlayerSlot.team_id` 作为阵营编号（0=红、1=蓝、2=绿、3=黄、4=紫、5=橙），
`null` 表示 FFA。前端 `TEAM_COLORS` + `teamClassFor` 把 `team_id` 映射到
CSS 类名（`team-red` / `team-blue` 等），座位边框和局内 `player-status`
信息栏边框都按阵营着色。**不预设游戏模式**：玩家通过选颜色和座位自由
组合（全不同色 = FFA、两红两蓝 = 2v2、三红一蓝 = 3v1）。

`play_card.source` 可取 `hand` 或 `creature`，`index` 始终是当前个性化状态中
对应区域的零基索引。成功动作后双方都会收到新的 `state`，其中 `revision`
单调递增。

浏览器应优先使用 `discard_cards`：玩家可先在本地增加或减去待弃牌，再一次确认。
服务端会先验证全部索引及可弃规则；任一牌不可弃时整批回滚，不会产生部分提交。

## 卡牌选择

需要选择时，服务端会回滚本次动作的所有中间修改并返回：

```json
{
  "type": "choice_required",
  "protocol_version": 2,
  "data": {
    "choice_id": "...",
    "choice": {
      "kind": "integer",
      "title": "燃烧",
      "prompt": "选择燃烧的生命（1-3）",
      "minimum": 1,
      "maximum": 3,
      "default": 1
    }
  }
}
```

客户端提交答案：

```json
{"action":"resolve_choice","data":{"choice_id":"...","value":3}}
```

`kind` 可能为 `integer`、`option` 或 `card_indexes`。一次卡牌包含多个选择时，
服务端会从干净快照重放已经回答的选择，再返回下一个 `choice_required`；因此
等待选择期间不会重复扣能量、伤害或弃牌。

## 服务端事件

- `connected`：WebSocket 已接受，返回本次连接 ID。
- `room_created` / `room_joined`：创建或加入成功。
- `room_state`：房间成员、选角、准备、规则和可选角色目录。
- `chat`：带发送者玩家编号的聊天消息。
- `match_started`：双方准备完成后的首个权威状态。
- `state`：响应 `request_state` 的个性化权威状态。
- `announcement` / `private_announcement`：公共或仅对应玩家可见的结算日志。
- `card_played`：公开最近打出的卡牌，不包含手牌信息。
- `choice_required` / `choice_cancelled`：选择挂起或取消。
- `room_left`：主动离开成功，客户端应清空本地房间/对局状态并返回入口。
- `room_closed`：房主离开，或对局中的任一玩家断线。
- `error`：可恢复的动作校验错误。

## 状态隐私与当前边界

中心服为两名玩家维护独立的 `hand / draw_pile / discard_pile`。`you` 包含本人
完整手牌、与手牌位置对齐的动态 `card_costs` / `card_discardable`，以及规则计算
后的 `effective_hand_size`；`opponent` 只包含手牌数量和牌堆计数。角色状态中的
待加入、待移除、待返还手牌队列也不会发送给对方。
`players` 中的公开核心值包含 `health`、`max_health`、`energy`、`strength`、
`poison` 和即时计算的 `defence`；前端用当前/最大生命绘制生命条，不自行猜测角色
生命上限。新增字段的归属、可见性和展示步骤见
[状态显示与新效果开发工作流](STATUS_EFFECT_WORKFLOW.md)。
`card_catalogs` 只包含本局角色的公开卡牌定义（名称、类型、费用、说明、消耗
标志），供浏览器渲染卡面，不携带任何一方的私有牌区。

当前阶段已复用角色目录、洗牌规则、`GameState`、`CombatEngine` 和五阶段时序，
支持权威抽牌、出牌、弃牌、回合结束、胜负判定及可暂停/恢复的选择。React
浏览器客户端位于 `frontend/`，已实现房间与对战界面。下一纵切应补齐双浏览器
端到端实战测试、断线重连令牌与服务端持久化。

## 浏览器前端

```bash
card-duel-web
cd frontend
npm install
npm run dev
```

本地页面为 `http://localhost:3000`。部署后的页面可在连接区填写可公开访问的
`wss://` 后端地址，或在构建时设置 `NEXT_PUBLIC_CARD_DUEL_WS_URL`。前端托管
不会自动暴露本机的 Python 进程；后端必须部署为独立、可长期运行的 ASGI 服务。
