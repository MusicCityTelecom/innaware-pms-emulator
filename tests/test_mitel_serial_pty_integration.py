import asyncio
import os

import pytest

if os.name != "nt":
    import pty
else:  # pragma: no cover - import guard for Windows collection
    pty = None

from innaware_pms_emulator.framing import ACK, ENQ, ETX, STX
from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager


pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX PTY integration test")


def _serial_config(device: str) -> InterfaceConfig:
    return InterfaceConfig(
        name="mitel-serial-pty",
        purpose="pms",
        protocol="MITEL 1",
        transport="serial",
        serial_device=device,
        baud_rate=1200,
        data_bits=8,
        parity="N",
        stop_bits=1,
        flow_control="xonxoff",
        enabled=False,
        options={"auto_ack": True, "strict_half_duplex": True},
    )


async def _wait_online(manager: InterfaceManager, name: str, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        runtime = manager.get(name)
        if runtime.state == "online":
            return
        if runtime.state == "error":
            raise AssertionError(runtime.last_error)
        await asyncio.sleep(0.01)
    raise AssertionError(f"serial interface did not become online: {manager.get(name).status()}")


async def _read_master(master_fd: int, minimum: int, timeout: float = 2.0) -> bytes:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    data = bytearray()
    while loop.time() < deadline:
        try:
            chunk = os.read(master_fd, 4096)
        except BlockingIOError:
            chunk = b""
        if chunk:
            data.extend(chunk)
            if len(data) >= minimum:
                return bytes(data)
        await asyncio.sleep(0.01)
    raise AssertionError(f"expected at least {minimum} byte(s) from PTY, got {bytes(data)!r}")


def test_mitel_serial_runtime_over_real_pty_fragmentation_and_reopen_reset():
    async def exercise() -> None:
        assert pty is not None
        master_fd, slave_fd = pty.openpty()
        slave_name = os.ttyname(slave_fd)
        os.close(slave_fd)
        os.set_blocking(master_fd, False)

        manager = InterfaceManager()
        await manager.create(_serial_config(slave_name))

        try:
            await manager.start("mitel-serial-pty")
            await _wait_online(manager, "mitel-serial-pty")

            # Exercise the real serial transport with an ENQ and a deliberately
            # fragmented STX/ETX application frame. The session should ACK the
            # ENQ and ACK the completed CHK1 frame only after ETX arrives.
            os.write(master_fd, bytes((ENQ, STX)) + b"CHK1ROOM")
            first = await _read_master(master_fd, 1)
            assert first == bytes((ACK,))

            os.write(master_fd, b"101" + bytes((ETX,)))
            second = await _read_master(master_fd, 1)
            assert second == bytes((ACK,))

            runtime = manager.get("mitel-serial-pty")
            status = runtime.transport_session_status
            assert status is not None
            assert status["transport"] == "serial"
            assert status["state"] == "idle"
            assert status["enq_received"] == 1
            assert status["frames_received"] == 1

            # Leave a partial frame in flight. Stopping the interface must close
            # the serial session and preserve an actionable framing diagnostic.
            os.write(master_fd, bytes((STX,)) + b"NAM2TEST,GUEST")
            await asyncio.sleep(0.05)
            await manager.stop("mitel-serial-pty")

            diagnostics = manager.diagnostics("mitel-serial-pty")
            incomplete = [item for item in diagnostics if item["code"] == "mitel_serial_close_incomplete_frame"]
            assert incomplete
            assert incomplete[-1]["evidence_class"] == "legacy_source_profile_verified"
            assert "STX" in incomplete[-1]["observed"]
            assert "ETX" in incomplete[-1]["expected"]

            # Reopen the same OS PTY and prove that decoder/half-duplex state is
            # new rather than inherited from the interrupted frame above.
            await manager.start("mitel-serial-pty")
            await _wait_online(manager, "mitel-serial-pty")
            os.write(master_fd, bytes((ENQ, STX)) + b"CHK0ROOM102" + bytes((ETX,)))
            reopened = await _read_master(master_fd, 2)
            assert reopened == bytes((ACK, ACK))

            status = manager.get("mitel-serial-pty").transport_session_status
            assert status is not None
            assert status["state"] == "idle"
            assert status["enq_received"] == 1
            assert status["frames_received"] == 1
            assert status["last_opcode"] == "CHK0"
        finally:
            try:
                await manager.stop("mitel-serial-pty")
            except Exception:
                pass
            os.close(master_fd)

    asyncio.run(exercise())
