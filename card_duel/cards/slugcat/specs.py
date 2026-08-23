"""Static card data for the Slugcat character.

The source of truth is ``docs/工作簿1.xlsx``.  Keeping the textual
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
    SlugcatCardSpec(
        1, "一根钢筋", "物品", 20, 1, "造成2点伤害并转换动能；穿透时插入目标。"
    ),
    SlugcatCardSpec(2, "一块石子", "物品", 10, 0, "造成1点伤害并转换动能。"),
    SlugcatCardSpec(
        3, "炸药", "物品", 3, 1, "造成10点伤害，随后自己受到5点伤害。", exhausted=True
    ),
    SlugcatCardSpec(
        4,
        "炸矛",
        "物品",
        3,
        2,
        "造成3点伤害并转换动能；穿透时额外失去10点生命并弃1张牌。",
        exhausted=True,
    ),
    SlugcatCardSpec(
        5,
        "电矛",
        "物品",
        1,
        2,
        "造成3点伤害并转换动能；穿透时插入，每回合开始力量-2/根。",
        exhausted=True,
    ),
    SlugcatCardSpec(
        6, "猫猫小跳", "技能", 6, 0, "获得1点敏捷；下一张矛或石子再获得1点敏捷。"
    ),
    SlugcatCardSpec(
        7, "脊背大跳", "技能", 4, 2, "获得3点敏捷；紧接翻滚或滑铲时耗能-1。"
    ),
    SlugcatCardSpec(8, "一个滑铲", "技能", 3, 1, "获得4点动能。"),
    SlugcatCardSpec(9, "翻滚", "技能", 4, 0, "要求敏捷至少2；敏捷+2后全部转换为动能。"),
    SlugcatCardSpec(
        10,
        "趴下",
        "技能",
        2,
        0,
        "清除敏捷和动能；本回合猫闯祸生成的生物进入对方手牌。",
    ),
    SlugcatCardSpec(11, "猫会后空翻", "技能", 3, 2, "获得4点动能和2点敏捷。"),
    SlugcatCardSpec(12, "猫睡觉", "技能", 6, 1, "消耗3点饱食度，获得1点业力。"),
    SlugcatCardSpec(
        13,
        "猫觅食",
        "技能",
        8,
        0,
        "按最近死亡生物生命值的五分之一获得饱食度，向上取整。抽1张牌。",
    ),
    SlugcatCardSpec(
        14,
        "猫跑路了",
        "技能",
        8,
        None,
        "清除手牌生物，耗尽全部能量，抽X-1张见闻牌；见闻不足则抽普通牌。",
    ),
    SlugcatCardSpec(15, "猫闯祸", "技能", 3, 2, "从当前场景加入1只随机生物。抽2张牌。"),
    SlugcatCardSpec(
        16,
        "小面条",
        "生物",
        2,
        0,
        "1点生命；转移后使其后续打出耗能+1，否则死亡。",
        True,
    ),
    SlugcatCardSpec(
        17,
        "面条蝇",
        "生物",
        0,
        None,
        "5点生命，造成5点伤害；每回合免疫首次攻击且不可打出。",
        True,
    ),
    SlugcatCardSpec(
        18, "射线虫", "生物", 0, 1, "1点生命；可转移，回合结束时引来秃鹫。", True
    ),
    SlugcatCardSpec(19, "秃鹫", "生物", 0, 2, "15点生命；打出后造成10点伤害。", True),
    SlugcatCardSpec(
        20, "绿蜥蜴", "生物", 3, 2, "10点生命；静止一回合后造成5点伤害。", True
    ),
    SlugcatCardSpec(21, "金蜥蜴", "生物", 0, 1, "6点生命；造成3点伤害。", True),
    SlugcatCardSpec(
        22, "烈焰蜈蚣", "生物", 0, 1, "共享20点生命；三张以上时造成15点伤害。", True
    ),
    SlugcatCardSpec(
        23,
        "烈焰蜥蜴",
        "生物",
        0,
        None,
        "20点生命；回合结束时造成10点伤害，受攻击时反伤3，不可打出；"
        "每回合可支付1点能量避免本回合伤害。",
        True,
    ),
    SlugcatCardSpec(
        24, "钢秃鹫", "生物", 0, 3, "30点生命；可转移，随后造成15点伤害。", True
    ),
    SlugcatCardSpec(
        25,
        "拾荒者",
        "生物",
        3,
        None,
        "5点生命；随机携带物品并对持有者使用，不可打出。",
        True,
    ),
    SlugcatCardSpec(
        26, "管虫", "生物", 0, 0, "1点生命；在场时见闻牌不占手牌上限。", True
    ),
    SlugcatCardSpec(
        27, "工业郊区", "见闻", 1, 2, "加入拾荒者、射线虫、秃鹫、泡水果和矛类物品。"
    ),
    SlugcatCardSpec(
        28, "阴影城堡", "见闻", 0, 2, "加入拾荒者、珍珠、闪光果、炸矛和炸药。"
    ),
    SlugcatCardSpec(29, "高墙绝壁", "见闻", 0, 2, "加入金蜥蜴、秃鹫和管虫。"),
    SlugcatCardSpec(
        30, "天空群岛", "见闻", 0, 2, "加入小面条、金蜥蜴、秃鹫、珍珠和炸矛。"
    ),
    SlugcatCardSpec(31, "断裂地窟", "见闻", 0, 2, "加入烈焰蜈蚣和烈焰蜥蜴。"),
    SlugcatCardSpec(32, "水道迷宫", "见闻", 0, 2, "加入泡水果和有色珍珠。"),
    SlugcatCardSpec(
        33, "农场阵列", "见闻", 0, 2, "加入拾荒者、小面条、烟雾果和矛类物品。"
    ),
    SlugcatCardSpec(
        34, "外层空间", "见闻", 0, 2, "加入多种生物、果实、炸药、矛和珍珠。"
    ),
    SlugcatCardSpec(
        35, "沉没巨构", "见闻", 0, 2, "加入钢秃鹫、质量稀释电池和有色珍珠。"
    ),
    SlugcatCardSpec(36, "猎手", "形态", 0, 4,
                    "三种矛伤+2；手牌上限+1。"
                    "解锁：用过三种矛杀死过生物后加入。", True),
    SlugcatCardSpec(37, "波浪舞者", "形态", 0, 4,
                    "每回合打出的第一张技能牌回到手牌。"
                    "解锁：迷宫水道达到6敏捷加入。", True),
    SlugcatCardSpec(38, "混沌胃袋", "形态", 0, 4,
                    "每回合开始时弃1抽1；获得上回合剩余能量数×2的动能。"
                    "解锁：3次觅食获得饱食后加入。", True),
    SlugcatCardSpec(39, "三 重 肯 定", "形态", 0, 4,
                    "每回合获得（锁定层数+1）张超度；受伤时锁定层数-1。"
                    "解锁：业力上限为10时加入。", True),
    SlugcatCardSpec(40, "观望者", "形态", 0, 4,
                    "所有生物牌可不耗能打出，移入对方生物牌堆。"
                    "解锁：连续三回合跑过路加入。", True),
    SlugcatCardSpec(
        41, "烟雾果", "物品", 0, 0, "免疫下一次受到的攻击；可直接击杀烈焰蜈蚣。"
    ),
    SlugcatCardSpec(42, "蝠蝇草", "物品", 5, 0, "留在手牌中时，每回合获得2点饱食度。"),
    SlugcatCardSpec(
        43, "闪光果", "物品", 0, 1, "转移生物；对玩家使用时限制其接下来两张攻击牌。"
    ),
    SlugcatCardSpec(44, "蓝果", "物品", 10, 0, "获得1点饱食度。"),
    SlugcatCardSpec(45, "泡水果", "物品", 0, 0, "选择视为蓝果或石子使用。"),
    SlugcatCardSpec(
        46, "白珍珠", "物品", 3, 0, "吸引拾荒者；对拾荒者使用时获得其携带物。"
    ),
    SlugcatCardSpec(47, "有色珍珠", "物品", 0, 0, "吸引拾荒者；对拾荒者使用时雇佣它。"),
    SlugcatCardSpec(48, "质量稀释电池", "物品", 0, 4, "立即获得99点敏捷。"),
    SlugcatCardSpec(
        49,
        "钢筋【插入】",
        "物品",
        0,
        1,
        "耗能1拔出体内钢筋；普通钢筋返回原主人的牌堆。不可弃牌。",
        True,
    ),
    SlugcatCardSpec(
        50,
        "电矛【插入】",
        "物品",
        0,
        1,
        "耗能1拔出电矛并恢复本回合对应的力量；电矛消耗，不返还。不可弃牌。",
        True,
    ),
    SlugcatCardSpec(
        51, "业力花", "物品", 0, 1, "下次复活不掉业力。", True
    ),
    SlugcatCardSpec(
        52, "僧侣", "形态", 0, 4,
        "业力下降时获得1张业力花（物品，耗能1：下次复活不掉业力）。"
        "解锁：手牌中的蜥蜴吃掉小面条后加入。", True,
    ),
    SlugcatCardSpec(
        55, "棘刺信使", "形态", 0, 4,
        "每回合获得一张骨矛（物品，相当于矛，造成血量损失时饱食+1）。"
        "解锁：在天空群岛打出一颗彩色珍珠后加入。", True,
    ),
    SlugcatCardSpec(
        56, "爆炸工匠", "形态", 0, 4,
        "有饱食时，矛/石子消耗1点饱食视为炸矛/炸弹，炸药不再自伤。"
        "解锁：击杀5只拾荒者后加入。", True,
    ),
    SlugcatCardSpec(58, "超度", "技能", 0, 2, "锁定层数+1；层数为5时超度对方。"),
    SlugcatCardSpec(
        61, "骨矛", "物品", 0, 2,
        "相当于矛，造成血量损失时饱食+1。", True
    ),
)

SLUGCAT_SPECS_BY_ID = {spec.card_id: spec for spec in SLUGCAT_CARD_SPECS}

# The initial deck contains every authored source card except creatures,
# discoveries, and temporary inserted cards.  Creatures/discoveries have their
# own pools and must never be reached by an ordinary draw.
SLUGCAT_INITIAL_DECK_COUNTS = {
    spec.card_id: spec.source_count
    for spec in SLUGCAT_CARD_SPECS
    if spec.source_count > 0
    and spec.card_type != "形态"
    and not 16 <= spec.card_id <= 35
    and spec.card_id not in (49, 50)
}

SLUGCAT_CREATURE_IDS = tuple(range(16, 27))
SLUGCAT_INSERTED_IDS = (49, 50)
SLUGCAT_DISCOVERY_IDS = tuple(range(27, 36))
SLUGCAT_FORM_IDS = (36, 37, 38, 39, 40, 52, 55, 56)
SLUGCAT_SPEAR_IDS = (4, 5, 61)
SLUGCAT_ATTACK_ITEM_IDS = (1, 2, 3, 4, 5)
SLUGCAT_NO_DISCARD_IDS = SLUGCAT_CREATURE_IDS + SLUGCAT_INSERTED_IDS
ABILITY_CARD_IDS = (*SLUGCAT_FORM_IDS, 51)
NO_KARMA_DISCOVERY_IDS = (27, 32, 34)

ABILITY_UNLOCK_CONDITIONS = {
    36: "用过三种矛杀死过生物后加入",
    37: "迷宫水道达到6敏捷加入",
    38: "3次觅食获得饱食后加入",
    39: "业力上限为10时加入",
    40: "连续三回合跑过路加入",
    52: "手牌中的蜥蜴吃掉小面条后加入",
    55: "在天空群岛打出一颗彩色珍珠后加入",
    56: "击杀5只拾荒者后加入",
}

CREATURE_BASE_HEALTH = {
    16: 1,
    17: 5,
    18: 1,
    19: 15,
    20: 10,
    21: 6,
    22: 20,
    23: 20,
    24: 30,
    25: 5,
    26: 1,
}

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

FORM_NAMES = {
    card_id: SLUGCAT_SPECS_BY_ID[card_id].name for card_id in SLUGCAT_FORM_IDS
}


def discovery_karma_gain(card_id: int, first_growth: bool) -> int:
    """Excluded scenes grant nothing; the first growth is +2, then +1."""
    if card_id in NO_KARMA_DISCOVERY_IDS:
        return 0
    return 2 if first_growth else 1
