# mxtop v0.1.1 — Modular Architecture, New Panels & Performance

> **mxtop** is an actively maintained fork of the original [`asitop`](https://github.com/tlkh/asitop).
> It aims to fix long-standing bugs and ensure compatibility with the latest macOS updates and Apple Silicon chips.

---

## Highlights

- **Modular architecture** — codebase split into focused, testable modules
- **New dashboard panels** — WiFi, Battery, Charger, Network I/O
- **Loguru logging** — structured logging with runtime `--log-level` control
- **Background metrics** — slow system calls no longer block the UI
- **Parallel startup** — SoC probes run concurrently for faster boot
- **WiFi compatibility** — 3-tier fallback works on all macOS versions

## What's New

### Modular Architecture

The monolithic `mxtop.py` has been split into dedicated modules:

| Module | Responsibility |
|--------|---------------|
| `mxtop.py` | CLI entry point & main loop orchestrator |
| `ui.py` | Dashboard layout and widget construction |
| `updater.py` | Widget update logic (applies metrics to gauges/charts) |
| `keyboard.py` | Background keyboard listener thread |
| `system_info.py` | WiFi, power, battery, charger, network collectors |
| `utils.py` | SoC info, powermetrics process, RAM metrics |
| `parsers.py` | Powermetrics plist parsing |

### New Dashboard Panels

- **WiFi** — SSID, signal strength (dBm + percentage), transmit rate, channel
- **Battery** — charge level, state (Charging / Discharging / Charged), time remaining
- **Charger** — adapter name, wattage, cable connection status
- **Network I/O** — real-time upload/download throughput (bytes/s)

### Performance Improvements

- **Parallel startup**: `get_soc_info()` runs CPU, core-count, and GPU probes concurrently via `ThreadPoolExecutor`, cutting boot time by ~60%.
- **Background metrics collector**: `BackgroundMetricsCollector` runs expensive system calls (`system_profiler`, `pmset`) in a daemon thread on a 5-second cycle. The main UI loop reads thread-safe cached snapshots — no more freezes.

### Loguru Logging

- Replaced `stdlib logging` with [`loguru`](https://github.com/Delgan/loguru) across all modules.
- New `--log-level` CLI flag (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- Structured log messages with lazy formatting (`logger.info("msg {}", val)`).

### WiFi Compatibility

WiFi detection now uses a 3-tier fallback strategy:

1. `system_profiler SPAirPortDataType` — works on all macOS versions
2. Legacy `airport -I` utility — older macOS where it still exists
3. `networksetup -getairportnetwork en0` — last-resort SSID detection

### Layout

- Power charts (CPU + GPU) get their own full-width bottom row for better readability.
- System info panel groups WiFi, Battery, and Charger vertically.

## Monitored Metrics

| Category | Metrics |
|----------|---------|
| **CPU** | E-Cluster & P-Cluster utilization, frequency (MHz) |
| **GPU** | Utilization, frequency (MHz) |
| **ANE** | Neural Engine utilization (estimated via power) |
| **Memory** | RAM & swap usage |
| **Power** | CPU, GPU, package power (W) with rolling avg & peak |
| **Thermal** | Throttle status |
| **WiFi** | SSID, RSSI (dBm), noise floor, TX rate, channel |
| **Battery** | Charge %, state, time remaining |
| **Charger** | Adapter name, wattage, cable status |
| **Network** | Upload & download throughput (bytes/s) |

## CLI Options

```bash
sudo mxtop --interval 2 --color 3 --avg 60 --log-level DEBUG
```

| Flag | Default | Description |
|------|---------|-------------|
| `--interval` | 1 | Sampling & display interval (seconds) |
| `--color` | 2 | TUI color scheme (0–8) |
| `--avg` | 30 | Rolling average window (seconds) |
| `--show_cores` | False | Show individual core utilization |
| `--max_count` | 0 | Restart powermetrics after N samples (0 = unlimited) |
| `--log-level` | WARNING | Loguru log level |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `dashing` | ≥ 0.1.0 | Terminal UI widgets |
| `loguru` | ≥ 0.7.0 | Structured logging (new) |
| `psutil` | ≥ 7.2.2 | System metrics (RAM, network) |

## Test Suite

62 tests covering all modules:

```bash
uv run pytest -v
```

## Requirements

- macOS Monterey or later
- Apple Silicon (M1, M2, M3, M4 family)
- Python ≥ 3.11

## License

MIT

---

**Full Changelog**: https://github.com/Vlor999/mxtop/compare/v0.1.0...v0.1.1
