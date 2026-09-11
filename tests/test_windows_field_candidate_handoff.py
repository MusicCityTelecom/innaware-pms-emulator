from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "accept-windows-field-candidate.ps1"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_windows_field_acceptance_handoff_exists_and_is_fail_closed():
    text = _text()

    for required in (
        "[string]$SourceSha",
        "[string]$Exe",
        "[string]$ExpectedExeSha256",
        "[string]$NativeScreenshot",
        "[string]$BrowserScreenshot",
        "Get-FileHash -Path $Exe -Algorithm SHA256",
        "Candidate EXE hash mismatch",
        "127.0.0.1",
        "INNAWARE_PMS_DATA_DIR",
        "check_app_updates_on_start = $false",
        "check_protocol_updates_on_start = $false",
        "send_anonymous_usage_statistics = $false",
        "/api/v1/health",
        "/api/v1/app-info",
        "/api/v1/telemetry/status",
        "screenshot_sha256",
        "child_processes_remaining = $false",
        'schema = "innaware-pms-emulator-windows-field-acceptance/v1"',
        'production_endpoints_used = $false',
        'server5_used = $false',
    ):
        assert required in text


def test_windows_field_acceptance_exercises_native_and_browser_surfaces_separately():
    text = _text()

    assert 'Invoke-AcceptanceSurface -Surface "native_gui"' in text
    assert 'Invoke-AcceptanceSurface -Surface "browser"' in text
    assert '$Arguments = @("--browser") + $Arguments' in text
    assert 'if ($NativePort -eq $BrowserPort)' in text
    assert 'New-AcceptanceDataDir -Surface $Surface' in text


def test_windows_field_acceptance_requires_fresh_nontrivial_screenshot_and_cleanup():
    text = _text()

    assert 'Remove-Item -Force $FullPath' in text
    assert '$Item.Length -ge 1024' in text
    assert 'Stop-CandidateProcessTree -RootPid $Process.Id' in text
    assert 'Get-CandidateProcesses' in text
    assert 'Candidate acceptance ended with' in text


def test_windows_field_acceptance_does_not_embed_remote_or_production_target():
    text = _text().lower()

    assert "http://127.0.0.1:" in text
    assert "https://" not in text
    assert "server5." not in text
    assert "production_pms_traffic" not in text
    assert "production_pbx_traffic" not in text
