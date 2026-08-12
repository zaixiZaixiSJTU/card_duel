# Card Duel（卡牌对决）

Python 双人卡牌对战项目，通过 TCP 支持同机或局域网联机。项目使用可扩展角色目录、五阶段回合引擎和统一消息协议；战士与蛞蝓猫已实现，女猎手和时间守护者目前是显式占位角色。

## 快速开始

要求 Python 3.10+。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

运行：

```powershell
python main.py   # 玩家 1 创建房间
python guest.py  # 玩家 2 加入房间
```

安装后也可使用 `card-duel-host`、`card-duel-join`。

本机测试时，在两个终端中分别启动 `main.py` 和 `guest.py`，玩家 2 输入 `127.0.0.1`。默认端口为 `65432`，此方式会完整经过真实选角、卡牌、回合、聊天和网络同步逻辑。

## 依赖方向

```text
启动入口 / UI / network
          │
          ▼
application          组装角色感知的用例服务
          │
          ├───────────────┐
          ▼               ▼
cards                 core
角色包、目录、注册表    纯状态、回合和通用规则
```

必须保持的边界：

- `core` 不依赖角色包、GUI 或 socket；
- `CardRegistry` 不导入任何具体角色；
- 卡牌处理器只接收一个 `CardPlayContext`；
- 角色规则通过目录注入 `CombatEngine`，核心规则不判断角色编号；
- `GameState` 只保存对局数据，窗口和连接属于 `GameSession`；
- UI 不结算伤害、抽牌、消耗或角色能力；
- 联机消息全部使用长度前缀 JSON，不依赖一次 `recv()` 恰好收到一条消息。

这些约束由 `tests/test_architecture.py` 固定，不只是文档约定。

## 项目结构

```text
card_duel/
├── application/
│   ├── choices.py              # 卡牌选择端口与无 GUI 实现
│   └── combat.py               # CombatEngine：角色感知的战斗用例
├── cards/
│   ├── models.py               # CardPlayContext、卡牌/角色契约
│   ├── registry.py             # 纯通用 CardRegistry，不导入具体角色
│   ├── catalog.py              # 内置角色包的唯一组合根
│   ├── placeholders.py         # 角色 2、3 的显式占位包
│   ├── warrior/
│   │   ├── state.py            # WarriorData
│   │   ├── effects.py          # 战士卡牌效果
│   │   ├── lifecycle.py        # 战士初始化与阶段能力
│   │   └── catalog.py          # 战士牌组和注册函数
│   └── slugcat/
│       ├── state.py            # SlugcatData
│       ├── hand.py             # 手牌区小型操作
│       ├── creatures.py        # 生物区域、血量、目标选择与死亡结算
│       ├── effects.py          # 蛞蝓猫卡牌效果
│       ├── lifecycle.py        # 业力、敏捷、生物和阶段判定
│       ├── specs.py            # 50 张卡牌静态规格（含两种插入物）
│       └── catalog.py          # 蛞蝓猫牌组和注册函数
├── core/
│   ├── models.py               # GameState、CharacterState、通用状态
│   ├── rules.py                # 牌堆、防御、抽牌、时间线基础操作
│   ├── game.py                 # 五阶段 TurnEngine
│   ├── resources.py            # 卡图加载与生成卡面
│   └── combat.py               # 仅供旧调用方使用的兼容门面
├── network/
│   ├── session.py              # 状态、目录、CombatEngine、窗口和连接
│   ├── setup.py                # 选角与联机窗口准备
│   ├── transport.py            # 长度前缀 JSON 分帧
│   ├── protocol.py             # 类型化消息信封和状态同步
│   ├── gameplay.py             # 双端共用五阶段主动回合
│   ├── server.py               # 玩家 1
│   └── client.py               # 玩家 2
└── ui/
    ├── network.py             # 联网主布局
    ├── network_style.py       # 联网视觉常量和主题
    ├── network_view.py        # 状态到控件的单向渲染
    ├── network_log.py         # 彩色战斗/聊天日志
    ├── card_interaction.py    # 手牌确认与右键预览
    ├── deck_viewer.py         # 牌堆、见闻池与生物池查看器
    ├── network_dialogs.py     # 选角和等待对话框
    └── choices.py             # ChoiceProvider 的 GUI 实现
```

根目录的 `main.py`、`guest.py` 是兼容启动入口。`output/`、虚拟环境、缓存和构建产物均由 `.gitignore` 排除。

## 卡牌究竟在哪里注册

注册分为三个明确角色：

