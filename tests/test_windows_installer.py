from pathlib import Path


INSTALLER = Path("packaging/windows/InnAware-PMS-Emulator.iss")


def test_installer_closes_pyinstaller_process_tree_before_upgrade():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "CloseApplications=force" in script
    assert "CloseApplicationsFilter={#AppExeName}" in script
    assert "RestartApplications=no" in script
    assert "function PrepareToInstall" in script
    assert "taskkill.exe" in script
    assert "'/F /T /IM \"{#AppExeName}\"'" in script
