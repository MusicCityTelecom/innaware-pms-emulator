import asyncio
import os

import pytest

if os.name != "nt":
    import pty
else:  # pragma: no cover - import guard for Windows collection
    pty = None

from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager


pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX PTY integration test")


def _phonesuite_serial_config(device: str, *, name: str = "phonesuite-serial-pty") -> InterfaceConfig:
    """Use operator-supplied settings without claiming PhoneSuite defaults."""
    return InterfaceConfig(
        name=name,
        purpose="pms",
        protocol="MITEL 1",
        transport="serial",
        personality_id="pbx-phonesuite",
        serial_device=device,
        baud_rate=19200,
        data_bits=8,
        parity="N",
        stop_bits=1,
        flow_control="none",
        enabled=False,
        options={"auto_ack": True, "strict_enq": True},
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


async def _wait_response_count(manager: InterfaceManager, name: str, count: int, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if manager.get(name).responses.qsize() >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"expected {count} queued response control(s), got {manager.get(name).responses.qsize()}")


def test_phonesuite_serial_runtime_over_real_pty_fragmentation_coalescing_and_reopen_reset() -> None:
    async def exercise() -> None:
        assert pty is not None
        master_fd, slave_fd = pty.openpty()
        slave_name = os.ttyname(slave_fd)
        os.close(slave_fd)
        os.set_blocking(master_fd, False)

        manager = InterfaceManager()
        config = _phonesuite_serial_config(slave_name)
        await manager.create(config)

        try:
            await manager.start(config.name)
            await _wait_online(manager, config.name)

            # The clean-room characterization permits ENQ/ACK followed by an
            # STX/ETX CHK record. Deliberately split the application frame so
            # the real serial path must retain decoder state until ETX arrives.
            os.write(master_fd, bytes((ENQ, STX)) + b"CHK1ROOM")
            assert await _read_master(master_fd, 1) == bytes((ACK,))

            os.write(master_fd, b"101" + bytes((ETX,)))
            assert await _read_master(master_fd, 1) == bytes((ACK,))

            runtime = manager.get(config.name)
            status = runtime.transport_session_status
            assert status is not None
            assert status["transport"] == "serial"
            assert status["pbx_family"] == "PhoneSuite"
            assert status["state"] == "idle"
            assert status["enq_received"] == 1
            assert status["frames_received"] == 1
            assert status["last_opcode"] == "CHK1"
            assert status["serial_defaults"] == "unqualified_configurable"

            # A complete ENQ + NAM2 frame in one OS-level write proves the same
            # decoder also handles coalesced controls/application data without
            # leaking into the generic Mitel serial session.
            os.write(
                master_fd,
                bytes((ENQ, STX)) + b"NAM2TEST,GUESTROOM102" + bytes((ETX,)),
            )
            assert await _read_master(master_fd, 2) == bytes((ACK, ACK))

            status = manager.get(config.name).transport_session_status
            assert status is not None
            assert status["pbx_family"] == "PhoneSuite"
            assert status["enq_received"] == 2
            assert status["frames_received"] == 2
            assert status["last_opcode"] == "NAM2"

            # Leave a partial characterized frame in flight. The ACK proves the
            # ENQ and partial STX bytes reached the PhoneSuite session before the
            # stop; close must retain an actionable incomplete-frame diagnostic.
            os.write(master_fd, bytes((ENQ, STX)) + b"CHK0ROOM")
            assert await _read_master(master_fd, 1) == bytes((ACK,))
            await manager.stop(config.name)

            diagnostics = manager.diagnostics(config.name)
            incomplete = [
                item for item in diagnostics
                if item["code"] == "phonesuite_serial_close_incomplete_frame"
            ]
            assert incomplete
            assert incomplete[-1]["evidence_class"] == "simulator_characterization"
            assert "STX" in incomplete[-1]["observed"]
            assert "ETX" in incomplete[-1]["expected"]

            # Reopen the exact PTY. Decoder/grant state must be fresh rather than
            # inherited from the interrupted frame, and configurable serial
            # parameters must not turn into a claimed PhoneSuite default.
            await manager.start(config.name)
            await _wait_online(manager, config.name)
            os.write(master_fd, bytes((ENQ, STX)) + b"CHK0ROOM103" + bytes((ETX,)))
            assert await _read_master(master_fd, 2) == bytes((ACK, ACK))

            status = manager.get(config.name).transport_session_status
            assert status is not None
            assert status["state"] == "idle"
            assert status["open_generation"] == 1
            assert status["enq_received"] == 1
            assert status["frames_received"] == 1
            assert status["last_opcode"] == "CHK0"
            assert status["serial_defaults"] == "unqualified_configurable"
        finally:
            try:
                await manager.stop(config.name)
            except Exception:
                pass
            os.close(master_fd)

    asyncio.run(exercise())


def test_phonesuite_serial_real_pty_routes_ack_nak_without_generic_auto_ack() -> None:
    async def exercise() -> None:
        assert pty is not None
        master_fd, slave_fd = pty.openpty()
        slave_name = os.ttyname(slave_fd)
        os.close(slave_fd)
        os.set_blocking(master_fd, False)

        manager = InterfaceManager()
        config = _phonesuite_serial_config(slave_name, name="phonesuite-serial-pty-controls")
        await manager.create(config)

        try:
            await manager.start(config.name)
            await _wait_online(manager, config.name)

            # Peer transaction responses are controls, not application frames.
            # They must reach the response queue and must not provoke the generic
            # serial auto-ACK fallback that PhoneSuite explicitly preempts.
            os.write(master_fd, bytes((ACK, NAK)))
            await _wait_response_count(manager, config.name, 2)

            runtime = manager.get(config.name)
            assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == ACK
            assert await asyncio.wait_for(runtime.responses.get(), timeout=1) == NAK
            assert runtime.responses.empty()

            await asyncio.sleep(0.05)
            try:
                unexpected = os.read(master_fd, 4096)
            except BlockingIOError:
                unexpected = b""
            assert unexpected == b""

            status = runtime.transport_session_status
            assert status is not None
            assert status["pbx_family"] == "PhoneSuite"
            assert status["serial_defaults"] == "unqualified_configurable"
        finally:
            try:
                await manager.stop(config.name)
            except Exception:
                pass
            os.close(master_fd)

    asyncio.run(exercise())