1. [registry.py](card_duel/cards/registry.py) 只定义通用容器和校验逻辑，不知道战士或蛞蝓猫；
2. 每个角色在自己的 `catalog.py` 中声明卡牌、牌组数量和生命周期规则；
3. [catalog.py](card_duel/cards/catalog.py) 是应用组合根，创建注册表并调用各角色的 `register()`。

蛞蝓猫的注册入口是：

```text
card_duel/cards/slugcat/catalog.py::register
```

默认组装过程：

```python
registry = CardRegistry()
register_warrior(registry)
register_placeholders(registry)
register_slugcat(registry)
registry.freeze()
```

因此新增角色不需要修改 `registry.py`，只需新增角色包，并在应用组合根选择是否装载它。

## 状态模型

`CharacterState` 分为三部分：

- 公共数值：生命、能量、防御、力量、毒；
- `CombatStatuses`：任何角色都可能受到的免疫、致盲、插入物、生物威胁等状态；
- `character_data`：由角色包创建的类型化 dataclass，例如 `WarriorData` 或 `SlugcatData`。

旧版无结构的 `special: dict[str, object]` 已移除。联机同步使用 dataclass 字段白名单，收到未知字段会拒绝应用。

防御效果属于对应的 `CharacterState`，`defence` 是由效果列表即时计算的只读属性；不存在需要 UI 刷新才能同步的第二份防御总值。

## 卡牌处理契约

所有卡牌处理器统一为：

```python
def effect(context: CardPlayContext) -> bool: ...
```

`CardPlayContext` 明确提供：

- `state`、`source`、`target`；
- 玩家编号和消息输出；
- `choices` 输入端口；
- `combat` 战斗服务；
- 当前 `registry` 与嵌套出牌方法；
- `ignore_cost`。

卡牌模块不导入 FreeSimpleGUI，也不通过全局变量或 `ContextVar` 偷渡依赖。

## 角色生命周期

每个角色规则对象负责：

- 创建类型化角色数据；
- 初始化玩家；
- 注册阶段钩子；
- 修正生命损失；
- 处理生命归零；
- 判断失败；
- 格式化角色状态。

因此 `CombatEngine` 不包含 `character_id == 4` 一类分支。蛞蝓猫的敏捷减伤和业力复活由 `SlugcatRules` 实现，战士的心连心由 `WarriorRules` 注册到回合开始阶段。

## 回合时序

```text
回合开始时 → 抽牌阶段 → 出牌阶段 → 弃牌阶段 → 回合结束时
```

```python
turn.register_phase_handler(
    TurnPhase.TURN_START,
    resolve_ability,
    priority=20,
)
```

优先级越小越先执行。阶段不可跳过、倒退或重复。

## 联机协议

所有消息均为统一信封：

```json
{"type": "chat", "message": "..."}
{"type": "announcement", "message": "..."}
{"type": "card_played", "player_id": 1, "character_id": 4, "card_id": 6}
{"type": "state", "players": {}, "defences": {}}
{"type": "turn_change"}
```

每个 JSON 负载前有四字节大端长度。状态一次发送，不再使用字符串标记和多轮 `pass` ACK，连续或拆分的 TCP 数据都能正确恢复消息边界。

当前协议版本为 3。生物、插入物和角色数据中的嵌套 dataclass 会按类型恢复；异步加入手牌、移除手牌、回归牌堆以及炸矛弃牌均在接收状态时立即处理。`card_played` 只同步已公开打出的卡，不包含手牌信息。协议版本不一致时双方会拒绝进入对局。

## 贡献与功能沿革

@CuiGer 在提交 `e6ba8b7`、`7f13456` 中完成了蛞蝓猫规则修复、生物与插入物系统、卡牌交互和联机同步改进。当前模块化实现以这两个提交为功能基线，并保留其 Git 作者记录；详细映射见 [docs/CUIGER_INTEGRATION.md](docs/CUIGER_INTEGRATION.md)。

## 新增角色

1. 新建 `card_duel/cards/<character>/`；
2. 定义角色数据 dataclass；
3. 实现 `CharacterRules`；
4. 使用 `CardPlayContext` 实现卡牌；
5. 在该包 `catalog.py` 提供 `register(registry)`；
6. 在需要该角色的组合根调用注册函数；
7. 添加规则、阶段、注册完整性和协议同步测试。

## 测试与检查

```powershell
python -m unittest discover -s tests -v
python -m compileall -q card_duel main.py guest.py examples tools tests
ruff check .
ruff format --check .
```

包元数据、命令入口、依赖和静态检查配置位于 `pyproject.toml`。
