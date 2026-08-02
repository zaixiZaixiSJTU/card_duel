"""Combat state, common calculations, resources, and card effect handlers."""

import base64
import io
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

import FreeSimpleGUI as sg
from PIL import Image, ImageDraw, ImageFont

from card_duel.core.characters import CHARACTER_NAMES


# ============================================================
# Constants
# ============================================================
IMAGE_SIZE = (160, 240)
CHARACTERS = ["未选择", *(CHARACTER_NAMES[index] for index in sorted(CHARACTER_NAMES))]

# ============================================================
# Game Classes
# ============================================================
@dataclass
class CharacterState:
    """Mutable combat values for one player."""

    health: int = 30
    energy: int = 0
    defence: int = 0
    strength: int = 0
    poison: int = 0
    special: dict[str, object] = field(
        default_factory=lambda: {
            "sacrifice": 0,
            "bastion": 0,
            "heartlink": 0,
        }
    )


@dataclass
class ScheduledEvent:
    """A delayed combat effect waiting on the shared timeline."""

    turns_remaining: int = 1
    effect_type: int = 0
    amount: int = 0
    target_player_id: int = 0
    message: str | None = None

    def __post_init__(self):
        if self.message is None:
            self.message = (
                f"玩家{self.target_player_id}的{self.effect_type}类数值"
                f"增加{self.amount}"
            )


@dataclass
class DefenceEffect:
    """A defence amount that expires after a number of turns."""

    turns_remaining: int = 1
    amount: int = 0

    def to_dict(self):
        return {
            "turns_remaining": self.turns_remaining,
            "amount": self.amount,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            turns_remaining=data["turns_remaining"],
            amount=data["amount"],
        )


class NetworkGameState:
    """All mutable state shared by the network game and its UI."""

    def __init__(self):
        self.players = {1: CharacterState(), 2: CharacterState()}
        self.hand_cards = [0] * 999
        self.hand_size = 0
        self.draw_pile = []
        self.defences = {1: [], 2: []}
        self.timeline = []
        self.character_ids = {1: None, 2: None}
        self.card_images = []
        self.peer_card_images = []
        self.window = None
        self.connection = None
        self.game_over = False
        self.max_card_id = 0
        self.local_player_id = 1
        self.round_number = 0
        self.active_player_id = None
        self.current_phase = None
        # Unified card-click interaction state.
        self.pending_arm_index = None
        self.card_selection_callback = None
        self.selection_mode_name = ""
        # Previous numeric values for change-flash feedback.
        self._prev_values = {1: {}, 2: {}}
        # Cached thumbnails for played-card slots.
        self._local_slot_thumbs = {}
        self._peer_slot_thumbs = {}
        # Optional open deck-viewer window.
        self.deck_viewer_window = None

    @property
    def local_player(self):
        return self.players[self.local_player_id]

    @property
    def opponent_player_id(self):
        return 2 if self.local_player_id == 1 else 1

    @property
    def opponent_player(self):
        return self.players[self.opponent_player_id]

    @property
    def local_character_id(self):
        return self.character_ids[self.local_player_id]

    @property
    def opponent_character_id(self):
        return self.character_ids[self.opponent_player_id]

    @property
    def local_defences(self):
        return self.defences[self.local_player_id]

    @property
    def opponent_defences(self):
        return self.defences[self.opponent_player_id]


# ============================================================
# Utility Functions
# ============================================================
def resolve_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    project_root = Path(__file__).resolve().parents[2]
    return project_root / relative_path


def encode_image(path, size=IMAGE_SIZE):
    image = Image.open(path)
    image.thumbnail(size, Image.LANCZOS)
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    return base64.b64encode(image_buffer.getvalue())


def build_shuffled_deck(first_card_id, last_card_id, card_counts=None):
    if card_counts is None:
        card_counts = {
            card_id: 1
            for card_id in range(first_card_id, last_card_id + 1)
        }
    deck = []
    for card_id in range(first_card_id, last_card_id + 1):
        deck.extend([card_id] * card_counts.get(card_id, 0))
    random.shuffle(deck)
    return deck


