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

### 6.17 烈焰蜈蚣未解锁却凭空加入手牌

**现象**：烈焰蜈蚣(22)在未解锁时莫名出现在玩家手牌中。

**根因**：`_resolve_centipede_spread`中，当双方场上蜈蚣数均为0时，代码无条件生成一只蜈蚣加入当前玩家手牌。这导致即使没有任何蜈蚣进场，每轮也会凭空生成。

**修复**：双方均无蜈蚣时直接`return`不增殖。增殖只在已有蜈蚣（有血量、已进场）时触发，符合"存活时增殖"的工作簿描述。

### 6.18 绿蜥蜴沉默回合无提示日志

**现象**：绿蜥蜴(20)首次进场的回合处于沉默状态（不造成伤害），但没有任何日志提示，玩家不知道下回合会被攻击。

**修复**：`_creature_damage`增加`announce`和`player_id`参数，绿蜥蜴沉默回合发送日志"绿蜥蜴静止中，下回合将造成5点伤害"。两处调用点（手牌生物、威胁生物）同步传入参数。

### 6.19 "失去生命"错误触发敏捷减伤

**现象**：钢筋插入、炸矛穿透等"失去生命"效果会被敏捷格挡并消耗敏捷，但"失去生命"应完全无视敏捷。

**根因**：敏捷格挡逻辑写在`lose_life`中，导致所有调用`lose_life`的效果（失去生命）都会触发敏捷减伤。实际上只有"造成伤害"(`apply_damage`)才应被敏捷格挡。

**修复**：将敏捷格挡逻辑从`lose_life`移到`apply_damage`。`lose_life`改为：不减少伤害（防不了），但仍消耗等量敏捷（敏捷掉的数值=失去生命的数值）。所有`lose_life`调用点（钢筋回合结算、炸矛穿透、战士燃起来、战士调度事件）现在都正确：防不了但敏捷照掉。

### 6.20 电矛插入无效

**现象**：蛞蝓猫被电矛插入后没有任何负面效果。

**根因**：`_on_turn_end`中先扣力量（`_resolve_inserted_items`），紧接着又恢复力量（`electric_penalty_this_turn`还原），等于没扣。

**修复**：力量扣减移到`_on_turn_start`（回合开始扣力量，本回合攻击伤害降低），`_on_turn_end`保留恢复逻辑。`_resolve_inserted_items`不再处理电矛，仅结算钢筋流血。

### 6.21 X费牌改为耗尽全部能量

**现象**：猫跑路(14)让玩家任选投入能量，与杀戮尖塔X费牌机制不符。

**修复**：`_play_run_away`改为耗尽全部剩余能量（`player.energy = 0`），抽X-1张见闻牌。删除`_choose_x_cost`弹窗。卡面描述更新为"耗尽全部能量，抽X-1张见闻牌"。

### 6.22 见闻解锁只加1个相邻

**现象**：首次打出工业郊区(27)只解锁1个相邻见闻（阴影城堡），但邻接表有3个（28/29/32）。

**根因**：`_unlock_adjacent_discovery`用`min(candidates, key=count)`只选1个加入池。

**修复**：改为遍历全部未见过的相邻见闻，全部加入`discovery_pool`。

### 6.23 见闻换场景保留旧牌堆

**现象**：打出新见闻时在原牌堆上累加物品和生物，旧场景的内容永远留着。

**修复**：`_play_discovery`改为进入新场景时：
1. 从抽牌堆移除所有物品牌（保留技能/形态/见闻牌）
2. 清空`unlocked_creature_counts`（放弃旧生物）
3. 只加入新场景的物品和生物

### 6.24 卡面字体加大 + 卡图尺寸扩大

**修改**：`combat.py`中`_render_card_placeholder`的卡图尺寸从120×180扩大到160×240，字体全部加大：
- 标题 14→18（粗体）、正文 9→12、描述 8→11
- 换行宽度 11→13、最多行数 7→8、行距 14→18
- 标题栏、费用圈、类型文字位置同步调整

### 6.25 手牌布局改为每行6张+竖向滚动

**修改**：`network.py`中`_build_card_grid`从单行12张改为多行布局（每行6张，共18槽位），滚动方向从水平改为竖向（`vertical_scroll_only=True`）。`MAX_HAND_BUTTONS` 12→18，新增`HAND_COLS=6`常量。

