> **mxtop** is an actively maintained fork of the original `asitop`. It aims to fix long-standing bugs and ensure compatibility with the latest macOS updates and Apple Silicon chips.
 
# mxtop

[![PyPI - Version](https://img.shields.io/pypi/v/mxtop)](https://pypi.org/project/mxtop/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/mxtop)](https://pypi.org/project/mxtop/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mxtop)
![License](https://img.shields.io/pypi/l/mxtop)

![macOS](https://img.shields.io/badge/macOS-000000?style=flat&logo=apple&logoColor=white)
[![GitHub Repo stars](https://img.shields.io/github/stars/Vlor999/mxtop?style=social)](https://github.com/Vlor999/mxtop)
[![GitHub issues](https://img.shields.io/github/issues/Vlor999/mxtop)](https://github.com/Vlor999/mxtop/issues)

Performance monitoring CLI tool for Apple Silicon

![](images/mxtop.png)

```shell
pip install mxtop
```

## What is `mxtop`

A Python-based `nvtop`-inspired command line tool for Apple Silicon (aka M1) Macs.

* Utilization info:
  * CPU (E-cluster and P-cluster), GPU
  * Frequency and utilization
  * ANE utilization (measured by power)
* Memory info:
  * RAM and swap, size and usage
  * (Apple removed memory bandwidth from `powermetrics`)
* Power info:
  * CPU power, GPU power (Apple removed package power from `powermetrics`)
  * Chart for CPU/GPU power
  * Peak power, rolling average display

`mxtop` uses the built-in [`powermetrics`](https://www.unix.com/man-page/osx/1/powermetrics/) utility on macOS, which allows access to a variety of hardware performance counters. Note that it requires `sudo` to run due to `powermetrics` needing root access to run. `mxtop` is lightweight and has minimal performance impact.

**`mxtop` works on Apple Silicon Macs (M1 through M4) on macOS Monterey and later.**

## Installation and Usage

`mxtop` is a Python-based command line tool. You need `pip` to download and install `mxtop`. macOS already comes with Python, to install `pip`, you can follow an [online guide](https://phoenixnap.com/kb/install-pip-mac). After you install `mxtop` via `pip`, you can use it via the Terminal.

```shell
# recommended — enter password before start
sudo mxtop

# it will prompt for password on start
mxtop

# press q or ESC to quit

# all options
mxtop [-h] [--interval INTERVAL] [--color COLOR] [--avg AVG]
            [--show_cores SHOW_CORES] [--max_count MAX_COUNT]

options:
  -h, --help            show this help message and exit
  --interval INTERVAL   Display interval and sampling interval for powermetrics (seconds)
  --color COLOR         Choose display color (0-8)
  --avg AVG             Interval for averaged values (seconds)
  --show_cores          Show individual core utilization
  --max_count MAX_COUNT Max samples before restarting powermetrics (0 = unlimited)
```

## How it works

`powermetrics` is used to measure the following:

* CPU/GPU utilization via active residency
* CPU/GPU frequency
* Package/CPU/GPU/ANE energy consumption
* CPU/GPU/Media Total memory bandwidth via the DCS (DRAM Command Scheduler)

[`psutil`](https://github.com/giampaolo/psutil) is used to measure the following:

* memory and swap usage

[`sysctl`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/sysctl.3.html) is used to measure the following:

* CPU name
* CPU core counts

[`system_profiler`](https://ss64.com/osx/system_profiler.html) is used to measure the following:

* GPU core count

Some information is guesstimate and hardcoded as there doesn't seem to be a official source for it on the system:

* CPU/GPU TDP
* CPU/GPU maximum memory bandwidth
* ANE max power
* Media engine max bandwidth

## License

MIT — see [LICENSE](LICENSE) for details.
