"""mxtop — Performance monitoring CLI tool for Apple Silicon."""

from __future__ import annotations

import sys
import time
import argparse
import threading
from collections import deque

from loguru import logger

from .utils import (
    get_soc_info,
    run_powermetrics_process,
    parse_powermetrics,
    cleanup_tmp_files,
    clear_console,
)
from .keyboard import keyboard_listener
from .ui import build_ui
from .system_info import BackgroundMetricsCollector
from .updater import (
    _MAX_CHART_POINTS,
    _cap_chart,
    update_processor_widgets,
    update_ram_widget,
    update_power_charts,
    update_wifi_widget,
    update_power_widgets,
    update_network_widget,
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="mxtop: Performance monitoring CLI tool for Apple Silicon"
    )
    parser.add_argument(
        "--interval", type=int, default=1,
        help="Display interval and sampling interval for powermetrics (seconds)",
    )
    parser.add_argument(
        "--color", type=int, default=2,
        help="Choose display color (0-8)",
    )
    parser.add_argument(
        "--avg", type=int, default=30,
        help="Interval for averaged values (seconds)",
    )
    parser.add_argument(
        "--show_cores", type=bool, default=False,
        help="Show individual core utilization",
    )
    parser.add_argument(
        "--max_count", type=int, default=0,
        help="Max sample count before restarting powermetrics (0 = unlimited)",
    )
    parser.add_argument(
        "--log-level", type=str, default="WARNING",
        help="Set loguru log level (DEBUG, INFO, WARNING, ERROR)",
    )
    args = parser.parse_args()

    # Configure loguru
    logger.remove()  # remove default stderr handler
    logger.add(sys.stderr, level=args.log_level.upper())

    print("\nmxtop - Performance monitoring CLI tool for Apple Silicon")
    print("Press  q  or  ESC  to quit.")
    print("Run with `sudo mxtop` for full metrics.\n")
    print("\n[1/3] Loading mxtop\n")
    print("\033[?25l")  # hide cursor

    soc_info = get_soc_info()
    logger.info("Detected SoC: {}", soc_info["name"])

    ui, w = build_ui(args, soc_info)

    w["processor_split"].title = (
        f"{soc_info['name']} "
        f"(cores: {soc_info['e_core_count']}E+"
        f"{soc_info['p_core_count']}P+"
        f"{soc_info['gpu_core_count']}GPU)"
    )

    cpu_max_power = soc_info["cpu_max_power"]
    gpu_max_power = soc_info["gpu_max_power"]

    print("\n[2/3] Starting powermetrics process\n")
    timecode = str(int(time.time()))
    powermetrics_process = run_powermetrics_process(timecode, interval=args.interval * 1000)
    logger.info("powermetrics started (timecode={})", timecode)

    print("\n[3/3] Waiting for first reading...\n")

    # Block until the first valid reading arrives
    ready = None
    while ready is None:
        time.sleep(0.1)
        ready = parse_powermetrics(timecode=timecode)
    last_timestamp = ready[-1]

    # Rolling averages state (mutated by update_power_charts)
    maxlen = max(1, int(args.avg / args.interval))
    avg_state: dict = {
        "avg_package_power_list": deque(maxlen=maxlen),
        "avg_cpu_power_list":     deque(maxlen=maxlen),
        "avg_gpu_power_list":     deque(maxlen=maxlen),
        "cpu_peak_power":         0.0,
        "gpu_peak_power":         0.0,
        "package_peak_power":     0.0,
    }

    # Start keyboard listener thread
    stop_event = threading.Event()
    kb_thread = threading.Thread(
        target=keyboard_listener, args=(stop_event,), daemon=True,
    )
    kb_thread.start()

    # Start background metrics collector (WiFi, battery, network — slow calls)
    bg_collector = BackgroundMetricsCollector(interval=5.0)
    bg_collector.start(stop_event)

    clear_console()
    count = 0

    try:
        while not stop_event.is_set():
            # Optionally restart powermetrics periodically
            if args.max_count > 0:
                if count >= args.max_count:
                    count = 0
                    powermetrics_process.terminate()
                    timecode = str(int(time.time()))
                    powermetrics_process = run_powermetrics_process(
                        timecode, interval=args.interval * 1000,
                    )
                    logger.debug("Restarted powermetrics (timecode={})", timecode)
                count += 1

            ready = parse_powermetrics(timecode=timecode)
            if ready:
                cpu_metrics, gpu_metrics, thermal_pressure, _, timestamp = ready

                if timestamp <= last_timestamp:
                    time.sleep(args.interval)
                    continue
                last_timestamp = timestamp

                # --- Processor (CPU / GPU / ANE / cores) ---
                update_processor_widgets(
                    w, cpu_metrics, gpu_metrics, soc_info,
                    show_cores=args.show_cores,
                )

                # --- RAM ---
                update_ram_widget(w)

                # --- Power charts ---
                update_power_charts(
                    w, cpu_metrics, thermal_pressure,
                    interval=args.interval,
                    cpu_max_power=cpu_max_power,
                    gpu_max_power=gpu_max_power,
                    avg_state=avg_state,
                )

                # --- WiFi ---
                update_wifi_widget(w, bg_collector.wifi)

                # --- Battery / charger ---
                update_power_widgets(w, bg_collector.power)

                # --- Network I/O ---
                update_network_widget(w, bg_collector.network, interval=args.interval)

                ui.display()

            time.sleep(args.interval)

    finally:
        stop_event.set()
        try:
            powermetrics_process.terminate()
            powermetrics_process.wait(timeout=3)
        except Exception:
            powermetrics_process.kill()
        cleanup_tmp_files()
        print("\033[?25h")  # restore cursor
        print("\nStopped.")
        logger.info("mxtop stopped")


if __name__ == "__main__":
    main()