### 6.26 猫跑路见闻池耗尽时抽普通牌

**修改**：`_play_run_away`中，当`discovery_pool`耗尽后不再停止，改为调用`combat.draw_cards`从抽牌堆抽普通牌补足X-1张。

### 6.27 猫闯祸抽牌改回2张

**修改**：`_play_trouble`的`draw_cards`从1张改回2张，卡面描述同步更新。

### 6.28 见闻牌弃牌后消失

**现象**：见闻牌打出后弃掉，没回discovery_pool，导致猫跑路抽不到。

**根因**：弃牌时所有牌统一`draw_pile.append`，但见闻牌打出时从`discovery_pool`中pop掉了，弃牌后没回pool。

**修复**：弃牌时判断见闻牌（27-35），放回`discovery_pool`而非`draw_pile`。

### 6.29 猫跑路卡面描述补充

**修改**：卡面描述补充"见闻不够抽其他牌"。

### 6.30 生物卡面动态血量显示 + 被打反馈

**现象**：生物牌卡面血量是静态的，看不出当前剩余血量；被攻击后无视觉反馈。

**修复**：
1. `combat.py`新增`render_creature_card_with_hp`函数，在卡图右下角叠加红色圆形血量徽章。
2. `refresh_cards`中生物牌根据`creature_health`动态生成带当前血量的卡图。
3. `_damage_hand_creature`和`_damage_threat_creature`伤害后调用`_refresh_after_creature_damage`刷新手牌，血量变化即时可见。

### 6.31 见闻牌堆显示混乱

**现象**：打出郊区后牌堆查看器显示"郊区×2"，新解锁的影城/高墙/水道不显示。

**根因**：
1. 见闻牌(27)source_count=1，开局同时存在于`draw_pile`和`discovery_pool`，导致重复
2. 打出见闻牌后回到`draw_pile`（gameplay.py:274），应回`discovery_pool`
3. 牌堆查看器不显示`discovery_pool`内容

**修复**：
1. `slugcat_data.py`：见闻牌(27-35)排除出`SLUGCAT_INITIAL_DECK_COUNTS`，不再进入初始`draw_pile`，仅存在于`discovery_pool`
2. `gameplay.py`：打出见闻牌后回`discovery_pool`而非`draw_pile`
3. `network.py`：牌堆查看器新增"见闻牌堆"区域，显示`discovery_pool`内容
4. `slugcat.py`：`_unlock_adjacent_discovery`新解锁见闻加到pool顶端（`insert(0, ...)`）

### 6.32 趴下改版（数量、费用、效果）

**修改**：
1. `slugcat_data.py`：趴下(10)source_count 4→2，cost 1→0，描述改为"清除敏捷和动能；本回合猫闯祸生成的生物进入对方手牌。"
2. 效果逻辑已在`redirect_creatures_to_opponent`中实现（回合开始清零、猫闯祸根据标记选择目标玩家），只需更新日志措辞。

### 6.33 面条蝇免疫与血量混淆

**现象**：面条蝇(17)被1点伤害击杀（5血），正常应存活。免疫后第二次攻击直接秒杀。

**根因**：面条蝇免疫用`health_list[0] = -abs(health_list[0])`标记已用免疫，将血量改为负值（如5→-5）。第二次攻击时`health_list[0] > 0`为False，跳过免疫，直接`-5 - damage`，结果≤0被判定击杀。血量字段同时承担了"剩余血量"和"免疫标记"两个职责。

**修复**：新增独立字段`noodle_fly_immunity_used`（布尔值）跟踪每回合免疫使用情况，不再修改血量。`_on_turn_start`中重置该字段为`False`，替代原来的`abs()`血量恢复逻辑。

### 6.34 攻击日志顺序错误

**现象**：打出攻击牌时，伤害/免疫日志在攻击声明之前显示，如"对面条蝇造成1点伤害"出现在"玩家1使用钢筋攻击面条蝇"之前。

**根因**：`_play_attack`和`_play_bubble_fruit`中，攻击声明`announce`放在`_damage_hand_creature`/`_damage_threat_creature`调用之后。

**修复**：将攻击声明`announce`移到伤害结算函数调用之前，确保日志顺序为：攻击声明→伤害结果→死亡效果。

### 6.35 觅食饱食度计算偏低

