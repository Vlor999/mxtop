"""Tests for mxtop.mxtop — UI helpers and chart capping."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from mxtop.updater import _cap_chart, _MAX_CHART_POINTS


# ---------------------------------------------------------------------------
# _cap_chart
# ---------------------------------------------------------------------------

class TestCapChart:
    def _make_chart(self, n: int):
        """Return a mock HChart with *n* datapoints."""
        chart = MagicMock()
        chart.datapoints = list(range(n))
        return chart

    def test_under_limit_untouched(self):
        chart = self._make_chart(10)
        _cap_chart(chart)
        assert len(chart.datapoints) == 10

    def test_exact_limit_untouched(self):
        chart = self._make_chart(_MAX_CHART_POINTS)
        _cap_chart(chart)
        assert len(chart.datapoints) == _MAX_CHART_POINTS

    def test_over_limit_trimmed(self):
        chart = self._make_chart(_MAX_CHART_POINTS + 100)
        _cap_chart(chart)
        assert len(chart.datapoints) == _MAX_CHART_POINTS
        # Should keep the newest values (tail)
        assert chart.datapoints[-1] == _MAX_CHART_POINTS + 99

    def test_empty(self):
        chart = self._make_chart(0)
        _cap_chart(chart)
        assert len(chart.datapoints) == 0

    def test_custom_maxlen(self):
        chart = self._make_chart(20)
        _cap_chart(chart, maxlen=5)
        assert len(chart.datapoints) == 5
        assert chart.datapoints == [15, 16, 17, 18, 19]

    def test_no_datapoints_attr(self):
        """Should not crash if chart lacks datapoints attribute."""
        chart = MagicMock(spec=[])  # no attributes
        _cap_chart(chart)  # should not raise


# ---------------------------------------------------------------------------
# _MAX_CHART_POINTS constant
# ---------------------------------------------------------------------------

def test_max_chart_points_is_sane():
    assert 100 <= _MAX_CHART_POINTS <= 10_000


# ---------------------------------------------------------------------------
# build_ui smoke test
# ---------------------------------------------------------------------------

class TestBuildUi:
    @patch("mxtop.ui.HChart")
    @patch("mxtop.ui.HGauge")
    @patch("mxtop.ui.VGauge")
    @patch("mxtop.ui.VSplit")
    @patch("mxtop.ui.HSplit")
    def test_returns_ui_and_widgets(self, mock_hsplit, mock_vsplit, mock_vgauge, mock_hgauge, mock_hchart):
        """build_ui should return (ui, widgets_dict)."""
        from mxtop.ui import build_ui
        import argparse

        args = argparse.Namespace(color=2, show_cores=False)
        soc_info = {
            "name": "Apple M1",
            "core_count": 8,
            "e_core_count": 4,
            "p_core_count": 4,
            "gpu_core_count": 8,
            "cpu_max_power": 20,
            "gpu_max_power": 20,
        }

        ui, widgets = build_ui(args, soc_info)
        assert isinstance(widgets, dict)
        expected_keys = {
            "cpu1_gauge", "cpu2_gauge", "gpu_gauge", "ane_gauge",
            "ram_gauge", "cpu_power_chart", "gpu_power_chart",
            "wifi_gauge", "battery_gauge", "charger_gauge", "net_gauge",
        }
        assert expected_keys <= set(widgets.keys())
