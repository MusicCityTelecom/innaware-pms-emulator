from pathlib import Path

import pytest

from innaware_pms_emulator.framing import FramingMode
from innaware_pms_emulator.replay import TcpStreamDecoder, fixture_from_dict, load_fixtures


DATA = Path(__file__).parent / "data" / "emulation"


def test_all_replay_fixtures_are_sanitized_and_structurally_valid():
    fixtures = load_fixtures(DATA / "personality_fixtures.json") + load_fixtures(DATA / "fault_scenarios.json")
    assert len(fixtures) == 20
    assert all(fixture.sanitized for fixture in fixtures)
    assert all(fixture.evidence for fixture in fixtures)
    assert {fixture.status for fixture in fixtures} <= {
        "supported", "partially_characterized", "capture_only", "incompatible"
    }


def test_fixture_corpus_covers_requested_personality_families():
    fixtures = load_fixtures(DATA / "personality_fixtures.json")
    assert {fixture.personality for fixture in fixtures} == {
        "pbx-generic-fias",
        "pms-hilton-pep-fias",
        "pbx-matrix-sarvam-opera",
        "pbx-matrix-type1",
        "pbx-matrix-type2",
        "pbx-matrix-extended-starlight",
        "pbx-mitel-1",
        "pbx-mitel-2",
        "pbx-voiceware-operaip",
        "pbx-innaware-ucp",
    }


def test_pbx_event_fixture_declares_bidirectional_event_targets():
    fixture = next(
        item for item in load_fixtures(DATA / "personality_fixtures.json")
        if item.fixture_id == "generic-fias-link-and-room-events"
    )
    assert {step.expect_record for step in fixture.steps} == {
        "link_start",
        "link_alive",
        "room_status",
        "posting",
        "call_posting",
        "message_status",
        "synchronization_request",
        "wakeup_status",
    }


def test_fault_fixture_catalog_covers_required_faults_without_wall_clock_waits():
    fixtures = load_fixtures(DATA / "fault_scenarios.json")
    assert {fixture.fixture_id for fixture in fixtures} == {
        "delayed-ack",
        "dropped-ack",
        "explicit-nak",
        "malformed-stx-etx",
        "bad-bcc",
        "disconnect-during-transaction",
        "retry-exhaustion",
        "duplicate-records",
        "out-of-order-records",
        "missing-link-alive",
    }
    assert any(step.timing for fixture in fixtures for step in fixture.steps)


def test_malformed_and_bad_bcc_scenarios_are_observable():
    malformed = TcpStreamDecoder(FramingMode.STX_ETX)
    assert malformed.feed(b"\x02LS|") == []
    assert malformed.finish()[0].error == "incomplete frame"

    bad_bcc = TcpStreamDecoder(FramingMode.STX_ETX_BCC)
    item = bad_bcc.feed(b"\x02TEST\x03\x00")[0]
    assert item.kind == "frame"
    assert item.bcc_valid is False

    nested = TcpStreamDecoder(FramingMode.STX_ETX)
    error, frame = nested.feed(b"\x02BROKEN\x02LS|\x03")
    assert error.error == "nested STX before ETX"
    assert frame.payload == b"LS|"


def test_loader_rejects_unsanitized_permanent_fixture():
    with pytest.raises(ValueError, match="sanitized"):
        fixture_from_dict({
            "id": "unsafe", "personality": "test", "protocol": "test",
            "framing": "raw", "status": "capture_only", "sanitized": False,
            "evidence": "test", "steps": [],
        })