**现象**：小面条(1血)和面条蝇(5血)先后死亡后觅食，仅获得1点饱食度，预期应为`ceil((5+1)/5)=2`。

**根因**：`_on_creature_death`中`last_dead_creature_health = base_health`用赋值覆盖，只记录最后一只死亡生物的血量（5），丢失了之前死亡生物的血量（1）。

**修复**：改为累加`last_dead_creature_health += base_health`，`_play_forage`计算后清零避免重复计算。`_play_white_pearl`的拾荒者交易同样改为累加。

### 6.36 见闻牌打着打着消失

**现象**：打几轮后`discovery_pool`里的见闻牌越来越少，尤其炸矛穿透后明显。

**根因**：至少 4 处将手牌弃回`draw_pile`时不区分卡牌类型，见闻牌(27-35)被误塞到`draw_pile`：
1. `_resolve_pending_discards`（炸矛随机弃牌，**最常见**）
2. `play_pack_god_card`（背包之神批量弃牌）
3. `play_burnt_offering_card`（燔祭批量弃牌）
4. `_receive_game_state_payload`中`pending_draw_returns`统一塞`draw_pile`（防御性遗漏）

`draw_pile`中的见闻牌无法被正常抽回（`_draw_slugcat_cards`只抽技能+物品，fallback跳过生物但可能抽不到），永久丢失。

**修复**：以上 4 处弃牌/回牌堆路径均改为分类路由：
- 见闻牌(27-35)且玩家为蛞蝓猫 → `player.special["discovery_pool"]`
- 其余 → `game_state.draw_pile`

### 6.37 炸矛随机弃牌不报牌名 + 立即生效

**原问题**：
1. 弃牌不报牌名，玩家不知道弃了什么
2. `_resolve_pending_discards`注册在`TURN_START`（抽牌之前），若上回合手牌打光（`hand_size=0`），循环不进入，`pending`被清零，**弃牌效果永久浪费**
3. 工作簿描述"穿透时...弃1张牌"应为当场生效，而非延迟到下回合

**修复**：
1. `_resolve_pending_discards`新增`announce`参数，每次弃牌后播报`随机弃掉：{卡名}`
2. 从`_on_turn_start`移除`_resolve_pending_discards`调用，改为在`_receive_game_state_payload`中**立即**执行——被打方接收状态后当场弃牌，不再等下回合
3. `_insert_explosive_spear`播报措辞从"需随机弃1张牌"改为"随机弃1张牌"
4. 弃掉的牌名仅本地显示（`colored_announce`），不泄露给对手

### 6.38 生物一致性修复与日志播报完善

**问题1：射线虫(18)重复加秃鹫**
- 原实现：`_on_creature_turn_end_hand`每回合结束加一只秃鹫 + `_on_creature_death`死亡时也加
- 描述只说"加入一张秃鹫"，应只触发一次
- **修正**：用户指出"回合结束加入秃鹫，所以射线虫死亡时不应该加，只有回合结束没死才加，但每次被移动都能再加一次"
- **最终修复**：
  - 恢复 `_on_creature_turn_end_hand` 中射线虫回合结束加秃鹫逻辑（存活才加）
  - 删除 `_on_creature_death` 中射线虫死亡时加秃鹫的逻辑（死了就不加）
  - 由于转移后在新持有者回合结束时再次触发，自然实现"每次被移动都能再加一次"

**问题2：拾荒者(25)携带物品不可见**
- 拾荒者伤害结算时播报`拾荒者携带{物品名}对玩家X造成Y点伤害`（已说明物品名）
- 但拾荒者死亡掉落物和白珍珠交易物只说"换来了拾荒者携带的物品"，不说明具体是什么
- **修复**：
  - 白珍珠交易和死亡掉落改为公开播报"换来了/掉落了携带的物品"，再用`colored_announce`本地显示具体物品名（保护手牌隐私）
  - `_creature_damage`中拾荒者伤害播报保留物品名（伤害事件是公开的）

**问题3：绿蜥蜴(20)觉醒无播报**
- 从静止→攻击的转换没有日志提示
- **修复**：觉醒时播报`绿蜥蜴苏醒，对玩家X造成5点伤害`

