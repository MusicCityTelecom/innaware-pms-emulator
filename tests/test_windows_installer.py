from pathlib import Path


INSTALLER = Path("packaging/windows/InnAware-PMS-Emulator.iss")
BUILD_SCRIPT = Path("scripts/build-windows.ps1")
SMOKE_SCRIPT = Path("scripts/smoke-windows.ps1")


def test_installer_closes_pyinstaller_process_tree_before_upgrade():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "CloseApplications=force" in script
    assert "CloseApplicationsFilter={#AppExeName}" in script
    assert "RestartApplications=no" in script
    assert "function PrepareToInstall" in script
    assert "taskkill.exe" in script
    assert "'/F /T /IM \"{#AppExeName}\"'" in script


def test_installer_and_build_ship_privacy_and_support_metadata():
    installer = INSTALLER.read_text(encoding="utf-8")
    build = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert 'SupportURL "https://support.innawareucp.com"' in installer
    assert "PRIVACY-TELEMETRY.md" in installer
    assert "PRIVACY-TELEMETRY.md" in build
    assert "support@innawareucp.com" in build
    assert "https://support.innawareucp.com" in build


def test_windows_frozen_build_embeds_version_metadata_pack_manifest_and_disables_smoke_telemetry():
    build = BUILD_SCRIPT.read_text(encoding="utf-8")
    smoke = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert '--copy-metadata innaware-pms-emulator' in build
    assert 'protocol-pack.json' in build
    assert '--add-data' in build
    assert 'send_anonymous_usage_statistics = $false' in smoke
    assert '/api/v1/telemetry/status' in smoke
