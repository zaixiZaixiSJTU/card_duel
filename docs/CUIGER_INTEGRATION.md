# @CuiGer 功能迁移说明

本项目在重构时以 `e6ba8b7`（“修复十几个蛞蝓猫bug”）和 `7f13456`（“debug”）为功能基线。重构只调整职责边界，不应删除这两个提交中与新结构不冲突的规则和交互。

## 规则功能对应关系

| 原修改范围 | 当前模块 |
| --- | --- |
| 敏捷、动能、业力、饱食度 | `cards/slugcat/state.py`、`cards/slugcat/lifecycle.py` |
| 50 张牌规格、初始牌库过滤 | `cards/slugcat/specs.py` |
| 猫闯祸、见闻、果实、形态等牌效 | `cards/slugcat/effects.py` |
| 生物血量、所有权、威胁区、攻击目标、死亡效果 | `cards/slugcat/creatures.py` |
| 插入钢筋/电矛的唯一 ID 与拔出效果 | `cards/injected.py`、`cards/slugcat/effects.py` |
| 五阶段时序和回合结束同步 | `core/game.py`、`network/gameplay.py` |
| 嵌套状态和整数字典键的联机恢复 | `network/protocol.py` |

其中初始牌库遵循最终规则：保留所有 `source_count > 0` 的普通来源牌，排除生物（16–26）、见闻（27–35）和临时插入物（49–50）。生物和见闻分别由自己的池管理，不能被普通抽牌主动抽出。

## 交互功能对应关系

| 原修改范围 | 当前模块 |
| --- | --- |
| 左键两次确认、右键预览 | `ui/card_interaction.py` |
| 分类牌堆、见闻池、已解锁生物 | `ui/deck_viewer.py` |
| 查看器/预览不阻塞联机收发 | `ui/auxiliary_windows.py` |
| 战斗/聊天彩色日志 | `ui/network_log.py` |
| 动态费用、生物血量、红/金边框、最近出牌 | `ui/network_view.py` |
| 18 个手牌槽、每行 6 张、竖向滚动 | `ui/network.py` |

## 等价但方向不同的实现

旧实现从列表末尾抽牌，因此使用后的卡需要 `insert(0, card_id)` 放到牌堆底部。当前核心统一从列表开头抽牌，因此对应操作是 `append(card_id)`。两者的游戏效果相同：刚打出或弃掉的牌进入牌堆底部，不会立刻被再次抽回。

以上功能由自动化测试覆盖；后续结构调整应先更新迁移表和测试，避免再次以重构名义覆盖已有功能。
