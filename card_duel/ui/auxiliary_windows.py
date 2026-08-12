"""Non-blocking lifecycle for optional network-game windows."""

from card_duel.ui.card_animations import close_card_animations
from card_duel.ui.card_interaction import close_card_preview, poll_card_preview
from card_duel.ui.deck_viewer import close_deck_viewer, poll_deck_viewer


def poll_auxiliary_windows(session) -> None:
    """Give each auxiliary window one non-blocking event-loop slice."""
    poll_deck_viewer(session)
    poll_card_preview(session)


def read_primary_window(session, timeout=24):
    """Read the game window and keep every optional window responsive."""
    require_window = getattr(session, "require_window", None)
    window = require_window() if require_window else session.window
    result = window.read(timeout=timeout)
    poll_auxiliary_windows(session)
    return result


def close_auxiliary_windows(session) -> None:
    close_card_animations(session)
    close_card_preview(session)
    close_deck_viewer(session)
