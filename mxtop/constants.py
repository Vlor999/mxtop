"""Tunable constants shared across mxtop."""

FALLBACK_TERM = "xterm-256color"
"""TERM used when the current one has no entry in the terminfo database."""

DISK_GAUGE_FULL_SCALE = 1024 ** 3
"""Throughput, in bytes/s, at which the disk I/O gauge reads full (1 GB/s)."""
