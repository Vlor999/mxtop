"""Widget updater — applies metric readings to dashing widgets."""

from __future__ import annotations

from typing import Any

from dashing import HChart

from loguru import logger

from .utils import get_ram_metrics_dict


_MAX_CHART_POINTS = 512  # cap HChart datapoints to prevent unbounded growth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cap_chart(chart: HChart, maxlen: int = _MAX_CHART_POINTS) -> None:
    """Trim the chart's internal datapoints list to *maxlen*."""
    if hasattr(chart, "datapoints") and len(chart.datapoints) > maxlen:
        chart.datapoints = chart.datapoints[-maxlen:]


def _format_bytes(b: int) -> str:
    """Human-readable byte size (e.g. 1.2 GB, 340 MB)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024  # type: ignore[assignment]
    return f"{b:.1f} PB"


# ---------------------------------------------------------------------------
# Per-tick CPU / GPU / ANE update
# ---------------------------------------------------------------------------

def update_processor_widgets(
    w: dict[str, Any],
    cpu_metrics: dict[str, Any],
    gpu_metrics: dict[str, Any],
    soc_info: dict[str, Any],
    *,
    show_cores: bool = False,
) -> None:
    """Refresh CPU clusters, GPU, ANE, and per-core gauges."""
    e_label = cpu_metrics.get("e_cluster_label", "E-CPU")
    p_label = cpu_metrics.get("p_cluster_label", "P-CPU")

    w["cpu1_gauge"].title = (
        f"{e_label} Usage: {cpu_metrics['E-Cluster_active']}%"
        f" @ {cpu_metrics['E-Cluster_freq_Mhz']} MHz"
    )
    w["cpu1_gauge"].value = cpu_metrics["E-Cluster_active"]

    w["cpu2_gauge"].title = (
        f"{p_label} Usage: {cpu_metrics['P-Cluster_active']}%"
        f" @ {cpu_metrics['P-Cluster_freq_Mhz']} MHz"
    )
    w["cpu2_gauge"].value = cpu_metrics["P-Cluster_active"]

    # Per-core gauges
    if show_cores:
        e_gauges = w.get("e_core_gauges", [])
        for idx, i in enumerate(cpu_metrics["e_core"]):
            if idx >= len(e_gauges):
                break
            e_gauges[idx].title = (
                f"Core-{i + 1} {cpu_metrics.get(f'E-Cluster{i}_active', 0)}%"
            )
            e_gauges[idx].value = cpu_metrics.get(f"E-Cluster{i}_active", 0)

        p_gauges = w.get("p_core_gauges", [])
        p_gauges_ext = w.get("p_core_gauges_ext", [])
        prefix = "Core-" if soc_info["p_core_count"] < 6 else "C-"
        for idx, i in enumerate(cpu_metrics["p_core"]):
            if idx < len(p_gauges):
                slot, gauges = idx, p_gauges
            elif idx - len(p_gauges) < len(p_gauges_ext):
                slot, gauges = idx - len(p_gauges), p_gauges_ext
            else:
                break
            gauges[slot].title = (
                f"{prefix}{i + 1} {cpu_metrics.get(f'P-Cluster{i}_active', 0)}%"
            )
            gauges[slot].value = cpu_metrics.get(f"P-Cluster{i}_active", 0)

    # GPU
    w["gpu_gauge"].title = (
        f"GPU Usage: {gpu_metrics['active']}%"
        f" @ {gpu_metrics['freq_MHz']} MHz"
    )
    w["gpu_gauge"].value = gpu_metrics["active"]

    # ANE — max power varies by chip; cap at 100% to avoid gauge overflow
    ane_max_power = soc_info.get("ane_max_power", 8.0)
    ane_w = cpu_metrics["ane_W"]
    ane_util = min(100, int(ane_w / ane_max_power * 100))
    w["ane_gauge"].title = f"ANE Usage: {ane_util}% @ {ane_w:.1f} W"
    w["ane_gauge"].value = ane_util


# ---------------------------------------------------------------------------
# RAM update
# ---------------------------------------------------------------------------

def update_ram_widget(w: dict[str, Any]) -> None:
    """Refresh the RAM gauge."""
    ram = get_ram_metrics_dict()
    if ram["swap_total_GB"] < 0.1:
        swap_str = "swap inactive"
    else:
        swap_str = f"swap: {ram['swap_used_GB']}/{ram['swap_total_GB']} GB"
    w["ram_gauge"].title = (
        f"RAM Usage: {ram['used_GB']}/{ram['total_GB']} GB — {swap_str}"
    )
    w["ram_gauge"].value = ram["free_percent"]


# ---------------------------------------------------------------------------
# Power chart update
# ---------------------------------------------------------------------------

def update_power_charts(
    w: dict[str, Any],
    cpu_metrics: dict[str, Any],
    thermal_pressure: str,
    *,
    interval: int,
    cpu_max_power: float,
    gpu_max_power: float,
    avg_state: dict[str, Any],
) -> None:
    """Refresh power charts and rolling-average state.

    *avg_state* is mutated in-place; it should contain:
    ``avg_package_power_list``, ``avg_cpu_power_list``, ``avg_gpu_power_list``,
    ``cpu_peak_power``, ``gpu_peak_power``, ``package_peak_power``.
    """
    thermal_throttle = "no" if thermal_pressure.strip().lower() == "nominal" else "yes"

    pkg_w = cpu_metrics["package_W"] / interval
    avg_state["package_peak_power"] = max(avg_state["package_peak_power"], pkg_w)
    avg_state["avg_package_power_list"].append(pkg_w)
    avg_pkg = sum(avg_state["avg_package_power_list"]) / len(
        avg_state["avg_package_power_list"]
    )
    w["power_charts"].title = (
        f"CPU+GPU+ANE Power: {pkg_w:.2f} W"
        f" (avg: {avg_pkg:.2f} W  peak: {avg_state['package_peak_power']:.2f} W)"
        f"  throttle: {thermal_throttle}"
    )

    cpu_w = cpu_metrics["cpu_W"] / interval
    avg_state["cpu_peak_power"] = max(avg_state["cpu_peak_power"], cpu_w)
    avg_state["avg_cpu_power_list"].append(cpu_w)
    avg_cpu = sum(avg_state["avg_cpu_power_list"]) / len(
        avg_state["avg_cpu_power_list"]
    )
    w["cpu_power_chart"].title = (
        f"CPU: {cpu_w:.2f} W (avg: {avg_cpu:.2f} W"
        f"  peak: {avg_state['cpu_peak_power']:.2f} W)"
    )
    w["cpu_power_chart"].append(int(cpu_w / cpu_max_power * 100))
    _cap_chart(w["cpu_power_chart"])

    gpu_w = cpu_metrics["gpu_W"] / interval
    avg_state["gpu_peak_power"] = max(avg_state["gpu_peak_power"], gpu_w)
    avg_state["avg_gpu_power_list"].append(gpu_w)
    avg_gpu = sum(avg_state["avg_gpu_power_list"]) / len(
        avg_state["avg_gpu_power_list"]
    )
    w["gpu_power_chart"].title = (
        f"GPU: {gpu_w:.2f} W (avg: {avg_gpu:.2f} W"
        f"  peak: {avg_state['gpu_peak_power']:.2f} W)"
    )
    w["gpu_power_chart"].append(int(gpu_w / gpu_max_power * 100))
    _cap_chart(w["gpu_power_chart"])


# ---------------------------------------------------------------------------
# WiFi widget update
# ---------------------------------------------------------------------------

def update_wifi_widget(w: dict[str, Any], wifi: dict[str, Any]) -> None:
    """Refresh the WiFi gauge with signal strength and network info.

    *wifi* is a pre-fetched dict from the background collector.
    """
    if wifi["connected"]:
        rssi = wifi["rssi_dBm"] or 0
        # Map RSSI to 0–100 gauge: –30 dBm = 100%, –90 dBm = 0%
        signal_pct = max(0, min(100, int((rssi + 90) / 60 * 100)))
        rate_str = f" {wifi['tx_rate_Mbps']:.0f} Mbps" if wifi["tx_rate_Mbps"] else ""
        w["wifi_gauge"].title = (
            f"WiFi: {wifi['ssid']}  {rssi} dBm ({signal_pct}%){rate_str}"
        )
        w["wifi_gauge"].value = signal_pct
    else:
        w["wifi_gauge"].title = "WiFi: disconnected"
        w["wifi_gauge"].value = 0


# ---------------------------------------------------------------------------
# Power / battery / charger widget update
# ---------------------------------------------------------------------------

def update_power_widgets(w: dict[str, Any], pwr: dict[str, Any]) -> None:
    """Refresh battery and charger gauges.

    *pwr* is a pre-fetched dict from the background collector.
    """

    # Battery gauge
    pct = pwr["battery_percent"]
    if pct is not None:
        state = "Charging" if pwr["charging"] else ("Charged" if pwr["charged"] else "Discharging")
        time_str = f" — {pwr['time_remaining']}" if pwr["time_remaining"] else ""
        w["battery_gauge"].title = f"Battery: {pct}% ({state}){time_str}"
        w["battery_gauge"].value = pct
    else:
        w["battery_gauge"].title = "Battery: N/A (Desktop Mac)"
        w["battery_gauge"].value = 0

    # Charger gauge
    if pwr["cable_connected"]:
        watt_str = f"{pwr['wattage']}W" if pwr["wattage"] else "?"
        name_str = pwr["adapter_name"] or "Unknown adapter"
        w["charger_gauge"].title = f"Charger: {name_str} ({watt_str}) — cable connected"
        w["charger_gauge"].value = 100
    else:
        w["charger_gauge"].title = "Charger: no cable connected"
        w["charger_gauge"].value = 0


# ---------------------------------------------------------------------------
# Network throughput widget update
# ---------------------------------------------------------------------------

_prev_net: dict[str, int] | None = None


def update_network_widget(
    w: dict[str, Any],
    net: dict[str, int],
    interval: int,
) -> None:
    """Refresh the network I/O gauge with per-second throughput.

    *net* is a pre-fetched dict from the background collector.
    """
    global _prev_net
    current = net

    if _prev_net is not None:
        sent_rate = (current["bytes_sent"] - _prev_net["bytes_sent"]) / interval
        recv_rate = (current["bytes_recv"] - _prev_net["bytes_recv"]) / interval
        w["net_gauge"].title = (
            f"Network: ↑ {_format_bytes(int(sent_rate))}/s"
            f"  ↓ {_format_bytes(int(recv_rate))}/s"
        )
        total_rate = sent_rate + recv_rate
        # Normalize to a simple 0-100 gauge (100 Mbps = 100%)
        max_rate = 100 * 1024 * 1024 / 8  # 100 Mbps in bytes
        w["net_gauge"].value = max(0, min(100, int(total_rate / max_rate * 100)))
    else:
        w["net_gauge"].title = "Network: measuring…"
        w["net_gauge"].value = 0

    _prev_net = current


# ---------------------------------------------------------------------------
# Top processes widget update
# ---------------------------------------------------------------------------

def update_top_widget(w: dict[str, Any], top: list[dict[str, Any]]) -> None:
    """Render the top-processes table.

    *top* is a pre-fetched list from the background collector.
    """
    widget = w.get("top_text")
    if widget is None:
        return
    if not top:
        widget.text = "sampling…"
        return
    widget.text = "\n".join(
        f"{row['cpu_percent']:5.1f}% {_format_bytes(row['rss']):>9}  "
        f"{row['name'][:18]}"
        for row in top
    )
