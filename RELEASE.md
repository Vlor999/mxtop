# mxtop v0.1.0 — Initial Release

> **mxtop** is an actively maintained fork of the original [`asitop`](https://github.com/tlkh/asitop).
> It aims to fix long-standing bugs and ensure compatibility with the latest macOS updates and Apple Silicon chips.

---

## Highlights

- Full rebrand from `asitop` to `mxtop`
- Cleaned and modernized codebase
- Keyboard-driven exit (press **q** or **ESC** to quit)
- Modern Python packaging with `pyproject.toml` and `uv`

## What's New

### Rebranding
- Package renamed from `asitop` to `mxtop` across all files, imports, and entry points.
- New repository: [github.com/Vlor999/mxtop](https://github.com/Vlor999/mxtop)

### Code Quality
- **Argument parsing** moved inside `main()` — no more side effects on import.
- **Wildcard imports** (`from .utils import *`) replaced with explicit named imports.
- **UI construction** extracted into a dedicated `_build_ui()` helper function.
- **~400 lines of dead code removed** — commented-out bandwidth gauges, duplicated main body, triple-quoted dead blocks.
- **String formatting** modernized — old `.join()` chains replaced with f-strings.

### Keyboard Input
- Added a background `_keyboard_listener()` thread for clean exit on **ESC**, **q**, or **Q**.
- Graceful cleanup: cursor is restored and terminal state is reset on exit.

### Packaging
- Migrated from `setup.py` to `pyproject.toml` with `hatchling` build backend.
- Dependency management via `uv`.
- Console entry point: `mxtop = "mxtop.mxtop:main"`

## Installation

```bash
pip install mxtop
```

Or install from source:

```bash
git clone https://github.com/Vlor999/mxtop.git
cd mxtop
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Usage

```bash
# Recommended (powermetrics requires root)
sudo mxtop

# Without sudo (will prompt for password)
mxtop

# Options
mxtop --interval 2 --color 3 --avg 60
```

Press **q** or **ESC** to quit.

## Monitored Metrics

| Category | Metrics |
|----------|---------|
| **CPU** | E-Cluster & P-Cluster utilization, frequency (MHz) |
| **GPU** | Utilization, frequency (MHz) |
| **ANE** | Neural Engine utilization (estimated via power) |
| **Memory** | RAM & swap usage |
| **Power** | CPU, GPU, package power (W) with rolling avg & peak |
| **Thermal** | Throttle status |

## Requirements

- macOS Monterey or later
- Apple Silicon (M1, M2, M3, M4 family)
- Python ≥ 3.11

## License

MIT

---

**Full Changelog**: https://github.com/Vlor999/mxtop/commits/v0.1.0
