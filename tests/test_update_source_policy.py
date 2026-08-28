from pathlib import Path

from innaware_pms_emulator import updates
from innaware_pms_emulator.update_console import html as update_console_html


REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
GITHUB_RELEASES = f"https://github.com/{REPOSITORY}/releases"
SUPPORT_URL = "https://support.innawareucp.com"


def test_application_and_protocol_updates_are_discovered_from_github_releases():
    assert updates.REPOSITORY == REPOSITORY
    assert updates.RELEASES_API == f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30"
    assert "support.innawareucp.com" not in updates.RELEASES_API


def test_update_center_separates_github_releases_from_support_site():
    page = update_console_html()
    assert GITHUB_RELEASES in page
    assert SUPPORT_URL in page
    assert "Official update source" in page
    assert "support site is for user help only" in page


def test_windows_installer_uses_github_for_updates_and_support_site_for_help():
    installer = Path("packaging/windows/InnAware-PMS-Emulator.iss").read_text(encoding="utf-8")
    assert '#define AppURL "https://github.com/MusicCityTelecom/innaware-pms-emulator"' in installer
    assert 'AppUpdatesURL={#AppURL}/releases' in installer
    assert '#define SupportURL "https://support.innawareucp.com"' in installer
    assert 'AppSupportURL={#SupportURL}' in installer
