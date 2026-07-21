"""Combat state, common calculations, resources, and card effect handlers."""

import base64
import io
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

import FreeSimpleGUI as sg
from PIL import Image

from card_duel.core.characters import CHARACTER_NAMES


# ============================================================
# Constants
# ============================================================
IMAGE_SIZE = (120, 180)
BUTTON_PAD = (5, 8)
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
    special: dict[str, int] = field(
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
        self.window = None
        self.connection = None
        self.game_over = False
        self.max_card_id = 0
        self.local_player_id = 1
        self.round_number = 0
        self.active_player_id = None
        self.current_phase = None

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
        sg.popup_error(f"缺少资源目录: {character_images_dir}")
        return [], 0

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


def apply_damage(game_state, damage, target_player_id):
    defence_effects = game_state.defences[target_player_id]
    while defence_effects:
        while defence_effects[0].amount > 0 and damage > 0:
            defence_effects[0].amount -= 1
            damage -= 1
        if damage == 0:
            break
        if defence_effects[0].amount == 0:
            defence_effects.pop(0)
    game_state.players[target_player_id].health -= damage


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
                target.health -= scheduled_event.amount - target.defence
                target.defence = 0
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
def draw_cards(game_state, amount):
    insert_index = 0
    while game_state.hand_cards[insert_index] != 0:
        insert_index += 1
    for _ in range(amount):
        if not game_state.draw_pile:
            break
        game_state.hand_cards[insert_index] = game_state.draw_pile.pop(0)
        insert_index += 1


# ============================================================
# Card Functions (Warrior)
# ============================================================
def _get_add_defence(game_state, player_id):
    return lambda amount, turns=1: add_defence(
        game_state.defences[player_id], amount, turns
    )


def _show_insufficient_energy():
    """Only failed actions interrupt the player with a short notice."""
    sg.popup(
        '能量不足',
        no_titlebar=True,
        background_color="#E8C8BE",
        keep_on_top=True,
    )


def play_unavailable_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    print('这张牌已经打出了！')
    return 0


def play_attack_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """攻 - Attack (cost 1)"""
    if game_state.players[source_player_id].energy >= 1 or ignore_cost == 1:
        announce(f'玩家{source_player_id}使用了攻(造成{2 + game_state.players[source_player_id].strength}伤害)')
        game_state.players[source_player_id].energy -= 1
        apply_damage(game_state, 2 + game_state.players[source_player_id].strength, target_player_id)
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
        announce(f'玩家{source_player_id}使用了盾击(伤害{2 + game_state.players[source_player_id].strength},防御+2)')
        game_state.players[source_player_id].energy -= 2
        _get_add_defence(game_state, source_player_id)(2)
        apply_damage(game_state, 2 + game_state.players[source_player_id].strength, target_player_id)
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_pack_god_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """背包之神 - Pack God (cost 0)"""
    if game_state.players[source_player_id].energy >= 0 or ignore_cost == 1:
        discard_count = _choose_discard_count(
            "背包之神 - 选择弃牌", game_state.hand_size
        )
        if discard_count is None:
            return 0
        if not _discard_selected_cards(
            game_state,
            "背包之神 - 弃牌",
            discard_count,
            exclude_id=4,
        ):
            return 0
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
        apply_damage(game_state, damage, target_player_id)
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
        apply_damage(game_state, damage, target_player_id)
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
            game_state.players[source_player_id].health -= health_cost
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
        apply_damage(game_state, damage, target_player_id)
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
            game_state.draw_pile.append(card_id)
        return 1
    else:
        _show_insufficient_energy()
        return 0


def play_burnt_offering_card(game_state, source_player_id, target_player_id, announce, ignore_cost=0):
    """燔祭 - Burnt Offering (cost 3)"""
    if game_state.players[source_player_id].energy >= 3 or ignore_cost == 1:
        discard_count = _choose_discard_count(
            "燔祭 - 选择弃牌", game_state.hand_size
        )
        if discard_count is None:
            return 0
        if not _discard_selected_cards(
            game_state,
            "燔祭 - 弃牌",
            discard_count,
            exclude_id=16,
        ):
            return 0
        damage = discard_count + 2 + game_state.players[source_player_id].strength
        announce(f'玩家{source_player_id}使用了燔祭(弃{discard_count}牌造成{damage}伤)')
        game_state.players[source_player_id].energy -= 3
        apply_damage(game_state, damage, target_player_id)
        return 1
    else:
        _show_insufficient_energy()
        return 0


def _choose_discard_count(title, hand_size):
    minimum_count = 0
    maximum_count = max(0, hand_size - 1)
    layout = [
        [
            sg.Text(
                f"弃牌数量({minimum_count}-{maximum_count}):",
                text_color='#6F89A8',
                font=('Microsoft YaHei', 13, 'bold'),
            )
        ],
        [
            sg.Slider(
                range=(minimum_count, maximum_count),
                default_value=minimum_count,
                orientation='h',
                key='-SLIDER-',
                enable_events=True,
                size=(25, 15),
            )
        ],
        [sg.Button("确定", size=(10, 1))],
    ]
    choice_window = sg.Window(
        title, layout, keep_on_top=True, finalize=True
    )
    selected_count = 1 if maximum_count >= 1 else 0
    while True:
        event, values = choice_window.read()
        if event == sg.WIN_CLOSED:
            choice_window.close()
            return None
        if event == '-SLIDER-':
            selected_count = int(values['-SLIDER-'])
        if event == '确定':
            choice_window.close()
            return selected_count


def _discard_selected_cards(
    game_state,
    title,
    discard_count,
    exclude_id=None,
):
    discard_window = _create_discard_window(
        game_state, title, exclude_id=exclude_id
    )
    discarded_indexes = []
    for _ in range(discard_count):
        while True:
            event, _ = discard_window.read()
            if event == sg.WIN_CLOSED:
                discard_window.close()
                return False
            if isinstance(event, str) and event.startswith('BTN'):
                break
        hand_index = int(event.removeprefix('BTN'))
        game_state.draw_pile.append(game_state.hand_cards[hand_index])
        game_state.hand_cards[hand_index] = 1
        game_state.hand_size -= 1
        discard_window[event].update(visible=False)
        discarded_indexes.append(hand_index)

    discard_window.close()
    for hand_index in discarded_indexes:
        game_state.hand_cards[hand_index] = -1
    return True


def _create_discard_window(game_state, title, exclude_id=None):
    layout = [
        [sg.Column(
            [[sg.Button(
                image_data=game_state.card_images[
                    game_state.hand_cards[row_index * 3 + column_index]
                ],
                key=f"BTN{row_index * 3 + column_index}",
                pad=BUTTON_PAD
            ) for column_index in range(3)]
                for row_index in range(40)],
            scrollable=True,
            size=(420, 350),
            vertical_scroll_only=True,
            expand_x=True, expand_y=True,
            key='-DISCARD-COL-'
        )]
    ]
    discard_window = sg.Window(
        title, layout, finalize=True, keep_on_top=True
    )
    hand_index = 0
    while game_state.hand_cards[hand_index] != 0:
        card_id = game_state.hand_cards[hand_index]
        discard_window[f'BTN{hand_index}'].update(
            image_data=game_state.card_images[card_id],
            visible=exclude_id is None or card_id != exclude_id,
        )
        hand_index += 1
    game_state.hand_size = hand_index
    while hand_index < 120 and game_state.hand_cards[hand_index] == 0:
        discard_window[f'BTN{hand_index}'].update(visible=False)
        hand_index += 1
    return discard_window


# ============================================================
# Win/Loss Check
# ============================================================
def check_game_over(game_state):
    if game_state.game_over:
        return
    if game_state.players[1].health <= 0:
        print('玩家2获胜')
        sg.popup_notify('还可以继续打牌哦', title='玩家2获胜',
                        display_duration_in_ms=3000, location=(700, 500))
        game_state.game_over = True
    if game_state.players[2].health <= 0:
        print('玩家1获胜')
        sg.popup_notify('还可以继续打牌哦', title='玩家1获胜',
                        display_duration_in_ms=3000, location=(700, 500))
        game_state.game_over = True
