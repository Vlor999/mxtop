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
    e_cluster_names: list[str] = []
    p_cluster_names: list[str] = []

    for cluster in clusters:
        cname = cluster["name"]
        metrics[f"{cname}_freq_Mhz"] = int(cluster["freq_hz"] / 1e6)
        metrics[f"{cname}_active"] = int((1 - cluster["idle_ratio"]) * 100)

        # P-prefixed → performance cluster; everything else (E, S, …) → efficiency.
        # Apple M4 Pro/Max uses "S-Cluster" for efficiency cores instead of "E-Cluster".
        is_e = not cname.startswith("P")
        prefix = "E-Cluster" if is_e else "P-Cluster"
        if is_e:
            e_cluster_names.append(cname)
            core_list = e_cores
        else:
            p_cluster_names.append(cname)
            core_list = p_cores

        for cpu in cluster["cpus"]:
            cpu_id = cpu["cpu"]
            core_list.append(cpu_id)
            metrics[f"{prefix}{cpu_id}_freq_Mhz"] = int(cpu["freq_hz"] / 1e6)
            metrics[f"{prefix}{cpu_id}_active"] = int((1 - cpu["idle_ratio"]) * 100)

    metrics["e_core"] = e_cores
    metrics["p_core"] = p_cores

    # Synthesize canonical aggregates using the actual cluster names seen above.
    # This handles any cluster naming scheme (E-Cluster, E0-Cluster, ECPU, …).
    _synthesize_from_names(metrics, "E-Cluster", e_cluster_names)
    _synthesize_from_names(metrics, "P-Cluster", p_cluster_names)

    # Power metrics (energy in mJ → convert to mW for per-interval use)
    metrics["ane_W"] = processor["ane_energy"] / 1000
    metrics["cpu_W"] = processor["cpu_energy"] / 1000
    metrics["gpu_W"] = processor["gpu_energy"] / 1000
    metrics["package_W"] = processor["combined_power"] / 1000

    return metrics


def _synthesize_from_names(
    metrics: dict[str, Any],
    canonical: str,
    names: list[str],
) -> None:
    """Ensure ``canonical`` aggregate exists; average sub-clusters if needed."""
    if f"{canonical}_active" in metrics:
        return
    actives = [metrics[f"{n}_active"] for n in names if f"{n}_active" in metrics]
    freqs = [metrics[f"{n}_freq_Mhz"] for n in names if f"{n}_freq_Mhz" in metrics]
    if actives:
        metrics[f"{canonical}_active"] = int(sum(actives) / len(actives))
    if freqs:
        metrics[f"{canonical}_freq_Mhz"] = max(freqs)


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

