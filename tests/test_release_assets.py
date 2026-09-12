import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("release_verifier", Path(__file__).resolve().parents[1] / "scripts/verify-release-assets.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
SHA = "a" * 40


@pytest.fixture
def release(tmp_path):
    output = tmp_path / "dist-windows"
    output.mkdir()
    manifest = {"application_version": "0.4.1", "release_tag": "v0.4.1", "protocol_pack_version": "test"}
    (tmp_path / "release-manifest.json").write_text(json.dumps(manifest))
    info = {"application_version": "0.4.1", "source_sha": SHA}
    (output / "build-info.json").write_text(json.dumps(info))
    for name in ["InnAware-PMS-Emulator.exe", "InnAware-PMS-Emulator-Setup.exe", "README-WINDOWS.txt", "PRIVACY-TELEMETRY.md"]:
        (output / name).write_bytes(b"synthetic release test data")
    exe = output / "InnAware-PMS-Emulator.exe"
    (output / "SHA256SUMS.txt").write_text(f"{verifier.digest(exe)}  {exe.name}\n")
    with zipfile.ZipFile(tmp_path / "InnAware-PMS-Emulator-Windows-0.4.1.zip", "w") as archive:
        for path in output.iterdir():
            if path.name != "InnAware-PMS-Emulator-Setup.exe":
                archive.write(path, path.name)
    with zipfile.ZipFile(tmp_path / "InnAware-PMS-Emulator-Source-0.4.1.zip", "w") as archive:
        archive.comment = SHA.encode()
        archive.writestr("release-manifest.json", json.dumps(manifest))
    pack = tmp_path / "InnAware-PMS-Protocol-Pack-test.zip"
    pack.write_bytes(b"synthetic pack")
    (tmp_path / "InnAware-PMS-Protocol-Pack-test.sha256.txt").write_text(f"{verifier.digest(pack)}  {pack.name}\n")
    evidence = tmp_path / f"InnAware-PMS-Interop-Evidence-{SHA}.json"
    evidence.write_text(json.dumps({"producer": {"source_sha": SHA}}))
    (tmp_path / (evidence.name + ".sha256.txt")).write_text(f"{verifier.digest(evidence)}  {evidence.name}\n")
    (tmp_path / "SHA256SUMS-WINDOWS-0.4.1.txt").write_text(f"{verifier.digest(exe)}  {exe.name}\n")
    return tmp_path


def test_complete_release_records_all_assets(release):
    result = verifier.verify(release, SHA)
    assert result["source_sha"] == SHA
    assert len(result["assets"]) == 14


def test_missing_installer_blocks_release(release):
    (release / "dist-windows/InnAware-PMS-Emulator-Setup.exe").unlink()
    with pytest.raises(ValueError, match="Missing or empty"):
        verifier.verify(release, SHA)


def test_changed_executable_blocks_release(release):
    (release / "dist-windows/InnAware-PMS-Emulator.exe").write_bytes(b"different")
    with pytest.raises(ValueError, match="checksum"):
        verifier.verify(release, SHA)


def test_source_archive_from_another_commit_blocks_release(release):
    with zipfile.ZipFile(release / "InnAware-PMS-Emulator-Source-0.4.1.zip", "a") as archive:
        archive.comment = b"b" * 40
    with pytest.raises(ValueError, match="another commit"):
        verifier.verify(release, SHA)