def load_character_images(character_id):
    character_images_dir = resolve_resource_path(f"assets/cards/{character_id}")
    if not character_images_dir.exists():
        return _generate_registered_card_images(character_id)

    card_images = []
    card_id = 0
    while True:
        image_path = character_images_dir / f"img-{card_id}.jpg"
        if image_path.exists():
            card_images.append(encode_image(str(image_path)))
            card_id += 1
        else:
            if card_id == 1:
                sg.popup_error(f"目录内无有效图片: {character_images_dir}")
            break
    return card_images, card_id - 1


def _generate_registered_card_images(character_id):
    """Generate readable paper cards when a character has no image pack."""
    # Delayed import avoids a module cycle during registry construction.
    from card_duel.cards.registry import get_character_card_catalog

    catalog = get_character_card_catalog(character_id)
    playable_cards = [definition for definition in catalog if definition.card_id]
    if not playable_cards:
        sg.popup_error(f"角色 {character_id} 没有卡图或已注册卡牌")
        return [], 0

    definitions = {definition.card_id: definition for definition in catalog}
    max_card_id = max(definitions)
    images = []
    for card_id in range(max_card_id + 1):
        definition = definitions.get(card_id)
        images.append(_render_card_placeholder(definition))
    return images, max_card_id


def _render_card_placeholder(definition, effective_cost=None):
    image = Image.new("RGB", IMAGE_SIZE, "#FFFDF8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (1, 1, IMAGE_SIZE[0] - 2, IMAGE_SIZE[1] - 2),
        radius=8,
        outline="#2E2A26",
        width=2,
    )
    if definition is None or definition.card_id == 0:
        return _encode_pil_image(image)

    accent_by_type = {
        "技能": "#6F89A8",
        "物品": "#C39A55",
        "生物": "#C86655",
        "见闻": "#719775",
        "形态": "#8B79A8",
    }
    accent = accent_by_type.get(definition.card_type, "#837A70")
    draw.rounded_rectangle((7, 7, 153, 41), radius=5, fill=accent)
    title_font = _load_card_font(18, bold=True)
    body_font = _load_card_font(12)
    small_font = _load_card_font(11)
    draw.text((14, 12), definition.name, fill="#FFFDF8", font=title_font)
    # Cost: use effective_cost if provided (and not None), else fall back to definition.cost
    cost = definition.cost if effective_cost is None else effective_cost
    cost_text = "X" if cost is None else str(cost)
    # Cost circle changes color when discounted (effective_cost < base cost)
    is_discounted = (
        effective_cost is not None
        and definition.cost is not None
        and effective_cost < definition.cost
    )
    cost_accent = "#2E7D32" if is_discounted else accent
    draw.ellipse((124, 48, 152, 76), outline=cost_accent, width=2)
    draw.text((132, 52), cost_text, fill=cost_accent, font=body_font)
    draw.text((13, 52), definition.card_type, fill=accent, font=body_font)
    y = 88
    for line in _wrap_card_text(definition.description, 13)[:8]:
        draw.text((13, y), line, fill="#2E2A26", font=small_font)
        y += 18
    return _encode_pil_image(image)


def _load_card_font(size, bold=False):
    font_names = ("msyhbd.ttc", "msyh.ttc") if bold else ("msyh.ttc",)
    for font_name in font_names:
        font_path = Path("C:/Windows/Fonts") / font_name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def _wrap_card_text(text, width):
    return [text[index:index + width] for index in range(0, len(text), width)]


def render_creature_card_with_hp(definition, hp):
    """Render a creature card with a dynamic red HP number overlaid.

    Reuses the base card image then draws a large red HP badge in the
    bottom-right corner so the player can see current health at a glance.
    """
    base_data = _render_card_placeholder(definition)
    # Decode base64 back to PIL image
    import base64 as _b64
    image_bytes = _b64.b64decode(base_data)
    image = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(image)
    hp_font = _load_card_font(20, bold=True)
    hp_text = str(max(0, hp))
    # Red badge in bottom-right
    badge_x, badge_y = IMAGE_SIZE[0] - 42, IMAGE_SIZE[1] - 38
    draw.ellipse((badge_x - 4, badge_y - 4, badge_x + 30, badge_y + 30), fill="#C8332B")
    draw.text((badge_x + 2, badge_y), hp_text, fill="#FFFDF8", font=hp_font)
    return _encode_pil_image(image)


