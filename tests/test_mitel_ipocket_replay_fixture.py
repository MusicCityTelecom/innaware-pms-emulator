from pathlib import Path

from innaware_pms_emulator.protocols.mitel import Mitel2Adapter
from innaware_pms_emulator.replay import TcpStreamDecoder, load_fixtures


FIXTURE_PATH = Path(__file__).parent / "data" / "emulation" / "mitel_ipocket_tcp.json"


def test_mitel_ipocket_fixture_is_sanitized_and_provenance_qualified():
    fixture = load_fixtures(FIXTURE_PATH)[0]

    assert fixture.fixture_id == "mitel-ipocket-tcp-sanitized-control-and-frame-sequence"
    assert fixture.personality == "pbx-mitel-sx200"
    assert fixture.status == "partially_characterized"
    assert fixture.sanitized is True
    assert "Issue #4" in fixture.evidence
    assert "synthetic" in fixture.evidence

    source = FIXTURE_PATH.read_text(encoding="utf-8")
    assert "192.168.1." not in source
    # Fixture payload bytes are deliberately stored as hex rather than plaintext.
    # Verify synthetic guest content by decoding the replay below instead of
    # requiring guest data to appear literally in the JSON source.
    assert '"hex"' in source


def test_mitel_ipocket_fixture_replays_capture_verified_controls_and_message_families():
    fixture = load_fixtures(FIXTURE_PATH)[0]
    decoder = TcpStreamDecoder(fixture.framing)
    adapter = Mitel2Adapter()

    items = []
    for step in fixture.steps:
        if step.direction == "rx" and step.raw is not None:
            items.extend(decoder.feed(step.raw))

    controls = [item.control for item in items if item.kind == "control"]
    records = [adapter.decode(item.payload) for item in items if item.kind == "frame"]

    assert controls == ["ENQ", "NAK"]
    assert [record.kind for record in records] == ["heartbeat", "checkin", "name_update"]
    assert records[1].fields["status"] == "1"
    assert records[2].fields["operation"] == "2"
    assert records[2].room == "101"
    assert records[2].fields["last_name"] == "TEST"
    assert records[2].fields["first_name"] == "GUEST"
    assert decoder.pending == b""


def test_mitel_ipocket_fixture_declares_ack_and_reconnect_without_hardcoding_endpoint_roles():
    fixture = load_fixtures(FIXTURE_PATH)[0]

    tx_controls = [step.expect_control for step in fixture.steps if step.direction == "tx"]
    disconnects = [step for step in fixture.steps if step.direction == "disconnect"]

    assert tx_controls == ["ACK"]
    assert disconnects[0].timing["behavior"] == "tcp_session_may_reconnect"
    assert all("192.168." not in (step.raw or b"").decode("latin-1", errors="ignore") for step in fixture.steps)
