# 变更记录：初版 → 当前版本

本文档记录蛞蝓猫角色从初版到当前版本的所有差距，涵盖卡牌数据、效果逻辑、UI交互和网络同步四个方面。

---

## 一、卡牌数据变更

### 1.1 新增卡牌

| ID | 名称 | 类型 | 数量 | 耗能 | 说明 |
|----|------|------|------|------|------|
| 49 | 钢筋【插入】 | 物品 | 0 | None | 对手插入体内的钢筋。打出免费拔出，普通钢筋返回牌堆。不可弃牌。红边框标识。 |
| 50 | 电矛【插入】 | 物品 | 0 | None | 插入体内的电矛。打出免费拔出，普通电矛返回牌堆。不可弃牌。红边框标识。 |

**设计原因**：初版插入物复用普通钢筋(1)/电矛(5)的ID，通过`embedded_rods`计数+手牌顺序区分红边框，导致普通钢筋被误标红。改为独立ID后彻底隔离，普通牌与插入物互不干扰。

### 1.2 数量调整

| ID | 名称 | 初版数量 | 当前数量 | 原因 |
|----|------|----------|----------|------|
| 27 | 工业郊区 | 3 | 1 | 作为见闻解锁链的唯一起点，数量过多会导致开局过快膨胀 |

### 1.3 效果实现差异

| ID | 名称 | 工作簿原版描述 | 实际实现差异 |
|----|------|----------------|--------------|
| 14 | 猫跑路了 | "浪费的能量会在回合结束随机生成一只生物" | 见闻池耗尽时不生成生物，浪费能量直接损失 |
| 16 | 小面条 | "0费转移到别人的手牌并耗能+1" | 实现了cost stacking：每次转移记录+1层耗能递增 |
| 23 | 烈焰蜥蜴 | "可1费避免" | 实现了avoidance机制：受到攻击时可花1费避免本次伤害 |

---

## 二、效果逻辑变更

### 2.1 敏捷与动能系统（替换防御与力量）

初版蛞蝓猫UI显示的是通用的"防御"和"力量"，现已替换为蛞蝓猫专属的"敏捷"和"动能"：

| 属性 | 初版 | 当前 |
|------|------|------|
| 防御 → 敏捷 | 通用防御值，回合开始清除 | 敏捷：减伤资源，持续到对手回合结束，仅在自己回合开始时重置 |
| 力量 → 动能 | 通用力量值，永久增伤 | 动能：攻击资源，打出攻击牌时全部转换为伤害并清零，回合结束清零 |

**敏捷减伤规则**（初版未实现，本次新增）：
- 敏捷格挡伤害但仅按实际生命损失量递减
- 2敏捷 vs 2伤害 = 0生命损失，敏捷保持2（完全格挡不消耗）
- 2敏捷 vs 3伤害 = 1生命损失，敏捷降到1
- 敏捷持续到对手回合结束用于减伤，仅在自己回合开始重置

### 2.2 抽牌机制

初版：标准抽3张牌（无类型区分）

当前：分层抽牌 `_draw_slugcat_cards`
- 每回合抽3张：优先2张技能牌 + 1张物品牌
- 若某类型不足，从抽牌堆补足
- 见闻牌优先抽未打过的（new before played）

### 2.3 初始牌组过滤

初版：`SLUGCAT_INITIAL_DECK_COUNTS` 包含所有 `source_count > 0` 的牌（含生物牌）

当前：排除规则
- 生物牌（16-26）：不进入初始牌堆，仅通过见闻解锁或卡牌效果加入
- 插入物（49-50）：永不进入任何牌堆，仅通过插入效果临时加入手牌

### 2.4 生物牌系统

初版：生物牌在初始牌堆中，可被抽取

当前：
- 生物牌仅通过见闻解锁（计入`unlocked_creature_counts`）或卡牌效果（猫闯祸/趴下等）加入手牌
- 已解锁生物在抽牌堆查看器中单独展示（"已解锁生物（不可抽取，仅展示）"），金色边框
- 生物牌不可弃牌，必须打出或通过其他方式处理
- 生物健康和所有权通过`creature_health`、`hand_creature_owners`、`creature_threats`跟踪
- 生物牌和插入物打完后通过`pending_draw_returns`返回原主人牌堆

### 2.5 见闻解锁链

初版：无解锁链概念

当前：
- 从工业郊区(27)开始，无孤立节点
- 相邻关系双向（`DISCOVERY_ADJACENCY`）
- 打出见闻牌时优先解锁相邻的未见闻牌
- 业力上限仅第一次打见闻+1
- 猫跑路了按投入能量获得见闻牌，见闻池耗尽时浪费能量直接损失