def render_card_with_effective_cost(definition, effective_cost):
    """Render a card placeholder with a custom effective cost.

    Used when the runtime cost of a card differs from its printed cost
    (e.g. discovery cards discounted by the played-discovery stacking
    mechanic). The cost-circle outline and digit turn green when discounted.
    """
    return _render_card_placeholder(definition, effective_cost=effective_cost)


def _encode_pil_image(image):
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    return base64.b64encode(image_buffer.getvalue())


def initialize_character_states(game_state):
    """Apply character-specific starting health and public resources."""
    for player_id, character_id in game_state.character_ids.items():
        player = game_state.players[player_id]
        player.health = 30
        player.energy = 0
        player.defence = 0
        player.strength = 0
        player.poison = 0
        player.special = {
            "sacrifice": 0,
            "bastion": 0,
            "heartlink": 0,
        }
        if character_id == 4:
            from card_duel.cards.slugcat import initialize_slugcat_player

            initialize_slugcat_player(player)


# ============================================================
# DefenceEffect Management
# ============================================================
def add_defence(defence_list, amount, turns_remaining=1):
    new_effect = DefenceEffect(turns_remaining, amount)
    if not defence_list:
        defence_list.append(new_effect)
    else:
        insert_index = 0
        while (
            insert_index < len(defence_list)
            and new_effect.turns_remaining
            >= defence_list[insert_index].turns_remaining
        ):
            if (
                new_effect.turns_remaining
                == defence_list[insert_index].turns_remaining
            ):
                defence_list[insert_index].amount += new_effect.amount
                return
            insert_index += 1
        defence_list.insert(insert_index, new_effect)


def update_defence_totals(game_state):
    for player_id, defence_effects in game_state.defences.items():
        game_state.players[player_id].defence = sum(
            effect.amount for effect in defence_effects
        )


def apply_damage(game_state, damage, target_player_id, announce=None):
    target = game_state.players[target_player_id]
    if target.special.get("immune_next_attack", 0):
        target.special["immune_next_attack"] -= 1
        return 0

    defence_effects = game_state.defences[target_player_id]
    while defence_effects:
        while defence_effects[0].amount > 0 and damage > 0:
            defence_effects[0].amount -= 1
            damage -= 1
        if damage == 0:
            break
        if defence_effects[0].amount == 0:
            defence_effects.pop(0)

    # 蛞蝓猫敏捷格挡：只在"造成伤害"(apply_damage)时生效，"失去生命"不触发。
    if damage > 0 and game_state.character_ids.get(target_player_id) == 4:
        agility = int(target.special.get("agility", 0))
        if agility > 0:
            # 敏捷格挡伤害，但只在实际扣血时才消耗等量敏捷。
            # 2敏捷防2伤 → 0扣血 → 敏捷不变；2敏捷防3伤 → 扣1血 → 敏捷-1。
            blocked = min(agility, damage)
            damage -= blocked
            life_lost = damage  # 溢出部分=实际扣血
            agility_loss = min(agility, life_lost)
            if agility_loss > 0:
                target.special["agility"] = agility - agility_loss
                if announce:
                    announce(
                        f"玩家{target_player_id}的敏捷减伤{blocked}点"
                        f"（扣血{life_lost}，敏捷-{agility_loss}，"
                        f"剩余{target.special['agility']}）"
                    )
            elif blocked > 0 and announce:
                announce(
                    f"玩家{target_player_id}的敏捷完全格挡{blocked}点伤害"
                    f"（敏捷不消耗，仍为{agility}）"
                )
    return lose_life(game_state, damage, target_player_id, announce=announce)


