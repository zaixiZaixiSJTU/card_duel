"""Static card data for the Slugcat character.

The source of truth is ``工作簿1_规范修订版.xlsx``.  Keeping the textual
rules here separate from effect code makes later balance edits auditable.
"""

from dataclasses import dataclass


SLUGCAT_CHARACTER_ID = 4


@dataclass(frozen=True)
class SlugcatCardSpec:
    card_id: int
    name: str
    card_type: str
    source_count: int
    cost: int | None
    description: str
    exhausted: bool = False


SLUGCAT_CARD_SPECS = (
    SlugcatCardSpec(1, "一根钢筋", "物品", 20, 1, "造成2点伤害并转换动能；穿透时插入目标。"),
    SlugcatCardSpec(2, "一块石子", "物品", 10, 0, "造成1点伤害并转换动能。"),
    SlugcatCardSpec(3, "炸药", "物品", 3, 1, "造成10点伤害，随后自己受到5点伤害。"),
    SlugcatCardSpec(4, "炸矛", "物品", 3, 2, "造成3点伤害并转换动能；穿透时额外失去10点生命并弃1张牌。"),
    SlugcatCardSpec(5, "电矛", "物品", 1, 2, "造成3点伤害并转换动能；穿透时插入对手体内，每回合开始使其力量-2/根，拔出后失效。"),
    SlugcatCardSpec(6, "猫猫小跳", "技能", 6, 0, "获得1点敏捷；下一张矛或石子再获得1点敏捷。"),
    SlugcatCardSpec(7, "脊背大跳", "技能", 4, 2, "获得3点敏捷；紧接翻滚或滑铲时耗能-1。"),
    SlugcatCardSpec(8, "一个滑铲", "技能", 3, 1, "获得4点动能。"),
    SlugcatCardSpec(9, "翻滚", "技能", 4, 0, "要求敏捷至少2；敏捷+2后全部转换为动能。"),
    SlugcatCardSpec(10, "趴下", "技能", 2, 0, "清除敏捷和动能；本回合猫闯祸生成的生物进入对方手牌。"),
    SlugcatCardSpec(11, "猫会后空翻", "技能", 3, 2, "获得4点动能和2点敏捷。"),
    SlugcatCardSpec(12, "猫睡觉", "技能", 6, 1, "消耗3点饱食度，获得1点业力。"),
    SlugcatCardSpec(13, "猫觅食", "技能", 8, 0, "按最近死亡生物生命值的五分之一获得饱食度，向上取整。抽1张牌。"),
    SlugcatCardSpec(14, "猫跑路了", "技能", 8, None, "清除手牌生物，耗尽全部能量，抽X-1张见闻牌（见闻不够抽其他牌）。"),
    SlugcatCardSpec(15, "猫闯祸", "技能", 3, 2, "将1只随机生物加入自己的手牌。抽2张牌。"),
    SlugcatCardSpec(16, "小面条", "生物", 2, 0, "1血。0费转移到别人的手牌并耗能+1，否则死亡。死亡时加入一张面条蝇。会和手牌中的蜥蜴一起消失。", True),
    SlugcatCardSpec(17, "面条蝇", "生物", 0, None, "5血。造成5伤害。每回合免疫1次攻击，不可打出。", True),
    SlugcatCardSpec(18, "射线虫", "生物", 0, 1, "1血。1费转移到别人的手牌。加入一张秃鹫。", True),
    SlugcatCardSpec(19, "秃鹫", "生物", 0, 2, "15血。场上有生物死亡或2费打出。造成10伤害。", True),
    SlugcatCardSpec(20, "绿蜥蜴", "生物", 3, 2, "10血。静止一回合才会造成5伤。2费打出。", True),
    SlugcatCardSpec(21, "金蜥蜴", "生物", 0, 1, "6血。造成3伤害。1费打出。", True),
    SlugcatCardSpec(22, "烈焰蜈蚣", "生物", 0, 1, "共享20血。1费打出。存活时在目前场上烈焰蜈蚣较多的角色手牌中加入一张，每张可免伤一次。手牌中数量≥3时造成15伤害。", True),
    SlugcatCardSpec(23, "烈焰蜥蜴", "生物", 0, None, "20血。造成10伤害，可1费避免。每次被攻击反伤3。不可打出。", True),
    SlugcatCardSpec(24, "钢秃鹫", "生物", 0, 3, "30点生命；可转移，随后造成15点伤害。", True),
    SlugcatCardSpec(25, "拾荒者", "生物", 3, None, "5点生命；随机携带物品并对持有者使用，不可打出。", True),
    SlugcatCardSpec(26, "管虫", "生物", 0, 0, "1点生命；在场时见闻牌不占手牌位（不计入手牌上限4）。", True),
    SlugcatCardSpec(27, "工业郊区", "见闻", 1, 2, "加入拾荒者、射线虫、秃鹫、泡水果和矛类物品。"),
    SlugcatCardSpec(28, "阴影城堡", "见闻", 0, 2, "加入拾荒者、珍珠、闪光果、炸矛和炸药。"),
    SlugcatCardSpec(29, "高墙绝壁", "见闻", 0, 2, "加入金蜥蜴、秃鹫和管虫。"),
    SlugcatCardSpec(30, "天空群岛", "见闻", 0, 2, "加入小面条、金蜥蜴、秃鹫、珍珠和炸矛。"),
    SlugcatCardSpec(31, "断裂地窟", "见闻", 0, 2, "加入烈焰蜈蚣和烈焰蜥蜴。"),
    SlugcatCardSpec(32, "水道迷宫", "见闻", 0, 2, "加入泡水果和有色珍珠。"),
    SlugcatCardSpec(33, "农场阵列", "见闻", 0, 2, "加入拾荒者、小面条、烟雾果和矛类物品。"),
    SlugcatCardSpec(34, "外层空间", "见闻", 0, 2, "加入多种生物、果实、炸药、矛和珍珠。"),
    SlugcatCardSpec(35, "沉没巨构", "见闻", 0, 2, "加入钢秃鹫、质量稀释电池和有色珍珠。"),
    SlugcatCardSpec(36, "猎手", "形态", 1, 0, "切换为猎手形态。", True),
    SlugcatCardSpec(37, "波浪舞者", "形态", 1, 0, "切换为波浪舞者形态。", True),
    SlugcatCardSpec(38, "混沌胃袋", "形态", 1, 0, "切换为混沌胃袋形态。", True),
    SlugcatCardSpec(39, "三 重 肯 定", "形态", 1, 0, "切换为三重肯定形态。", True),
    SlugcatCardSpec(40, "涟漪编织者", "形态", 1, 0, "切换为涟漪编织者形态。", True),
    SlugcatCardSpec(41, "烟雾果", "物品", 0, 0, "免疫下一次受到的攻击；可直接击杀烈焰蜈蚣。"),
    SlugcatCardSpec(42, "蝠蝇草", "物品", 5, 0, "留在手牌中时，每回合获得2点饱食度。"),
    SlugcatCardSpec(43, "闪光果", "物品", 0, 1, "转移生物；对玩家使用时限制其接下来两张攻击牌。"),
    SlugcatCardSpec(44, "蓝果", "物品", 10, 0, "获得1点饱食度。"),
    SlugcatCardSpec(45, "泡水果", "物品", 0, 0, "选择视为蓝果或石子使用。"),
    SlugcatCardSpec(46, "白珍珠", "物品", 3, 0, "吸引拾荒者；对拾荒者使用时获得其携带物。"),
    SlugcatCardSpec(47, "有色珍珠", "物品", 0, 0, "吸引拾荒者；对拾荒者使用时雇佣它。"),
    SlugcatCardSpec(48, "质量稀释电池", "物品", 0, 4, "立即获得99点敏捷。"),
    # 49/50 插入物：独立卡牌ID，完全避免与普通钢筋/电矛（1/5）以及形态卡（36-40）混淆。
    # 仅通过插入效果加入手牌，不在任何牌堆中。耗能1拔出（参照工作簿原版描述）。
    SlugcatCardSpec(49, "钢筋【插入】", "物品", 0, 1, "对手插入体内的钢筋。耗能1拔出，返回对方牌堆。不可弃牌。", True),
    SlugcatCardSpec(50, "电矛【插入】", "物品", 0, 1, "插入体内的电矛。每回合开始力量-2/根。耗能1拔出返回牌堆，并恢复本回合扣减的力量。不可弃牌。", True),
)

