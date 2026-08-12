# mxtop v0.2.0 — Disk I/O, Top Processes, Export & Root Hardening

> **mxtop** is an actively maintained fork of the original [`asitop`](https://github.com/tlkh/asitop).
> It aims to fix long-standing bugs and ensure compatibility with the latest macOS updates and Apple Silicon chips.

---

## Highlights

- **Disk I/O panel** — read/write throughput alongside network
- **Top processes panel** — heaviest processes by CPU, with resident memory (`--top N`)
- **Sample export** — append every reading to CSV or JSON Lines (`--export PATH`)
- **Ghostty support** — no more unstyled dashboard on terminals missing a terminfo entry
- **Runs without `sudo`** — degrades instead of crashing when the powermetrics file is not writable
- **Security hardening** — mxtop runs as root; five places that trusted attacker-controlled input are closed

## What's New

### Disk I/O panel

Read and write throughput now sit next to network throughput in a shared **I/O**
panel. Rates are derived from a timestamp carried on each sample rather than the
display interval, so they stay correct whatever the collector's refresh rate is.

```
Network: ↑ 12.4 KB/s  ↓ 1.2 MB/s
Disk: R 340.0 KB/s  W 12.1 MB/s
```

### Top processes (`--top N`)

A new panel lists the heaviest processes by CPU, then by resident memory.
`--top 0` hides it. CPU percentages are measured between successive collector
passes, so the first sample after startup reads 0% for everything and the
ranking becomes meaningful from the second pass on.

```
 42.1%   1.2 GB   Safari
 18.7% 340.0 MB   WindowServer
```

### Sample export (`--export PATH`)

Append every reading to a file, format chosen by the extension:

| extension | format |
|---|---|
| `.csv` | CSV with a header row |
| `.json`, `.jsonl`, `.ndjson` | JSON Lines, one object per line |

Rows are flushed as they are written, so the file is readable while mxtop is
still running and stays complete if the run is interrupted with `q` or Ctrl-C.
Under `sudo mxtop` the file is handed back to the invoking user rather than left
root-owned.

### Terminal compatibility

`TERM` values with no entry in the system terminfo database — Ghostty's
`xterm-ghostty` is the common one — now fall back to `xterm-256color` at package
import, before `blessed` is loaded. Previously the dashboard rendered unstyled
behind a `setupterm` warning, and the only workarounds were `TERM=xterm-256color
sudo mxtop` or editing the Ghostty config. Fixes #5.

### Running without `sudo`

`powermetrics` always runs as root, so without `sudo mxtop` its output file
belongs to root and cannot be opened for writing. That is no longer fatal: the
file is read read-only and left untouched instead of raising.

A failed `powermetrics` start is also reported now. Its stderr goes to
`DEVNULL`, so the startup loop used to spin forever on
`[3/3] Waiting for first reading...`; it polls the child and exits with its
status.

### Security hardening

mxtop runs as root under `sudo mxtop`. Five places took input from somewhere a
local unprivileged user controls:

| what | before | after |
|---|---|---|
| powermetrics temp file | `/tmp/mxtop_powermetrics<epoch>` — predictable name in a world-writable directory, reopened `O_RDWR`, truncated and rewritten as root | private `mkdtemp` directory (0700), opened `O_NOFOLLOW` with an `S_ISREG` check |
| helper binaries | resolved through `$PATH`; macOS sudo sets no `secure_path`, so that is the invoking user's `PATH` | absolute paths at every call site |
| `clear_console()` | `os.system("clear")` — a shell, plus a `$PATH` lookup | one `print()` of the ANSI sequence |
| process names, WiFi SSIDs, adapter names | rendered raw into a root-driven terminal | control characters stripped before rendering |
| `--export` under sudo | root-owned file the user could not edit or delete | `fchown` back to the invoking user |

The first of these allowed a local user to have root truncate and overwrite an
arbitrary file. If you run mxtop with `sudo`, upgrade.

## CLI Options

```bash
sudo mxtop --interval 2 --color 3 --avg 60 --top 8 --export run.csv
```

| Flag | Default | Description |
|------|---------|-------------|
| `--interval` | 1 | Sampling & display interval (seconds) |
| `--color` | 2 | TUI color scheme (0–8) |
| `--avg` | 30 | Rolling average window (seconds) |
| `--show_cores` | False | Show individual core utilization |
| `--max_count` | 0 | Restart powermetrics after N samples (0 = unlimited) |
| `--top` | 5 | Top CPU processes to display (0 hides the panel) |
| `--export` | — | Append every sample to PATH (`.csv`, or `.json`/`.jsonl`/`.ndjson`) |
| `--log-level` | WARNING | Loguru log level |

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
| **Disk** | Read & write throughput (bytes/s) |
| **Processes** | Top N by CPU, with resident memory |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `dashing` | ≥ 0.1.0 | Terminal UI widgets |
| `loguru` | ≥ 0.7.0 | Structured logging |
| `psutil` | ≥ 7.2.2 | System metrics (RAM, network, disk, processes) |

## Test Suite

93 tests:

```bash
uv run --group test pytest tests/ -q
```

## Requirements

- macOS Monterey or later
- Apple Silicon (M1, M2, M3, M4 family)
- Python ≥ 3.11

## License

MIT

---

**Full Changelog**: https://github.com/Vlor999/mxtop/compare/v0.1.1...v0.2.0
