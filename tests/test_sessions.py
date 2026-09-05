import asyncio
import socket

from innaware_pms_emulator.framing import ACK, ENQ, ETX, STX
from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_state(runtime, expected: str, *, timeout: float = 1.0) -> None:
    """Wait for an asynchronous connection callback without assuming one loop tick."""
    async def observe() -> None:
        while runtime.state != expected:
            await asyncio.sleep(0.001)

    await asyncio.wait_for(observe(), timeout=timeout)


def test_tcp_server_stop_closes_clients_and_stays_stopped():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = InterfaceConfig(
            name="lifecycle-test",
            purpose="pms",
            protocol="FIAS",
            transport="tcp_server",
            bind_host="127.0.0.1",
            port=_available_port(),
        )
        runtime = await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)
        await _wait_for_state(runtime, "online")
        assert runtime.state == "online"

        await manager.stop(config.name)
        assert runtime.state == "stopped"
        assert runtime.server is None
        assert runtime.clients == set()
        assert runtime.client_tasks == set()
        assert await asyncio.wait_for(reader.read(), timeout=1) == b""
        await asyncio.sleep(0)
        assert runtime.state == "stopped"
        writer.close()

        await manager.start(config.name)
        assert runtime.state == "listening"
        reader2, writer2 = await asyncio.open_connection("127.0.0.1", config.port)
        await manager.stop(config.name)
        assert await asyncio.wait_for(reader2.read(), timeout=1) == b""
        writer2.close()

    asyncio.run(exercise())


def test_operaip_tcp_server_performs_legacy_control_handshake():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = InterfaceConfig(
            name="operaip-wire-test",
            purpose="pms",
            protocol="OPERAIP_FIAS",
            transport="tcp_server",
            bind_host="127.0.0.1",
            port=_available_port(),
            options={
                "framing": "stx_etx", "role": "pms",
                "ack_enq": True, "ack_records": True,
            },
        )
        await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)
        writer.write(bytes((ENQ,)))
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == bytes((ACK,))

        writer.write(bytes((STX,)) + b"LA|DA260827|TI220000|" + bytes((ETX,)))
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=1) == bytes((ACK,))
        await manager.stop(config.name)
        writer.close()

    asyncio.run(exercise())


def test_remove_stops_active_interface_and_deletes_runtime():
    async def exercise() -> None:
        manager = InterfaceManager()
        config = InterfaceConfig(
            name="delete-test",
            purpose="pms",
            protocol="FIAS",
            transport="tcp_server",
            bind_host="127.0.0.1",
            port=_available_port(),
        )
        runtime = await manager.create(config)
        reader, writer = await asyncio.open_connection("127.0.0.1", config.port)
        await asyncio.sleep(0)

        await manager.remove(config.name)
        assert manager.list() == []
        assert runtime.state == "stopped"
        assert await asyncio.wait_for(reader.read(), timeout=1) == b""
        writer.close()

    asyncio.run(exercise())
