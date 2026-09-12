import io
import json
import sys

import pytest

from innaware_pms_emulator import windows_launcher as launcher


@pytest.mark.parametrize("payload", [None, [], 1, "ok"])
def test_health_rejects_nonobject_json(monkeypatch, payload):
    class Response(io.BytesIO):
        status = 200
    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda *a, **kw: Response(json.dumps(payload).encode()))
    assert launcher._health("127.0.0.1", 8080) is None


def test_missing_native_runtime_starts_browser_service_after_child_cleanup(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["emulator"])
    monkeypatch.setattr(launcher, "_start_user_launch_telemetry", lambda: None)
    monkeypatch.setattr(launcher, "_health", lambda *a: None)
    monkeypatch.setattr(launcher, "_port_open", lambda *a: False)
    monkeypatch.setattr(launcher, "_wait_for_health", lambda *a: {"status": "ok"})
    child = object()
    monkeypatch.setattr(launcher, "_spawn_server", lambda *a: (child, None))
    events = []
    def fail_native(*args):
        raise RuntimeError("WebView2 unavailable")
    monkeypatch.setattr(launcher, "_run_native_window", fail_native)
    monkeypatch.setattr(launcher, "_stop_child", lambda process, *a: events.append(("stop", process)))
    monkeypatch.setattr(launcher, "_run_browser_foreground", lambda *a: events.append(("browser", a)))
    monkeypatch.setattr(launcher, "_show_error", lambda message: pytest.fail(message))
    launcher.main()
    assert events[0] == ("stop", child)
    assert events[1][0] == "browser"
    assert "WebView2 unavailable" in launcher._log_path().read_text()
