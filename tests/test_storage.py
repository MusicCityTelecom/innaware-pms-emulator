from pathlib import Path

from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.storage import ConfigStore


def test_config_store_round_trip(tmp_path: Path):
    path = tmp_path / "interfaces.json"
    store = ConfigStore(path)
    config = InterfaceConfig(
        name="Hilton PMS",
        purpose="pms",
        protocol="HILTON_PEP_FIAS",
        transport="tcp_server",
        enabled=True,
        bind_host="0.0.0.0",
        port=5001,
        options={"framing": "stx_etx", "role": "pms"},
    )
    store.save([config])
    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].name == "Hilton PMS"
    assert loaded[0].protocol == "HILTON_PEP_FIAS"
    assert loaded[0].port == 5001
    assert loaded[0].options["framing"] == "stx_etx"


def test_invalid_config_file_does_not_break_startup(tmp_path: Path):
    path = tmp_path / "interfaces.json"
    path.write_text("not json", encoding="utf-8")
    assert ConfigStore(path).load() == []
