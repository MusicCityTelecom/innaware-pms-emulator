from innaware_pms_emulator.models import EmulationRole, InterfaceConfig


def test_interface_tracks_emulated_and_peer_personalities():
    config = InterfaceConfig(
        name="matrix-pbx-test",
        purpose="pms",
        protocol="FIAS",
        transport="tcp_server",
        emulation_role="pms",
        personality_id="PMS-OPERA-FIAS",
        peer_personality_id="PBX-MATRIX-SARVAM-OPERA",
    )

    assert config.personality_id == "pms-opera-fias"
    assert config.peer_personality_id == "pbx-matrix-sarvam-opera"
    assert config.effective_emulation_role() is EmulationRole.PMS


def test_legacy_interface_still_defaults_to_pms_role():
    config = InterfaceConfig(
        name="legacy-fias",
        purpose="pms",
        protocol="FIAS",
        transport="tcp_server",
    )

    assert config.personality_id is None
    assert config.peer_personality_id is None
    assert config.effective_emulation_role() is EmulationRole.PMS
