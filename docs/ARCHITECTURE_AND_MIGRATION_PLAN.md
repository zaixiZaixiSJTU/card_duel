# Card Duel 项目架构分析与 Web 迁移规划

## 1. 当前项目架构概览

当前项目（Card Duel）采用了极其标准且优秀的**领域驱动设计（DDD）**和**关注点分离**原则。项目被清晰地划分为不同的分层模块，这为后续的系统扩展以及跨平台迁移奠定了极佳的基础。

### 1.1 目录结构与职责

*   **`card_duel/core/` (核心领域模型)**
    *   **职责**：定义游戏的纯数据模型（如 `GameState`, `CharacterState`, `ScheduledEvent`）和通用基础规则（如洗牌、抽牌逻辑）。
    *   **特性**：**纯 Python 逻辑，零外部依赖**（不依赖任何 UI 库或网络 Socket 库）。这是整个游戏的“唯一事实来源”。
*   **`card_duel/cards/` (卡牌与角色插件层)**
    *   **职责**：实现具体角色的生命周期、特色机制以及具体的卡牌效果。
    *   **特性**：采用**注册表模式 (Registry Pattern)** 和 **上下文驱动的命令模式 (CardPlayContext)**。各个角色（如 `warrior`, `slugcat`）作为插件包独立存在，通过接口协议介入游戏生命周期。
*   **`card_duel/application/` (应用服务层)**
    *   **职责**：连接核心状态和卡牌规则的主干业务逻辑，如战斗引擎 (`CombatEngine`)。
*   **`card_duel/network/` (网络基础设施层)**
    *   **职责**：处理玩家之间的状态同步和回合控制。
    *   **特性**：目前基于 Python 原生 TCP `socket` 实现 Host/Guest 房间直连机制。
*   **`card_duel/ui/` (表现层)**
    *   **职责**：将 `GameState` 渲染给玩家，并接收玩家输入。
    *   **特性**：目前基于 `FreeSimpleGUI` (Tkinter 桌面窗口) 构建，采用“数据驱动视图”的响应式设计思路。

### 1.2 卡牌设计思路亮点

1.  **高度解耦**：抽象了基础战斗模型，将卡牌的具体特色玩法完全下放到“角色定义包”中。
2.  **流派差异化**：
    *   **战士 (Warrior)**：传统的卡牌构建者设计，依赖能量 (Energy) 循环和攻防数值的简单闭环。
    *   **蛞蝓猫 (Slugcat)**：受《雨世界》启发，引入了高复杂度的状态机（如敏捷、饱食度、业力）、动态费用连击系统以及独特的**生物互动（Creature Mechanics）**和**异物插入（Inserted Items）**机制，展现了引擎极强的包容性和扩展性。

---

## 2. Web 网页版迁移规划

为了让玩家实现“免安装、双击即玩”，并将游戏部署至拥有的 2C4G 5Mbps 服务器上，项目将由当前的“桌面端直连”模式全面改造为**“前后端分离的权威服务器模式 (Authoritative Server)”**。

### 2.1 架构改造策略：动静分离

鉴于 5Mbps 服务器宽带（约 625 KB/s）是最大瓶颈，需严格分离静态资源和实时数据：

*   **2C4G 服务器 (后端)**：仅运行核心游戏引擎。通过 WebSocket 传输轻量级的 JSON 格式的 `GameState`。2核4G资源足以支撑成百上千个回合制并发房间，而轻量的状态数据完美避开宽带瓶颈。
*   **云端 CDN 托管 (前端)**：游戏界面、大量图片资源和音频将交由 Vercel、Cloudflare Pages 或 Github Pages 等免费的静态托管平台进行全球分发。

### 2.2 具体模块迁移方案

| 现有模块 | 目标形态 | 迁移成本 / 方案 |
| :--- | :--- | :--- |
| `core/`, `application/`, `cards/` | WebSocket 服务端内核 | **0 重构成本**。直接复用现有的纯 Python 代码逻辑。 |
| `network/` | WebSocket 通信层 | **必须重构**。废弃原生 TCP socket。建议使用 Python `FastAPI` (支持 ASGI) 或 `websockets` 编写带有房间管理的中心化服务器。 |
| `ui/` | Web 前端界面 | **必须重写**。废弃 `FreeSimpleGUI`。建议使用 **Vue3 / React** (DOM流) 或 **Pixi.js / Phaser.js** (Canvas流)，依据下发的 `GameState` 渲染 UI 并发送玩家指令。 |

### 2.3 分阶段实施计划

#### 阶段一：后端 API 与 WebSocket 服务化 (后端开发)
1.  **引入 Web 框架**：在项目中集成 `FastAPI`。
2.  **构建房间管理器**：实现一套基于内存的 Room Manager，支持通过生成随机 6 位房间号让玩家加入匹配。
3.  **协议适配**：将现有传输协议改为通过 WebSocket 收发 `{"action": "...", "data": {...}}` 格式的 JSON 载荷，下发核心引擎计算后的完整/增量 `GameState`。

#### 阶段二：前端界面重构 (前端开发)
1.  **技术栈初始化**：在项目根目录新建 `/web` 或 `/frontend` 目录，初始化基于 Vue/React 或 Phaser 的项目。
2.  **核心 UI 还原**：实现卡牌渲染组件、玩家状态栏（血量条、各种Buff图标）、场地生物展示区。
3.  **网络对接**：建立 WebSocket 连接，实现界面渲染与后端 `GameState` 状态同步，以及交互事件（打牌、结束回合）的回传。

#### 阶段三：部署与测试上线 (DevOps)
1.  **后端部署**：使用 Docker 封装 Python 后端服务，部署至 2C4G 服务器，通过 Nginx 反向代理配置 `wss://` 协议。
2.  **前端部署**：配置 CI/CD，将前端静态产物自动构建部署至静态托管平台。

---

*This document serves as the primary architectural guideline for agents and developers continuing the implementation phase of the Card Duel Web migration.*
