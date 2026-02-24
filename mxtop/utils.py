"""Utility helpers for mxtop: system info, powermetrics process, RAM metrics."""

from __future__ import annotations

import glob
import os
import plistlib
import subprocess
from typing import Any

import psutil
from loguru import logger

from .parsers import parse_cpu_metrics, parse_gpu_metrics, parse_thermal_pressure

# ---------------------------------------------------------------------------
# SoC power / bandwidth database
# ---------------------------------------------------------------------------

_SOC_SPECS: dict[str, dict[str, int]] = {
    # name -> {cpu_max_power, gpu_max_power, cpu_max_bw, gpu_max_bw}
    # M1 family
    "Apple M1":       {"cpu": 20,  "gpu": 20,  "cpu_bw": 70,  "gpu_bw": 70},
    "Apple M1 Pro":   {"cpu": 30,  "gpu": 30,  "cpu_bw": 200, "gpu_bw": 200},
    "Apple M1 Max":   {"cpu": 30,  "gpu": 60,  "cpu_bw": 250, "gpu_bw": 400},
    "Apple M1 Ultra": {"cpu": 60,  "gpu": 120, "cpu_bw": 500, "gpu_bw": 800},
    # M2 family
    "Apple M2":       {"cpu": 25,  "gpu": 15,  "cpu_bw": 100, "gpu_bw": 100},
    "Apple M2 Pro":   {"cpu": 30,  "gpu": 35,  "cpu_bw": 200, "gpu_bw": 200},
    "Apple M2 Max":   {"cpu": 30,  "gpu": 60,  "cpu_bw": 250, "gpu_bw": 400},
    "Apple M2 Ultra": {"cpu": 60,  "gpu": 120, "cpu_bw": 500, "gpu_bw": 800},
    # M3 family
    "Apple M3":       {"cpu": 25,  "gpu": 20,  "cpu_bw": 100, "gpu_bw": 100},
    "Apple M3 Pro":   {"cpu": 30,  "gpu": 35,  "cpu_bw": 150, "gpu_bw": 150},
    "Apple M3 Max":   {"cpu": 40,  "gpu": 60,  "cpu_bw": 300, "gpu_bw": 400},
    "Apple M3 Ultra": {"cpu": 80,  "gpu": 120, "cpu_bw": 600, "gpu_bw": 800},
    # M4 family
    "Apple M4":       {"cpu": 25,  "gpu": 20,  "cpu_bw": 120, "gpu_bw": 120},
    "Apple M4 Pro":   {"cpu": 30,  "gpu": 35,  "cpu_bw": 200, "gpu_bw": 200},
    "Apple M4 Max":   {"cpu": 40,  "gpu": 60,  "cpu_bw": 350, "gpu_bw": 500},
    "Apple M4 Ultra": {"cpu": 80,  "gpu": 120, "cpu_bw": 700, "gpu_bw": 900},
}

_SOC_DEFAULT = {"cpu": 20, "gpu": 20, "cpu_bw": 70, "gpu_bw": 70}


# ---------------------------------------------------------------------------
# Powermetrics file parsing
# ---------------------------------------------------------------------------

_READ_TAIL_BYTES = 64 * 1024  # only read the last 64 KiB of the file


def parse_powermetrics(
    path: str = "/tmp/mxtop_powermetrics",
    timecode: str = "0",
) -> tuple[dict, dict, str, None, Any] | None:
    """Parse the plist written by powermetrics.

    Returns ``(cpu_metrics, gpu_metrics, thermal_pressure, None, timestamp)``
    or *None* if no valid data is available yet.

    Only the tail of the file is read to avoid unbounded memory growth
    (powermetrics keeps appending NUL-separated plists).  After a
    successful parse the file is truncated to keep only the last valid
    blob, preventing disk growth as well.
    """
    filepath = path + timecode
    try:
        fd = os.open(filepath, os.O_RDWR)
    except FileNotFoundError:
        return None

    try:
        file_size = os.fstat(fd).st_size
        if file_size == 0:
            return None

        # Read only the tail — one plist blob is typically < 10 KiB
        read_start = max(0, file_size - _READ_TAIL_BYTES)
        os.lseek(fd, read_start, os.SEEK_SET)
        tail = os.read(fd, file_size - read_start)

        # Walk chunks from the end to find the latest valid plist
        chunks = tail.split(b"\x00")
        for chunk in reversed(chunks):
            if not chunk:
                continue
            try:
                plist = plistlib.loads(chunk)
                # Truncate file: keep only this last good blob
                os.ftruncate(fd, 0)
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, chunk)
                return (
                    parse_cpu_metrics(plist),
                    parse_gpu_metrics(plist),
                    parse_thermal_pressure(plist),
                    None,
                    plist["timestamp"],
                )
            except Exception:  # noqa: BLE001
                continue

        return None
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------