def lose_life(game_state, amount, target_player_id, announce=None):
    """Lose life directly — bypasses defence, can't reduce damage, but still
    consumes agility equal to the life lost.

    Use this for effects that make the player "失去生命" (lose life) rather
    than "受到伤害" (take damage).  Centipede immunity still applies.

    播报顺序（Bug 6.40/6.41）：
      1. 先结算蜈蚣免伤 → 扣敏捷 → 扣血 → **立即播报"失去X点生命（敏捷-Y，剩余Z）"**
      2. 再结算Karma回血（如果health≤0） → 播报"消耗1点业力重返雨中"
    这样用户先看到损失再看到复原，不会出现"报了损失但实际没扣 / Karma复原后反算actual_loss为负而跳过播报"。
    生命值播报数值 = amount（蜈蚣免伤后的失去生命效果值），不是扣完Karma再反算的net。
    """
    target = game_state.players[target_player_id]
    amount = max(0, amount)
    if amount == 0:
        return 0
    agility_loss = 0
    final_agility = 0
    is_slugcat = game_state.character_ids.get(target_player_id) == 4
    if is_slugcat:
        # 烈焰蜈蚣免伤（仍对失去生命生效）
        from card_duel.cards.slugcat import check_centipede_immunity

        amount = check_centipede_immunity(
            game_state, target_player_id, amount, announce=announce
        )
        if amount <= 0:
            return 0
        # 失去生命不防伤害，但消耗等量敏捷（敏捷掉的数值=失去生命的数值）
        agility = int(target.special.get("agility", 0))
        if agility > 0 and amount > 0:
            agility_loss = min(agility, amount)
            final_agility = agility - agility_loss
            target.special["agility"] = final_agility
        else:
            final_agility = agility
    # Apply HP loss
    target.health -= amount
    # Announce loss immediately (BEFORE karma revive)
    if announce is not None:
        if is_slugcat and agility_loss > 0:
            announce(
                f"玩家{target_player_id}失去{amount}点生命"
                f"（敏捷-{agility_loss}，剩余{final_agility}）"
            )
        else:
            announce(f"玩家{target_player_id}失去{amount}点生命")
    # Karma revive (runs AFTER loss announcement so order is correct in log)
    if is_slugcat and target.health <= 0:
        from card_duel.cards.slugcat import resolve_slugcat_karma

        resolve_slugcat_karma(game_state, target_player_id, announce=announce)
    return amount


# ============================================================
# Timeline Management
# ============================================================
def schedule_event(timeline, scheduled_event):
    insert_index = 0
    while (
        insert_index < len(timeline)
        and scheduled_event.turns_remaining
        >= timeline[insert_index].turns_remaining
    ):
        insert_index += 1
    timeline.insert(insert_index, scheduled_event)


def resolve_scheduled_event(game_state, scheduled_event, announce):
    if scheduled_event.turns_remaining == 0:
        target = game_state.players[scheduled_event.target_player_id]
        announce(scheduled_event.message)
        if scheduled_event.effect_type == 1:
            if target.defence >= scheduled_event.amount:
                target.defence -= scheduled_event.amount
            else:
                raw_damage = scheduled_event.amount - target.defence
                target.defence = 0
                lose_life(
                    game_state,
                    raw_damage,
                    scheduled_event.target_player_id,
                    announce=announce,
                )
        elif scheduled_event.effect_type == 2:
            target.energy += scheduled_event.amount
        elif scheduled_event.effect_type == 3:
            target.defence += scheduled_event.amount
        elif scheduled_event.effect_type == 4:
            target.strength += scheduled_event.amount
        elif scheduled_event.effect_type == 5:
            target.poison += scheduled_event.amount
        elif scheduled_event.effect_type == 6:
            game_state.hand_size += scheduled_event.amount
    else:
        game_state.timeline.append(
            ScheduledEvent(
                scheduled_event.turns_remaining - 1,
                scheduled_event.effect_type,
                scheduled_event.amount,
                scheduled_event.target_player_id,
                scheduled_event.message,
            )
        )


