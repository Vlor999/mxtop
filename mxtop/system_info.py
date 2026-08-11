"""System information collectors: WiFi, power source, battery, cable/charger.

Expensive calls (``system_profiler``, etc.) are collected in a background
thread via :class:`BackgroundMetricsCollector` so they never block the UI.
"""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

import psutil
from loguru import logger


# ---------------------------------------------------------------------------
# WiFi metrics
# ---------------------------------------------------------------------------

def get_wifi_metrics() -> dict[str, Any]:
    """Return WiFi connection metrics.

    Tries ``system_profiler SPAirPortDataType`` first (works on all macOS
    versions), then falls back to the legacy ``airport -I`` utility.

    Keys returned:
    - ``ssid``        – Network name (str or ``None``)
    - ``rssi_dBm``    – Signal strength in dBm (int or ``None``)
    - ``noise_dBm``   – Noise floor in dBm (int or ``None``)
    - ``tx_rate_Mbps`` – Current transmit rate (float or ``None``)
    - ``channel``     – Channel info string (e.g. "36")
    - ``connected``   – ``True`` if associated to a network
    """
    result: dict[str, Any] = {
        "ssid": None,
        "rssi_dBm": None,
        "noise_dBm": None,
        "tx_rate_Mbps": None,
        "channel": None,
        "connected": False,
    }

    # ---------- primary: system_profiler -----------------------------------
    try:
        proc = subprocess.run(
            ["system_profiler", "SPAirPortDataType", "-detailLevel", "basic"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            _parse_airport_profiler(proc.stdout, result)
            if result["connected"]:
                return result
    except Exception as exc:
        logger.debug("system_profiler SPAirPortDataType failed: {}", exc)

    # ---------- fallback: legacy airport utility ---------------------------
    try:
        proc = subprocess.run(
            [
                "/System/Library/PrivateFrameworks/Apple80211.framework"
                "/Versions/Current/Resources/airport",
                "-I",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            _parse_airport_legacy(proc.stdout, result)
    except FileNotFoundError:
        logger.debug("airport utility not found — using system_profiler only")
    except Exception as exc:
        logger.debug("airport -I failed: {}", exc)

    # ---------- SSID via networksetup (last resort) -----------------------
    if result["ssid"] is None:
        try:
            proc = subprocess.run(
                ["networksetup", "-getairportnetwork", "en0"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and "Current Wi-Fi Network:" in proc.stdout:
                result["ssid"] = proc.stdout.split(":", 1)[1].strip()
                result["connected"] = True
        except Exception:
            pass

    return result


def _parse_airport_profiler(output: str, result: dict[str, Any]) -> None:
    """Parse ``system_profiler SPAirPortDataType`` output into *result*."""
    in_current = False
    for line in output.splitlines():
        stripped = line.strip()

        # Look for the "Current Network Information:" section
        if "Current Network Information" in stripped:
            in_current = True
            continue

        if in_current:
            # The SSID is the first indented key ending with ":"
            if result["ssid"] is None and stripped.endswith(":") and ":" in stripped:
                result["ssid"] = stripped.rstrip(":")
                result["connected"] = True

            if stripped.startswith("Signal / Noise:"):
                # e.g. "Signal / Noise: -52 dBm / -90 dBm"
                parts = stripped.split(":", 1)[1].strip()
                tokens = parts.replace("dBm", "").split("/")
                try:
                    result["rssi_dBm"] = int(tokens[0].strip())
                except (ValueError, IndexError):
                    pass
                try:
                    result["noise_dBm"] = int(tokens[1].strip())
                except (ValueError, IndexError):
                    pass

            elif stripped.startswith("Transmit Rate:"):
                try:
                    result["tx_rate_Mbps"] = float(
                        stripped.split(":", 1)[1].strip()
                    )
                except ValueError:
                    pass

            elif stripped.startswith("Channel:"):
                result["channel"] = stripped.split(":", 1)[1].strip()

            # Stop when the section ends (next top-level heading)
            if not line.startswith(" ") and not line.startswith("\t") and stripped and in_current and result["ssid"]:
                break


def _parse_airport_legacy(output: str, result: dict[str, Any]) -> None:
    """Parse legacy ``airport -I`` output into *result*."""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("SSID:"):
            result["ssid"] = line.split(":", 1)[1].strip()
            result["connected"] = True
        elif line.startswith("agrCtlRSSI:"):
            result["rssi_dBm"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("agrCtlNoise:"):
            result["noise_dBm"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("lastTxRate:"):
            result["tx_rate_Mbps"] = float(line.split(":", 1)[1].strip())
        elif line.startswith("channel:"):
            result["channel"] = line.split(":", 1)[1].strip()


# ---------------------------------------------------------------------------
# Power source / charger / battery
# ---------------------------------------------------------------------------

def _parse_pmset_line(line: str, key: str) -> str | None:
    """Extract a value from a ``pmset -g batt`` output line by key."""
    if key in line:
        after = line.split(key, 1)[1]
        # Take everything up to the next semicolon or newline
        return after.split(";")[0].strip().strip("'\"")
    return None


def get_power_metrics() -> dict[str, Any]:
    """Return power source, battery, and charger information.

    Keys returned:
    - ``source``         – "Battery" | "AC Power" | "Unknown"
    - ``battery_percent`` – Battery level 0–100 (int or ``None``)
    - ``charging``       – ``True`` if currently charging
    - ``charged``        – ``True`` if fully charged
    - ``time_remaining`` – Human-readable time remaining string or ``None``
    - ``wattage``        – Charger wattage (int or ``None``)
    - ``adapter_name``   – Charger/adapter name string or ``None``
    - ``cable_connected`` – ``True`` if a power cable is connected
    """
    result: dict[str, Any] = {
        "source": "Unknown",
        "battery_percent": None,
        "charging": False,
        "charged": False,
        "time_remaining": None,
        "wattage": None,
        "adapter_name": None,
        "cable_connected": False,
    }

    # --- pmset -g batt (works without sudo) ---
    try:
        proc = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = proc.stdout.strip().splitlines()
        if lines:
            first_line = lines[0]
            if "AC Power" in first_line:
                result["source"] = "AC Power"
                result["cable_connected"] = True
            elif "Battery Power" in first_line:
                result["source"] = "Battery"

            for line in lines[1:]:
                # "InternalBattery-0 (id=...)  95%; charging; 1:23 remaining"
                if "%" in line:
                    pct_part = line.split("%")[0]
                    # The percentage is the last token before %
                    pct_str = pct_part.strip().split()[-1]
                    try:
                        result["battery_percent"] = int(pct_str)
                    except ValueError:
                        pass

                lower = line.lower()
                if "charging" in lower and "not charging" not in lower and "discharging" not in lower:
                    result["charging"] = True
                if "charged" in line.lower():
                    result["charged"] = True
                if "remaining" in line.lower():
                    parts = line.split(";")
                    for part in parts:
                        if "remaining" in part.lower():
                            result["time_remaining"] = part.strip()

    except Exception as exc:
        logger.opt(exception=True).debug("pmset -g batt failed: {}", exc)

    # --- system_profiler for charger details ---
    try:
        proc = subprocess.run(
            ["system_profiler", "SPPowerDataType", "-detailLevel", "basic"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in proc.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Wattage"):
                val = stripped.split(":", 1)[1].strip().replace("W", "").strip()
                try:
                    result["wattage"] = int(val)
                except ValueError:
                    pass
            elif stripped.startswith("Name:") or stripped.startswith("Adapter Name:"):
                result["adapter_name"] = stripped.split(":", 1)[1].strip()
            elif "Connected" in stripped and "Yes" in stripped:
                result["cable_connected"] = True
    except Exception as exc:
        logger.opt(exception=True).debug("system_profiler SPPowerDataType failed: {}", exc)

    return result


# ---------------------------------------------------------------------------
# Network throughput (bytes sent/received since boot)
# ---------------------------------------------------------------------------

def get_network_throughput() -> dict[str, int]:
    """Return cumulative network I/O counters.

    Keys: ``bytes_sent``, ``bytes_recv``.
    """
    counters = psutil.net_io_counters()
    return {
        "bytes_sent": counters.bytes_sent,
        "bytes_recv": counters.bytes_recv,
    }


# ---------------------------------------------------------------------------
# Top processes
# ---------------------------------------------------------------------------

def get_top_processes(count: int = 5) -> list[dict[str, Any]]:
    """Return the *count* heaviest processes by CPU, then by memory.

    Each entry has ``pid``, ``name``, ``cpu_percent`` and ``rss``.

    ``cpu_percent`` is measured between successive calls, so the very first
    call after startup reports 0.0 for every process — psutil keeps the
    per-process state behind ``process_iter``, and the ranking becomes
    meaningful from the second call on.
    """
    rows: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            mem = info["memory_info"]
            rows.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "cpu_percent": info["cpu_percent"] or 0.0,
                "rss": mem.rss if mem else 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda r: (r["cpu_percent"], r["rss"]), reverse=True)
    return rows[:count]


# ---------------------------------------------------------------------------
# Disk throughput (bytes read/written since boot)
# ---------------------------------------------------------------------------

def get_disk_throughput() -> dict[str, float]:
    """Return cumulative disk I/O counters plus the sampling timestamp.

    Keys: ``read_bytes``, ``write_bytes``, ``t`` (``time.monotonic()``).
    ``read_bytes``/``write_bytes`` are 0 when the platform exposes no
    counters (psutil returns ``None`` on some sandboxed setups).
    """
    counters = psutil.disk_io_counters()
    return {
        "read_bytes": float(counters.read_bytes) if counters else 0.0,
        "write_bytes": float(counters.write_bytes) if counters else 0.0,
        "t": time.monotonic(),
    }


# ---------------------------------------------------------------------------
# Background metrics collector
# ---------------------------------------------------------------------------

class BackgroundMetricsCollector:
    """Collect slow metrics in a background thread so the UI never blocks.

    Usage::

        collector = BackgroundMetricsCollector(interval=5)
        collector.start(stop_event)

        # In the main loop — instant, non-blocking reads:
        wifi  = collector.wifi
        power = collector.power
        net   = collector.network
    """

    def __init__(self, interval: float = 5.0, top_count: int = 5) -> None:
        self.interval = interval
        self.top_count = top_count

        # Latest snapshots (read by main thread, written by bg thread)
        self._wifi: dict[str, Any] = {
            "ssid": None, "rssi_dBm": None, "noise_dBm": None,
            "tx_rate_Mbps": None, "channel": None, "connected": False,
        }
        self._power: dict[str, Any] = {
            "source": "Unknown", "battery_percent": None,
            "charging": False, "charged": False, "time_remaining": None,
            "wattage": None, "adapter_name": None, "cable_connected": False,
        }
        self._network: dict[str, int] = {"bytes_sent": 0, "bytes_recv": 0}
        self._top: list[dict[str, Any]] = []
        if top_count:
            get_top_processes(top_count)  # prime psutil's per-process CPU state
        self._disk: dict[str, float] = get_disk_throughput()

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # -- public read accessors (thread-safe) --

    @property
    def wifi(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._wifi)

    @property
    def power(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._power)

    @property
    def network(self) -> dict[str, int]:
        with self._lock:
            return dict(self._network)

    @property
    def top(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._top)

    @property
    def disk(self) -> dict[str, float]:
        with self._lock:
            return dict(self._disk)

    # -- lifecycle --

    def start(self, stop_event: threading.Event) -> None:
        """Launch the background collection thread."""
        self._thread = threading.Thread(
            target=self._run, args=(stop_event,), daemon=True,
        )
        self._thread.start()
        logger.debug("BackgroundMetricsCollector started (interval={}s)", self.interval)

    def _run(self, stop_event: threading.Event) -> None:
        """Periodically refresh all slow metrics."""
        while not stop_event.is_set():
            try:
                wifi = get_wifi_metrics()
                power = get_power_metrics()
                network = get_network_throughput()
                top = get_top_processes(self.top_count) if self.top_count else []
                disk = get_disk_throughput()
                with self._lock:
                    self._wifi = wifi
                    self._power = power
                    self._network = network
                    self._top = top
                    self._disk = disk
                logger.debug("Background metrics refreshed")
            except Exception:
                logger.opt(exception=True).warning("Background metrics collection failed")
            stop_event.wait(self.interval)
