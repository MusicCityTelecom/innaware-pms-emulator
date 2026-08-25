from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import serial_asyncio

from .framing import ACK, ENQ, NAK, FramingMode, control_name, encode_frame
from .models import InterfaceConfig, TransportMode
from .state import CallAccountingStateMachine, EngineAction, FiasStateMachine


@dataclass(slots=True)
class CaptureRecord:
    timestamp: str
    direction: str
    data: bytes
    peer: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "direction": self.direction,
            "peer": self.peer,
            "note": self.note,
            "hex": self.data.hex(" "),
            "text": self.data.decode("latin-1", errors="replace"),
        }


@dataclass
class InterfaceRuntime:
    config: InterfaceConfig
    state: str = "stopped"
    last_error: str | None = None
    server: asyncio.AbstractServer | None = None
    task: asyncio.Task | None = None
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    peer: str | None = None
    captures: deque[CaptureRecord] = field(default_factory=lambda: deque(maxlen=2000))
    clients: set[asyncio.StreamWriter] = field(default_factory=set)
    engine: FiasStateMachine | CallAccountingStateMachine | None = None

    def capture(self, direction: str, data: bytes, *, peer: str | None = None, note: str | None = None) -> None:
        self.captures.append(CaptureRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            direction=direction,
            data=data,
            peer=peer,
            note=note,
        ))

    def status(self) -> dict[str, Any]:
        result = {
            "name": self.config.name,
            "purpose": self.config.purpose.value,
            "protocol": self.config.protocol,
            "transport": self.config.transport.value,
            "state": self.state,
            "peer": self.peer,
            "connected_clients": len(self.clients),
            "last_error": self.last_error,
        }
        if self.engine:
            result["protocol_state"] = self.engine.status()
        return result