### 2.6 插入物系统

初版：
- 插入物使用普通钢筋(1)/电矛(5)的ID
- 通过`embedded_steel_rods`/`embedded_electric_spears`计数+手牌顺序区分红边框
- 拔出逻辑：打出普通钢筋/电矛时检查embedded计数，>0则执行拔出
- `pending_insertions`未在发送游戏状态后清除 → 重复插入bug

当前：
- 插入物使用独立ID 49/50，与普通1/5和形态卡36-40完全隔离
- 红边框直接通过`card_id in SLUGCAT_INSERTED_IDS`判断，不再依赖计数
- 拔出逻辑：打出49/50时执行拔出（免费），普通钢筋/电矛返回牌堆
- `pending_insertions`和`pending_draw_returns`在发送游戏状态后清除
- 插入物不可弃牌（`SLUGCAT_NO_DISCARD_IDS`统一拦截）

### 2.7 攻击目标选择

初版：攻击直接打玩家，`get_attack_targets`仅显示本地玩家自己的手牌生物

当前：
- `get_attack_targets`读取双方同步的`player.special["creature_health"]`展示手牌生物
- 整合三类目标：玩家本体、手牌生物、威胁生物
- 战士攻击牌（攻/盾击/重剑打击等）通过`resolve_attack_target → choose_attack_target`走同一条链路
- 跨角色攻击目标选择：非蛞蝓猫角色也能攻击蛞蝓猫的生物

### 2.8 蜈蚣增殖逻辑

初版：client/server双方各自判定 → 状态不同步

当前：仅在server侧（`local_player_id == 1`）每轮执行一次，通过`pending_insertions`同步给client

### 2.9 伤害计算链路

初版：`apply_damage → lose_life`未传递`announce`参数 → 业力播报不触发

当前：`announce`参数贯穿`apply_damage → lose_life → resolve_slugcat_karma`，确保业力播报和防御机制正常

---

## 三、UI交互变更

### 3.1 安全辅助函数

初版：直接调用`window[key].update()` → "Unable to complete operation on element"错误

当前：引入`_safe_update`和`_safe_set_text`，吞掉异常防止崩溃

### 3.2 卡牌交互统一模型

初版：无统一交互模型

当前：
- 左键双击 = 选中/打出/弃置
- 右键 = 预览卡牌详情
- `card_selection_callback`统一回调

### 3.3 手牌边框标识

初版：无区分

当前：
- 插入物（49/50）：红色7px边框
- 生物牌（16-26）：金色7px边框
- 普通牌：1px纸色边框
- 通过`_apply_hand_card_border`直接配置Tk widget（`borderwidth`+`relief='solid'`）

### 3.4 抽牌堆查看器

初版：无分类展示

当前：
- 分类展示所有已解锁卡牌类型
- 每种一张卡+数量标识
- 每行最多5张
- 已解锁生物单独分区（金色边框，标注"不可抽取，仅展示"）

### 3.5 文本播报颜色

初版：`Multiline`组件`reroute_stdout=True`，所有文本同色

当前：
- 移除`reroute_stdout`，改用Tkinter标签着色
- `_classify_announce_color(message)`函数分类颜色：
  - 红色 = 伤害/生命损失/插入拔出
  - 绿色 = 抽牌/增益
  - 金色 = 警告/回合标记
  - 蓝色 = 回合信息/[我]方聊天
  - 灰色 = [对方]聊天/分隔线
  - 墨色 = 默认
- `colored_announce(game_state, message)`为规范播报方式
- 抽牌信息（"抽牌：XXX"）仅本地显示，不同步给对手

### 3.6 面板属性显示

初版：显示通用"防御"和"力量"

当前：蛞蝓猫面板显示"敏捷"和"动能"，玩家面板靠近排列减少左右视线移动

---

## 四、网络同步变更

### 3.1 状态同步清理

初版：`pending_insertions`和`pending_draw_returns`未在发送后清除 → 重复插入/返回

当前：`protocol.py`的`send_game_state`后清除这两个字段

### 3.2 实时手牌刷新

初版：插入/移除后仅在下次抽牌时刷新

当前：插入/移除事件触发`_refresh_local_hand`立即刷新

### 3.3 对手手牌生物可见性

初版：对手手牌生物不可见（仅本地`hand_cards`）

