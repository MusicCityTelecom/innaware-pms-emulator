from __future__ import annotations

import json
import os
import socket
import ssl
import urllib.error
import uuid

import pytest

from innaware_pms_emulator import windows_launcher
from innaware_pms_emulator.protocol_packs import current_protocol_pack_version
from innaware_pms_emulator.telemetry import TelemetryService
from innaware_pms_emulator.updates import UpdateManager


EXPECTED_FIELDS = {
    "event",
    "version",
    "platform",
    "architecture",
    "protocol_pack_version",
    "install_id",
}


def test_first_run_creates_uuid_and_sends_install_then_run(tmp_path):
    payloads = []
    service = TelemetryService(
        tmp_path,
        pack_version_provider=lambda: "pack-1",
        post_func=lambda payload: payloads.append(payload) or True,
    )

    result = service.run_once("0.3.6", enabled=True)

    assert result["attempted"] == ["install", "run"]
    assert [item["event"] for item in payloads] == ["install", "run"]
    install_id = payloads[0]["install_id"]
    assert uuid.UUID(install_id).version == 4
    assert payloads[1]["install_id"] == install_id
    assert payloads[0]["protocol_pack_version"] == "pack-1"
    assert set(payloads[0]) == EXPECTED_FIELDS
    assert set(payloads[1]) == EXPECTED_FIELDS


def test_second_and_later_runs_reuse_uuid_and_send_run_only(tmp_path):
    first = []
    TelemetryService(tmp_path, pack_version_provider=lambda: "pack-1", post_func=lambda p: first.append(p) or True).run_once("0.3.6", enabled=True)
    install_id = first[0]["install_id"]

    for version in ("0.3.6", "0.3.6", "0.3.7"):
        payloads = []
        service = TelemetryService(tmp_path, pack_version_provider=lambda: "pack-1", post_func=lambda p: payloads.append(p) or True)
        result = service.run_once(version, enabled=True)
        assert result["attempted"] == ["run"]
        assert len(payloads) == 1
        assert payloads[0]["event"] == "run"
        assert payloads[0]["install_id"] == install_id
        assert payloads[0]["version"] == version


def test_protocol_pack_update_is_reported_on_next_run(tmp_path):
    payloads = []
    versions = iter(["pack-1", "pack-1", "pack-2"])
    provider = lambda: next(versions)
    service = TelemetryService(tmp_path, pack_version_provider=provider, post_func=lambda p: payloads.append(p) or True)
    service.run_once("0.3.6", enabled=True)
    service.run_once("0.3.6", enabled=True)
    assert payloads[0]["protocol_pack_version"] == "pack-1"
    assert payloads[1]["protocol_pack_version"] == "pack-1"
    assert payloads[2]["protocol_pack_version"] == "pack-2"


def test_disabled_telemetry_makes_no_requests(tmp_path):
    payloads = []
    service = TelemetryService(tmp_path, post_func=lambda payload: payloads.append(payload) or True)
    result = service.run_once("0.3.6", enabled=False)
    assert payloads == []
    assert result["enabled"] is False
    assert uuid.UUID(result["install_id"]).version == 4


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError("endpoint unavailable"),
        socket.gaierror("dns failure"),
        ssl.SSLError("tls failure"),
        OSError("offline"),
        TimeoutError("timeout"),
    ],
)
def test_network_failures_never_break_startup_or_retry_install(tmp_path, failure):
    calls = []

    def failing(payload):
        calls.append(payload["event"])
        raise failure

    service = TelemetryService(tmp_path, post_func=failing)
    first = service.run_once("0.3.6", enabled=True)
    assert first["attempted"] == ["install", "run"]
    assert calls == ["install", "run"]

    calls.clear()
    second = service.run_once("0.3.6", enabled=True)
    assert second["attempted"] == ["run"]
    assert calls == ["run"]


def test_corrupt_state_recreates_random_uuid_and_install_event(tmp_path):
    (tmp_path / "telemetry.json").write_text("{not-json", encoding="utf-8")
    payloads = []
    service = TelemetryService(tmp_path, post_func=lambda p: payloads.append(p) or True)
    result = service.run_once("0.3.6", enabled=True)
    assert result["attempted"] == ["install", "run"]
    assert uuid.UUID(result["install_id"]).version == 4
    state = json.loads((tmp_path / "telemetry.json").read_text(encoding="utf-8"))
    assert state["install_id"] == result["install_id"]
    assert state["install_event_attempted"] is True


def test_payload_contains_no_sensitive_or_extra_fields(tmp_path):
    payloads = []
    service = TelemetryService(tmp_path, pack_version_provider=lambda: "pack-privacy", post_func=lambda p: payloads.append(p) or True)
    service.run_once("0.3.6", enabled=True)
    forbidden = {
        "ip", "ip_address", "hostname", "username", "email", "mac", "sid",
        "machine_guid", "hardware_id", "property", "hotel", "credentials",
        "guest", "room", "telephone", "number", "call", "network", "license", "path",
    }
    for payload in payloads:
        assert set(payload) == EXPECTED_FIELDS
        assert forbidden.isdisjoint(payload)


def test_update_settings_default_enabled_and_persist_disable(tmp_path):
    manager = UpdateManager(tmp_path / "updates")
    assert manager.load_settings()["send_anonymous_usage_statistics"] is True
    saved = manager.save_settings({"send_anonymous_usage_statistics": False})
    assert saved["send_anonymous_usage_statistics"] is False
    assert manager.load_settings()["send_anonymous_usage_statistics"] is False


def test_current_protocol_pack_version_prefers_active_pack(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    packs = tmp_path / "protocol-packs"
    active = packs / "2026.08.28.9"
    active.mkdir(parents=True)
    (active / "protocol-pack.json").write_text(json.dumps({
        "schema_version": 1,
        "pack_version": "2026.08.28.9",
        "profiles": [],
    }), encoding="utf-8")
    (packs / "active.json").write_text(json.dumps({
        "pack_version": "2026.08.28.9",
        "source_release": "test",
        "source_asset": "test.zip",
        "source_digest": "0" * 64,
        "installed_at": "2026-08-28T00:00:00+00:00",
    }), encoding="utf-8")
    assert current_protocol_pack_version() == "2026.08.28.9"


def test_windows_user_launch_owns_telemetry_and_suppresses_service_duplicate(monkeypatch):
    calls = []
    monkeypatch.delenv(windows_launcher.TELEMETRY_SUPPRESS_ENV, raising=False)
    monkeypatch.setattr(
        windows_launcher.update_manager,
        "load_settings",
        lambda: {"send_anonymous_usage_statistics": True},
    )
    monkeypatch.setattr(
        windows_launcher.telemetry_service,
        "start_background",
        lambda version, *, enabled: calls.append((version, enabled)),
    )

    windows_launcher._start_user_launch_telemetry()

    assert calls == [(windows_launcher.__version__, True)]
    assert os.environ[windows_launcher.TELEMETRY_SUPPRESS_ENV] == "1"
