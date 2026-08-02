"""验证攻击目标选择和生物显示相关数据。"""
import sys, os
sys.path.insert(0, r'c:\Users\79420\Desktop\card_duel')
os.chdir(r'c:\Users\79420\Desktop\card_duel')

from card_duel.core.combat import NetworkGameState
from card_duel.cards.registry import initialize_player
from card_duel.cards.slugcat import (
    initialize_slugcat_player,
    get_attack_targets,
    _add_creature_to_hand,
)
from card_duel.cards.slugcat_data import (
    SLUGCAT_SPECS_BY_ID, SLUGCAT_CREATURE_IDS, SLUGCAT_CHARACTER_ID,
)

# 构造双方玩家
gs = NetworkGameState()
gs.local_player_id = 1
gs.character_ids[1] = 1  # 战士（攻击者）
gs.character_ids[2] = SLUGCAT_CHARACTER_ID  # 蛞蝓猫（被攻击者）
gs.players[1].name = "玩家1"
gs.players[2].name = "玩家2"
initialize_player(gs, 1)
initialize_slugcat_player(gs, 2)

print("=== 初始化后，玩家2（蛞蝓猫）的 special 关键数据 ===")
p2 = gs.players[2]
print("character_ids:", gs.character_ids)
print("unlocked_creature_counts:", p2.special.get("unlocked_creature_counts", "MISSING!"))
print("creature_health:", p2.special.get("creature_health", "MISSING!"))

# 给玩家2加一个手牌生物：面条蝇 17
print("\n=== 给玩家2加一只面条蝇到手牌 ===")
_add_creature_to_hand(gs, 2, 17, owner_id=2)
print("玩家2 creature_health:", p2.special.get("creature_health", {}))

# 模拟网络序列化：dict key变成str
import json
sync_special = json.loads(json.dumps(p2.special))
p2.special.update(sync_special)
print("序列化后 creature_health:", p2.special.get("creature_health", {}))
print("序列化后 creature_health 的key类型:", [type(k) for k in p2.special.get("creature_health", {}).keys()])

# 调用 get_attack_targets
print("\n=== 调用 get_attack_targets(gs, 2) ===")
targets = get_attack_targets(gs, 2)
print("targets:", targets)
print("len(targets):", len(targets), " -> 弹窗吗？", "是" if len(targets) > 1 else "否")