当前：通过`creature_health`数据结构同步，双方都能看到对手的手牌生物（用于攻击目标选择）

---

## 五、工作簿更新

本次已将以下变更同步到 `工作簿1.xlsx`：
- 新增"钢筋【插入】"(ID49)和"电矛【插入】"(ID50)两行
- 工业郊区数量从3改为1

---

## 六、Bug修复记录

### 6.1 网络同步后creature_health key类型问题（KeyError: '18'）

**现象**：客户端选择攻击目标时崩溃，报 `KeyError: '18'`。

**根因**：`player.special["creature_health"]` 经JSON序列化/反序列化后，dict的key从int变为str（如`18` → `"18"`），而`SLUGCAT_SPECS_BY_ID`的key是int，直接查找导致KeyError。

**修复**：`get_attack_targets`中遍历`creature_health`和`creature_threats`时，统一用`int(raw_id)`转换再查表。

### 6.2 烟雾果（ID41）只能秒杀自己手牌的蜈蚣

**现象**：烟雾果使用`_remove_hand_creature(game_state, 22)`，只检查本地玩家手牌，无法秒杀威胁区或对手的蜈蚣。

**修复**：新增`choose_creature_target`函数搜索所有可见位置（己方手牌/己方威胁/敌方威胁）的指定生物，让玩家选择目标；新增`_kill_creature_at`函数根据位置执行秒杀并触发死亡效果。

### 6.3 闪光果（ID43）无法选择转移哪只生物

**现象**：`_pop_first_creature_from_hand`总是取手牌中第一张生物牌，玩家有多个生物时无法选择。

**修复**：新增`_choose_own_hand_creature`函数列出所有手牌生物类型供选择，配合`_remove_hand_creature`精确移除选中类型。

### 6.4 泡水果（ID45）当石子用时无法选目标攻击生物

**现象**：泡水果选"石子"模式时调用`_attack_with_momentum`直接打玩家，跳过了`choose_attack_target`，无法攻击生物。

**修复**：改为与`_play_attack`相同的逻辑：计算伤害后调用`choose_attack_target`选目标，根据目标类型分流到`apply_damage`/`_damage_hand_creature`/`_damage_threat_creature`。

### 6.5 新增通用生物目标选择辅助函数

| 函数 | 用途 |
|------|------|
| `choose_creature_target(game_state, card_id_filter)` | 从所有可见位置收集指定类型生物，弹窗让玩家选择 |
| `_kill_creature_at(game_state, target, announce)` | 根据位置（own_hand/own_threat/opp_threat）秒杀生物并触发死亡效果 |
| `_choose_own_hand_creature(game_state)` | 列出己方手牌生物类型供选择，返回card_id |

### 6.6 生物牌被主动抽出（抽到未解锁生物）

**现象**：抽牌时抽到生物牌（16-26），即使该生物未被见闻解锁。

**根因**：生物牌可通过`_on_creature_death`（生物死亡返回牌堆）和烈焰蜥蜴避免（返回牌堆）进入抽牌堆，但`draw_cards`和`_draw_slugcat_cards`的fallback逻辑不区分卡牌类型，会抽出生物牌。

**修复**：
- `combat.py` `draw_cards`：遍历牌堆时跳过`SLUGCAT_CREATURE_IDS`中的卡，跳过的生物牌放回牌堆底部
- `gameplay.py` `_draw_slugcat_cards` fallback：同样跳过生物牌，放回底部
- 生物牌仍可在牌堆中（数量动态变化），但永远不会被主动抽出

### 6.7 抽牌堆查看器看不到已解锁生物

**现象**：已解锁生物在抽牌堆查看器中不显示。

**根因**：`unlocked_creature_counts`经JSON网络同步后dict的key从int变为str，`_deck_viewer_card_rows`中`0 <= card_id`比较和`SLUGCAT_SPECS_BY_ID[card_id]`查表均失败。

**修复**：`open_deck_viewer`读取`unlocked_creature_counts`时用`int(k)`转换所有key。

### 6.8 趴下（ID10）错误生成生物

**现象**：趴下执行`random.choice`生成一只随机生物到对方威胁区，与工作簿描述"随机加入的生物优先加入其他人手牌"不符。

**修复**：
- 趴下不再生成生物，改为设置`redirect_creatures_to_opponent`标记
- 猫闯祸（ID15）检查该标记，若为True则随机生物加入对方手牌而非自己手牌
- 标记在回合开始时清除（`_on_turn_start`）

### 6.9 拔矛不耗费能量

