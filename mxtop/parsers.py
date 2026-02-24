"""Parsers for Apple Silicon powermetrics plist output."""

from __future__ import annotations

from typing import Any

from loguru import logger


def parse_thermal_pressure(plist: dict[str, Any]) -> str:
    """Return the thermal pressure string (e.g. 'Nominal')."""
    return plist["thermal_pressure"]


# ---------------------------------------------------------------------------
# CPU metrics
# ---------------------------------------------------------------------------

def parse_cpu_metrics(plist: dict[str, Any]) -> dict[str, Any]:
    """Extract CPU cluster and per-core metrics from a powermetrics plist."""
    processor = plist["processor"]
    clusters = processor["clusters"]

    metrics: dict[str, Any] = {}
    e_cores: list[int] = []
    p_cores: list[int] = []

    for cluster in clusters:
        cname = cluster["name"]
        metrics[f"{cname}_freq_Mhz"] = int(cluster["freq_hz"] / 1e6)
        metrics[f"{cname}_active"] = int((1 - cluster["idle_ratio"]) * 100)

        # Determine canonical prefix (E-Cluster / P-Cluster)
        prefix = "E-Cluster" if cname[0] == "E" else "P-Cluster"
        core_list = e_cores if cname[0] == "E" else p_cores

        for cpu in cluster["cpus"]:
            cpu_id = cpu["cpu"]
            core_list.append(cpu_id)
            metrics[f"{prefix}{cpu_id}_freq_Mhz"] = int(cpu["freq_hz"] / 1e6)
            metrics[f"{prefix}{cpu_id}_active"] = int((1 - cpu["idle_ratio"]) * 100)

    metrics["e_core"] = e_cores
    metrics["p_core"] = p_cores

    # Synthesize aggregate E-Cluster / P-Cluster values for multi-die chips
    # (M1 Ultra has E0/E1, P0/P1/P2/P3 clusters)
    _synthesize_cluster(metrics, "E-Cluster", "E")
    _synthesize_cluster(metrics, "P-Cluster", "P")

    # Power metrics (energy in mJ → convert to mW for per-interval use)
    metrics["ane_W"] = processor["ane_energy"] / 1000
    metrics["cpu_W"] = processor["cpu_energy"] / 1000
    metrics["gpu_W"] = processor["gpu_energy"] / 1000
    metrics["package_W"] = processor["combined_power"] / 1000

    return metrics


def _synthesize_cluster(
    metrics: dict[str, Any],
    canonical: str,
    letter: str,
) -> None:
    """If ``canonical`` (e.g. 'E-Cluster') is missing, average sub-clusters."""
    if f"{canonical}_active" in metrics:
        return

    # Find all sub-cluster keys like P0-Cluster_active, P1-Cluster_active …
    sub_active = [
        v for k, v in metrics.items()
        if k.startswith(f"{letter}") and k.endswith("-Cluster_active")
    ]
    sub_freq = [
        v for k, v in metrics.items()
        if k.startswith(f"{letter}") and k.endswith("-Cluster_freq_Mhz")
    ]

    if sub_active:
        metrics[f"{canonical}_active"] = int(sum(sub_active) / len(sub_active))
    if sub_freq:
        metrics[f"{canonical}_freq_Mhz"] = max(sub_freq)


# ---------------------------------------------------------------------------
# GPU metrics
# ---------------------------------------------------------------------------

def parse_gpu_metrics(plist: dict[str, Any]) -> dict[str, Any]:
    """Extract GPU utilization and frequency from a powermetrics plist."""
    gpu = plist["gpu"]
    return {
        "freq_MHz": int(gpu["freq_hz"] / 1e6),
        "active": int((1 - gpu["idle_ratio"]) * 100),
    }

