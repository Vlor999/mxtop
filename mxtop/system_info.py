"""System information collectors: WiFi, power source, battery, cable/charger.

Expensive calls (``system_profiler``, etc.) are collected in a background
thread via :class:`BackgroundMetricsCollector` so they never block the UI.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Any

import psutil
from loguru import logger


# ---------------------------------------------------------------------------
# WiFi metrics
# ---------------------------------------------------------------------------

def _drop_to_sudo_user():
    """preexec_fn : drop root privileges to the original user (SUDO_UID/GID)."""
    uid = os.environ.get("SUDO_UID")
    gid = os.environ.get("SUDO_GID")
    if uid and gid:
        os.setgid(int(gid))
        os.setuid(int(uid))


def _get_wifi_interface() -> str:
    """Detect the WiFi interface name (e.g. 'en0', 'en1') via networksetup."""
    try:
        proc = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            preexec_fn=_drop_to_sudo_user,
            capture_output=True, text=True, timeout=5,
        )
        lines = proc.stdout.splitlines()
        for i, line in enumerate(lines):
            if "Wi-Fi" in line or "AirPort" in line:
                for j in range(i, min(i + 3, len(lines))):
                    if "Device:" in lines[j]:
                        return lines[j].split(":", 1)[1].strip()
    except Exception:
        pass
    return "en0"


def get_wifi_metrics() -> dict[str, Any]:
    """Return WiFi connection metrics.

    Uses ``system_profiler SPAirPortDataType -json`` (language-independent),
    then falls back to ``networksetup -getairportnetwork <iface>``.

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

    # ---------- primary: wdutil info (fonctionne en root sans drop) --------
    try:
        proc = subprocess.run(
            ["wdutil", "info"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            _parse_wdutil(proc.stdout, result)
            if result["connected"]:
                return result
    except Exception as exc:
        logger.debug("wdutil info failed: {}", exc)

    # ---------- fallback: system_profiler JSON (drop root → user original) -
    try:
        proc = subprocess.run(
            ["system_profiler", "SPAirPortDataType", "-json"],
            preexec_fn=_drop_to_sudo_user,
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            _parse_airport_json(json.loads(proc.stdout), result)
    except Exception as exc:
        logger.debug("system_profiler failed: {}", exc)

    return result


def _parse_wdutil(output: str, result: dict[str, Any]) -> None:
    """Parse ``wdutil info`` output — works as root.

    wdutil info contains multiple sections; RSSI/Noise/Channel are only
    meaningful in the section that contains the connected SSID.
    """
    lines = output.splitlines()

    # First pass: find the SSID line index
    ssid_idx = None
    for i, line in enumerate(lines):
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        if key.strip() == "SSID" and val.strip():
            result["ssid"] = val.strip()
            result["connected"] = True
            ssid_idx = i
            break

    if ssid_idx is None:
        return

    # Second pass: read metrics from the same section (lines after SSID)
    for line in lines[ssid_idx + 1: ssid_idx + 20]:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "RSSI":
            try:
                result["rssi_dBm"] = int(val.split()[0])
            except (ValueError, IndexError):
                pass
        elif key == "Noise":
            try:
                result["noise_dBm"] = int(val.split()[0])
            except (ValueError, IndexError):
                pass
        elif key == "Channel":
            result["channel"] = val
        elif key in ("TX Rate", "TxRate"):
            try:
                result["tx_rate_Mbps"] = float(val.split()[0])
            except (ValueError, IndexError):
                pass


def _parse_airport_json(data: dict[str, Any], result: dict[str, Any]) -> None:
    """Parse ``system_profiler SPAirPortDataType -json`` output into *result*."""
    for section in data.get("SPAirPortDataType", []):
        for iface in section.get("spairport_airport_interfaces", []):
            net = iface.get("spairport_current_network_information")
            if not net:
                continue
            result["ssid"] = net.get("_name")
            result["connected"] = True
            # "-68 dBm / -95 dBm"
            sig_noise = net.get("spairport_signal_noise", "")
            if sig_noise:
                tokens = sig_noise.replace("dBm", "").split("/")
                try:
                    result["rssi_dBm"] = int(tokens[0].strip())
                except (ValueError, IndexError):
                    pass
                try:
                    result["noise_dBm"] = int(tokens[1].strip())
                except (ValueError, IndexError):
                    pass
            rate = net.get("spairport_network_rate")
            if rate is not None:
                try:
                    result["tx_rate_Mbps"] = float(rate)
                except (ValueError, TypeError):
                    pass
            channel = net.get("spairport_network_channel")
            if channel:
                result["channel"] = str(channel)
            return  # premier réseau connecté suffit


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

    def __init__(self, interval: float = 5.0) -> None:
        self.interval = interval

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
                with self._lock:
                    self._wifi = wifi
                    self._power = power
                    self._network = network
                logger.debug("Background metrics refreshed")
            except Exception:
                logger.opt(exception=True).warning("Background metrics collection failed")
            stop_event.wait(self.interval)
