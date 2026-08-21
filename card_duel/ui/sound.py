"""Minimal non-blocking sound effects (Windows winsound, synthesized WAVs)."""

from __future__ import annotations

from card_duel.core.resources import resolve_resource_path

_activated = False
_enabled = True


def activate() -> None:
    """Enable sound playback; called by the real game entry points only."""
    global _activated
    _activated = True


def set_enabled(value: bool) -> None:
    global _enabled
    _enabled = bool(value)


def play_sound(name: str) -> None:
    """Play a named synthesized effect asynchronously; never blocks."""
    if not (_activated and _enabled):
        return
    path = resolve_resource_path(f"assets/sounds/{name}.wav")
    if not path.exists():
        return
    try:
        import winsound

        winsound.PlaySound(
            str(path), winsound.SND_ASYNC | winsound.SND_FILENAME
        )
    except Exception:
        return
