"""Tests for mxtop.updater — widget update functions."""

from __future__ import annotations

from collections import deque
from unittest.mock import patch, MagicMock

from mxtop.updater import (
    _cap_chart,
    _format_bytes,
    _MAX_CHART_POINTS,
    update_processor_widgets,
    update_ram_widget,
    update_power_charts,
    update_wifi_widget,
    update_power_widgets,
    update_network_widget,
)


# ---------------------------------------------------------------------------
# _format_bytes
# ---------------------------------------------------------------------------

class TestFormatBytes:
    def test_bytes(self):
        assert _format_bytes(512) == "512.0 B"

    def test_kb(self):
        assert _format_bytes(2048) == "2.0 KB"

    def test_mb(self):
        assert _format_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_gb(self):
        assert _format_bytes(3 * 1024 ** 3) == "3.0 GB"


# ---------------------------------------------------------------------------
# update_processor_widgets
# ---------------------------------------------------------------------------

class TestUpdateProcessorWidgets:
    def _make_widgets(self):
        return {
            "cpu1_gauge": MagicMock(),
            "cpu2_gauge": MagicMock(),
            "gpu_gauge":  MagicMock(),
            "ane_gauge":  MagicMock(),
            "e_core_gauges": [MagicMock() for _ in range(4)],
            "p_core_gauges": [MagicMock() for _ in range(4)],
            "p_core_gauges_ext": [],
        }

    def test_basic_update(self):
        w = self._make_widgets()
        cpu = {
            "E-Cluster_active": 42,
            "E-Cluster_freq_Mhz": 2064,
            "P-Cluster_active": 70,
            "P-Cluster_freq_Mhz": 3504,
            "ane_W": 2.0,
            "e_core": [],
            "p_core": [],
        }
        gpu = {"active": 55, "freq_MHz": 1398}
        soc = {"p_core_count": 4}

        update_processor_widgets(w, cpu, gpu, soc)
        assert w["cpu1_gauge"].value == 42
        assert w["cpu2_gauge"].value == 70
        assert w["gpu_gauge"].value == 55


# ---------------------------------------------------------------------------
# update_ram_widget
# ---------------------------------------------------------------------------

class TestUpdateRamWidget:
    @patch("mxtop.updater.get_ram_metrics_dict")
    def test_basic(self, mock_ram):
        mock_ram.return_value = {
            "total_GB": 16.0,
            "used_GB": 10.0,
            "free_GB": 6.0,
            "free_percent": 63,
            "swap_total_GB": 2.0,
            "swap_used_GB": 0.5,
            "swap_free_GB": 1.5,
            "swap_free_percent": 25,
        }
        w = {"ram_gauge": MagicMock()}
        update_ram_widget(w)
        assert w["ram_gauge"].value == 63
        assert "16.0" in w["ram_gauge"].title
        assert "10.0" in w["ram_gauge"].title


# ---------------------------------------------------------------------------
# update_power_charts
# ---------------------------------------------------------------------------

class TestUpdatePowerCharts:
    def test_basic(self):
        w = {
            "power_charts": MagicMock(),
            "cpu_power_chart": MagicMock(),
            "gpu_power_chart": MagicMock(),
        }
        cpu = {"package_W": 15.0, "cpu_W": 8.0, "gpu_W": 5.0}
        avg_state = {
            "avg_package_power_list": deque(maxlen=30),
            "avg_cpu_power_list": deque(maxlen=30),
            "avg_gpu_power_list": deque(maxlen=30),
            "cpu_peak_power": 0.0,
            "gpu_peak_power": 0.0,
            "package_peak_power": 0.0,
        }

        update_power_charts(
            w, cpu, "Nominal",
            interval=1, cpu_max_power=20, gpu_max_power=20,
            avg_state=avg_state,
        )
        assert avg_state["cpu_peak_power"] == 8.0
        assert avg_state["gpu_peak_power"] == 5.0
        assert avg_state["package_peak_power"] == 15.0


# ---------------------------------------------------------------------------
# update_wifi_widget
# ---------------------------------------------------------------------------

class TestUpdateWifiWidget:
    def test_connected(self):
        wifi_data = {
            "connected": True,
            "ssid": "TestNet",
            "rssi_dBm": -50,
            "tx_rate_Mbps": 866.0,
        }
        w = {"wifi_gauge": MagicMock()}
        update_wifi_widget(w, wifi_data)
        assert "TestNet" in w["wifi_gauge"].title
        assert w["wifi_gauge"].value > 0

    def test_disconnected(self):
        wifi_data = {
            "connected": False,
            "ssid": None,
            "rssi_dBm": None,
            "tx_rate_Mbps": None,
        }
        w = {"wifi_gauge": MagicMock()}
        update_wifi_widget(w, wifi_data)
        assert "disconnected" in w["wifi_gauge"].title
        assert w["wifi_gauge"].value == 0


# ---------------------------------------------------------------------------
# update_power_widgets
# ---------------------------------------------------------------------------

class TestUpdatePowerWidgets:
    def test_on_battery(self):
        pwr_data = {
            "source": "Battery",
            "battery_percent": 80,
            "charging": False,
            "charged": False,
            "time_remaining": "3:00 remaining",
            "wattage": None,
            "adapter_name": None,
            "cable_connected": False,
        }
        w = {"battery_gauge": MagicMock(), "charger_gauge": MagicMock()}
        update_power_widgets(w, pwr_data)
        assert w["battery_gauge"].value == 80
        assert "Discharging" in w["battery_gauge"].title
        assert "no cable" in w["charger_gauge"].title

    def test_on_ac(self):
        pwr_data = {
            "source": "AC Power",
            "battery_percent": 95,
            "charging": True,
            "charged": False,
            "time_remaining": "0:30 remaining",
            "wattage": 96,
            "adapter_name": "96W USB-C",
            "cable_connected": True,
        }
        w = {"battery_gauge": MagicMock(), "charger_gauge": MagicMock()}
        update_power_widgets(w, pwr_data)
        assert w["battery_gauge"].value == 95
        assert "Charging" in w["battery_gauge"].title
        assert w["charger_gauge"].value == 100
        assert "96W" in w["charger_gauge"].title


# ---------------------------------------------------------------------------
# update_network_widget
# ---------------------------------------------------------------------------

class TestUpdateNetworkWidget:
    def test_first_call_measuring(self):
        """First call has no previous data — should show 'measuring'."""
        import mxtop.updater as mod
        mod._prev_net = None  # reset global state

        net_data = {"bytes_sent": 1000, "bytes_recv": 2000}
        w = {"net_gauge": MagicMock()}
        update_network_widget(w, net_data, interval=1)
        assert "measuring" in w["net_gauge"].title

    def test_second_call_shows_rate(self):
        import mxtop.updater as mod
        mod._prev_net = {"bytes_sent": 1000, "bytes_recv": 2000}

        net_data = {"bytes_sent": 2000, "bytes_recv": 4000}
        w = {"net_gauge": MagicMock()}
        update_network_widget(w, net_data, interval=1)
        assert "↑" in w["net_gauge"].title
        assert "↓" in w["net_gauge"].title
