"""Disk I/O collection and widget update."""

from types import SimpleNamespace

from mxtop import updater
from mxtop.system_info import get_disk_throughput


def _widgets():
    return {"disk_gauge": SimpleNamespace(title="", value=0)}


def setup_function():
    updater._prev_disk = None


def test_get_disk_throughput_keys():
    d = get_disk_throughput()
    assert set(d) == {"read_bytes", "write_bytes", "t"}
    assert d["read_bytes"] >= 0 and d["write_bytes"] >= 0


def test_first_sample_only_primes():
    w = _widgets()
    updater.update_disk_widget(w, {"read_bytes": 0.0, "write_bytes": 0.0, "t": 100.0})
    assert "measuring" in w["disk_gauge"].title


def test_rate_uses_sample_timestamps():
    w = _widgets()
    updater.update_disk_widget(w, {"read_bytes": 0.0, "write_bytes": 0.0, "t": 100.0})
    # 10 MB read + 5 MB written over 5 s -> 2.0 MB/s read, 1.0 MB/s written
    updater.update_disk_widget(
        w,
        {
            "read_bytes": 10 * 1024**2,
            "write_bytes": 5 * 1024**2,
            "t": 105.0,
        },
    )
    assert "R 2.0 MB/s" in w["disk_gauge"].title
    assert "W 1.0 MB/s" in w["disk_gauge"].title
    # 3 MB/s out of a 1 GB/s full-scale gauge rounds to 0%
    assert w["disk_gauge"].value == 0


def test_gauge_saturates_and_clamps():
    w = _widgets()
    updater.update_disk_widget(w, {"read_bytes": 0.0, "write_bytes": 0.0, "t": 0.0})
    updater.update_disk_widget(
        w, {"read_bytes": 4 * 1024**3, "write_bytes": 0.0, "t": 1.0},
    )
    assert w["disk_gauge"].value == 100


def test_repeated_sample_keeps_previous_reading():
    w = _widgets()
    updater.update_disk_widget(w, {"read_bytes": 0.0, "write_bytes": 0.0, "t": 0.0})
    updater.update_disk_widget(w, {"read_bytes": 1024.0, "write_bytes": 0.0, "t": 1.0})
    title = w["disk_gauge"].title
    updater.update_disk_widget(w, {"read_bytes": 1024.0, "write_bytes": 0.0, "t": 1.0})
    assert w["disk_gauge"].title == title
