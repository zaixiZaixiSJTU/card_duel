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


def save_settings(session) -> None:
    """Write the current session display settings to the JSON config."""
    data = {
        "log_type_colors": dict(
            getattr(session, "log_type_colors", None) or {}
        ),
        "card_border_colors": dict(
            getattr(session, "card_border_colors", None) or {}
        ),
    }
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except OSError:
        pass
