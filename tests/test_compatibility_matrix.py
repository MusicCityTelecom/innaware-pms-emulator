from pathlib import Path

import pytest

from innaware_pms_emulator.compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    CompatibilityEntry,
    Direction,
    EvidenceClass,
    SupportStatus,
    compatibility_catalog,
    find_compatibility,
    validate_supported_test_coverage,
)


def test_matrix_keys_are_unique_and_six_dimensional() -> None:
    keys = [entry.key for entry in COMPATIBILITY_MATRIX]
    assert len(keys) == len(set(keys))
    assert all(len(key) == 6 for key in keys)


def test_supported_claims_require_tests_and_non_inference_evidence() -> None:
    for entry in COMPATIBILITY_MATRIX:
        entry.validate()
        if entry.status is SupportStatus.SUPPORTED:
            assert entry.deterministic_tests
            assert entry.evidence_class not in {EvidenceClass.INFERENCE, EvidenceClass.NONE}


def test_supported_claim_rejected_without_deterministic_coverage() -> None:
    entry = CompatibilityEntry(
        pbx_family="Example",
        pbx_dialect="example",
        transport="tcp",
        pms_family="Example PMS",
        pms_protocol="example",
        direction=Direction.BIDIRECTIONAL,
        status=SupportStatus.SUPPORTED,
        evidence_class=EvidenceClass.PACKET_CAPTURE,
    )
    with pytest.raises(ValueError, match="deterministic test coverage"):
        entry.validate()


def test_inference_cannot_be_promoted_to_supported() -> None:
    entry = CompatibilityEntry(
        pbx_family="Example",
        pbx_dialect="example",
        transport="serial",
        pms_family="Example PMS",
        pms_protocol="example",
        direction=Direction.PBX_TO_PMS,
        status=SupportStatus.SUPPORTED,
        evidence_class=EvidenceClass.INFERENCE,
        deterministic_tests=("tests/test_example.py",),
    )
    with pytest.raises(ValueError, match="stronger than inference"):
        entry.validate()


def test_unlisted_combination_fails_closed_as_unsupported() -> None:
    entry = find_compatibility(
        pbx_family="PhoneSuite",
        pbx_dialect="unverified-dialect",
        transport="tcp",
        pms_family="Oracle / MICROS Opera",
        pms_protocol="FIAS",
        direction=Direction.BIDIRECTIONAL,
    )
    assert entry.status is SupportStatus.UNSUPPORTED
    assert entry.evidence_class is EvidenceClass.NONE
    assert "Do not auto-select" in entry.notes


def test_known_mitel_tcp_row_is_partial_capture_backed() -> None:
    entry = find_compatibility(
        pbx_family="Mitel",
        pbx_dialect="MITEL 1 / iPocket-characterized",
        transport="tcp",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.BIDIRECTIONAL,
    )
    assert entry.status is SupportStatus.PARTIAL
    assert entry.evidence_class is EvidenceClass.PACKET_CAPTURE
    assert "tests/test_mitel_tcp_session.py" in entry.deterministic_tests


def test_mitel_serial_remains_distinct_and_partial() -> None:
    entry = find_compatibility(
        pbx_family="Mitel",
        pbx_dialect="legacy MTL-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PBX_TO_PMS,
    )
    assert entry.status is SupportStatus.PARTIAL
    assert entry.transport == "serial"
    assert entry.evidence_class is EvidenceClass.LEGACY_SOURCE_PROFILE
    assert "not yet wired" in entry.notes


def test_catalog_is_structured_for_api_cli_gui_consumers() -> None:
    catalog = compatibility_catalog()
    assert catalog
    assert set(catalog[0]) == {
        "pbx_family",
        "pbx_dialect",
        "transport",
        "pms_family",
        "pms_protocol",
        "direction",
        "status",
        "evidence_class",
        "deterministic_tests",
        "notes",
    }


def test_any_supported_rows_reference_existing_test_files() -> None:
    test_paths = {str(path).replace("\\", "/") for path in Path("tests").glob("test_*.py")}
    assert validate_supported_test_coverage(test_paths) == []
