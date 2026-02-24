"""Tests for mxtop.parsers."""

from mxtop.parsers import (
    parse_cpu_metrics,
    parse_gpu_metrics,
    parse_thermal_pressure,
    _synthesize_cluster,
)


# ---------------------------------------------------------------------------
# Fixtures — realistic plist dicts
# ---------------------------------------------------------------------------

def _make_plist(
    *,
    e_clusters=1,
    p_clusters=1,
    e_cores_per=4,
    p_cores_per=4,
    thermal="Nominal",
):
    """Build a minimal plist dict mimicking powermetrics output."""
    clusters = []

    for ci in range(e_clusters):
        name = "E-Cluster" if e_clusters == 1 else f"E{ci}-Cluster"
        cpus = [
            {"cpu": ci * e_cores_per + i, "freq_hz": 2_064_000_000, "idle_ratio": 0.5}
            for i in range(e_cores_per)
        ]
        clusters.append({
            "name": name,
            "freq_hz": 2_064_000_000,
            "idle_ratio": 0.5,
            "cpus": cpus,
        })

    for ci in range(p_clusters):
        name = "P-Cluster" if p_clusters == 1 else f"P{ci}-Cluster"
        cpus = [
            {"cpu": ci * p_cores_per + i, "freq_hz": 3_504_000_000, "idle_ratio": 0.3}
            for i in range(p_cores_per)
        ]
        clusters.append({
            "name": name,
            "freq_hz": 3_504_000_000,
            "idle_ratio": 0.3,
            "cpus": cpus,
        })

    return {
        "thermal_pressure": thermal,
        "processor": {
            "clusters": clusters,
            "ane_energy": 500,
            "cpu_energy": 8000,
            "gpu_energy": 5000,
            "combined_power": 20000,
        },
        "gpu": {
            "freq_hz": 1_398_000_000,
            "idle_ratio": 0.6,
        },
    }


# ---------------------------------------------------------------------------
# parse_thermal_pressure
# ---------------------------------------------------------------------------

class TestParseThermalPressure:
    def test_nominal(self):
        plist = _make_plist()
        assert parse_thermal_pressure(plist) == "Nominal"

    def test_heavy(self):
        plist = _make_plist(thermal="Heavy")
        assert parse_thermal_pressure(plist) == "Heavy"


# ---------------------------------------------------------------------------
# parse_gpu_metrics
# ---------------------------------------------------------------------------

class TestParseGpuMetrics:
    def test_basic(self):
        plist = _make_plist()
        gpu = parse_gpu_metrics(plist)
        assert gpu["freq_MHz"] == 1398
        assert gpu["active"] == 40  # (1 - 0.6) * 100

    def test_full_load(self):
        plist = _make_plist()
        plist["gpu"]["idle_ratio"] = 0.0
        gpu = parse_gpu_metrics(plist)
        assert gpu["active"] == 100

    def test_idle(self):
        plist = _make_plist()
        plist["gpu"]["idle_ratio"] = 1.0
        gpu = parse_gpu_metrics(plist)
        assert gpu["active"] == 0


# ---------------------------------------------------------------------------
# parse_cpu_metrics
# ---------------------------------------------------------------------------

class TestParseCpuMetrics:
    def test_standard_m1(self):
        plist = _make_plist(e_clusters=1, p_clusters=1, e_cores_per=4, p_cores_per=4)
        m = parse_cpu_metrics(plist)
        assert m["E-Cluster_active"] == 50  # (1 - 0.5) * 100
        assert m["E-Cluster_freq_Mhz"] == 2064
        assert m["P-Cluster_active"] == 70  # (1 - 0.3) * 100
        assert m["P-Cluster_freq_Mhz"] == 3504
        assert len(m["e_core"]) == 4
        assert len(m["p_core"]) == 4

    def test_per_core_values(self):
        plist = _make_plist(e_cores_per=2, p_cores_per=2)
        m = parse_cpu_metrics(plist)
        # Each E-core should be at 50% active
        for i in m["e_core"]:
            assert m[f"E-Cluster{i}_active"] == 50
            assert m[f"E-Cluster{i}_freq_Mhz"] == 2064
        # Each P-core should be at 70% active
        for i in m["p_core"]:
            assert m[f"P-Cluster{i}_active"] == 70
            assert m[f"P-Cluster{i}_freq_Mhz"] == 3504

    def test_power_metrics(self):
        plist = _make_plist()
        m = parse_cpu_metrics(plist)
        assert m["ane_W"] == 0.5       # 500 / 1000
        assert m["cpu_W"] == 8.0       # 8000 / 1000
        assert m["gpu_W"] == 5.0       # 5000 / 1000
        assert m["package_W"] == 20.0  # 20000 / 1000

    def test_ultra_multi_die_synthesis(self):
        """Multi-die (Ultra) chips have E0/E1 and P0/P1/.. clusters."""
        plist = _make_plist(e_clusters=2, p_clusters=4, e_cores_per=2, p_cores_per=2)
        m = parse_cpu_metrics(plist)
        # E-Cluster should be synthesized as average of sub-clusters
        assert "E-Cluster_active" in m
        assert "E-Cluster_freq_Mhz" in m
        # P-Cluster should be synthesized
        assert "P-Cluster_active" in m
        assert "P-Cluster_freq_Mhz" in m
        # All cores should be listed
        assert len(m["e_core"]) == 4   # 2 clusters * 2 cores
        assert len(m["p_core"]) == 8   # 4 clusters * 2 cores


# ---------------------------------------------------------------------------
# _synthesize_cluster
# ---------------------------------------------------------------------------

class TestSynthesizeCluster:
    def test_already_present(self):
        metrics = {"E-Cluster_active": 42, "E-Cluster_freq_Mhz": 2000}
        _synthesize_cluster(metrics, "E-Cluster", "E")
        assert metrics["E-Cluster_active"] == 42  # unchanged

    def test_synthesize_from_sub(self):
        metrics = {
            "E0-Cluster_active": 40,
            "E1-Cluster_active": 60,
            "E0-Cluster_freq_Mhz": 2000,
            "E1-Cluster_freq_Mhz": 2200,
        }
        _synthesize_cluster(metrics, "E-Cluster", "E")
        assert metrics["E-Cluster_active"] == 50  # avg(40, 60)
        assert metrics["E-Cluster_freq_Mhz"] == 2200  # max

    def test_noop_if_no_data(self):
        metrics = {}
        _synthesize_cluster(metrics, "E-Cluster", "E")
        assert "E-Cluster_active" not in metrics
