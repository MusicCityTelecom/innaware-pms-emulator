"""Persisted Windows opt-out settings must not silently fall back to opt-in."""
import json

import pytest

from innaware_pms_emulator.updates import UpdateManager


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_settings_honor_opt_out_with_or_without_windows_utf8_bom(tmp_path, encoding):
    manager = UpdateManager(tmp_path / "updates")
    disabled = {key: False for key in manager.default_settings()}
    # Windows PowerShell 5.1 Set-Content -Encoding UTF8 emits this BOM.
    manager.settings_path.write_text(json.dumps(disabled), encoding=encoding)

    assert manager.load_settings() == disabled