**问题4：秒杀播报与击杀播报混淆**
- `_kill_creature_at`调用`_on_creature_death`，后者播报"被击杀"
- 烟雾果秒杀蜈蚣时还额外播报"烟雾秒杀了烈焰蜈蚣"，与"被击杀"重复
- **修复**：`_on_creature_death`新增`cause`参数（默认"被击杀"），`_kill_creature_at`传`cause="被秒杀"`；删除烟雾果的重复播报

**问题5：`_add_creature_threat`无统一加入播报**
- **修复**：新增可选`announce`参数，传入时播报`{生物名}进入玩家X的威胁区`。现有调用点已有各自语境播报，不强制传入

**问题6：蜥蜴吃小面条播报不完整**
- 原播报"蜥蜴吃掉了小面条"未提及后续引来面条蝇
- **修复**：合并为`蜥蜴吃掉了小面条，引来面条蝇`

**问题7：闪光果转移目标不明确**
- 原播报"闪光果将{生物名}赶向对手"，"对手"不明确是哪个玩家
- **修复**：改为`闪光果将{生物名}赶向玩家{target_id}`

### 6.39 猫闯祸生物池Bug + 初始生物数量调整

**问题1：猫闯祸(15)无视见闻场景，从全生物(16-26)随机**
- 原代码 `creature_id = random.choice(SLUGCAT_CREATURE_IDS)`，每次都从11种生物里随机
- 导致开局就能抽到烈焰蜥蜴(23)、钢秃鹫(24)等后期生物，场景切换系统形同虚设
- **修复**：从 `player.special["unlocked_creature_counts"].keys()`（当前场景生物池）中随机
  - 开局（未打见闻）→ 从{16小面条, 20绿蜥蜴, 25拾荒者} 中随机
  - 进入工业郊区 → 从{25拾荒者, 18射线虫, 19秃鹫} 中随机
  - 进入阴影城堡 → 从{25拾荒者} 中随机
  - 进入断裂地窟 → 从{22烈焰蜈蚣, 23烈焰蜥蜴} 中随机
  - 空池 fallback：保底 {16, 20, 25}
- 注意：网络同步后dict key可能为str，用`int()`转换再查表

**问题2：初始生物数量过多**
- 原 `小面条×5`、`绿蜥蜴×5`，开局生物基础量太高
- **修复**：`slugcat_data.py` 中调整：
  - 小面条(16) source_count 5 → 2
  - 绿蜥蜴(20) source_count 5 → 3
- `unlocked_creature_counts` 初始化从 `spec.source_count` 生成，自动同步

### 6.40 lose_life 播报顺序+重复播报Bug

**现象**：回合结束结算时，日志出现 `玩家1失去2点生命` → `消耗1点业力重返雨中` → `2根钢筋使玩家1失去2点生命`，用户反馈"播报了失去生命但实际没效果"。

**根因1（时机错误）**：`lose_life`（combat.py#L404-408）先 `announce("玩家X失去N点生命")`，再扣血，再结算Karma回血。导致播报时还没结算Karma，等Karma回满血了实际没扣，播报已经输出了。

**根因2（重复播报）**：`_resolve_inserted_items`（slugcat.py#L813-814）先调 `lose_life`（之前也会播报"失去X点生命"），紧接着又自己播 `"N根钢筋使玩家X失去N点生命"` — 同样的扣血事件播报两次。

**根因3（非蛞蝓猫播报遗漏）**：`lose_life`里只有蛞蝓猫+有敏捷分支才播报"失去生命"，非蛞蝓猫角色完全没有这条播报。

**修复**：
1. **播报时机后置**：`lose_life`改为先扣血→再结算`resolve_slugcat_karma`→最后用`actual_loss = old_health - target.health`计算实际扣掉的生命值（如果karma回满了actual_loss=0，就不播报）。
2. **消除重复播报**：`_resolve_inserted_items`先说明原因 `"N根钢筋在体内造成流血"`，然后调一次`lose_life`由后者统一播报"失去X点生命"。删除旧的 `"N根钢筋使玩家X失去N点生命"` 重复播报。
3. **覆盖全角色**：合并分支逻辑，蛞蝓猫+有敏捷扣减播`（敏捷-N，剩余X）`后缀，其余走通用播报，非蛞蝓猫角色不再遗漏。

### 6.41 2血插2矛"播报了没扣血"的二次修正