**现象**：插入物49/50的`cost=None`（不可主动打出），打出时免费拔出。工作簿原版描述为"耗1能打出"。

**修复**：
- `slugcat_data.py`：插入物49/50的cost从`None`改为`1`
- `_play_attack`：插入物分支增加`_pay_cost`调用，能量不足时无法拔出
- 工作簿同步更新卡面描述为"耗能1：拔出体内的钢筋/电矛"

### 6.10 `_remove_hand_creature`总是操作local_player的creature_health

**现象**：攻击对手手牌生物时，`_damage_hand_creature`调用`_remove_hand_creature`移除生物，但后者硬编码操作`game_state.local_player_id`的`creature_health`，导致对手的已死生物记录不被清除，本地玩家的记录可能被误删。

**修复**：`_remove_hand_creature`新增`player_id`参数：
- `player_id == local_player_id`：从`hand_cards`和`creature_health`中移除
- `player_id != local_player_id`：只从`creature_health`中移除（对手手牌通过`pending_insertions`同步）
- `_damage_hand_creature`调用时传入`target_player_id`

### 6.11 抽牌堆查看器看不到已解锁生物 + 初始化缺失字段

**现象**：已解锁生物在抽牌堆查看器中不显示。

**根因**：`initialize_slugcat_player`未初始化`unlocked_creature_counts`和`redirect_creatures_to_opponent`，导致`player.special`中缺少这些key时`.get()`返回默认值而非同步数据。

**修复**：`initialize_slugcat_player`中显式初始化`unlocked_creature_counts={}`和`redirect_creatures_to_opponent=False`。

### 6.12 调试输出

在`choose_attack_target`中添加`print`调试语句，输出`creature_health`、`creature_threats`和`targets`的内容，用于排查"打矛没有弹窗"问题。确认问题后将移除。

### 6.13 攻击牌无法选择目标（弹窗不弹出）

**现象**：打出钢筋等攻击牌时不弹窗选目标，无法攻击手牌中的生物（即使自己/对方手牌里有面条蝇等）。

**根因**：`get_attack_targets`只读取`target_player_id`（对手）的`creature_health`。当生物实际在攻击者自己手牌中（或网络同步只填充了单侧数据）时，查不到生物，`choose_attack_target`因`len(targets)<=1`早退返回None，不弹窗。

**修复**：
- `get_attack_targets`改为扫描**攻击者+对手双方**的`creature_health`及对手`creature_threats`，每个目标带`player_id`标识所属玩家。
- `choose_attack_target`签名增加`source_player_id`，弹窗选项标注`[己方]/[敌方]`。
- `_play_attack`、`_play_bubble_fruit`、`combat.resolve_attack_target`三处调用统一传入`source_player_id`，并按`target_obj["player_id"]`把伤害交给正确的`_damage_hand_creature`/`_damage_threat_creature`。
- `combat`端把"仅目标为蛞蝓猫才弹窗"放宽为"任一方为蛞蝓猫即弹窗"。
- 移除`choose_attack_target`中的调试`print`。

### 6.14 开局抽牌堆看不到基础生物

**现象**：开局抽牌堆查看器的"已解锁生物"区为空，小面条/绿蜥蜴/拾荒者等基础生物不显示。

**根因**：`unlocked_creature_counts`初始为`{}`，仅在见闻牌打出后才填充；基础生物（`source_count>0`的16-26）开局即拥有却不显示。

**修复**：`initialize_slugcat_player`初始化`unlocked_creature_counts`时填入所有`source_count>0`的生物（小面条×5、绿蜥蜴×5、拾荒者×3），见闻解锁时在其基础上累加。

### 6.15 攻击牌始终弹窗选目标

**现象**：打出攻击牌时仍无选目标环节；用户要求不论场上有几个生物都弹窗，生物数量只影响选项多少。

**修复**：`choose_attack_target`去掉`len(targets)<=1`早退逻辑，改为**总是弹窗**。即使场上无生物，也会弹出只有"对方玩家"一个选项的选择框。

### 6.16 猫觅食/猫闯祸/猫跑路抽牌统一为1张 + 卡面描述补充

**现象**：猫觅食(13)抽2张、猫闯祸(15)抽2张，与猫跑路(14)抽1张不一致；三张卡的卡面描述均未提及抽牌效果。

**修复**：
- 猫觅食、猫闯祸的`draw_cards`调用统一改为1张，announce文本同步更新。
- 猫觅食(13)、猫跑路(14)、猫闯祸(15)三张卡的`description`均补充"抽1张牌"。

