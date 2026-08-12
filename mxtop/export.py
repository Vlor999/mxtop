"""Sample export — write each reading to a CSV or JSON Lines file."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, TextIO

from loguru import logger

_FORMATS = {".csv": "csv", ".jsonl": "jsonl", ".json": "jsonl", ".ndjson": "jsonl"}


def sample_row(
    timestamp: Any,
    cpu_metrics: dict[str, Any],
    gpu_metrics: dict[str, Any],
    ram: dict[str, Any],
    thermal_pressure: str,
) -> dict[str, Any]:
    """Flatten one reading into the exported record."""
    return {
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
        "e_cluster_active_pct": cpu_metrics["E-Cluster_active"],
        "e_cluster_freq_mhz": cpu_metrics["E-Cluster_freq_Mhz"],
        "p_cluster_active_pct": cpu_metrics["P-Cluster_active"],
        "p_cluster_freq_mhz": cpu_metrics["P-Cluster_freq_Mhz"],
        "gpu_active_pct": gpu_metrics["active"],
        "gpu_freq_mhz": gpu_metrics["freq_MHz"],
        "package_w": cpu_metrics["package_W"],
        "cpu_w": cpu_metrics["cpu_W"],
        "gpu_w": cpu_metrics["gpu_W"],
        "ane_w": cpu_metrics["ane_W"],
        "ram_used_gb": ram["used_GB"],
        "ram_total_gb": ram["total_GB"],
        "swap_used_gb": ram["swap_used_GB"],
        "thermal_pressure": thermal_pressure,
    }


def _give_back_to_sudo_user(fh: TextIO) -> None:
    """Hand a file created under ``sudo mxtop`` back to the invoking user.

    Otherwise every export is root-owned and the user cannot edit or delete it
    without sudo. Uses ``fchown`` on the open handle, so a symlinked target
    cannot redirect the ownership change.
    """
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if not (uid and gid):
        return
    try:
        os.fchown(fh.fileno(), int(uid), int(gid))
    except OSError as exc:
        logger.debug("could not chown the export file: {}", exc)


class Exporter:
    """Append one record per sample to *path*.

    The format follows the extension: ``.csv`` writes CSV with a header row,
    ``.json`` / ``.jsonl`` / ``.ndjson`` write JSON Lines — one object per
    line, so the file stays valid and readable while mxtop is still running.

    Rows are flushed as they are written; a run killed with ``q`` or Ctrl-C
    still leaves a complete file.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        fmt = _FORMATS.get(self.path.suffix.lower())
        if fmt is None:
            raise ValueError(
                f"unsupported export extension {self.path.suffix!r} — "
                f"use one of {', '.join(sorted(_FORMATS))}"
            )
        self.format = fmt
        self._fh: TextIO = self.path.open("w", newline="", encoding="utf-8")
        _give_back_to_sudo_user(self._fh)
        self._writer: csv.DictWriter | None = None
        logger.info("Exporting samples to {} ({})", self.path, self.format)

    def write(self, row: dict[str, Any]) -> None:
        if self.format == "csv":
            if self._writer is None:
                self._writer = csv.DictWriter(self._fh, fieldnames=list(row))
                self._writer.writeheader()
            self._writer.writerow(row)
        else:
            self._fh.write(json.dumps(row) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> Exporter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