def advance_turn_effects(game_state, player_id, announce):
    defence_effects = game_state.defences[player_id]
    if game_state.players[player_id].special['bastion'] == 0:
        for effect in defence_effects:
            effect.turns_remaining -= 1
        while defence_effects and defence_effects[0].turns_remaining == 0:
            expired_defence = defence_effects.pop(0).amount
            announce(f'玩家{player_id}的{expired_defence}点防御消散')

    while game_state.timeline and game_state.timeline[0].turns_remaining == 0:
        resolve_scheduled_event(game_state, game_state.timeline.pop(0), announce)

    for scheduled_event in game_state.timeline:
        scheduled_event.turns_remaining -= 1

    while game_state.timeline and game_state.timeline[0].turns_remaining == 0:
        resolve_scheduled_event(game_state, game_state.timeline.pop(0), announce)


# ============================================================
# Card Deal
# ============================================================
def add_card_to_hand(game_state, card_id):
    """Insert a card into the first free local hand slot."""
    for insert_index, current_card_id in enumerate(game_state.hand_cards):
        if current_card_id in (0, -1):
            game_state.hand_cards[insert_index] = card_id
            game_state.hand_size = max(game_state.hand_size, insert_index + 1)
            return True
    return False


def draw_cards(game_state, amount):
    from card_duel.cards.slugcat_data import SLUGCAT_CREATURE_IDS

    drawn = 0
    skipped = []
    while drawn < amount and game_state.draw_pile:
        card_id = game_state.draw_pile.pop(0)
        if card_id in SLUGCAT_CREATURE_IDS:
            # 生物牌可在牌堆中但不会被主动抽取
            skipped.append(card_id)
            continue
        if add_card_to_hand(game_state, card_id):
            drawn += 1
        else:
            game_state.draw_pile.insert(0, card_id)
            break
    # 跳过的生物牌放回牌堆底部
    game_state.draw_pile.extend(skipped)


# ============================================================
# Card Functions (Warrior)
# ============================================================
def _get_add_defence(game_state, player_id):
    return lambda amount, turns=1: add_defence(
        game_state.defences[player_id], amount, turns
    )


def resolve_attack_target(game_state, target_player_id, damage, announce=None, attacker_id=None):
    """Generic target resolution for Warrior (or any) attack cards.

    If the opponent is a Slugcat with creatures on board, prompts the
    attacker to pick between the player itself, hand creatures, and threat
    creatures.  Returns the amount of HP actually lost by the final target.

    Any target creature damage / death effects are handled by delegating back
    to the Slugcat module (only relevant when target is a Slugcat player).
    """
    # Prompt for target when either side is a Slugcat (creatures may live in
    # either player's hand / threat zone).
    source_is_slugcat = game_state.character_ids.get(attacker_id) == 4
    target_is_slugcat = game_state.character_ids.get(target_player_id) == 4
    target_obj = None
    if source_is_slugcat or target_is_slugcat:
        from card_duel.cards.slugcat import (
            choose_attack_target,
            _damage_hand_creature,
            _damage_threat_creature,
        )

        target_obj = choose_attack_target(game_state, attacker_id, target_player_id, announce)
        if target_obj is not None and target_obj["type"] != "player":
            creature_owner = target_obj.get("player_id", target_player_id)
            if target_obj["type"] == "hand":
                _damage_hand_creature(
                    game_state, creature_owner, target_obj["card_id"],
                    damage, announce, attacker_id=attacker_id,
                )
            else:
                threats = game_state.players[creature_owner].special.get(
                    "creature_threats", []
                )
                idx = next(
                    (i for i, t in enumerate(threats)
                     if int(t["card_id"]) == target_obj["card_id"]),
                    -1,
                )
                if idx >= 0:
                    _damage_threat_creature(
                        game_state, creature_owner, idx, damage, announce,
                        attacker_id=attacker_id,
                    )
            return 0
    # Fall-through: attack the player directly.
    return apply_damage(game_state, damage, target_player_id, announce=announce)


