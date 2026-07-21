# Card Duel（卡牌对决）

Card Duel 是一个 Python 双人卡牌对战项目，提供两种运行方式：

- 本地演示版：使用 `customtkinter`，两名玩家在同一窗口中轮流操作。
- 局域网对战版：使用 `FreeSimpleGUI` 和 TCP Socket，由服务端（玩家 1）与客户端（玩家 2）共同完成一局游戏。

源码已统一为 UTF-8，并按“核心规则、界面、网络、应用入口”拆分。根目录的三个启动脚本仍兼容原有命令。

## 界面风格

本地版与联网版使用统一的简笔画简约风：

- 暖白纸张背景和轻量横线纹理；
- 深色墨线卡片与扁平描边按钮；
- 低饱和红、绿、蓝作为少量状态提示色；
- 成功出牌直接写入战斗记录，不再用弹窗打断操作；
- 联机版提供常驻聊天输入栏，双方在出牌或等待阶段都可发送消息；
- 保留错误、能量不足和连接异常等必要提示。

纸张背景由 Pillow 实时生成，不需要额外图片或新增第三方依赖。

## 环境要求

- Python 3.10 或更高版本
- Windows、macOS 或 Linux（联网版界面与字体在 Windows 下效果最佳）

安装依赖：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS / Linux：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

如果旧 `.venv` 记录了已经卸载的 Python 路径，请删除该虚拟环境后按上述命令重新创建。

## 运行方式

### 本地演示版

```bash
python demo.py
```

依次为玩家 1、玩家 2 选择角色，然后在同一窗口中轮流出牌。

### 局域网对战版

先在玩家 1 的电脑上启动服务端：

```bash
python main.py
```

再在玩家 2 的电脑上启动客户端：

```bash
python guest.py
```

客户端输入服务端的局域网 IP。双方默认使用 TCP 端口 `65432`，如无法连接，请检查系统防火墙是否允许 Python 使用该端口。同一台电脑测试时可输入 `127.0.0.1`。

也可以直接使用包入口：

```bash
python -m card_duel.apps.local
python -m card_duel.network.server
python -m card_duel.network.client
```

## 项目结构

```text
PythonProject/
├── card_duel/                 # 主程序包
│   ├── apps/
│   │   └── local.py           # 本地演示版应用与窗口切换
│   ├── cards/
│   │   └── registry.py        # 卡牌数量、元数据与效果函数注册表
│   ├── core/
│   │   ├── characters.py      # 共用角色名称与角色配置
│   │   ├── combat.py          # 战斗状态、数值结算与卡牌效果函数
│   │   ├── demo.py            # 不依赖 UI 的本地演示规则
│   │   └── game.py            # 五阶段回合状态机与阶段钩子
│   ├── network/
│   │   ├── client.py          # 玩家 2：连接、选角和客户端主循环
│   │   ├── gameplay.py        # 双端共用的出牌、弃牌和回合流程
│   │   ├── protocol.py        # 状态同步、确认消息和回合切换协议
│   │   └── server.py          # 玩家 1：监听、选角和服务端主循环
│   └── ui/
│       ├── background.py      # 本地版纸张纹理与线稿背景
│       ├── character_card.py  # 可点击的角色卡组件
│       ├── game.py            # 本地版战斗界面
│       ├── network.py         # 联网版布局与界面刷新函数
│       ├── selection.py       # 本地版角色选择界面
│       ├── theme.py           # 本地版主题常量
│       └── widgets.py         # 简笔画风格通用控件
├── assets/
│   └── cards/
│       └── 1/                 # 角色 1（战士）的联网版卡图
├── examples/
│   └── slider_dialog.py       # FreeSimpleGUI 滑块示例
├── tests/
│   ├── test_local_game.py     # 本地纯逻辑单元测试
│   └── test_turn_engine.py    # 五阶段顺序与阶段钩子测试
├── tools/
│   └── socket_echo_server.py  # 独立 Socket 调试工具
├── output/                    # 历史构建产物，不参与源码运行
├── demo.py                    # 本地版兼容启动脚本
├── guest.py                   # 客户端兼容启动脚本
├── main.py                    # 服务端兼容启动脚本
├── requirements.txt           # Python 依赖
└── README.md
```

## 代码分层与调用关系

```text
启动脚本
  ├─ demo.py  ──> apps/local.py ──> ui/* ──> core/demo.py
  ├─ main.py  ──> network/server.py ─┐
  └─ guest.py ──> network/client.py ─┴─> network/gameplay.py
                                         ├─> network/protocol.py
                                         ├─> core/game.py
                                         ├─> core/combat.py
                                         ├─> cards/registry.py
                                         └─> ui/network.py
```

