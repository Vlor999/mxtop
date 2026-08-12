"""mxtop — Performance monitoring CLI tool for Apple Silicon."""

from __future__ import annotations

import curses
import os

from .constants import FALLBACK_TERM


def ensure_known_term(fallback: str = FALLBACK_TERM) -> str | None:
    """Fall back to a known TERM when the current one has no terminfo entry.

    Terminals such as Ghostty ship a terminfo name (``xterm-ghostty``) that is
    absent from the system database, which makes blessed — and therefore the
    whole UI — degrade to a warning and no styling. Must run before blessed is
    imported. Returns the TERM actually in effect.
    """
    term = os.environ.get("TERM")
    if not term:
        return term
    try:
        curses.setupterm(term, 1)
    except Exception:  # noqa: BLE001 — curses.error, or a closed fd
        os.environ["TERM"] = term = fallback
    return term


ensure_known_term()
