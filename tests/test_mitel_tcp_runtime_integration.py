import asyncio
import socket

from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _mitel_server(name: str) -> InterfaceConfig:
    return InterfaceConfig(
        name=name,
        purpose="pms",
        protocol="MITEL 1",
        transport="tcp_server",
        bind_host="127.0.0.1",
        port=_available_port(),
        options={"auto_ack": True, "strict_half_duplex": True},
    )


def test_mitel_tcp_runtime_uses_stream_aware_control_routing():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = _mitel_server("mitel-stream-routing")
        runtime = await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)

        # One TCP read may contain both the ENQ and an application frame. The
        # ACK byte embedded in the NAM2 payload must remain application data,
        # not become an outbound-transaction response token.
        frame = bytes((STX,)) + b"NAM2JO\x06HNSMITH101" + bytes((ETX,))
        writer.write(bytes((ENQ,)) + frame)
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(2), timeout=1) == bytes((ACK, ACK))
        await asyncio.sleep(0)

        assert runtime.responses.empty()
        status = runtime.status()["transport_session"]
        assert status["transport"] == "tcp"
        assert status["state"] == "idle"
        assert status["last_opcode"] == "NAM2"
        assert status["enq_received"] == 1
        assert status["frames_received"] == 1

        # Standalone ACK/NAK controls are transaction responses and must still
        # reach the sender queue even when coalesced in one TCP read.
        writer.write(bytes((ACK, NAK)))
        await writer.drain()
        assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == ACK
        assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == NAK

        writer.close()
        await writer.wait_closed()
        await manager.stop(config.name)

    asyncio.run(exercise())


def test_mitel_tcp_runtime_rejects_frame_without_enq_and_exports_diagnostic():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = _mitel_server("mitel-diagnostic")
        await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)

        writer.write(bytes((STX,)) + b"CHK1ROOM101" + bytes((ETX,)))
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == bytes((NAK,))
        await asyncio.sleep(0)

        diagnostics = manager.diagnostics(config.name)
        assert diagnostics[-1]["code"] == "mitel_tcp_frame_without_enq"
        assert diagnostics[-1]["confidence"] == "high"
        assert diagnostics[-1]["evidence_class"] == "vendor_public_specification"
        assert "ENQ" in diagnostics[-1]["expected"]
        assert diagnostics[-1]["peer"]

        writer.close()
        await writer.wait_closed()
        await manager.stop(config.name)

    asyncio.run(exercise())


def test_mitel_tcp_runtime_resets_partial_frame_across_reconnect():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = _mitel_server("mitel-reconnect")
        runtime = await manager.create(config)

        reader1, writer1 = await asyncio.open_connection("127.0.0.1", config.port)
        writer1.write(bytes((ENQ,)))
        await writer1.drain()
        assert await asyncio.wait_for(reader1.readexactly(1), timeout=1) == bytes((ACK,))
        writer1.write(bytes((STX,)) + b"CHK1PARTIAL")
        await writer1.drain()
        writer1.close()
        await writer1.wait_closed()
        await asyncio.sleep(0.05)

        assert any(
            item["code"] == "mitel_tcp_disconnect_incomplete_frame"
            for item in manager.diagnostics(config.name)
        )

        reader2, writer2 = await asyncio.open_connection("127.0.0.1", config.port)
        writer2.write(bytes((ENQ, STX)) + b"CHK1ROOM102" + bytes((ETX,)))
        await writer2.drain()
        assert await asyncio.wait_for(reader2.readexactly(2), timeout=1) == bytes((ACK, ACK))
        await asyncio.sleep(0)

        status = runtime.status()["transport_session"]
        assert status["pending_bytes"] == 0
        assert status["last_opcode"] == "CHK1"

        writer2.close()
        await writer2.wait_closed()
        await manager.stop(config.name)

    asyncio.run(exercise())


def test_mitel_serial_does_not_use_tcp_session_state_machine():
    manager = InterfaceManager()
    config = InterfaceConfig(
        name="mitel-serial-boundary",
        purpose="pms",
        protocol="MITEL 1",
        transport="serial",
        serial_device="loop://",
    )
    runtime = type("RuntimeStub", (), {"config": config})()
    assert manager._uses_mitel_tcp_session(runtime) is False
