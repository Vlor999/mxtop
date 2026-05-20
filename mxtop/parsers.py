"""Parsers for Apple Silicon powermetrics plist output."""

from __future__ import annotations

from typing import Any

from loguru import logger


def parse_thermal_pressure(plist: dict[str, Any]) -> str:
    """Return the thermal pressure string (e.g. 'Nominal')."""
    return plist.get("thermal_pressure", "Nominal")


# ---------------------------------------------------------------------------
# CPU metrics
# ---------------------------------------------------------------------------

_CLUSTER_RANK: dict[str, int] = {"E": 0, "P": 1, "S": 2}


def parse_cpu_metrics(plist: dict[str, Any]) -> dict[str, Any]:
    """Extract CPU cluster and per-core metrics from a powermetrics plist.

    Apple cluster hierarchy (performance order): E < P < S.
    The lowest-rank prefix present maps to the efficiency slot (cpu1 gauge),
    the highest-rank prefix maps to the performance slot (cpu2 gauge).

    Examples:
      M1–M4 : E-Cluster → efficiency,  P-Cluster  → performance
      M5    : P-Cluster → efficiency,  S-Cluster  → performance
    """
    processor = plist.get("processor") or {}
    clusters = processor.get("clusters") or []
    if not clusters:
        raise ValueError("plist has no CPU cluster data")

    # Determine efficiency / performance split by cluster rank
    unique_prefixes = sorted(
        set(c["name"][0] for c in clusters),
        key=lambda l: _CLUSTER_RANK.get(l, 1),
    )
    e_prefix = unique_prefixes[0] if unique_prefixes else "E"
    p_prefix = unique_prefixes[-1] if len(unique_prefixes) >= 2 else "P"

    metrics: dict[str, Any] = {}
    e_cores: list[int] = []
    p_cores: list[int] = []
    e_cluster_names: list[str] = []
    p_cluster_names: list[str] = []

    for cluster in clusters:
        cname = cluster["name"]
        metrics[f"{cname}_freq_Mhz"] = int(cluster["freq_hz"] / 1e6)
        metrics[f"{cname}_active"] = int((1 - cluster["idle_ratio"]) * 100)

        is_e = cname[0] == e_prefix
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
    _synthesize_from_names(metrics, "E-Cluster", e_cluster_names)
    _synthesize_from_names(metrics, "P-Cluster", p_cluster_names)

    # Display labels reflect the actual cluster prefix letters:
    #   M1–M4: "E-CPU" / "P-CPU"     M5: "P-CPU" / "S-CPU"
    metrics["e_cluster_label"] = f"{e_prefix}-CPU"
    metrics["p_cluster_label"] = f"{p_prefix}-CPU"

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
    gpu = plist.get("gpu")
    if not gpu:
        return {"freq_MHz": 0, "active": 0}
    return {
        "freq_MHz": int(gpu.get("freq_hz", 0) / 1e6),
        "active": int((1 - gpu.get("idle_ratio", 1)) * 100),
    }

