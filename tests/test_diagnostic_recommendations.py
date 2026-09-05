from innaware_pms_emulator.diagnostic_recommendations import remediation_plan
from innaware_pms_emulator.diagnostics import diagnose_interface
from innaware_pms_emulator.profiles import build_interface_from_profile


MATRIX_LS = {
    "direction": "rx",
    "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 54 49 30 30 30 30 30 30 7c 03",
}


def test_matrix_mismatch_produces_reviewable_config_plan():
    report = diagnose_interface(
        {
            "name": "matrix-live",
            "protocol": "FIAS",
            "options": {"framing": "crlf"},
        },
        [
            MATRIX_LS,
            {
                "direction": "tx",
                "hex": "4c 53 7c 44 41 32 36 30 39 30 31 7c 54 49 30 30 30 30 30 31 7c 0d 0a",
            },
        ],
    )

    plans = remediation_plan(report)
    by_id = {item["id"]: item for item in plans}

    assert by_id["match-peer-framing"]["configuration_patch"] == {
        "options": {"framing": "stx_etx"}
    }
    assert by_id["match-peer-framing"]["requires_operator_confirmation"] is True
    assert by_id["match-peer-framing"]["requires_reconnect"] is True

    personality = by_id["consider-matrix-sarvam-personality"]
    assert personality["configuration_patch"] == {
        "protocol": "FIAS",
        "peer_personality_id": "pbx-matrix",
        "options": {"framing": "stx_etx"},
    }
    assert "personality_id" not in personality["configuration_patch"]
    assert "does not change what InnAware is emulating" in personality["caveat"]
    assert "do not assume a generic FIAS LD/LR/LA order" in personality["validate_after"][1]
    assert personality["risk"] == "medium"


def test_dedicated_matrix_profile_does_not_recommend_rewriting_endpoint_identity():
    config = build_interface_from_profile(
        "matrix-micros-opera-fias-tcp-server",
        name="matrix-qualified-wire",
        enabled=False,
    )
    report = diagnose_interface(config, [MATRIX_LS])
    plan_ids = {item["id"] for item in remediation_plan(report)}

    assert config.peer_personality_id == "pbx-matrix"
    assert config.personality_id is None
    assert config.protocol == "FIAS"
    assert config.options["framing"] == "stx_etx"
    assert "consider-matrix-sarvam-personality" not in plan_ids


def test_protocol_mismatch_suggests_fias_without_silent_apply():
    report = diagnose_interface(
        {
            "name": "wrong-protocol",
            "protocol": "OPERA_LEGACY",
            "options": {"framing": "raw"},
        },
        [
            {
                "direction": "rx",
                "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 03",
            }
        ],
    )

    plans = remediation_plan(report)
    plan = next(item for item in plans if item["id"] == "select-observed-fias-protocol")
    assert plan["configuration_patch"] == {"protocol": "FIAS"}
    assert plan["requires_operator_confirmation"] is True


def test_unanswered_enq_suggests_ack_behavior():
    report = diagnose_interface(
        {
            "name": "mitel-test",
            "protocol": "MITEL 1",
            "options": {"framing": "stx_etx"},
        },
        [{"direction": "rx", "hex": "05"}],
    )

    plan = next(item for item in remediation_plan(report) if item["id"] == "enable-enq-ack")
    assert plan["configuration_patch"]["options"]["ack_enq"] is True
    assert plan["configuration_patch"]["options"]["auto_ack"] is True
