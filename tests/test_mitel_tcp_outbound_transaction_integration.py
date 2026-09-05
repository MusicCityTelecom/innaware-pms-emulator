import asyncio
import socket

from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _mitel_server(name: str, **options) -> InterfaceConfig:
    defaults = {
        "auto_ack": True,
        "strict_half_duplex": True,
        "ack_timeout": 0.2,
        "max_attempts": 2,
        "max_record_retries": 1,
        "framing": "stx_etx",
        "transaction_framing": "stx_etx",
    }
    defaults.update(options)
    return InterfaceConfig(
        name=name,
        purpose="pms",
        protocol="MITEL 1",
        transport="tcp_server",
        bind_host="127.0.0.1",
        port=_available_port(),
        options=defaults,
    )


async def _wait_for_single_client(runtime) -> None:
    for _ in range(100):
        if len(runtime.clients) == 1:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Mitel TCP test client was not accepted")


def test_outbound_mitel_transaction_uses_integrated_ack_queue_and_message_only_retry():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = _mitel_server("mitel-outbound-retry")
        runtime = await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)
        await _wait_for_single_client(runtime)

        record = b"CHK1ROOM101"
        wire_record = bytes((STX,)) + record + bytes((ETX,))
        transaction = asyncio.create_task(manager.send_pms_transaction(config.name, record))

        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == bytes((ENQ,))
        writer.write(bytes((ACK,)))
        await writer.drain()

        assert await asyncio.wait_for(reader.readexactly(len(wire_record)), timeout=1) == wire_record
        writer.write(bytes((NAK,)))
        await writer.drain()

        # Evidence-qualified Mitel retry behavior resends the application frame
        # without acquiring a second ENQ grant.
        assert await asyncio.wait_for(reader.readexactly(len(wire_record)), timeout=1) == wire_record
        writer.write(bytes((ACK,)))
        await writer.drain()

        result = await asyncio.wait_for(transaction, timeout=1)
        assert result["success"] is True
        assert result["stage"] == "complete"
        assert result["attempts"] == 2
        assert "diagnostic" not in result

        tx = [item for item in manager.captures(config.name) if item["direction"] == "tx"]
        assert sum(item["hex"] == "05" for item in tx) == 1
        assert sum(item["hex"] == wire_record.hex(" ") for item in tx) == 2

        writer.close()
        await writer.wait_closed()
        await manager.stop(config.name)

    asyncio.run(exercise())


def test_outbound_wait_ignores_ack_valued_byte_inside_peer_application_frame():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = _mitel_server("mitel-outbound-stream-routing", max_record_retries=0)
        runtime = await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)
        await _wait_for_single_client(runtime)

        record = b"NAM2JOHNSMITH101"
        wire_record = bytes((STX,)) + record + bytes((ETX,))
        transaction = asyncio.create_task(manager.send_pms_transaction(config.name, record))
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == bytes((ENQ,))

        # The 0x06 below is payload data, not a standalone ACK. The peer frame
        # is also invalid here because it did not acquire its own ENQ grant, so
        # the receive state machine returns NAK while the outbound transaction
        # continues waiting for a real standalone response control.
        peer_frame = bytes((STX,)) + b"NAM2JO\x06HNSMITH101" + bytes((ETX,))
        writer.write(peer_frame)
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == bytes((NAK,))
        await asyncio.sleep(0.02)
        assert transaction.done() is False

        writer.write(bytes((ACK,)))
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(len(wire_record)), timeout=1) == wire_record
        writer.write(bytes((ACK,)))
        await writer.drain()

        result = await asyncio.wait_for(transaction, timeout=1)
        assert result["success"] is True
        assert any(
            diagnostic["code"] == "mitel_tcp_frame_without_enq"
            for diagnostic in manager.diagnostics(config.name)
        )

        writer.close()
        await writer.wait_closed()
        await manager.stop(config.name)

    asyncio.run(exercise())


def test_outbound_mitel_nak_failure_is_persisted_as_structured_transaction_diagnostic():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = _mitel_server("mitel-outbound-diagnostic", max_record_retries=0)
        runtime = await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)
        await _wait_for_single_client(runtime)

        record = b"CHK1ROOM101"
        wire_record = bytes((STX,)) + record + bytes((ETX,))
        transaction = asyncio.create_task(manager.send_pms_transaction(config.name, record))

        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == bytes((ENQ,))
        writer.write(bytes((ACK,)))
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(len(wire_record)), timeout=1) == wire_record
        writer.write(bytes((NAK,)))
        await writer.drain()

        result = await asyncio.wait_for(transaction, timeout=1)
        assert result["success"] is False
        assert result["stage"] == "record"
        assert result["diagnostic"]["code"] == "mitel_transaction_record_nak_exhausted"
        assert result["diagnostic"]["confidence"] == "high"
        assert "WHAT" not in result["diagnostic"]  # structured fields carry the explanation directly
        assert manager.transactions(config.name)[-1]["diagnostic"] == result["diagnostic"]

        writer.close()
        await writer.wait_closed()
        await manager.stop(config.name)

    asyncio.run(exercise())
