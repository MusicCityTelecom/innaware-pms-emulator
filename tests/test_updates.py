from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from innaware_pms_emulator.profiles import build_interface_from_profile, profile_catalog
from innaware_pms_emulator.updates import UpdateError, UpdateManager, version_tuple


def _pack_bytes(*, version: str = "test-1", profiles: list[dict] | None = None, extra: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    manifest = {
        "schema_version": 1,
        "pack_version": version,
        "minimum_app_version": "0.3.1",
        "profiles": profiles or [],
    }
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("protocol-pack.json", json.dumps(manifest))
        archive.writestr("stubs/example.json", json.dumps({"profile": "Example", "synthetic_only": True}))
        for name, payload in (extra or {}).items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_version_tuple_handles_beta_release_tags():
    assert version_tuple("v0.3.1-beta") == (0, 3, 1)
    assert version_tuple("0.4.0") > version_tuple("0.3.9")
    assert version_tuple("protocols-2026") == (0, 0, 0)


def test_update_check_selects_newer_prerelease(monkeypatch, tmp_path):
    manager = UpdateManager(tmp_path / "updates")
    releases = [
        {
            "tag_name": "v0.3.1-beta",
            "name": "0.3.1 beta",
            "draft": False,
            "prerelease": True,
            "published_at": "2026-08-28T00:00:00Z",
            "html_url": "https://example.invalid/release",
            "assets": [
                {
                    "name": "InnAware-PMS-Emulator-Setup.exe",
                    "size": 123,
                    "digest": "sha256:" + ("a" * 64),
                    "browser_download_url": "https://example.invalid/setup.exe",
                }
            ],
        },
        {
            "tag_name": "v0.3.0-beta",
            "name": "0.3.0 beta",
            "draft": False,
            "prerelease": True,
            "published_at": "2026-08-27T00:00:00Z",
            "html_url": "https://example.invalid/old",
            "assets": [],
        },
    ]
    monkeypatch.setattr(manager, "fetch_releases", lambda: releases)
    status = manager.check("0.3.0", include_prereleases=True)
    assert status["app"]["latest_tag"] == "v0.3.1-beta"
    assert status["app"]["update_available"] is True
    assert status["app"]["asset"]["name"] == "InnAware-PMS-Emulator-Setup.exe"


def test_installed_protocol_pack_with_same_github_digest_is_current(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    digest = "a" * 64
    rebuilt_digest = "b" * 64
    packs = tmp_path / "protocol-packs"
    packs.mkdir()
    installed = packs / "2026.08.27.1"
    installed.mkdir()
    (installed / "protocol-pack.json").write_text(json.dumps({
        "schema_version": 1, "pack_version": "2026.08.27.1", "profiles": [],
    }), encoding="utf-8")
    (packs / "active.json").write_text(json.dumps({
        "pack_version": "2026.08.27.1",
        "source_release": "v0.3.1",
        "source_asset": "InnAware-PMS-Protocol-Pack-2026.08.27.1.zip",
        "source_digest": digest,
        "installed_at": "2026-08-28T04:18:39+00:00",
    }), encoding="utf-8")
    manager = UpdateManager(tmp_path / "updates")
    monkeypatch.setattr(manager, "fetch_releases", lambda: [{
        "tag_name": "v0.3.1", "draft": False, "prerelease": True,
        "published_at": "2026-08-28T04:12:16Z", "assets": [{
            "name": "InnAware-PMS-Protocol-Pack-2026.08.27.1.zip",
            "digest": f"sha256:{rebuilt_digest}", "browser_download_url": "https://example.invalid/pack.zip",
        }],
    }])

    status = manager.check("0.3.1", include_prereleases=True)

    assert status["protocol_pack"]["local"]["installed"] is True
    assert status["protocol_pack"]["remote"]["pack_version"] == "2026.08.27.1"
    assert status["protocol_pack"]["update_available"] is False


def test_protocol_pack_installs_data_only_profiles(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    manager = UpdateManager(tmp_path / "updates")
    profile = {
        "id": "pack-fias-serial",
        "name": "Pack FIAS Serial",
        "purpose": "pms",
        "protocol": "FIAS",
        "description": "Data-only profile supplied by a protocol pack.",
        "maturity": "fixture-backed",
        "defaults": {
            "transport": "serial",
            "serial_device": None,
            "baud_rate": 9600,
            "data_bits": 8,
            "parity": "N",
            "stop_bits": 1,
            "flow_control": "none",
            "options": {"framing": "crlf", "role": "pms"},
        },
    }
    archive = tmp_path / "pack.zip"
    archive.write_bytes(_pack_bytes(profiles=[profile]))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    result = manager.install_protocol_pack_file(
        archive,
        source_release="v0.3.1-beta",
        source_asset="InnAware-PMS-Protocol-Pack-test-1.zip",
        source_digest=digest,
    )
    assert result["pack_version"] == "test-1"
    catalog = {item["id"]: item for item in profile_catalog()}
    assert catalog["pack-fias-serial"]["source"] == "protocol-pack"
    config = build_interface_from_profile("pack-fias-serial", name="pack-test", enabled=False, overrides={"serial_device": "COM9"})
    assert config.protocol == "FIAS"
    assert config.serial_device == "COM9"


def test_protocol_pack_cannot_override_builtin_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    manager = UpdateManager(tmp_path / "updates")
    override = {
        "id": "fias-pms-tcp-server",
        "name": "Do Not Override",
        "purpose": "pms",
        "protocol": "FIAS",
        "description": "Attempted override.",
        "maturity": "bad",
        "defaults": {"transport": "tcp_server", "bind_host": "0.0.0.0", "port": 9999},
    }
    archive = tmp_path / "override.zip"
    archive.write_bytes(_pack_bytes(profiles=[override]))
    manager.install_protocol_pack_file(archive, source_release="test", source_asset="test.zip", source_digest="0" * 64)
    catalog = {item["id"]: item for item in profile_catalog()}
    assert catalog["fias-pms-tcp-server"]["name"] == "Generic CRLF FIAS (No ENQ/ACK) - TCP Server"
    assert catalog["fias-pms-tcp-server"]["source"] == "built-in"


def test_protocol_pack_rejects_executable_content(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    manager = UpdateManager(tmp_path / "updates")
    archive = tmp_path / "bad.zip"
    archive.write_bytes(_pack_bytes(extra={"stubs/evil.py": b"print('no')"}))
    with pytest.raises(UpdateError, match="unsupported file|Executable content"):
        manager.install_protocol_pack_file(archive, source_release="test", source_asset="bad.zip", source_digest="0" * 64)


def test_protocol_pack_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    manager = UpdateManager(tmp_path / "updates")
    archive = tmp_path / "bad-path.zip"
    archive.write_bytes(_pack_bytes(extra={"../outside.json": b"{}"}))
    with pytest.raises(UpdateError, match="unsafe path"):
        manager.install_protocol_pack_file(archive, source_release="test", source_asset="bad.zip", source_digest="0" * 64)