**现象**（用户具体场景）：玩家1（蛞蝓猫）2血，体内插2根钢筋，回合结束钢筋流血应该致死。用户反馈"播报了失去2血、敏捷-2、消耗1点业力，但实际血量/敏捷/业力都没变"。

**根因**：6.40的修复把"失去生命"播报放在Karma回血**之后**，用`actual_loss = old_health - target.health`计算。
- 实际执行：2血扣2 → health=0 → Karma回满血=5 → actual_loss = 2-5 = **-3（负数）**
- 结果：`actual_loss <= 0` 判定命中，**整条"失去生命"播报被跳过**
- 用户同时没看到扣血提示，也可能误以为"没扣血"——但实际上health=0→health=5，UI从2变5（无中间态0），看起来确实"像没掉血"

**二次修正**（combat.py lose_life）：
1. **播报顺序调整**：先扣敏捷→扣血→**立即播报"失去X点生命（敏捷-Y，剩余Z）"**→再结算Karma回血播报。用户先看到死亡威胁，再看到业力救回，两条播报的先后不再混淆。
2. **播报数值改用amount**：生命值播报用`amount`（蜈蚣免伤后的效果值），不再扣完Karma反算net。
3. **敏捷播报用快照**：保存`final_agility`局部变量播报，避免播报时访问`target.special["agility"]`读到未定义/被后续代码覆盖。
4. **赋值正确性确认**：`target = game_state.players[target_player_id]`是引用，直接修改`.health`/`.special["agility"]`/`resolve_slugcat_karma`里的`.special["karma"]`——所有赋值都直接改动`game_state`数据，无本地copy导致失效问题。

### 6.42 电矛拔出后下回合仍减力量

**现象**：玩家拔出电矛后，下一回合开始时仍然被扣除力量；电矛卡面也未说明持续扣力量效果。

**根因**：拔出电矛时仅减少了`embedded_electric_spears`计数，但：
1. 本回合开始时已扣减的力量（`spears * 2`）未立即恢复，`electric_penalty_this_turn`也未同步更新。若有多根电矛，回合结束按原始`electric_penalty_this_turn`全额恢复会导致数值错乱。
2. 卡面描述（电矛5/电矛【插入】50）未说明"每回合开始力量-2/根"及"拔出后失效"，玩家无法理解持续效果。

**修复**（slugcat.py `_play_attack` 拔出分支）：
1. 拔出电矛(card_id==50)时，立即恢复2点力量（对应拔出的那根电矛），并将`electric_penalty_this_turn`减2。多根电矛场景下，回合结束只恢复剩余部分的惩罚，数值精确。
2. 卡面描述更新：电矛(5)补充"每回合开始使其力量-2/根，拔出后失效"；电矛【插入】(50)补充"每回合开始力量-2/根。耗能1拔出返回牌堆，并恢复本回合扣减的力量"。

### 6.43 见闻牌打出后耗能堆叠折扣 + 管虫改效果

**需求**：
1. 每张见闻牌打出后，后续见闻牌成本-1（堆叠）。卡面能量数字实时变化，弃掉见闻牌不触发折扣。
2. 管虫（26）效果改为：在场时见闻牌不占手牌位（不计入手牌上限4）。

**设计思路**：
- 新增 `discovery_discount` 字典（按见闻牌card_id独立计数，**不共通**：打出27只让27下次便宜，不影响28/29等），回合开始清空，每成功打出一张见闻牌该card_id计数+1，`_effective_cost` 中成本 `max(0, base - 该card_id计数)`。
- `_render_card_placeholder` 支持 `effective_cost` 覆盖参数，折扣时成本圈和数字变绿色。`refresh_cards` 对见闻牌计算实际成本，若与卡面不同则重渲染动态图。
- 弃牌阶段改为 `effective_hand_size_for_limit(game_state)`：若手牌含管虫(26)，见闻牌不计入超牌判定和手牌上限显示。UI手牌数量当有效≠总时以 `有效/总` 双格式显示。

**改动文件**：
- `slugcat_data.py`：管虫（26）描述改为 `"1点生命；在场时见闻牌不占手牌位（不计入手牌上限4）。"`。
- `slugcat.py`：
  - `initialize_slugcat_player` 初始化 `"discovery_discount": {}`（按card_id计数的字典）；
  - `_on_turn_start` 回合开始清空 `discovery_discount`；
  - `_effective_cost` 移除旧 `管虫在场见闻-1` 逻辑，改为按card_id查询 `discovery_discount[card_id]` 扣减；
  - `play_slugcat_card` 见闻牌成功打出后 `discovery_discount[card_id] += 1`；
  - 新增 `effective_hand_size_for_limit` / `get_displayed_hand_count` 工具函数。
