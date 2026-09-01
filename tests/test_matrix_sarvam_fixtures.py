from pathlib import Path

from innaware_pms_emulator.framing import ETX, STX, FramingMode, encode_frame
from innaware_pms_emulator.protocols.fias import FiasAdapter
from innaware_pms_emulator.replay import TcpStreamDecoder, load_fixtures


DATA = Path(__file__).parent / "data" / "emulation" / "personality_fixtures.json"


def _matrix_fixture():
    return next(
        fixture for fixture in load_fixtures(DATA)
        if fixture.fixture_id == "matrix-sarvam-opera-field-observation-sanitized"
    )


def test_sanitized_matrix_sarvam_field_frame_parses_as_fias_link_start():
    fixture = _matrix_fixture()
    observed = fixture.steps[0].raw
    assert observed is not None
    item = TcpStreamDecoder(fixture.framing).feed(observed)[0]
    decoded = FiasAdapter().decode(item.payload)
    assert item.framing is FramingMode.STX_ETX
    assert decoded.kind == "link_start"
    assert decoded.fields == {"code": "LS", "DA": "000101", "TI": "000000"}


def test_matrix_compatible_link_response_uses_stx_etx_not_crlf():
    payload = FiasAdapter().encode_event({"action": "link_start"}).rstrip(b"\r\n")
    wire = encode_frame(payload, _matrix_fixture().framing)
    assert wire == bytes((STX,)) + b"LS|" + bytes((ETX,))
    assert not wire.endswith(b"\r\n")


def test_matrix_claim_remains_model_qualified_and_sanitized():
    fixture = _matrix_fixture()
    assert fixture.status == "supported"
    assert "firmware/model-qualified" in fixture.evidence.lower()
    assert fixture.sanitized is True
    assert b"260831" not in (fixture.steps[0].raw or b"")
    assert b"225018" not in (fixture.steps[0].raw or b"")
