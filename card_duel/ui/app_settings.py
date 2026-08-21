"""Persistent display settings stored as JSON next to the project."""

from __future__ import annotations

import json

from card_duel.core.resources import resolve_resource_path

CONFIG_PATH = resolve_resource_path("settings.json")


def load_settings(session) -> None:
    """Read the JSON config into the session and apply runtime colors."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return
    colors = data.get("log_type_colors")
    if isinstance(colors, dict):
        session.log_type_colors = {
            key: value for key, value in colors.items() if isinstance(value, str)
        }
    borders = data.get("card_border_colors")
    if isinstance(borders, dict):
        session.card_border_colors = {
            key: value for key, value in borders.items() if isinstance(value, str)
        }
        from card_duel.ui.network_view import set_card_border_colors

        set_card_border_colors(session.card_border_colors)
    if isinstance(data.get("sound_enabled"), bool):
        session.sound_enabled = data["sound_enabled"]
        from card_duel.ui.sound import set_enabled

        set_enabled(session.sound_enabled)
    if isinstance(data.get("room_first_player"), str):
        session.room_first_player = data["room_first_player"]
    if isinstance(data.get("room_seed_text"), str):
        session.room_seed_text = data["room_seed_text"]
    if isinstance(data.get("room_round1_no_damage"), bool):
        session.room_round1_no_damage = data["room_round1_no_damage"]
    if isinstance(data.get("sound_effects"), list):
        session.sound_effects = {
            item for item in data["sound_effects"] if isinstance(item, str)
        }
    if isinstance(data.get("single_click_play"), bool):
        session.single_click_play = data["single_click_play"]


def save_settings(session) -> None:
    """Merge-save so one change never wipes other saved settings.

    host/guest 本机联机时两个进程共用同一个 settings.json，整块覆盖会
    把另一方的配置清掉；这里逐键合并，保留文件中未被本次修改的键。
    """
    existing: dict = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            existing = loaded
    except (OSError, ValueError):
        existing = {}

    merged_log = dict(existing.get("log_type_colors") or {})
    for key, value in (getattr(session, "log_type_colors", None) or {}).items():
        if isinstance(value, str):
            merged_log[key] = value
    merged_border = dict(existing.get("card_border_colors") or {})
    for key, value in (
        getattr(session, "card_border_colors", None) or {}
    ).items():
        if isinstance(value, str):
            merged_border[key] = value
    data = {
        "log_type_colors": merged_log,
        "card_border_colors": merged_border,
        "sound_enabled": bool(
            getattr(session, "sound_enabled", existing.get("sound_enabled", True))
        ),
        "room_first_player": str(
            getattr(session, "room_first_player", "random")
        ),
        "room_seed_text": str(getattr(session, "room_seed_text", "")),
        "room_round1_no_damage": bool(
            getattr(session, "room_round1_no_damage", True)
        ),
        "sound_effects": sorted(
            str(item)
            for item in (getattr(session, "sound_effects", None) or ())
        ),
        "single_click_play": bool(
            getattr(session, "single_click_play", False)
        ),
    }
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except OSError:
        pass
