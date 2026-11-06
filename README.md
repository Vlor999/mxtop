# mxtop

[![CI](https://github.com/Vlor999/mxtop/actions/workflows/ci.yml/badge.svg)](https://github.com/Vlor999/mxtop/actions/workflows/ci.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/mxtop)](https://pypi.org/project/mxtop/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/mxtop)](https://pypi.org/project/mxtop/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mxtop)
![License](https://img.shields.io/pypi/l/mxtop)

![macOS](https://img.shields.io/badge/macOS-000000?style=flat&logo=apple&logoColor=white)
[![GitHub Repo stars](https://img.shields.io/github/stars/Vlor999/mxtop?style=social)](https://github.com/Vlor999/mxtop)
[![GitHub issues](https://img.shields.io/github/issues/Vlor999/mxtop)](https://github.com/Vlor999/mxtop/issues)

Performance monitoring CLI tool for Apple silicon.

mxtop is a maintained fork of [`asitop`](https://github.com/tlkh/asitop) that fixes its long-standing bugs and keeps it working on new macOS releases and chips.

![](images/mxtop.png)

```shell
pip install mxtop
```

## What is `mxtop`

A Python-based `nvtop`-inspired command line tool for Apple silicon (M1 and later) Macs.

* Utilization info:
  * CPU (E-cluster and P-cluster), GPU
  * Frequency and utilization
  * ANE utilization (measured by power)
* Memory info:
  * RAM and swap, size and usage
  * (Apple removed memory bandwidth from `powermetrics`)
* I/O info:
  * Network throughput (up/down)
  * Disk throughput (read/write)
* Top processes:
  * Heaviest processes by CPU, with their resident memory
* Power info:
  * CPU power, GPU power, and combined CPU+GPU+ANE power (`powermetrics` no longer reports a true package power)
  * Chart for CPU/GPU power
  * Peak power, rolling average display
  * Thermal throttling state
* System info:
  * WiFi connection
  * Battery level and charger

`mxtop` uses the built-in [`powermetrics`](https://www.unix.com/man-page/osx/1/powermetrics/) utility on macOS, which allows access to a variety of hardware performance counters. Note that it requires `sudo` to run due to `powermetrics` needing root access to run. `mxtop` is lightweight and has minimal performance impact.

**`mxtop` works on Apple Silicon Macs (M1 through M4) on macOS Monterey and later.**

## Installation and Usage

`mxtop` needs Python 3.11 or later. The `python3` bundled with the Xcode Command Line Tools can be older than that, so install a recent Python first (from python.org, Homebrew or `uv`). Then install `mxtop` with `pip install mxtop`, or as an isolated tool with `uv tool install mxtop` or `pipx install mxtop`, and run it from the Terminal.

```shell
# recommended: enter your password before start
sudo mxtop

# it will prompt for password on start
mxtop

# press q or ESC to quit

# all options
mxtop [-h] [--interval INTERVAL] [--color COLOR] [--avg AVG]
      [--show_cores SHOW_CORES] [--max_count MAX_COUNT] [--top N]
      [--export PATH] [--log-level LOG_LEVEL]

options:
  -h, --help            show this help message and exit
  --interval INTERVAL   Display interval and sampling interval for powermetrics (seconds)
  --color COLOR         Choose display color (0-8)
  --avg AVG             Interval for averaged values (seconds)
  --show_cores SHOW_CORES
                        Show individual core utilization. Takes a value:
                        any non-empty value turns it on, including `False`,
                        so pass `--show_cores 1` or leave it out.
  --max_count MAX_COUNT Max samples before restarting powermetrics (0 = unlimited)
  --top N               Number of top CPU processes to display (0 hides the
                        panel, default 5)
  --export PATH         Append every sample to PATH. `.csv` writes a header row
                        plus one row per sample; `.json`, `.jsonl` and `.ndjson`
                        write JSON Lines (one object per line). Rows are flushed
                        as they are written, so the file is readable while mxtop
                        runs and stays complete if the run is interrupted.
  --log-level LOG_LEVEL Log level for messages on stderr (DEBUG, INFO,
                        WARNING, ERROR; default WARNING)
```

## How it works

`powermetrics` is used to measure the following:

* CPU/GPU utilization via active residency
* CPU/GPU frequency
* CPU/GPU/ANE energy consumption
* Thermal pressure

[`psutil`](https://github.com/giampaolo/psutil) is used to measure the following:

* memory and swap usage
* network and disk throughput
* top processes by CPU

[`sysctl`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/sysctl.3.html) is used to measure the following:

* CPU name
* CPU core counts

[`system_profiler`](https://ss64.com/osx/system_profiler.html) is used to measure the following:

* GPU core count
* WiFi connection
* battery and charger details

[`pmset`](https://ss64.com/osx/pmset.html) is used to measure the following:

* battery level and power source

Some values are hardcoded estimates, because the system does not expose an official source for them:

* CPU/GPU TDP per chip, used to scale the power charts
* ANE max power (8 W for every chip), used to turn ANE power into a utilization percentage

## License

MIT, see [LICENSE](LICENSE) for details.
