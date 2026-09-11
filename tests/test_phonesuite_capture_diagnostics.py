from __future__ import annotations

from types import SimpleNamespace

from innaware_pms_emulator import main
from innaware_pms_emulator.capture_diagnostics import diagnose_capture_interface


def _frame(direction: str, text: str) -> dict:
    return {
        "direction": direction,
        "data": b"\x02" + text.encode("latin-1") + b"\x03",
        "peer": "lab-peer",
    }


def _phonesuite_ids(report) -> set[str]:
    return {item.id for item in report.findings if item.id.startswith("phonesuite_pms_")}


def test_local_phonesuite_pbx_checks_only_inbound_pms_to_pbx_records():
    report = diagnose_capture_interface(
        {
            "name": "phonesuite-pbx",
            "protocol": "MITEL 1",
            "transport": "serial",
            "emulation_role": "pbx",
            "personality_id": "pbx-phonesuite",
            "options": {"framing": "stx_etx"},
        },
        [
            _frame("rx", "MW1 101"),
            _frame("tx", "NAM0 TEST,GUEST 101"),
        ],
    )

    ids = _phonesuite_ids(report)
    assert ids == {"phonesuite_pms_mw_spacing_invalid"}
    assert report.observations["phonesuite_pms_to_pbx_capture_direction"] == "rx"
    assert report.observations["phonesuite_pms_format_findings"] == 1


def test_local_pms_with_phonesuite_peer_checks_only_outbound_pms_to_pbx_records():
    report = diagnose_capture_interface(
        {
            "name": "phonesuite-peer",
            "protocol": "MITEL 1",
            "transport": "serial",
            "emulation_role": "pms",
            "peer_personality_id": "pbx-phonesuite",
            "options": {"framing": "stx_etx"},
        },
        [
            _frame("rx", "MW1 101"),
            _frame("tx", "NAM0 TEST,GUEST 101"),
        ],
    )

    ids = _phonesuite_ids(report)
    assert ids == {"phonesuite_pms_nam_index_invalid"}
    assert report.observations["phonesuite_pms_to_pbx_capture_direction"] == "tx"


def test_reverse_direction_does_not_inherit_phonesuite_pms_format_policy():
    report = diagnose_capture_interface(
        {
            "name": "phonesuite-peer",
            "protocol": "MITEL 1",
            "transport": "serial",
            "emulation_role": "pms",
            "peer_personality_id": "pbx-phonesuite",
            "options": {"framing": "stx_etx"},
        },
        [_frame("rx", "NAM0 TEST,GUEST 101")],
    )

    assert _phonesuite_ids(report) == set()
    assert report.observations["phonesuite_pms_format_findings"] == 0


def test_matrix_mitel_and_unknown_personalities_do_not_trigger_phonesuite_policy():
    configs = [
        {
            "name": "matrix",
            "protocol": "MITEL 1",
            "transport": "serial",
            "emulation_role": "pbx",
            "personality_id": "pbx-matrix",
            "options": {"framing": "stx_etx"},
        },
        {
            "name": "mitel",
            "protocol": "MITEL 1",
            "transport": "serial",
            "emulation_role": "pbx",
            "personality_id": "pbx-mitel-sx200",
            "options": {"framing": "stx_etx"},
        },
        {
            "name": "unknown",
            "protocol": "MITEL 1",
            "transport": "serial",
            "emulation_role": "pbx",
            "options": {"framing": "stx_etx"},
        },
    ]

    for config in configs:
        report = diagnose_capture_interface(config, [_frame("rx", "MW1 101")])
        assert _phonesuite_ids(report) == set(), config["name"]
        assert report.observations["phonesuite_pms_to_pbx_capture_direction"] is None


def test_missing_explicit_emulation_role_fails_closed():
    report = diagnose_capture_interface(
        {
            "name": "legacy-saved-config",
            "protocol": "MITEL 1",
            "transport": "serial",
            "personality_id": "pbx-phonesuite",
            "options": {"framing": "stx_etx"},
        },
        [_frame("rx", "MW1 101")],
    )

    assert _phonesuite_ids(report) == set()
    assert report.observations["phonesuite_pms_to_pbx_capture_direction"] is None


def test_capture_diagnostics_api_uses_runtime_identity_and_bounded_capture_projection(monkeypatch):
    config = {
        "name": "phonesuite-api",
        "protocol": "MITEL 1",
        "transport": "serial",
        "emulation_role": "pbx",
        "personality_id": "pbx-phonesuite",
        "options": {"framing": "stx_etx"},
    }
    runtime = SimpleNamespace(config=config)
    seen: dict[str, object] = {}

    monkeypatch.setattr(main.manager, "get", lambda name: runtime)

    def captures(name: str, limit: int):
        seen["name"] = name
        seen["limit"] = limit
        return [_frame("rx", "MW1 101")]

    monkeypatch.setattr(main.manager, "captures", captures)

    result = main.interface_capture_diagnostics("phonesuite-api", limit=37)

    assert seen == {"name": "phonesuite-api", "limit": 37}
    assert result["interface_name"] == "phonesuite-api"
    assert result["personality_id"] == "pbx-phonesuite"
    assert result["observations"]["phonesuite_pms_to_pbx_capture_direction"] == "rx"
    assert {item["id"] for item in result["findings"] if item["id"].startswith("phonesuite_pms_")} == {
        "phonesuite_pms_mw_spacing_invalid"
    }


def test_capture_diagnostics_api_never_reclassifies_matrix_as_phonesuite(monkeypatch):
    runtime = SimpleNamespace(config={
        "name": "matrix-api",
        "protocol": "FIAS",
        "transport": "tcp_server",
        "emulation_role": "pms",
        "peer_personality_id": "pbx-matrix",
        "options": {"framing": "stx_etx"},
    })
    monkeypatch.setattr(main.manager, "get", lambda name: runtime)
    monkeypatch.setattr(main.manager, "captures", lambda name, limit: [_frame("tx", "MW1 101")])

    result = main.interface_capture_diagnostics("matrix-api")

    assert not any(item["id"].startswith("phonesuite_pms_") for item in result["findings"])
    assert result["observations"]["phonesuite_pms_to_pbx_capture_direction"] is None