def _show_insufficient_energy():
    """Only failed actions interrupt the player with a short notice."""
    sg.popup(
        '能量不足',
        no_titlebar=True,
        background_color="#E8C8BE",
        keep_on_top=True,
    )


def play_unavailable_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    from card_duel.ui.network import colored_announce
    colored_announce(game_state, '这张牌已经打出了！')
    return 0


def play_attack_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """攻 - Attack (cost 1)"""
    if game_state.players[source_player_id].energy >= 1 or ignore_cost == 1:
        damage = 2 + game_state.players[source_player_id].strength
        announce(f'玩家{source_player_id}使用了攻(造成{damage}伤害)')
        game_state.players[source_player_id].energy -= 1
        resolve_attack_target(
            game_state, target_player_id, damage,
            announce=announce, attacker_id=source_player_id,
        )
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_defend_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """防 - Defend (cost 2)"""
    if game_state.players[source_player_id].energy >= 2 or ignore_cost == 1:
        announce(f'玩家{source_player_id}使用了防(防御+3)')
        game_state.players[source_player_id].energy -= 2
        _get_add_defence(game_state, source_player_id)(3)
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_shield_bash_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """盾击 - Shield Bash (cost 2)"""
    if game_state.players[source_player_id].energy >= 2 or ignore_cost == 1:
        damage = 2 + game_state.players[source_player_id].strength
        announce(f'玩家{source_player_id}使用了盾击(伤害{damage},防御+2)')
        game_state.players[source_player_id].energy -= 2
        _get_add_defence(game_state, source_player_id)(2)
        resolve_attack_target(
            game_state, target_player_id, damage,
            announce=announce, attacker_id=source_player_id,
        )
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_pack_god_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """背包之神 - Pack God (cost 0)"""
    if game_state.players[source_player_id].energy >= 0 or ignore_cost == 1:
        from card_duel.network.gameplay import select_hand_cards_in_place
        from card_duel.ui.network import refresh_cards as _refresh_hand

        selected = select_hand_cards_in_place(game_state, "背包之神", exclude_id=4)
        if selected is None:
            return 0
        from card_duel.cards.slugcat_data import SLUGCAT_CHARACTER_ID as _SCID
        source_player = game_state.players[source_player_id]
        for hand_index in selected:
            card_id = game_state.hand_cards[hand_index]
            # 路由见闻牌回discovery_pool，其他回draw_pile
            if 27 <= card_id <= 35 and game_state.character_ids.get(source_player_id) == _SCID:
                pool = source_player.special.setdefault("discovery_pool", [])
                pool.insert(0, card_id)
            else:
                # 弃牌插底，避免刚弃的牌下一回合又被抽到
                game_state.draw_pile.insert(0, card_id)
            game_state.hand_cards[hand_index] = -1
        _refresh_hand(game_state)

        discard_count = len(selected)
        announce(
            f'玩家{source_player_id}召唤了背包之神'
            f'(弃{discard_count}牌得{discard_count - 1}能量)'
        )
        game_state.players[source_player_id].energy += discard_count - 1
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_sacrifice_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """献祭 - Sacrifice (cost 2)"""
    if game_state.players[source_player_id].energy >= 2 or ignore_cost == 1:
        game_state.players[source_player_id].energy -= 2
        game_state.players[source_player_id].special['sacrifice'] += 1
        layers = game_state.players[source_player_id].special['sacrifice']
        announce(f'玩家{source_player_id}使用了献祭(每次因自己扣1血摸1牌[{layers}层])')
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_heavy_sword_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """重剑打击 - Heavy Sword (cost 3)"""
    if game_state.players[source_player_id].energy >= 3 or ignore_cost == 1:
        damage = 3 + 2 * game_state.players[source_player_id].strength
        announce(f'玩家{source_player_id}使用了重剑打击(造成{damage}伤害)')
        game_state.players[source_player_id].energy -= 3
        resolve_attack_target(
            game_state, target_player_id, damage,
            announce=announce, attacker_id=source_player_id,
        )
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_heavy_hammer_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """重锤打击 - Heavy Hammer (cost 7)"""
    if game_state.players[source_player_id].energy >= 7 or ignore_cost == 1:
        damage = 10 + game_state.players[source_player_id].strength
        announce(f'玩家{source_player_id}使用了重锤打击(造成{damage}伤害)')
        game_state.players[source_player_id].energy -= 7
        resolve_attack_target(
            game_state, target_player_id, damage,
            announce=announce, attacker_id=source_player_id,
        )
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_burn_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """燃烧 - Burn (cost 0, pay HP)"""
    layout = [
        [sg.Text("燃烧的血量(1-3):", text_color='#C86655', font=('Microsoft YaHei', 13, 'bold'))],
        [sg.Slider(range=(1, 3), default_value=1, orientation='h',
                   key='-SLIDER-', enable_events=True, size=(25, 15))],
        [sg.Button("确定", size=(10, 1))]
    ]
    choice_window = sg.Window("燃烧 - 选择代价", layout, keep_on_top=True)
    health_cost = 1
    while True:
        event, values = choice_window.read()
        if event == sg.WIN_CLOSED:
            choice_window.close()
            return 0
        if event == "-SLIDER-":
            health_cost = int(values['-SLIDER-'])
        if event == "确定":
            choice_window.close()
            lose_life(
                game_state, health_cost, source_player_id, announce=announce
            )
            game_state.players[source_player_id].strength += health_cost
            if game_state.players[source_player_id].special['sacrifice']:
                draw_cards(game_state, health_cost * game_state.players[source_player_id].special['sacrifice'])
            announce(f'玩家{source_player_id}燃起来了(力量+{health_cost})')
            schedule_event(game_state.timeline, ScheduledEvent(1, 4, -health_cost, source_player_id, f'[ 玩家{source_player_id}燃尽了。]'))
            return 1


