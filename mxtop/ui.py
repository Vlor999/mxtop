"""UI construction for mxtop — builds all dashing widgets and layouts."""

from __future__ import annotations

from typing import Any

from dashing import VSplit, HSplit, HGauge, HChart, VGauge

from loguru import logger


def build_ui(args: Any, soc_info: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Create and return all dashing widgets and the top-level UI split.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments (``color``, ``show_cores``).
    soc_info : dict
        SoC information from :func:`mxtop.utils.get_soc_info`.

    Returns
    -------
    tuple[ui, widgets]
        *ui* is the top-level dashing split; *widgets* is a dict of named
        widget references used by the updater.
    """
    color = args.color
    e_core_count = soc_info["e_core_count"]
    p_core_count = soc_info["p_core_count"]

    logger.debug(
        "Building UI (color={}, show_cores={}, e={}, p={})",
        color, args.show_cores, e_core_count, p_core_count,
    )

    # ---- Processor gauges ------------------------------------------------
    cpu1_gauge = HGauge(title="E-CPU Usage", val=0, color=color)
    cpu2_gauge = HGauge(title="P-CPU Usage", val=0, color=color)
    gpu_gauge  = HGauge(title="GPU Usage",   val=0, color=color)
    ane_gauge  = HGauge(title="ANE",         val=0, color=color)

    e_core_gauges = [
        VGauge(val=0, color=color, border_color=color)
        for _ in range(e_core_count)
    ]
    p_core_gauges = [
        VGauge(val=0, color=color, border_color=color)
        for _ in range(min(p_core_count, 8))
    ]
    p_core_split = [HSplit(*p_core_gauges)]

    p_core_gauges_ext: list[VGauge] = []
    if p_core_count > 8:
        p_core_gauges_ext = [
            VGauge(val=0, color=color, border_color=color)
            for _ in range(p_core_count - 8)
        ]
        p_core_split.append(HSplit(*p_core_gauges_ext))

    if args.show_cores:
        processor_gauges = [
            cpu1_gauge, HSplit(*e_core_gauges),
            cpu2_gauge, *p_core_split,
            gpu_gauge, ane_gauge,
        ]
    else:
        processor_gauges = [
            HSplit(cpu1_gauge, cpu2_gauge),
            HSplit(gpu_gauge, ane_gauge),
        ]

    processor_split = VSplit(
        *processor_gauges,
        title="Processor Utilization",
        border_color=color,
    )

    # ---- Memory ----------------------------------------------------------
    ram_gauge = HGauge(title="RAM Usage", val=0, color=color)
    memory_gauges = VSplit(ram_gauge, border_color=color, title="Memory")

    # ---- Power charts ----------------------------------------------------
    cpu_power_chart = HChart(title="CPU Power", color=color)
    gpu_power_chart = HChart(title="GPU Power", color=color)

    if args.show_cores:
        power_charts = VSplit(
            cpu_power_chart, gpu_power_chart,
            title="Power Chart", border_color=color,
        )
    else:
        power_charts = HSplit(
            cpu_power_chart, gpu_power_chart,
            title="Power Chart", border_color=color,
        )

    # ---- WiFi panel ------------------------------------------------------
    wifi_gauge = HGauge(title="WiFi", val=0, color=color)

    # ---- Power source / battery panel ------------------------------------
    battery_gauge  = HGauge(title="Battery", val=0, color=color)
    charger_gauge  = HGauge(title="Charger", val=0, color=color)

    system_info_panel = VSplit(
        wifi_gauge,
        battery_gauge,
        charger_gauge,
        title="System Info",
        border_color=color,
    )

    # ---- Network throughput panel ----------------------------------------
    net_gauge = HGauge(title="Network", val=0, color=color)

    # ---- Network throughput wrapped panel ---------------------------------
    net_panel = VSplit(net_gauge, border_color=color, title="Network I/O")

    # ---- Top-level layout ------------------------------------------------
    if args.show_cores:
        ui = HSplit(
            processor_split,
            VSplit(
                memory_gauges,
                HSplit(system_info_panel, net_panel),
                power_charts,
            ),
        )
    else:
        ui = VSplit(
            processor_split,
            HSplit(memory_gauges, system_info_panel, net_panel),
            power_charts,
        )

    widgets = {
        "cpu1_gauge":        cpu1_gauge,
        "cpu2_gauge":        cpu2_gauge,
        "gpu_gauge":         gpu_gauge,
        "ane_gauge":         ane_gauge,
        "e_core_gauges":     e_core_gauges,
        "p_core_gauges":     p_core_gauges,
        "p_core_gauges_ext": p_core_gauges_ext,
        "ram_gauge":         ram_gauge,
        "cpu_power_chart":   cpu_power_chart,
        "gpu_power_chart":   gpu_power_chart,
        "power_charts":      power_charts,
        "processor_split":   processor_split,
        "wifi_gauge":        wifi_gauge,
        "battery_gauge":     battery_gauge,
        "charger_gauge":     charger_gauge,
        "net_gauge":         net_gauge,
    }
    return ui, widgets