- `core/game.py` 只负责回合阶段的顺序推进和阶段回调分发。
- `core/combat.py` 保存联网版战斗状态、数值结算和具体卡牌效果。
- `cards/registry.py` 是唯一的卡牌注册区域，集中维护牌组数量、名称、效果函数和消耗属性。
- `ui` 只负责创建控件、显示状态和处理界面事件。
- `network/protocol.py` 集中维护两端完全一致的通信格式，避免服务端与客户端各写一份同步代码。
- `network/gameplay.py` 集中维护共用的主动回合流程，服务端和客户端只决定谁先行动。
- `apps` 负责组装核心逻辑与界面，不保存卡牌规则。

## 关键数据模型

### 联网版

`NetworkGameState` 是联网版的唯一聚合状态，主要字段如下：

- `players`：以玩家编号为键的 `CharacterState`。
- `character_ids`：双方选择的角色编号。
- `hand_cards` / `hand_size`：本地手牌和有效手牌数量。
- `draw_pile`：当前角色的牌堆。
- `defences`：双方带剩余回合数的防御效果。
- `timeline`：延迟生效的 `ScheduledEvent` 列表。
- `connection` / `window`：当前网络连接与界面对象。

`CARD_REGISTRY` 使用 `(角色编号, 卡牌编号)` 映射到 `CardDefinition`。卡牌函数统一接收：

```text
game_state, source_player_id, target_player_id, announce, ignore_cost
```

## 回合时序

联网版每个玩家的回合严格按以下顺序执行：

```text
回合开始时 → 抽牌阶段 → 出牌阶段 → 弃牌阶段 → 回合结束时
```

`TurnEngine` 不允许跳过、重复或倒退阶段。卡牌、角色能力和通用规则可以通过下面的方式注册判定：

```python
turn.register_phase_handler(
    TurnPhase.TURN_START,
    resolve_ability,
    priority=20,
)
```

优先级数值越小越先执行。回调会收到 `TurnContext`，其中包含游戏状态、回合数、行动玩家、对手、当前阶段和消息输出函数。

当前默认判定位置：

- 回合开始时：防御持续时间、延迟事件、心连心等开始阶段效果。
- 抽牌阶段：标准抽 3 张牌及由能力产生的额外抽牌。
- 出牌阶段：读取并结算玩家选择的卡牌。
- 弃牌阶段：将手牌整理到 4 张以内。
- 回合结束时：预留给结束阶段的卡牌、能力和状态效果。

### 本地演示版

`LocalGame` 管理 `LocalPlayer`、当前回合、行动玩家和胜负状态。界面通过公开属性和方法读取状态，不直接修改规则细节。

## 卡图资源约定

联网版按下面的目录格式加载图片：

```text
assets/cards/<character_id>/img-0.jpg
assets/cards/<character_id>/img-1.jpg
assets/cards/<character_id>/img-2.jpg
...
```

图片编号必须连续。`img-0.jpg` 用作默认/占位图片，实际卡牌编号从 1 开始。添加角色时还需要同步更新：

1. `card_duel/core/characters.py` 中的角色信息；
2. `card_duel/cards/registry.py` 中的牌组数量；
3. `CARD_REGISTRY` 中的卡牌定义与效果函数；
4. 对应的 `assets/cards/<character_id>/` 图片目录。

目前联网版完整卡图和卡牌规则仅实现了角色 1（战士）；角色 2、3 仍是预留配置。本地演示版三个角色均可选择，但使用的是简化随机伤害规则。

## 测试与检查

运行单元测试：

```bash
python -m unittest discover -s tests -v
```

检查全部 Python 文件的语法：

```bash
python -m compileall -q card_duel main.py guest.py demo.py examples tools tests
```

## 命名约定

- 类名使用 `PascalCase`，例如 `NetworkGameState`、`DefenceEffect`。
- 函数、变量和模块使用 `snake_case`，例如 `send_game_state`、`round_number`。
- 玩家编号变量统一以 `_player_id` 结尾，角色编号统一以 `_character_id` 结尾。
- 布尔变量优先使用 `is_`、`has_` 或描述结果的过去式，例如 `is_over`、`was_played`。
- UI 控件变量体现用途，例如 `progress_window`、`confirm_button`，不再使用 `w`、`rs`、`qp` 等缩写。