- `combat.py`：`_render_card_placeholder` 新增 `effective_cost` 参数，折扣时用 `#2E7D32`（深绿）绘制成本圈和数字；新增公共封装 `render_card_with_effective_cost`。
- `network.py`：
  - `refresh_status` 手牌数量显示：管虫在场时显示 `有效/总`，否则纯数字；
  - `refresh_cards` 见闻牌成本与卡面不一致时调用 `render_card_with_effective_cost` 动态渲染。
- `gameplay.py`：弃牌阶段超牌判定、达标判定、提示都使用 `effective_hand_size_for_limit`。

### 6.44 插入钢筋"有播报无数值"+弃牌随机性循环

**问题1 现象**：被插入钢筋（或生物死亡）后，对方能看到"X根钢筋在体内造成流血"、"玩家失去X点生命"、"敏捷减伤Y点"等文本播报，但血量和敏捷面板完全没变化。

**问题1 根因**：`play_active_turn` 的 `TURN_END` 阶段结算 `_resolve_inserted_items`（钢筋流血）、`_resolve_creatures`（生物伤害等）时，通过 `announce → send_announcement` 发送了文本，但 `play_active_turn` 返回后、`signal_turn_change` 之前**没有调用 `send_game_state`**。对端看到了文字，但血量/敏捷/special数据都没同步，数值显示"原封不动"——表现就是"播报完全对，但是没效果"。打出牌阶段每次出牌后都有send_game_state同步，唯独TURN_END结算后漏掉了这一步。

**问题1 修复**（`server.py` / `client.py`）：在 `play_active_turn` 结束、`signal_turn_change` 之前调用 `refresh_status` + `send_game_state` 同步TURN_END结算过的完整数值。

---

**问题2 现象**：弃2技能+1物品（或类似组合）后，下一回合抽牌刚好又把这3张抽回来，牌堆毫无随机性可言。

**问题2 根因**：
- 牌堆返回位置：弃牌、打出牌全部 `draw_pile.append(card_id)` → 放在牌堆**顶部**（末尾）。
- 抽牌逻辑：`_draw_slugcat_cards` 中的 `_pick` 从牌堆**末尾倒序**扫描（`range(len(pile)-1, -1, -1)`），匹配到技能/物品就 `pop(idx)`（优先抽最新的）。
- 结果：上回合刚弃/刚打的牌在顶部，`_pick` 又优先从末尾抽 → 弃2技能+1物品 = 抽2技能+1物品的配额刚好命中刚弃的3张 → 循环复用。

**问题2 修复**：所有"刚用完的牌"统一放回牌堆**底部**（`draw_pile.insert(0, card_id)` / `discovery_pool.insert(0, card_id)`），而"获得新牌"语义的场景继续保留顶部append：

| 位置 | 场景 | 放回位置 |
|------|------|----------|
| `gameplay.py _run_discard_phase` | 弃牌阶段弃牌（含见闻牌） | 插底 `insert(0, x)` |
| `gameplay.py on_select` 出牌 | 打出非exhausted牌（含见闻牌） | 插底 `insert(0, x)` |
| `slugcat.py _resolve_pending_discards` | 炸矛随机弃牌 | 插底 `insert(0, x)` |
| `combat.py 背包之神` / `燔祭` | 主动弃牌效果 | 插底 `insert(0, x)` |
| `combat.py play_black_flash_card` | 黑闪打出的牌用完返回 | 插底 `insert(0, x)` |
| `slugcat.py 拔出钢筋/电矛`（L272） | 拔出后普通版返回牌堆（获得可再次使用的新牌） | 顶部 append（保持不变） |
| `slugcat.py _on_creature_death`（L1262） | 生物死亡返回所有者牌堆 | 顶部 append（保持不变） |
| `protocol.py pending_draw_returns`（L248） | 对端生物转移返回牌堆 | 顶部 append（保持不变） |
| `slugcat.py 效果加入牌堆`（如L913） | 秃鹫等通过效果加入牌堆 | 顶部 append（保持不变） |