SLUGCAT_SPECS_BY_ID = {spec.card_id: spec for spec in SLUGCAT_CARD_SPECS}

# 初始牌组直接从 source_count 生成：source_count > 0 的牌一开始就在牌堆中，
# source_count == 0 的牌需要通过见闻解锁后才加入。
# 排除规则：
#   - 生物牌（16-26）不进入初始牌堆——仅通过见闻解锁或卡牌效果加入。
#   - 插入物（49-50）永不进入初始/返回牌堆/抽牌堆——仅通过插入效果临时加入手牌。
SLUGCAT_INITIAL_DECK_COUNTS = {
    spec.card_id: spec.source_count
    for spec in SLUGCAT_CARD_SPECS
    if spec.source_count > 0
    and not (16 <= spec.card_id <= 26)  # 排除生物
    and not (27 <= spec.card_id <= 35)  # 排除见闻（仅存在于discovery_pool）
    and spec.card_id not in (49, 50)     # 排除插入物
}

SLUGCAT_CREATURE_IDS = tuple(range(16, 27))
SLUGCAT_INSERTED_IDS = (49, 50)  # 插入的钢筋/电矛，独立ID不与普通1/5或形态卡36-40混淆
SLUGCAT_DISCOVERY_IDS = tuple(range(27, 36))
SLUGCAT_FORM_IDS = tuple(range(36, 41))
SLUGCAT_ATTACK_ITEM_IDS = (1, 2, 3, 4, 5)  # 普通攻击物品，不包含插入版本
# 不可弃的卡牌：生物（16-26）+ 插入物（49-50）
SLUGCAT_NO_DISCARD_IDS = tuple(range(16, 27)) + SLUGCAT_INSERTED_IDS

