from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi import HTTPException

from innaware_pms_emulator import main
from innaware_pms_emulator.support import build_support_bundle


def _diagnostic() -> dict:
    return {
        "timestamp": "2026-09-02T16:00:00+00:00",
        "peer": "127.0.0.1:20744",
        "protocol": "MITEL 2",
        "code": "mitel_frame_without_enq",
        "severity": "warning",
        "confidence": "high",
        "evidence_class": "capture",
        "observed": "STX/ETX application frame arrived before an ENQ grant.",
        "expected": "Peer requests the half-duplex channel with ENQ before sending an application frame.",
        "corrective_action": "Verify the selected Mitel TCP personality and peer handshake configuration.",
    }


def test_interface_diagnostics_api_returns_bounded_manager_projection(monkeypatch):
    seen: dict[str, object] = {}

    monkeypatch.setattr(main.manager, "get", lambda name: object())

    def diagnostics(name: str, limit: int):
        seen["name"] = name
        seen["limit"] = limit
        return [_diagnostic()]

    monkeypatch.setattr(main.manager, "diagnostics", diagnostics)

    result = main.interface_diagnostics("mitel-lab", limit=37)

    assert seen == {"name": "mitel-lab", "limit": 37}
    assert result == {"diagnostics": [_diagnostic()]}


def test_interface_diagnostics_api_preserves_interface_not_found(monkeypatch):
    def missing(name: str):
        raise KeyError(name)

    monkeypatch.setattr(main.manager, "get", missing)

    with pytest.raises(HTTPException) as exc_info:
        main.interface_diagnostics("missing")

    assert exc_info.value.status_code == 404


def test_support_bundle_includes_structured_interface_diagnostics():
    diagnostic = _diagnostic()
    data = build_support_bundle(
        interface_statuses=[{"name": "mitel lab"}],
        interface_configs=[{"name": "mitel lab", "protocol": "MITEL 2"}],
        property_summaries=[],
        protocol_catalog=[],
        serial_ports=[],
        captures_by_interface={"mitel lab": []},
        transactions_by_interface={"mitel lab": []},
        diagnostics_by_interface={"mitel lab": [diagnostic]},
        full_property_state=None,
    )

    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        assert "diagnostics/mitel_lab.json" in archive.namelist()
        payload = json.loads(archive.read("diagnostics/mitel_lab.json"))

    assert payload == [diagnostic]
    assert "guest" not in json.dumps(payload).lower()
