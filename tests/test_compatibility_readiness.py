from innaware_pms_emulator.compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    Direction,
    EvidenceClass,
    SupportStatus,
    find_compatibility,
)
from innaware_pms_emulator.compatibility_readiness import (
    compatibility_readiness_catalog,
    readiness_for,
    validate_readiness_registry,
)


def _gap_codes(entry) -> set[str]:
    return {gap.code for gap in readiness_for(entry).evidence_gaps}


def test_every_partial_and_planned_row_has_explicit_evidence_gaps() -> None:
    assert validate_readiness_registry() == []
    for entry in COMPATIBILITY_MATRIX:
        if entry.status in {SupportStatus.PARTIAL, SupportStatus.PLANNED}:
            readiness = readiness_for(entry)
            assert readiness.evidence_gaps
            assert not readiness.release_ready
            assert "readiness_registry_missing" not in _gap_codes(entry)


def test_hitachi_profile_readiness_is_actionable_and_transport_safe() -> None:
    entry = find_compatibility(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT / Epitome Hitachi emulation",
        transport="unknown",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT",
        direction=Direction.PMS_TO_PBX,
    )
    assert entry.status is SupportStatus.PLANNED
    assert entry.evidence_class is EvidenceClass.LEGACY_SOURCE_PROFILE

    readiness = readiness_for(entry)
    codes = _gap_codes(entry)
    assert {
        "profile_body",
        "transport",
        "framing_control",
        "record_layout",
        "checksum_contract",
        "reverse_direction",
    } <= codes
    profile_action = next(gap.action for gap in readiness.evidence_gaps if gap.code == "profile_body")
    transport_action = next(gap.action for gap in readiness.evidence_gaps if gap.code == "transport")
    assert "SHA-256" in profile_action
    assert "psip-pbx-protocol.EPIT-HIT" in profile_action
    assert "do not inherit generic Voiceware transport guidance" in transport_action


def test_hitachi_layout_variant_requires_sanitized_profile_delta() -> None:
    entry = find_compatibility(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT2 / Epitome Hitachi room-name layout variant",
        transport="unknown",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT2",
        direction=Direction.PMS_TO_PBX,
    )
    readiness = readiness_for(entry)
    assert "profile_delta" in _gap_codes(entry)
    action = next(gap.action for gap in readiness.evidence_gaps if gap.code == "profile_delta")
    assert "EPIT-HIT2" in action
    assert "EPIT-HIT" in action
    assert "Epitome" in action
    assert "sanitized comparator" in action


def test_mitel_serial_readiness_does_not_transpose_tcp_evidence() -> None:
    pms_to_pbx = find_compatibility(
        pbx_family="Mitel",
        pbx_dialect="legacy MTL-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PMS_TO_PBX,
    )
    codes = _gap_codes(pms_to_pbx)
    assert {"real_hardware_serial", "serial_timing_scope"} == codes
    timing_action = next(
        gap.action
        for gap in readiness_for(pms_to_pbx).evidence_gaps
        if gap.code == "serial_timing_scope"
    )
    assert "serial evidence" in timing_action
    assert "TCP" in timing_action


def test_phonesuite_readiness_keeps_checksum_and_retry_unqualified() -> None:
    entry = find_compatibility(
        pbx_family="PhoneSuite",
        pbx_dialect="MITEL 1-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PMS_TO_PBX,
    )
    codes = _gap_codes(entry)
    assert "checksum_contract" in codes
    assert "retry_policy" in codes
    assert "serial_parameter_scope" in codes
    checksum_action = next(
        gap.action
        for gap in readiness_for(entry).evidence_gaps
        if gap.code == "checksum_contract"
    )
    assert "algorithm" in checksum_action
    assert "placement" in checksum_action


def test_matrix_readiness_names_known_post_ls_and_reverse_direction_gaps() -> None:
    entry = find_compatibility(
        pbx_family="Matrix",
        pbx_dialect="MICROS Opera / FIAS",
        transport="tcp",
        pms_family="Oracle / MICROS Opera",
        pms_protocol="FIAS",
        direction=Direction.PBX_TO_PMS,
    )
    codes = _gap_codes(entry)
    assert {
        "post_ls_progression",
        "retry_timing",
        "site_port",
        "handshake",
        "guest_events",
        "reverse_direction",
    } == codes


def test_unregistered_combination_gets_exact_row_missing_gap() -> None:
    entry = find_compatibility(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT / Epitome Hitachi emulation",
        transport="serial",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT",
        direction=Direction.PMS_TO_PBX,
    )
    assert entry.status is SupportStatus.UNSUPPORTED
    readiness = readiness_for(entry)
    assert _gap_codes(entry) == {"exact_row_missing"}
    assert not readiness.release_ready


def test_readiness_catalog_preserves_all_six_matrix_dimensions() -> None:
    catalog = compatibility_readiness_catalog()
    assert len(catalog) == len(COMPATIBILITY_MATRIX)
    for row in catalog:
        assert {
            "pbx_family",
            "pbx_dialect",
            "transport",
            "pms_family",
            "pms_protocol",
            "direction",
            "status",
            "evidence_class",
            "evidence_gaps",
            "release_ready",
        } <= set(row)
        assert row["release_ready"] is False


def test_status_filtered_readiness_catalog_is_deterministic() -> None:
    planned = compatibility_readiness_catalog(statuses=(SupportStatus.PLANNED,))
    assert len(planned) == 2
    assert {row["pbx_family"] for row in planned} == {"Hitachi"}
    assert {row["pms_protocol"] for row in planned} == {"EPIT-HIT", "EPIT-HIT2"}