def clear_console() -> None:
    os.system("clear")


def _bytes_to_gb(value: int | float) -> float:
    return round(value / (1 << 30), 1)


# ---------------------------------------------------------------------------
# Subprocess management
# ---------------------------------------------------------------------------

_TMP_PREFIX = "/tmp/mxtop_powermetrics"


def cleanup_tmp_files() -> None:
    """Remove leftover powermetrics temp files."""
    for f in glob.glob(f"{_TMP_PREFIX}*"):
        try:
            os.remove(f)
        except OSError:
            pass


def run_powermetrics_process(
    timecode: str,
    nice: int = 10,
    interval: int = 1000,
) -> subprocess.Popen:
    """Spawn ``powermetrics`` as a background process writing to a temp file."""
    cleanup_tmp_files()
    cmd = [
        "sudo", "nice", f"-n{nice}",
        "powermetrics",
        "--samplers", "cpu_power,gpu_power,thermal",
        "-o", f"{_TMP_PREFIX}{timecode}",
        "-f", "plist",
        "-i", str(interval),
    ]
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# RAM / swap metrics
# ---------------------------------------------------------------------------

def get_ram_metrics_dict() -> dict[str, Any]:
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()

    total_gb = _bytes_to_gb(ram.total)
    used_gb = _bytes_to_gb(ram.total - ram.available)
    free_gb = _bytes_to_gb(ram.available)
    swap_total_gb = _bytes_to_gb(swap.total)
    swap_used_gb = _bytes_to_gb(swap.used)
    swap_free_gb = _bytes_to_gb(swap.total - swap.used)

    return {
        "total_GB": total_gb,
        "free_GB": free_gb,
        "used_GB": used_gb,
        "free_percent": int(100 - (ram.available / ram.total * 100)) if ram.total else 0,
        "swap_total_GB": swap_total_gb,
        "swap_used_GB": swap_used_gb,
        "swap_free_GB": swap_free_gb,
        "swap_free_percent": (
            int(100 - (swap_free_gb / swap_total_gb * 100))
            if swap_total_gb > 0
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Hardware introspection (cached — only called once at startup)
# ---------------------------------------------------------------------------

def _run_sysctl(key: str) -> str | None:
    """Fetch a single sysctl value, returning None on failure."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", key],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _get_cpu_info() -> dict[str, str]:
    brand = _run_sysctl("machdep.cpu.brand_string") or "Unknown"
    cores = _run_sysctl("machdep.cpu.core_count") or "0"
    return {"brand": brand, "core_count": cores}


def _get_core_counts() -> tuple[int, int]:
    """Return (e_core_count, p_core_count)."""
    p = _run_sysctl("hw.perflevel0.logicalcpu")
    e = _run_sysctl("hw.perflevel1.logicalcpu")
    return int(e) if e else 0, int(p) if p else 0


def _get_gpu_cores() -> int | str:
    try:
        result = subprocess.run(
            ["system_profiler", "-detailLevel", "basic", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "Total Number of Cores" in line:
                return int(line.split(": ")[-1])
    except Exception:
        pass
    return "?"


def get_soc_info() -> dict[str, Any]:
    """Gather SoC information. Called once at startup.

    Parallelises the expensive subprocess calls to reduce boot time.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_cpu  = pool.submit(_get_cpu_info)
        fut_core = pool.submit(_get_core_counts)
        fut_gpu  = pool.submit(_get_gpu_cores)

        cpu_info = fut_cpu.result()
        e_cores, p_cores = fut_core.result()
        gpu_cores = fut_gpu.result()

    name = cpu_info["brand"]
    specs = _SOC_SPECS.get(name, _SOC_DEFAULT)

    return {
        "name": name,
        "core_count": int(cpu_info["core_count"]),
        "e_core_count": e_cores,
        "p_core_count": p_cores,
        "gpu_core_count": gpu_cores,
        "cpu_max_power": specs["cpu"],
        "gpu_max_power": specs["gpu"],
        "cpu_max_bw": specs["cpu_bw"],
        "gpu_max_bw": specs["gpu_bw"],
    }

