"""Keyboard listener for mxtop — runs in a background thread."""

from __future__ import annotations

import sys
import tty
import select
import termios
import threading

from loguru import logger


def keyboard_listener(stop_event: threading.Event) -> None:
    """Block in a background thread; set *stop_event* on ESC / q / Q.

    Restores the terminal to its original settings on exit.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        logger.debug("Keyboard listener started (fd={})", fd)
        while not stop_event.is_set():
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch in ("\x1b", "q", "Q"):
                    logger.info("Quit key pressed ({})", repr(ch))
                    stop_event.set()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        logger.debug("Keyboard listener stopped, terminal restored")
