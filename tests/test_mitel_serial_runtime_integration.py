import asyncio

from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager, InterfaceRuntime
import innaware_pms_emulator.sessions as sessions_module


class _MemoryWriter:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.writes.append(bytes(data))

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None

    def get_extra_info(self, name: str):
        return None


def _serial_config(name: str = "mitel-serial-runtime") -> InterfaceConfig:
    return InterfaceConfig(
        name=name,
        purpose="pms",
        protocol="MITEL 1",
        transport="serial",
        serial_device="TEST-SERIAL",
        baud_rate=1200,
        data_bits=8,
        parity="N",
        stop_bits=1,
        flow_control="xonxoff",
        enabled=False,
        options={"auto_ack": True, "strict_half_duplex": True},
    )


def test_mitel_serial_reader_uses_serial_state_machine_and_stream_aware_controls():
    async def exercise() -> None:
        manager = InterfaceManager()
        runtime = InterfaceRuntime(config=_serial_config())
        writer = _MemoryWriter()
        runtime.writer = writer
        runtime.peer = runtime.config.serial_device

        reader = asyncio.StreamReader()
        # ACK-valued data inside NAM2 must remain payload, not satisfy a
        # transaction waiter. ENQ plus frame may arrive in one serial read.
        reader.feed_data(bytes((ENQ, STX)) + b"NAM2JO\x06HNSMITH101" + bytes((ETX,)))
        reader.feed_data(bytes((ACK, NAK)))
        reader.feed_eof()

        await manager._reader_loop(runtime, reader, runtime.peer)

        assert writer.writes[:2] == [bytes((ACK,)), bytes((ACK,))]
        assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == ACK
        assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == NAK
        assert runtime.responses.empty()

        status = runtime.transport_session_status
        assert status is not None
        assert status["transport"] == "serial"
        assert status["state"] == "closed"
        assert status["last_opcode"] is None
        assert status["enq_received"] == 1
        assert status["frames_received"] == 1
        assert status["serial"] == {
            "baud_rate": 1200,
            "data_bits": 8,
            "parity": "N",
            "stop_bits": 1.0,
            "flow_control": "xonxoff",
        }

    asyncio.run(exercise())


def test_mitel_serial_reader_rejects_frame_without_enq_and_exports_diagnostic():
    async def exercise() -> None:
        manager = InterfaceManager()
        runtime = InterfaceRuntime(config=_serial_config("mitel-serial-diagnostic"))
        writer = _MemoryWriter()
        runtime.writer = writer
        runtime.peer = runtime.config.serial_device

        reader = asyncio.StreamReader()
        reader.feed_data(bytes((STX,)) + b"CHK1ROOM101" + bytes((ETX,)))
        reader.feed_eof()

        await manager._reader_loop(runtime, reader, runtime.peer)

        assert writer.writes == [bytes((NAK,))]
        diagnostics = list(runtime.session_diagnostics)
        finding = next(item for item in diagnostics if item["code"] == "mitel_serial_frame_without_enq")
        assert finding["confidence"] == "high"
        assert finding["evidence_class"] == "legacy_source_profile_verified"
        assert "ENQ" in finding["expected"]
        assert finding["peer"] == "TEST-SERIAL"

    asyncio.run(exercise())


def test_serial_loop_passes_config_to_pyserial_and_uses_mitel_session_path():
    async def exercise() -> None:
        manager = InterfaceManager()
        runtime = InterfaceRuntime(config=_serial_config("mitel-serial-open"))
        reader = asyncio.StreamReader()
        reader.feed_data(bytes((ENQ, STX)) + b"CHK1ROOM102" + bytes((ETX,)))
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
            "url": "TEST-SERIAL",
            "baudrate": 1200,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1.0,
            "rtscts": False,
            "xonxoff": True,
        }
        assert runtime.state == "online"
        assert runtime.peer == "TEST-SERIAL"
        assert writer.writes == [bytes((ACK,)), bytes((ACK,))]
        assert runtime.transport_session_status["transport"] == "serial"
        assert runtime.transport_session_status["frames_received"] == 1

    asyncio.run(exercise())


def test_mitel_serial_and_tcp_runtime_selectors_are_mutually_exclusive():
    manager = InterfaceManager()
    runtime = InterfaceRuntime(config=_serial_config("mitel-serial-boundary"))
    assert manager._uses_mitel_serial_session(runtime) is True
    assert manager._uses_mitel_tcp_session(runtime) is False
