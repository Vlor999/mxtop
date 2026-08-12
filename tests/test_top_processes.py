"""Top-processes collection, rendering and the --top flag."""

from types import SimpleNamespace

from mxtop import system_info
from mxtop.system_info import get_top_processes
from mxtop.ui import build_ui
from mxtop.updater import update_top_widget

SOC = {
    "e_core_count": 4, "p_core_count": 4,
    "gpu_core_count": 10, "name": "Apple M3",
}


class _FakeProc:
    def __init__(self, pid, name, cpu, rss):
        self.info = {
            "pid": pid, "name": name, "cpu_percent": cpu,
            "memory_info": SimpleNamespace(rss=rss),
        }


def test_get_top_processes_shape():
    rows = get_top_processes(5)
    assert 0 < len(rows) <= 5
    assert set(rows[0]) == {"pid", "name", "cpu_percent", "rss"}


def test_heaviest_cpu_first_then_memory(monkeypatch):
    procs = [
        _FakeProc(1, "idle", 0.0, 10),
        _FakeProc(2, "busy", 90.0, 10),
        _FakeProc(3, "medium", 5.0, 10),
        _FakeProc(4, "fat-idle", 0.0, 999),
    ]
    monkeypatch.setattr(system_info.psutil, "process_iter", lambda attrs: procs)
    assert [r["name"] for r in get_top_processes(4)] == [
        "busy", "medium", "fat-idle", "idle",
    ]
    assert [r["name"] for r in get_top_processes(2)] == ["busy", "medium"]


def test_render_formats_one_line_per_process():
    w = {"top_text": SimpleNamespace(text="")}
    update_top_widget(w, [
        {"pid": 1, "name": "python3.13", "cpu_percent": 42.5, "rss": 3 * 1024**2},
        {"pid": 2, "name": "a-very-long-process-name", "cpu_percent": 1.0, "rss": 512},
    ])
    lines = w["top_text"].text.splitlines()
    assert len(lines) == 2
    assert " 42.5%" in lines[0] and "3.0 MB" in lines[0] and "python3.13" in lines[0]
    assert "a-very-long-proces" in lines[1]  # name truncated to 18 chars
    assert "a-very-long-process-name" not in lines[1]


def test_render_before_first_sample():
    w = {"top_text": SimpleNamespace(text="x")}
    update_top_widget(w, [])
    assert "sampling" in w["top_text"].text


def test_top_zero_hides_panel():
    _, w = build_ui(SimpleNamespace(color=2, show_cores=False, top=0), SOC)
    assert w["top_text"] is None
    update_top_widget(w, [{"pid": 1, "name": "x", "cpu_percent": 1.0, "rss": 1}])


def test_top_nonzero_creates_panel():
    _, w = build_ui(SimpleNamespace(color=2, show_cores=False, top=5), SOC)
    assert w["top_text"] is not None
