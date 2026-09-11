from innaware_pms_emulator.compatibility_matrix import (
    Direction,
    EvidenceClass,
    SupportStatus,
    find_compatibility,
)


REPLAY_TEST = "tests/test_mitel_serial_replay_fixture.py"


def _lookup(direction: Direction):
    return find_compatibility(
        pbx_family="Mitel",
        pbx_dialect="legacy MTL-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=direction,
    )


def test_serial_pms_to_pbx_matrix_row_declares_sanitized_replay_regression():
    entry = _lookup(Direction.PMS_TO_PBX)

    assert entry.status is SupportStatus.PARTIAL
    assert entry.evidence_class is EvidenceClass.SIMULATOR_CHARACTERIZATION
    assert REPLAY_TEST in entry.deterministic_tests
    assert "sanitized deterministic replay fixture" in entry.notes


def test_serial_replay_regression_is_not_transposed_to_opposite_direction():
    entry = _lookup(Direction.PBX_TO_PMS)

    assert entry.status is SupportStatus.PARTIAL
    assert entry.evidence_class is EvidenceClass.LEGACY_SOURCE_PROFILE
    assert REPLAY_TEST not in entry.deterministic_tests


def test_serial_direction_rows_do_not_manufacture_aggregate_bidirectional_claim():
    aggregate = _lookup(Direction.BIDIRECTIONAL)

    assert aggregate.status is SupportStatus.UNSUPPORTED
    assert aggregate.evidence_class is EvidenceClass.NONE
    assert REPLAY_TEST not in aggregate.deterministic_tests
