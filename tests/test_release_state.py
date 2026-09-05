from __future__ import annotations

import json
import tomllib
from pathlib import Path

from innaware_pms_emulator.updates import UpdateManager


ROOT = Path(__file__).resolve().parents[1]


def test_release_manifest_matches_v040_field_candidate():
    manifest = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    protocol_pack = json.loads((ROOT / "protocol-pack.json").read_text(encoding="utf-8"))

    app_version = project["project"]["version"]
    assert app_version == "0.4.0"
    assert manifest["schema_version"] == 1
    assert manifest["application_version"] == app_version
    assert manifest["release_tag"] == f"v{app_version}"
    assert manifest["release_channel"] == "field-beta"
    assert manifest["protocol_pack_version"] == protocol_pack["pack_version"]
    assert manifest["repository"] == "MusicCityTelecom/innaware-pms-emulator"
    assert manifest["update_source"] == "https://github.com/MusicCityTelecom/innaware-pms-emulator/releases"
    assert manifest["publish"] is False
    assert manifest["prerelease"] is True
    assert manifest["make_latest"] is False


def test_cached_status_is_rebound_to_running_version(tmp_path):
    manager = UpdateManager(tmp_path / "updates")
    manager.status_path.write_text(
        json.dumps(
            {
                "checked_at": "2026-08-29T00:00:00+00:00",
                "error": None,
                "include_prereleases": True,
                "app": {
                    "current_version": "0.3.7",
                    "latest_tag": "v0.3.7",
                    "latest_version": "0.3.7",
                    "update_available": False,
                    "release_url": "https://github.com/MusicCityTelecom/innaware-pms-emulator/releases/tag/v0.3.7",
                },
                "protocol_pack": {"local": {}, "remote": None, "update_available": False},
            }
        ),
        encoding="utf-8",
    )

    status = manager.load_status(current_version="0.3.6")

    assert status["app"]["current_version"] == "0.3.6"
    assert status["app"]["latest_version"] == "0.3.7"
    assert status["app"]["update_available"] is True


def test_current_release_notes_do_not_advertise_telemetry():
    manifest = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
    notes = (ROOT / "docs" / f"RELEASE_NOTES_{manifest['application_version']}.md").read_text(encoding="utf-8").lower()
    assert "telemetry" not in notes
