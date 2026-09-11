import asyncio

from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager, InterfaceRuntime
import innaware_pms_emulator.sessions as sessions_module


class _MemoryWriter:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(bytes(data))

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None

    def get_extra_info(self, name: str):
        return None


def _phonesuite_serial_config(name: str = "phonesuite-serial-runtime") -> InterfaceConfig:
    return InterfaceConfig(
        name=name,
        purpose="pms",
        protocol="MITEL 1",
        transport="serial",
        personality_id="pbx-phonesuite",
        serial_device="TEST-PHONESUITE",
        baud_rate=19200,
        data_bits=7,
        parity="E",
        stop_bits=2,
        flow_control="none",
        enabled=False,
        options={"auto_ack": True, "strict_enq": True},
    )


def test_phonesuite_serial_runtime_preempts_generic_mitel_serial_session() -> None:
    async def exercise() -> None:
        manager = InterfaceManager()
        runtime = InterfaceRuntime(config=_phonesuite_serial_config())
        writer = _MemoryWriter()
        runtime.writer = writer
        runtime.peer = runtime.config.serial_device

        reader = asyncio.StreamReader()
        reader.feed_data(bytes((ENQ, STX)) + b"CHK1ROOM101" + bytes((ETX,)))
        reader.feed_data(bytes((ACK, NAK)))
        reader.feed_eof()

        await manager._reader_loop(runtime, reader, runtime.peer)

        assert writer.writes == [bytes((ACK,)), bytes((ACK,))]
        assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == ACK
        assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == NAK
        assert runtime.responses.empty()

        status = runtime.transport_session_status
        assert status is not None
        assert status["transport"] == "serial"
        assert status["pbx_family"] == "PhoneSuite"
        assert status["state"] == "closed"
        assert status["frames_received"] == 1
        assert status["serial_defaults"] == "unqualified_configurable"
        assert "serial" not in status

    asyncio.run(exercise())


def test_phonesuite_serial_runtime_exports_characterization_diagnostic() -> None:
    async def exercise() -> None:
        manager = InterfaceManager()
        runtime = InterfaceRuntime(config=_phonesuite_serial_config("phonesuite-diagnostic"))
        writer = _MemoryWriter()
        runtime.writer = writer
        runtime.peer = runtime.config.serial_device

        reader = asyncio.StreamReader()
        reader.feed_data(bytes((ENQ, STX)) + b"WKP0715ROOM101" + bytes((ETX,)))
        reader.feed_eof()

        await manager._reader_loop(runtime, reader, runtime.peer)

        assert writer.writes == [bytes((ACK,))]
        diagnostics = list(runtime.session_diagnostics)
        finding = next(item for item in diagnostics if item["code"] == "phonesuite_serial_uncharacterized_record")
        assert finding["evidence_class"] == "simulator_characterization"
        assert finding["peer"] == "TEST-PHONESUITE"
        assert "another PBX family" in finding["corrective_action"]

    asyncio.run(exercise())


def test_phonesuite_serial_loop_preserves_operator_configured_serial_parameters() -> None:
    async def exercise() -> None:
        manager = InterfaceManager()
        runtime = InterfaceRuntime(config=_phonesuite_serial_config("phonesuite-open"))
        reader = asyncio.StreamReader()
        reader.feed_data(bytes((ENQ, STX)) + b"NAM2TEST,GUESTROOM101" + bytes((ETX,)))
        reader.feed_eof()
        writer = _MemoryWriter()
        called: dict[str, object] = {}

        original = sessions_module.serial_asyncio.open_serial_connection

        async def fake_open_serial_connection(**kwargs):
            called.update(kwargs)
            return reader, writer

        sessions_module.serial_asyncio.open_serial_connection = fake_open_serial_connection
        try:
            await manager._serial_loop(runtime)
        finally:
            sessions_module.serial_asyncio.open_serial_connection = original

        assert called == {
            "url": "TEST-PHONESUITE",
            "baudrate": 19200,
            "bytesize": 7,
            "parity": "E",
            "stopbits": 2.0,
            "rtscts": False,
            "xonxoff": False,
        }
        assert writer.writes == [bytes((ACK,)), bytes((ACK,))]
        assert runtime.transport_session_status["pbx_family"] == "PhoneSuite"
        assert runtime.transport_session_status["serial_defaults"] == "unqualified_configurable"

    asyncio.run(exercise())


def test_phonesuite_and_mitel_serial_runtime_selectors_are_mutually_exclusive() -> None:
    manager = InterfaceManager()
    phonesuite = InterfaceRuntime(config=_phonesuite_serial_config("phonesuite-boundary"))
    assert manager._uses_phonesuite_serial_session(phonesuite) is True
    assert manager._uses_mitel_serial_session(phonesuite) is False

    mitel_config = _phonesuite_serial_config("mitel-boundary").model_copy(update={"personality_id": "pbx-mitel-sx200"})
    mitel = InterfaceRuntime(config=mitel_config)
    assert manager._uses_phonesuite_serial_session(mitel) is False
    assert manager._uses_mitel_serial_session(mitel) is True


def test_real_phonesuite_peer_identity_also_selects_phonesuite_serial_runtime() -> None:
    manager = InterfaceManager()
    config = _phonesuite_serial_config("phonesuite-peer").model_copy(
        update={"personality_id": "pms-generic-fias", "peer_personality_id": "pbx-phonesuite"}
    )
    runtime = InterfaceRuntime(config=config)
    assert manager._uses_phonesuite_serial_session(runtime) is True
    assert manager._uses_mitel_serial_session(runtime) is False
