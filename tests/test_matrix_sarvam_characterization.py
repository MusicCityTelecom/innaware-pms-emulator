from pathlib import Path

from innaware_pms_emulator.diagnostics import diagnose_interface
from innaware_pms_emulator.framing import ETX, STX, FramingMode, encode_frame
from innaware_pms_emulator.profiles import BUILTIN_PROFILES, build_interface_from_profile
from innaware_pms_emulator.protocols.fias import FiasAdapter
from innaware_pms_emulator.replay import TcpStreamDecoder, load_fixtures
from innaware_pms_emulator.state import FiasStateMachine


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pbx" / "matrix_sarvam_micros_opera_characterization.json"


def _fixture():
    fixtures = load_fixtures(FIXTURE_PATH)
    assert len(fixtures) == 1
    return fixtures[0]


def _observed_wire() -> bytes:
    raw = _fixture().steps[0].raw
    assert raw is not None
    return raw


def test_matrix_sarvam_fixture_preserves_only_qualified_link_start_observation():
    fixture = _fixture()
    assert fixture.personality == "pbx-matrix"
    assert fixture.protocol == "FIAS"
    assert fixture.framing == "stx_etx"
    assert fixture.status == "partially_characterized"
    assert fixture.sanitized is True
    assert len(fixture.steps) == 1

    items = TcpStreamDecoder(fixture.framing).feed(_observed_wire())
    assert len(items) == 1
    item = items[0]
    decoded = FiasAdapter().decode(item.payload)

    assert item.framing is FramingMode.STX_ETX
    assert decoded.kind == "link_start"
    assert decoded.fields == {"code": "LS", "DA": "000101", "TI": "000000"}
    assert b"260831" not in item.raw
    assert b"225018" not in item.raw
    assert "no broader link progression" in fixture.evidence.lower()


def test_matrix_micros_opera_profile_keeps_transport_and_application_layers_separate():
    profile = BUILTIN_PROFILES["matrix-micros-opera-fias-tcp-server"]
    config = build_interface_from_profile(
        profile.id,
        name="matrix-fixture",
        enabled=False,
    )

    assert profile.protocol == "FIAS"
    assert profile.maturity == "field-observed"
    assert config.transport.value == "tcp_server"
    assert config.peer_personality_id == "pbx-matrix"
    assert config.effective_emulation_role().value == "pms"
    assert config.options["framing"] == "stx_etx"
    assert config.options["role"] == "pms"
    assert "ack_enq" not in config.options
    assert "ack_records" not in config.options
    assert any("not a Matrix vendor default" in note for note in profile.notes)


def test_matrix_link_start_reply_uses_observed_stx_etx_and_stays_negotiating():
    engine = FiasStateMachine(role="pms")
    actions = engine.feed(_observed_wire())

    assert engine.state == "negotiating"
    assert len(actions) == 1
    assert actions[0].note == "FIAS LS reply"
    assert actions[0].apply_framing is True

    reply = encode_frame(actions[0].payload, FramingMode.STX_ETX)
    assert reply[0] == STX
    assert reply[-1] == ETX
    assert reply[1:-1].startswith(b"LS|DA")
    assert not reply.endswith(b"\r\n")


def test_matrix_diagnostics_identify_crlf_link_start_reply_mismatch():
    wrong_config = build_interface_from_profile(
        "fias-pms-tcp-server",
        name="matrix-wrong-framing",
        enabled=False,
        overrides={"peer_personality_id": "pbx-matrix"},
    )
    bad_reply = b"LS|DA000101|TI000001|\r\n"
    report = diagnose_interface(
        wrong_config,
        [
            {"direction": "rx", "data": _observed_wire()},
            {"direction": "tx", "data": bad_reply},
        ],
    )
    finding_ids = {finding.id for finding in report.findings}

    assert "configured-framing-mismatch" in finding_ids
    assert "wire-framing-asymmetry" in finding_ids
    assert "fias-link-start-framing-mismatch" in finding_ids


def test_matrix_profile_removes_known_link_start_framing_mismatch():
    config = build_interface_from_profile(
        "matrix-micros-opera-fias-tcp-server",
        name="matrix-correct-framing",
        enabled=False,
    )
    good_reply = encode_frame(b"LS|DA000101|TI000001|", FramingMode.STX_ETX)
    report = diagnose_interface(
        config,
        [
            {"direction": "rx", "data": _observed_wire()},
            {"direction": "tx", "data": good_reply},
        ],
    )
    finding_ids = {finding.id for finding in report.findings}

    assert "configured-framing-mismatch" not in finding_ids
    assert "wire-framing-asymmetry" not in finding_ids
    assert "fias-link-start-framing-mismatch" not in finding_ids
