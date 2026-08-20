"""Non-blocking lifecycle for optional network-game windows."""

from card_duel.ui.card_animations import close_card_animations
from card_duel.ui.card_interaction import close_card_preview, poll_card_preview
from card_duel.ui.debug_tool import close_debug_tool, poll_debug_tool
from card_duel.ui.deck_viewer import (
    close_deck_viewer,
    handle_deck_viewer_event,
    poll_deck_viewer,
)
from card_duel.ui.opponent_viewer import (
    OPPONENT_VIEW_KEY,
    close_opponent_viewer,
    open_opponent_viewer,
    poll_opponent_viewer,
)

DECK_EVENT_HANDLED = "-DECK-EVENT-HANDLED-"


def poll_auxiliary_windows(session) -> None:
    """Give each auxiliary window one non-blocking event-loop slice."""
    poll_deck_viewer(session)
    poll_card_preview(session)
    poll_debug_tool(session)
    poll_opponent_viewer(session)


def read_primary_window(session, timeout=24):
    """Read the game window and keep every optional window responsive."""
    require_window = getattr(session, "require_window", None)
    window = require_window() if require_window else session.window
    event, values = window.read(timeout=timeout)
    if handle_deck_viewer_event(session, event):
        event = DECK_EVENT_HANDLED
    elif event == OPPONENT_VIEW_KEY:
        open_opponent_viewer(session)
        event = DECK_EVENT_HANDLED
    poll_auxiliary_windows(session)
    return event, values


def close_auxiliary_windows(session) -> None:
    close_card_animations(session)
    close_card_preview(session)
    close_deck_viewer(session)
    close_debug_tool(session)
    close_opponent_viewer(session)
