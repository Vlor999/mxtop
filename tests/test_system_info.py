"""Tests for mxtop.system_info — WiFi, power source, network metrics."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from mxtop.system_info import get_wifi_metrics, get_power_metrics, get_network_throughput


# ---------------------------------------------------------------------------
# get_wifi_metrics
# ---------------------------------------------------------------------------

class TestGetWifiMetrics:
    @patch("mxtop.system_info.subprocess.run")
    def test_connected_via_system_profiler(self, mock_run):
        """system_profiler SPAirPortDataType provides WiFi info on modern macOS."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Wi-Fi:\n"
                "\n"
                "      Current Network Information:\n"
                "        MyNetwork:\n"
                "          PHY Mode: ax\n"
                "          Channel: 36\n"
                "          Signal / Noise: -52 dBm / -90 dBm\n"
                "          Transmit Rate: 866\n"
            ),
        )
        wifi = get_wifi_metrics()
        assert wifi["connected"] is True
        assert wifi["ssid"] == "MyNetwork"
        assert wifi["rssi_dBm"] == -52
        assert wifi["noise_dBm"] == -90
        assert wifi["tx_rate_Mbps"] == 866.0
        assert wifi["channel"] == "36"

    @patch("mxtop.system_info.subprocess.run")
    def test_connected_via_legacy_airport(self, mock_run):
        """Falls back to legacy airport -I when system_profiler has no data."""
        def side_effect(cmd, **kw):
            if "system_profiler" in cmd:
                return MagicMock(returncode=0, stdout="Wi-Fi:\n")
            if "airport" in cmd[0]:
                return MagicMock(
                    returncode=0,
                    stdout=(
                        "     agrCtlRSSI: -52\n"
                        "     agrCtlNoise: -90\n"
                        "           SSID: LegacyNet\n"
                        "        channel: 36,80\n"
                        "    lastTxRate: 866\n"
                    ),
                )
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect
        wifi = get_wifi_metrics()
        assert wifi["connected"] is True
        assert wifi["ssid"] == "LegacyNet"

    @patch("mxtop.system_info.subprocess.run")
    def test_disconnected(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Wi-Fi:\n",
        )
        wifi = get_wifi_metrics()
        assert wifi["connected"] is False
        assert wifi["ssid"] is None

    @patch("mxtop.system_info.subprocess.run", side_effect=Exception("fail"))
    def test_all_methods_fail(self, mock_run):
        wifi = get_wifi_metrics()
        assert wifi["connected"] is False

    @patch("mxtop.system_info.subprocess.run")
    def test_nonzero_returncode(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        wifi = get_wifi_metrics()
        assert wifi["connected"] is False


# ---------------------------------------------------------------------------
# get_power_metrics
# ---------------------------------------------------------------------------

class TestGetPowerMetrics:
    @patch("mxtop.system_info.subprocess.run")
    def test_ac_power(self, mock_run):
        def side_effect(cmd, **kw):
            if "pmset" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=(
                        "Now drawing from 'AC Power'\n"
                        " -InternalBattery-0 (id=1234)\t95%; charging; 0:30 remaining\n"
                    ),
                )
            # system_profiler
            return MagicMock(
                returncode=0,
                stdout=(
                    "      Wattage (W): 96\n"
                    "      Name: 96W USB-C Power Adapter\n"
                    "      Connected: Yes\n"
                ),
            )

        mock_run.side_effect = side_effect
        pwr = get_power_metrics()
        assert pwr["source"] == "AC Power"
        assert pwr["cable_connected"] is True
        assert pwr["battery_percent"] == 95
        assert pwr["charging"] is True
        assert pwr["wattage"] == 96

    @patch("mxtop.system_info.subprocess.run")
    def test_battery_power(self, mock_run):
        def side_effect(cmd, **kw):
            if "pmset" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=(
                        "Now drawing from 'Battery Power'\n"
                        " -InternalBattery-0 (id=1234)\t72%; discharging; 3:45 remaining\n"
                    ),
                )
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect
        pwr = get_power_metrics()
        assert pwr["source"] == "Battery"
        assert pwr["cable_connected"] is False
        assert pwr["battery_percent"] == 72
        assert pwr["charging"] is False

    @patch("mxtop.system_info.subprocess.run", side_effect=Exception("fail"))
    def test_failure_returns_defaults(self, mock_run):
        pwr = get_power_metrics()
        assert pwr["source"] == "Unknown"
        assert pwr["battery_percent"] is None


# ---------------------------------------------------------------------------
# get_network_throughput
# ---------------------------------------------------------------------------

class TestGetNetworkThroughput:
    @patch("mxtop.system_info.psutil")
    def test_basic(self, mock_psutil):
        mock_psutil.net_io_counters.return_value = MagicMock(
            bytes_sent=1000, bytes_recv=2000,
        )
        result = get_network_throughput()
        assert result["bytes_sent"] == 1000
        assert result["bytes_recv"] == 2000
