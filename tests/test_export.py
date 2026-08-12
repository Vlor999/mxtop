"""Sample export to CSV / JSON Lines."""

import csv
import json
from datetime import datetime

import pytest

from mxtop.export import Exporter, sample_row

CPU = {
    "E-Cluster_active": 12, "E-Cluster_freq_Mhz": 1200,
    "P-Cluster_active": 40, "P-Cluster_freq_Mhz": 3200,
    "package_W": 8.5, "cpu_W": 5.0, "gpu_W": 3.0, "ane_W": 0.5,
}
GPU = {"active": 30, "freq_MHz": 900}
RAM = {"used_GB": 12.3, "total_GB": 16.0, "swap_used_GB": 0.5}


def test_sample_row_flattens_a_reading():
    row = sample_row(datetime(2026, 1, 2, 3, 4, 5), CPU, GPU, RAM, "Nominal")
    assert row["timestamp"] == "2026-01-02T03:04:05"
    assert row["p_cluster_active_pct"] == 40
    assert row["gpu_freq_mhz"] == 900
    assert row["cpu_w"] == 5.0
    assert row["ram_used_gb"] == 12.3
    assert row["thermal_pressure"] == "Nominal"


def test_csv_has_a_header_and_one_row_per_sample(tmp_path):
    path = tmp_path / "out.csv"
    with Exporter(path) as exp:
        exp.write(sample_row("t0", CPU, GPU, RAM, "Nominal"))
        exp.write(sample_row("t1", CPU, GPU, RAM, "Heavy"))
    rows = list(csv.DictReader(path.read_text().splitlines()))
    assert [r["timestamp"] for r in rows] == ["t0", "t1"]
    assert rows[1]["thermal_pressure"] == "Heavy"
    assert rows[0]["package_w"] == "8.5"


@pytest.mark.parametrize("suffix", [".json", ".jsonl", ".ndjson"])
def test_json_extensions_write_json_lines(tmp_path, suffix):
    path = tmp_path / f"out{suffix}"
    with Exporter(path) as exp:
        exp.write(sample_row("t0", CPU, GPU, RAM, "Nominal"))
        exp.write(sample_row("t1", CPU, GPU, RAM, "Nominal"))
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["timestamp"] == "t0"
    assert json.loads(lines[1])["gpu_w"] == 3.0


def test_rows_are_readable_before_close(tmp_path):
    path = tmp_path / "out.csv"
    exp = Exporter(path)
    exp.write(sample_row("t0", CPU, GPU, RAM, "Nominal"))
    assert len(path.read_text().splitlines()) == 2  # header + row, already flushed
    exp.close()


def test_unknown_extension_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unsupported export extension"):
        Exporter(tmp_path / "out.txt")
    assert not (tmp_path / "out.txt").exists()
