from innaware_pms_emulator.diagnostics import diagnose_interface, observe_capture


def _ids(report):
    return {item.id for item in report.findings}


def test_matrix_field_capture_explains_crlf_vs_stx_etx_mismatch():
    config = {
        "name": "matrix-live",
        "protocol": "FIAS",
        "personality_id": None,
        "emulation_role": "pms",
        "options": {"framing": "crlf"},
    }
    captures = [
        {
            "direction": "rx",
            "peer": "192.0.2.20:38657",
            "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 54 49 30 30 30 30 30 30 7c 03",
        },
        {
            "direction": "tx",
            "peer": "192.0.2.20:38657",
            "hex": "4c 53 7c 44 41 32 36 30 39 30 31 7c 54 49 30 30 30 30 30 31 7c 0d 0a",
        },
    ]

    report = diagnose_interface(config, captures)
    ids = _ids(report)

    assert "configured-framing-mismatch" in ids
    assert "wire-framing-asymmetry" in ids
    assert "fias-link-start-framing-mismatch" in ids
    assert "matrix-sarvam-opera-signature" in ids

    critical = next(item for item in report.findings if item.id == "fias-link-start-framing-mismatch")
    assert critical.severity == "critical"
    assert "stx_etx" in critical.summary
    assert "crlf" in critical.summary


def test_opera_legacy_configuration_is_flagged_when_peer_is_fias():
    report = diagnose_interface(
        {
            "name": "wrong-protocol",
            "protocol": "OPERA_LEGACY",
            "options": {"framing": "raw"},
        },
        [
            {
                "direction": "rx",
                "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 54 49 30 30 30 30 30 30 7c 03",
            }
        ],
    )

    assert "protocol-observation-mismatch" in _ids(report)


def test_correct_matrix_framing_does_not_report_framing_mismatch():
    config = {
        "name": "matrix-profile",
        "protocol": "FIAS",
        "personality_id": "pbx-matrix-sarvam-opera",
        "emulation_role": "pms",
        "options": {"framing": "stx_etx"},
    }
    captures = [
        {"direction": "rx", "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 03"},
        {"direction": "tx", "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 03"},
    ]

    report = diagnose_interface(config, captures)
    ids = _ids(report)

    assert "configured-framing-mismatch" not in ids
    assert "wire-framing-asymmetry" not in ids
    signature = next(item for item in report.findings if item.id == "matrix-sarvam-opera-signature")
    assert signature.confidence == "high"


def test_detects_crlf_inside_stx_etx_when_peer_does_not_use_it():
    config = {
        "name": "matrix-profile",
        "protocol": "FIAS",
        "options": {"framing": "stx_etx"},
    }
    captures = [
        {"direction": "rx", "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 03"},
        {
            "direction": "tx",
            "hex": "02 47 49 7c 52 4e 31 30 31 7c 47 4e 47 55 45 53 54 7c 0d 0a 03",
        },
    ]

    report = diagnose_interface(config, captures)
    assert "embedded-line-ending-in-stx-etx-fias" in _ids(report)


def test_detects_unanswered_enq_and_peer_nak():
    config = {
        "name": "transactional",
        "protocol": "MITEL 1",
        "options": {"framing": "stx_etx"},
    }
    captures = [
        {"direction": "rx", "hex": "05"},
        {"direction": "rx", "hex": "15"},
    ]

    report = diagnose_interface(config, captures)
    ids = _ids(report)
    assert "unanswered-enq" in ids
    assert "peer-nak" in ids


def test_wire_observation_decodes_fias_stx_etx():
    item = observe_capture({
        "direction": "rx",
        "hex": "02 4c 53 7c 44 41 32 36 30 39 30 31 7c 03",
    })
    assert item.framing == "stx_etx"
    assert item.record_family == "fias"
    assert item.record_code == "LS"


def test_detects_bad_bcc():
    # XOR over b"ABC" + ETX is not zero, so this fixture is intentionally invalid.
    item = {"direction": "rx", "hex": "02 41 42 43 03 00"}
    report = diagnose_interface(
        {"name": "bcc", "protocol": "HOBIS", "options": {"framing": "stx_etx_bcc"}},
        [item],
    )
    assert "invalid-bcc" in _ids(report)


def test_detects_coalesced_tcp_elements():
    report = diagnose_interface(
        {"name": "tcp", "protocol": "FIAS", "options": {"framing": "stx_etx"}},
        [
            {
                "direction": "rx",
                "hex": "05 02 4c 53 7c 03",
            }
        ],
    )
    assert "tcp-message-coalescing-observed" in _ids(report)
