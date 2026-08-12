"""Regression tests for the root-privilege hardening."""

import os
import plistlib
import stat

from mxtop.utils import _TMP_DIR, _TMP_PREFIX, parse_powermetrics
from mxtop.updater import _printable, update_top_widget, update_wifi_widget


def _valid_plist() -> bytes:
    return plistlib.dumps({
        "timestamp": "now",
        "processor": {
            "clusters": [{
                "name": "E-Cluster", "idle_ratio": 0.5, "freq_hz": 1e9,
                "cpus": [{"cpu": 0, "idle_ratio": 0.5, "freq_hz": 1e9}],
            }],
            "ane_energy": 0, "cpu_energy": 0, "gpu_energy": 0, "combined_power": 0,
        },
        "gpu": {"freq_hz": 1e9, "idle_ratio": 0.5},
        "thermal_pressure": "Nominal",
    })


# --- temp file location ----------------------------------------------------

def test_tmp_dir_is_private_and_unpredictable():
    assert not _TMP_PREFIX.startswith("/tmp/mxtop_powermetrics")
    mode = os.stat(_TMP_DIR).st_mode
    assert stat.S_IMODE(mode) == 0o700
    assert os.stat(_TMP_DIR).st_uid == os.geteuid()


def test_symlinked_powermetrics_file_is_refused(tmp_path):
    """A symlink in place of the temp file must not be read, let alone rewritten.

    The victim holds *parseable* content followed by junk, so that without
    O_NOFOLLOW the parser succeeds and truncates the file down to the plist —
    which is exactly the root-owned overwrite this guards against.
    """
    original = _valid_plist() + b"\x00" + b"PADDING" * 100
    victim = tmp_path / "victim"
    victim.write_bytes(original)

    prefix = str(tmp_path / "pm")
    os.symlink(victim, prefix + "1")

    assert parse_powermetrics(path=prefix, timecode="1") is None
    assert victim.read_bytes() == original, "symlink target was rewritten"


def test_regular_file_is_still_parsed(tmp_path):
    prefix = str(tmp_path / "pm")
    (tmp_path / "pm1").write_bytes(_valid_plist())

    result = parse_powermetrics(path=prefix, timecode="1")
    assert result is not None
    assert result[-1] == "now"


# --- untrusted text --------------------------------------------------------

def test_printable_strips_escape_sequences():
    assert _printable("\x1b]0;pwned\x07Safari") == "]0;pwnedSafari"
    assert _printable("a\nb\tc") == "abc"
    assert _printable("Wi-Fi Café 5GHz") == "Wi-Fi Café 5GHz"


class _FakeWidget:
    text = ""
    title = ""
    value = 0


def test_process_name_escapes_never_reach_the_widget():
    """A local user picks their own process name — it must not drive the terminal."""
    w = {"top_text": _FakeWidget()}
    update_top_widget(w, [{
        "pid": 1, "name": "\x1b]0;pwned\x07evil", "cpu_percent": 1.0, "rss": 1024,
    }])
    assert "\x1b" not in w["top_text"].text


def test_ssid_escapes_never_reach_the_widget():
    """SSIDs come from whatever access point is nearby."""
    w = {"wifi_gauge": _FakeWidget()}
    update_wifi_widget(w, {
        "connected": True, "ssid": "\x1b[2Jfree wifi", "rssi_dBm": -50,
        "tx_rate_Mbps": None, "noise_dBm": None, "channel": None,
    })
    assert "\x1b" not in w["wifi_gauge"].title
