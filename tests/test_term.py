"""TERM fallback for terminals without a terminfo entry (e.g. Ghostty)."""

import os
import subprocess
import sys

CODE = "import mxtop, os; print(os.environ['TERM'])"


def _term_after_import(term: str) -> str:
    env = {**os.environ, "TERM": term}
    out = subprocess.run(
        [sys.executable, "-c", CODE], env=env, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def test_unknown_term_falls_back():
    assert _term_after_import("xterm-nosuchterm-xyz") == "xterm-256color"


def test_known_term_is_kept():
    assert _term_after_import("xterm-256color") == "xterm-256color"
    assert _term_after_import("vt100") == "vt100"