def play_glycogen_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """糖原堆积 - Glycogen (cost 2)"""
    if game_state.players[source_player_id].energy >= 2 or ignore_cost == 1:
        announce(f'玩家{source_player_id}使用了糖原堆积(下回合力量+2)')
        game_state.players[source_player_id].energy -= 2
        schedule_event(game_state.timeline, ScheduledEvent(1, 4, 2, source_player_id, f'[ 玩家{source_player_id}的糖原堆积了。]'))
        schedule_event(game_state.timeline, ScheduledEvent(2, 4, -2, source_player_id, f'[ 玩家{source_player_id}的糖原变成了乳酸。]'))
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_bastion_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """壁垒 - Bastion (cost 4)"""
    if game_state.players[source_player_id].energy >= 4 or ignore_cost == 1:
        announce(f'玩家{source_player_id}使用了壁垒，防御不再自然消散了。')
        game_state.players[source_player_id].energy -= 4
        game_state.players[source_player_id].special['bastion'] = 1
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_consolidate_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """巩固 - Consolidate (cost 3) - FIX: use correct defence list"""
    if game_state.players[source_player_id].energy >= 3 or ignore_cost == 1:
        announce(f'玩家{source_player_id}使用了巩固(防御*1.5)')
        game_state.players[source_player_id].energy -= 3
        # BUG FIX: use correct defence list based on source_player_id player
        defence_effects = game_state.defences[source_player_id]
        for defence_effect in defence_effects:
            defence_effect.amount = int(1.5 * defence_effect.amount)
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_full_body_slam_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """全身撞击 - Full Body Slam (cost 4)"""
    if game_state.players[source_player_id].energy >= 4 or ignore_cost == 1:
        damage = game_state.players[source_player_id].defence + game_state.players[source_player_id].strength
        announce(f'玩家{source_player_id}使用了全身撞击(造成{damage}吨冲击)')
        game_state.players[source_player_id].energy -= 4
        resolve_attack_target(
            game_state, target_player_id, damage,
            announce=announce, attacker_id=source_player_id,
        )
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_immovable_mountain_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """不动如山 - Immovable Mountain (cost 3)"""
    if game_state.players[source_player_id].energy >= 3 or ignore_cost == 1:
        announce(f'玩家{source_player_id}使用了不动如山(+10防)')
        game_state.players[source_player_id].energy -= 3
        _get_add_defence(game_state, source_player_id)(10)
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_heartlink_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """心连心 - Heartlink (cost 2)"""
    if game_state.players[source_player_id].energy >= 2 or ignore_cost == 1:
        announce(f'玩家{source_player_id}使用了心连心(双方每回合-1)')
        game_state.players[source_player_id].energy -= 2
        game_state.players[source_player_id].special['heartlink'] += 1
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_black_flash_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """黑闪 - Black Flash (cost 2)"""
    if game_state.players[source_player_id].energy >= 2:
        announce(' 黑闪！')
        game_state.players[source_player_id].energy -= 2
        card_id = game_state.draw_pile.pop(0)
        character_id = game_state.character_ids[source_player_id]
        # 延迟导入，避免卡牌效果模块与注册表循环依赖。
        from card_duel.cards.registry import play_registered_card

        play_registered_card(
            game_state,
            character_id,
            card_id,
            source_player_id,
            target_player_id,
            announce,
            ignore_cost=True,
        )
        if card_id != 13 and card_id != 10:
            # 黑闪打出的牌用完插底，不立即再次抽到。
            game_state.draw_pile.insert(0, card_id)
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_burnt_offering_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """燔祭 - Burnt Offering (cost 3)"""
    if game_state.players[source_player_id].energy >= 3 or ignore_cost == 1:
        from card_duel.network.gameplay import select_hand_cards_in_place
        from card_duel.ui.network import refresh_cards as _refresh_hand

        selected = select_hand_cards_in_place(game_state, "燔祭", exclude_id=16)
        if selected is None:
            return 0
        from card_duel.cards.slugcat_data import SLUGCAT_CHARACTER_ID as _SCID2
        src_player = game_state.players[source_player_id]
        for hand_index in selected:
            card_id = game_state.hand_cards[hand_index]
            # 路由见闻牌回discovery_pool，其他回draw_pile
            if 27 <= card_id <= 35 and game_state.character_ids.get(source_player_id) == _SCID2:
                pool = src_player.special.setdefault("discovery_pool", [])
                pool.insert(0, card_id)
            else:
                # 弃牌插底，避免刚弃的牌下一回合又被抽到
                game_state.draw_pile.insert(0, card_id)
            game_state.hand_cards[hand_index] = -1
        _refresh_hand(game_state)

        discard_count = len(selected)
        damage = discard_count + 2 + game_state.players[source_player_id].strength
        announce(f'玩家{source_player_id}使用了燔祭(弃{discard_count}牌造成{damage}伤)')
        game_state.players[source_player_id].energy -= 3
        apply_damage(
            game_state, damage, target_player_id, announce=announce
        )
        return 1
    else:
        _show_insufficient_energy()
        return 0


# ============================================================
# Win/Loss Check
# ============================================================
def check_game_over(game_state):
    if game_state.game_over:
        return
    if _is_player_defeated(game_state, 1):
        from card_duel.ui.network import colored_announce
        colored_announce(game_state, '玩家2获胜')
        sg.popup_notify('还可以继续打牌哦', title='玩家2获胜',
                        display_duration_in_ms=3000, location=(700, 500))
        game_state.game_over = True
    if _is_player_defeated(game_state, 2):
        from card_duel.ui.network import colored_announce
        colored_announce(game_state, '玩家1获胜')
        sg.popup_notify('还可以继续打牌哦', title='玩家1获胜',
                        display_duration_in_ms=3000, location=(700, 500))
        game_state.game_over = True


def _is_player_defeated(game_state, player_id):
    player = game_state.players[player_id]
    if game_state.character_ids.get(player_id) == 4:
        return player.special.get("karma", 0) <= 0
    return player.health <= 0
