"""Tests for mxtop.utils."""

from __future__ import annotations

import os
import plistlib
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from mxtop.utils import (
    _bytes_to_gb,
    get_ram_metrics_dict,
    parse_powermetrics,
    cleanup_tmp_files,
    get_soc_info,
    _SOC_SPECS,
    _SOC_DEFAULT,
    _READ_TAIL_BYTES,
)


# ---------------------------------------------------------------------------
# _bytes_to_gb
# ---------------------------------------------------------------------------

class TestBytesToGb:
    def test_one_gb(self):
        assert _bytes_to_gb(1 << 30) == 1.0

    def test_zero(self):
        assert _bytes_to_gb(0) == 0.0

    def test_half_gb(self):
        assert _bytes_to_gb((1 << 30) // 2) == 0.5

    def test_large(self):
        assert _bytes_to_gb(16 * (1 << 30)) == 16.0


# ---------------------------------------------------------------------------
# SoC specs lookup
# ---------------------------------------------------------------------------

class TestSocSpecs:
    def test_known_chip(self):
        assert "Apple M1" in _SOC_SPECS
        assert _SOC_SPECS["Apple M1"]["cpu"] == 20

    def test_unknown_falls_back(self):
        assert _SOC_SPECS.get("Apple M99", _SOC_DEFAULT) == _SOC_DEFAULT

    def test_all_m4_present(self):
        for variant in ("Apple M4", "Apple M4 Pro", "Apple M4 Max", "Apple M4 Ultra"):
            assert variant in _SOC_SPECS


# ---------------------------------------------------------------------------
# parse_powermetrics
# ---------------------------------------------------------------------------

def _make_plist_bytes() -> bytes:
    """Create a minimal valid plist blob like powermetrics would write."""
    data = {
        "timestamp": "2024-01-01 00:00:00",
        "thermal_pressure": "Nominal",
        "processor": {
            "clusters": [
                {
                    "name": "E-Cluster",
                    "freq_hz": 2_064_000_000,
                    "idle_ratio": 0.5,
                    "cpus": [
                        {"cpu": 0, "freq_hz": 2_064_000_000, "idle_ratio": 0.5},
                    ],
                },
                {
                    "name": "P-Cluster",
                    "freq_hz": 3_500_000_000,
                    "idle_ratio": 0.3,
                    "cpus": [
                        {"cpu": 1, "freq_hz": 3_500_000_000, "idle_ratio": 0.3},
                    ],
                },
            ],
            "ane_energy": 100,
            "cpu_energy": 5000,
            "gpu_energy": 3000,
            "combined_power": 10000,
        },
        "gpu": {
            "freq_hz": 1_398_000_000,
            "idle_ratio": 0.4,
        },
    }
    return plistlib.dumps(data, fmt=plistlib.FMT_XML)


class TestParsePowermetrics:
    def test_missing_file(self, tmp_path):
        result = parse_powermetrics(
            path=str(tmp_path / "nonexistent"), timecode=""
        )
        assert result is None

    def test_empty_file(self, tmp_path):
        f = tmp_path / "pm"
        f.write_bytes(b"")
        result = parse_powermetrics(path=str(f), timecode="")
        assert result is None

    def test_valid_single_blob(self, tmp_path):
        f = tmp_path / "pm"
        f.write_bytes(_make_plist_bytes())
        result = parse_powermetrics(path=str(f), timecode="")
        assert result is not None
        cpu_metrics, gpu_metrics, thermal, _, timestamp = result
        assert thermal == "Nominal"
        assert gpu_metrics["freq_MHz"] == 1398
        assert gpu_metrics["active"] == 60  # (1 - 0.4) * 100
        assert cpu_metrics["E-Cluster_active"] == 50
        assert timestamp == "2024-01-01 00:00:00"

    def test_multiple_blobs_returns_last(self, tmp_path):
        """Powermetrics separates plists with NUL bytes."""
        f = tmp_path / "pm"
        blob = _make_plist_bytes()
        f.write_bytes(blob + b"\x00" + blob + b"\x00" + blob)
        result = parse_powermetrics(path=str(f), timecode="")
        assert result is not None

    def test_file_truncated_after_read(self, tmp_path):
        """After a successful parse, the file should be truncated."""
        f = tmp_path / "pm"
        blob = _make_plist_bytes()
        # Write multiple blobs to grow the file
        f.write_bytes(blob + b"\x00" + blob + b"\x00" + blob)
        original_size = f.stat().st_size

        result = parse_powermetrics(path=str(f), timecode="")
        assert result is not None

        # File should now be smaller (only the last valid blob)
        new_size = f.stat().st_size
        assert new_size < original_size
        assert new_size == len(blob)

    def test_garbage_data_returns_none(self, tmp_path):
        f = tmp_path / "pm"
        f.write_bytes(b"not a plist at all\x00also garbage")
        result = parse_powermetrics(path=str(f), timecode="")
        assert result is None


# ---------------------------------------------------------------------------
# cleanup_tmp_files
# ---------------------------------------------------------------------------

class TestCleanupTmpFiles:
    def test_removes_files(self, tmp_path, monkeypatch):
        """Create fake temp files and verify cleanup removes them."""
        # Create files matching the pattern
        for name in ("mxtop_powermetrics123", "mxtop_powermetrics456"):
            (tmp_path / name).write_text("data")

        monkeypatch.setattr("mxtop.utils._TMP_PREFIX", str(tmp_path / "mxtop_powermetrics"))
        cleanup_tmp_files()

        remaining = list(tmp_path.iterdir())
        assert len(remaining) == 0

    def test_no_files_no_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mxtop.utils._TMP_PREFIX", str(tmp_path / "nonexistent"))
        cleanup_tmp_files()  # should not raise


# ---------------------------------------------------------------------------
# get_ram_metrics_dict
# ---------------------------------------------------------------------------

class TestGetRamMetrics:
    def test_keys_present(self):
        ram = get_ram_metrics_dict()
        expected_keys = {
            "total_GB", "free_GB", "used_GB", "free_percent",
            "swap_total_GB", "swap_used_GB", "swap_free_GB", "swap_free_percent",
        }
        assert expected_keys <= set(ram.keys())

    def test_total_positive(self):
        ram = get_ram_metrics_dict()
        assert ram["total_GB"] > 0

    def test_used_leq_total(self):
        ram = get_ram_metrics_dict()
        assert ram["used_GB"] <= ram["total_GB"]


# ---------------------------------------------------------------------------
# get_soc_info (mocked — no need for sudo or real hardware)
# ---------------------------------------------------------------------------

class TestGetSocInfo:
    @patch("mxtop.utils._run_sysctl")
    @patch("mxtop.utils._get_gpu_cores", return_value=10)
    def test_basic(self, mock_gpu, mock_sysctl):
        # Map sysctl key → return value
        responses = {
            "machdep.cpu.brand_string": "Apple M1 Pro",
            "machdep.cpu.core_count": "10",
            "hw.perflevel0.logicalcpu": "8",
            "hw.perflevel1.logicalcpu": "2",
        }
        mock_sysctl.side_effect = lambda k: responses.get(k)

        info = get_soc_info()
        assert info["name"] == "Apple M1 Pro"
        assert info["core_count"] == 10
        assert info["e_core_count"] == 2
        assert info["p_core_count"] == 8
        assert info["gpu_core_count"] == 10
        assert info["cpu_max_power"] == _SOC_SPECS["Apple M1 Pro"]["cpu"]

    @patch("mxtop.utils._run_sysctl", return_value=None)
    @patch("mxtop.utils._get_gpu_cores", return_value="?")
    def test_unknown_chip(self, mock_gpu, mock_sysctl):
        info = get_soc_info()
        # Should fall back to _SOC_DEFAULT
        assert info["cpu_max_power"] == _SOC_DEFAULT["cpu"]