# Base health for each creature type (per workbook).
CREATURE_BASE_HEALTH = {
    16: 1,   # 小面条
    17: 5,   # 面条蝇
    18: 1,   # 射线虫
    19: 15,  # 秃鹫
    20: 10,  # 绿蜥蜴
    21: 6,   # 金蜥蜴
    22: 20,  # 烈焰蜈蚣（共享）
    23: 20,  # 烈焰蜥蜴
    24: 30,  # 钢秃鹫
    25: 5,   # 拾荒者
    26: 1,   # 管虫
}

# Lizard IDs that eat noodles (per workbook: 小面条会和蜥蜴一起消失).
LIZARD_IDS = (20, 21)

DISCOVERY_CONTENTS = {
    27: {25: 5, 18: 3, 19: 1, 45: 5, 3: 1, 4: 1, 5: 1},
    28: {25: 5, 47: 1, 43: 10, 4: 3, 3: 3},
    29: {21: 5, 19: 3, 26: 3},
    30: {16: 3, 21: 5, 19: 1, 47: 1, 4: 3},
    31: {22: 1, 23: 2},
    32: {45: 10, 47: 1},
    33: {25: 3, 16: 3, 41: 10, 4: 3, 5: 3},
    34: {16: 3, 25: 5, 22: 1, 41: 5, 43: 5, 3: 5, 4: 3, 5: 3, 47: 2},
    35: {24: 5, 48: 1, 47: 1},
}

DISCOVERY_ADJACENCY = {
    27: (28, 29, 32),
    28: (27,),
    29: (27, 30),
    30: (29, 33),
    31: (33, 34, 35),
    32: (27, 31),
    33: (30, 31),
    34: (31,),
    35: (31,),
}

FORM_NAMES = {card_id: SLUGCAT_SPECS_BY_ID[card_id].name for card_id in SLUGCAT_FORM_IDS}
