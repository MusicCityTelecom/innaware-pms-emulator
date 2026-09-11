import pytest

from innaware_pms_emulator.phonesuite_pms_policy import diagnose_phonesuite_pms_record_format


@pytest.mark.parametrize(
    "payload",
    [
        b"CHK1 101",
        b"CHK1 101 TEST,GUEST",
        b"CHK0 101",
        b"LMT 101 25.00",
        b"LMT 1001 $999.99",
        b"DND1 101",
        b"DND0 1001",
        b"GRP 101 GOLD",
        b"LNGen101",
        b"MW 1 101",
        b"MW 0 1001",
        b"RST2 101",
        b"AREYUTHERE",
        b"GRS",
        b"END",
        b"NAM1 TEST,GUEST 101",
        b"NAM4 TEST GUEST 1001",
    ],
)
def test_source_backed_phonesuite_pms_formats_accept_documented_shapes(payload: bytes) -> None:
    assert diagnose_phonesuite_pms_record_format(payload) == []


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"CHK1101", "phonesuite_pms_chk_format_invalid"),
        (b"CHK1 12", "phonesuite_pms_extension_format_invalid"),
        (b"CHK1 101 ABCDEFGHIJKLMNOPQRSTU", "phonesuite_pms_chk_name_too_long"),
        (b"LMT 101 1000.00", "phonesuite_pms_lmt_amount_invalid"),
        (b"DND2 101", "phonesuite_pms_dnd_format_invalid"),
        (b"GRP 101 THISGROUPISWAYTOOLONG", "phonesuite_pms_group_code_invalid"),
        (b"LNGEN101", "phonesuite_pms_language_code_invalid"),
        (b"LNGeng101", "phonesuite_pms_lng_format_invalid"),
        (b"MW1 101", "phonesuite_pms_mw_spacing_invalid"),
        (b"MW  1 101", "phonesuite_pms_mw_spacing_invalid"),
        (b"MW 2 101", "phonesuite_pms_mw_status_invalid"),
        (b"RST 2 101", "phonesuite_pms_rst_format_invalid"),
        (b"NAM 2 TEST,GUEST 101", "phonesuite_pms_nam_index_invalid"),
        (b"NAM0 TEST,GUEST 101", "phonesuite_pms_nam_index_invalid"),
        (b"NAM2 ABCDEFGHIJKLMNOPQRSTU 101", "phonesuite_pms_nam_name_too_long"),
        (b"AREYUTHERE extra", "phonesuite_pms_control_record_has_arguments"),
    ],
)
def test_source_backed_phonesuite_pms_formats_emit_actionable_diagnostics(
    payload: bytes,
    code: str,
) -> None:
    findings = diagnose_phonesuite_pms_record_format(payload)
    assert code in [item.code for item in findings]
    assert all(item.evidence_class == "legacy_source_profile" for item in findings)
    assert all(item.confidence == "high" for item in findings)
    assert all(item.corrective_action for item in findings)


def test_phonesuite_format_diagnostics_do_not_promote_reverse_or_ambiguous_direction() -> None:
    for payload in (b"MOV 101 102", b"MSG1 101", b"STS2 101", b"RQINZ", b"UNKNOWN 101"):
        assert diagnose_phonesuite_pms_record_format(payload) == []


def test_phonesuite_extension_diagnostic_does_not_claim_property_membership() -> None:
    finding = diagnose_phonesuite_pms_record_format(b"CHK1 ABCD")[0]
    assert finding.code == "phonesuite_pms_extension_format_invalid"
    assert "property membership is checked separately" in finding.expected
    assert "serial/TCP" in finding.corrective_action