class InterfaceManager:
    def __init__(self) -> None:
        self._interfaces: dict[str, InterfaceRuntime] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _build_engine(config: InterfaceConfig):
        protocol = config.protocol.upper()
        if protocol in {"FIAS", "HILTON_PEP_FIAS"}:
            return FiasStateMachine(role=str(config.options.get("role", "pms")))
        if protocol in {"INNFORM_XL", "HOBIS"}:
            return CallAccountingStateMachine(
                ack_type=str(config.options.get("ack_type", "ack")),
                auto_ack=bool(config.options.get("auto_ack", True)),
                ack_enq=bool(config.options.get("ack_enq", True)),
            )
        return None

    async def create(self, config: InterfaceConfig) -> InterfaceRuntime:
        key = config.name.strip().lower()
        async with self._lock:
            if key in self._interfaces:
                raise ValueError(f"Interface '{config.name}' already exists")
            runtime = InterfaceRuntime(config=config, engine=self._build_engine(config))
            self._interfaces[key] = runtime
        if config.enabled:
            await self.start(config.name)
        return runtime

    def get(self, name: str) -> InterfaceRuntime:
        runtime = self._interfaces.get(name.strip().lower())
        if not runtime:
            raise KeyError(name)
        return runtime

    def list(self) -> list[dict[str, Any]]:
        return [runtime.status() for runtime in self._interfaces.values()]

    async def remove(self, name: str) -> None:
        await self.stop(name)
        async with self._lock:
            self._interfaces.pop(name.strip().lower(), None)

    async def start(self, name: str) -> None:
        runtime = self.get(name)
        if runtime.state not in {"stopped", "error"}:
            return
        runtime.last_error = None
        transport = runtime.config.transport
        if transport is TransportMode.TCP_SERVER:
            await self._start_tcp_server(runtime)
        elif transport is TransportMode.TCP_CLIENT:
            runtime.task = asyncio.create_task(self._tcp_client_loop(runtime), name=f"pms-client:{name}")
        elif transport is TransportMode.SERIAL:
            runtime.task = asyncio.create_task(self._serial_loop(runtime), name=f"pms-serial:{name}")
        elif transport is TransportMode.HTTP_SERVER:
            runtime.state = "ready"
        else:
            raise ValueError(f"Unsupported transport: {transport}")

    async def stop(self, name: str) -> None:
        runtime = self.get(name)
        if runtime.server:
            runtime.server.close()
            await runtime.server.wait_closed()
            runtime.server = None
        if runtime.task:
            runtime.task.cancel()
            try:
                await runtime.task
            except asyncio.CancelledError:
                pass
            runtime.task = None
        for writer in list(runtime.clients):
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        runtime.clients.clear()
        if runtime.writer:
            runtime.writer.close()
            try:
                await runtime.writer.wait_closed()
            except Exception:
                pass
        runtime.reader = None
        runtime.writer = None
        runtime.peer = None
        runtime.state = "stopped"

    async def send(self, name: str, payload: bytes, *, frame: bool = True) -> int:
        runtime = self.get(name)
        framing = runtime.config.options.get("framing", "raw")
        wire = encode_frame(payload, FramingMode(framing)) if frame else payload
        sent = 0
        if runtime.config.transport is TransportMode.TCP_SERVER:
            dead: list[asyncio.StreamWriter] = []
            for writer in list(runtime.clients):
                try:
                    writer.write(wire)
                    await writer.drain()
                    sent += 1
                    runtime.capture("tx", wire, peer=self._peer_name(writer))
                except Exception:
                    dead.append(writer)
            for writer in dead:
                runtime.clients.discard(writer)
        elif runtime.writer:
            runtime.writer.write(wire)
            await runtime.writer.drain()
            sent = 1
            runtime.capture("tx", wire, peer=runtime.peer)
        else:
            raise RuntimeError(f"Interface '{name}' has no connected endpoint")
        return sent

    async def send_control(self, name: str, control: str) -> int:
        mapping = {"ENQ": ENQ, "ACK": ACK, "NAK": NAK}
        value = mapping.get(control.upper())
        if value is None:
            raise ValueError("Control must be ENQ, ACK, or NAK")
        return await self.send(name, bytes((value,)), frame=False)

    def captures(self, name: str, limit: int = 200) -> list[dict[str, Any]]:
        runtime = self.get(name)
        records = list(runtime.captures)[-max(1, min(limit, 2000)):]
        return [record.as_dict() for record in records]

    async def _start_tcp_server(self, runtime: InterfaceRuntime) -> None:
        if not runtime.config.port:
            raise ValueError("TCP server requires port")
        runtime.state = "starting"

        async def connected(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            runtime.clients.add(writer)
            peer = self._peer_name(writer)
            runtime.peer = peer
            runtime.state = "online"
            try:
                await self._reader_loop(runtime, reader, peer)
            finally:
                runtime.clients.discard(writer)
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                if not runtime.clients:
                    runtime.peer = None
                    runtime.state = "listening"

        runtime.server = await asyncio.start_server(
            connected,
            host=runtime.config.bind_host,
            port=runtime.config.port,
        )
        runtime.state = "listening"

    async def _tcp_client_loop(self, runtime: InterfaceRuntime) -> None:
        if not runtime.config.host or not runtime.config.port:
            runtime.state = "error"
            runtime.last_error = "TCP client requires host and port"
            return
        reconnect = float(runtime.config.options.get("reconnect_seconds", 5.0))
        while True:
            try:
                runtime.state = "connecting"
                reader, writer = await asyncio.open_connection(runtime.config.host, runtime.config.port)
                runtime.reader, runtime.writer = reader, writer
                runtime.peer = self._peer_name(writer)
                runtime.state = "online"
                await self._reader_loop(runtime, reader, runtime.peer)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                runtime.last_error = str(exc)
                runtime.state = "reconnecting"
            finally:
                if runtime.writer:
                    runtime.writer.close()
                    try:
                        await runtime.writer.wait_closed()
                    except Exception:
                        pass
                runtime.reader = runtime.writer = None
                runtime.peer = None
            await asyncio.sleep(max(reconnect, 0.2))

    async def _serial_loop(self, runtime: InterfaceRuntime) -> None:
        if not runtime.config.serial_device:
            runtime.state = "error"
            runtime.last_error = "Serial transport requires serial_device"
            return
        parity = runtime.config.parity.upper()
        runtime.state = "connecting"
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=runtime.config.serial_device,
                baudrate=runtime.config.baud_rate,
                bytesize=runtime.config.data_bits,
                parity=parity,
                stopbits=runtime.config.stop_bits,
                rtscts=runtime.config.flow_control.lower() == "rtscts",
                xonxoff=runtime.config.flow_control.lower() == "xonxoff",
            )
            runtime.reader, runtime.writer = reader, writer
            runtime.peer = runtime.config.serial_device
            runtime.state = "online"
            await self._reader_loop(runtime, reader, runtime.peer)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            runtime.last_error = str(exc)
            runtime.state = "error"

    async def _reader_loop(self, runtime: InterfaceRuntime, reader: asyncio.StreamReader, peer: str | None) -> None:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            note = None
            if len(data) == 1:
                note = control_name(data[0])
            runtime.capture("rx", data, peer=peer, note=note)

            if runtime.engine:
                for action in runtime.engine.feed(data):
                    await self._send_action(runtime, peer, action)
            elif runtime.config.options.get("auto_ack") and data != bytes((ACK,)):
                await self._send_action(
                    runtime,
                    peer,
                    EngineAction(bytes((ACK,)), "generic auto ACK", apply_framing=False),
                )

    async def _send_action(self, runtime: InterfaceRuntime, peer: str | None, action: EngineAction) -> None:
        writer = self._writer_for_peer(runtime, peer)
        if not writer:
            return
        framing = runtime.config.options.get("framing", "raw")
        wire = encode_frame(action.payload, FramingMode(framing)) if action.apply_framing else action.payload
        writer.write(wire)
        await writer.drain()
        runtime.capture("tx", wire, peer=peer, note=action.note)

    @staticmethod
    def _peer_name(writer: asyncio.StreamWriter) -> str | None:
        peer = writer.get_extra_info("peername")
        if isinstance(peer, tuple) and len(peer) >= 2:
            return f"{peer[0]}:{peer[1]}"
        return str(peer) if peer else None

    @staticmethod
    def _writer_for_peer(runtime: InterfaceRuntime, peer: str | None) -> asyncio.StreamWriter | None:
        if runtime.writer:
            return runtime.writer
        for writer in runtime.clients:
            if InterfaceManager._peer_name(writer) == peer:
                return writer
        return None


manager = InterfaceManager()
