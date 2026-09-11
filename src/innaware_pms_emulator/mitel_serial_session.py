from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .framing import ACK, ENQ, ETX, NAK, STX
from .mitel_session import MitelSessionAction, MitelSessionDiagnostic, MitelSessionRecord


_SERIAL_NORMAL_FAMILIES = {
    "AREYUTHERE",
    "CHK",
    "NAM",
    "WKP",
    "RST",
    "DND",
    "MW",
    "LNG",
    "LMT",
    "DPT",
    "LOC",
    "VIP",
    "SDD",
    "STE",
    "MOV",
    "EDT",
    "STS",
    "MSG",
    "GRS",
    "END",
    "RQINZ",
}
_OPCODE_RE = re.compile(r"^([A-Z]+)([0-9]*)")


@dataclass(slots=True)
class MitelSerialFeed:
    actions: list[MitelSessionAction] = field(default_factory=list)
    response_controls: list[int] = field(default_factory=list)
    records: list[MitelSessionRecord] = field(default_factory=list)
    diagnostics: list[MitelSessionDiagnostic] = field(default_factory=list)


class _SerialStxEtxDecoder:
    """Incrementally separate serial controls from STX/ETX records.

    Serial driver reads are arbitrary chunks just like TCP reads, but this
    decoder is intentionally serial-specific so transport/session behavior is
    not coupled to the Mitel TCP implementation.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    @property
    def pending(self) -> bytes:
        return bytes(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()

    def finish(self) -> bytes:
        pending = bytes(self._buffer)
        self._buffer.clear()
        return pending

    def feed(self, chunk: bytes) -> list[tuple[str, bytes]]:
        self._buffer.extend(chunk)
        items: list[tuple[str, bytes]] = []
        while self._buffer:
            first = self._buffer[0]
            if first in {ENQ, ACK, NAK}:
                del self._buffer[0]
                items.append(("control", bytes((first,))))
                continue
            if first != STX:
                value = bytes((self._buffer.pop(0),))
                items.append(("error", value))
                continue
            nested = self._buffer.find(bytes((STX,)), 1)
            end = self._buffer.find(bytes((ETX,)), 1)
            if nested != -1 and (end == -1 or nested < end):
                raw = bytes(self._buffer[:nested])
                del self._buffer[:nested]
                items.append(("error", raw))
                continue
            if end == -1:
                break
            raw = bytes(self._buffer[: end + 1])
            del self._buffer[: end + 1]
            items.append(("frame", raw[1:-1]))
        return items


class MitelSerialSessionStateMachine:
    """Legacy-evidence Mitel serial half-duplex receive session.

    This state machine is deliberately independent from the TCP session state
    machine. Shared application families are reused only where the durable
    evidence index records legacy MTL/profile or simulator support. The serial
    framing/control defaults are the legacy MTL values ENQ=0x05, STX=0x02,
    ETX=0x03, ACK=0x06, NAK=0x15, checksum disabled; they are not asserted as
    universal behavior for every Mitel model.
    """

    def __init__(
        self,
        *,
        auto_ack: bool = True,
        strict_half_duplex: bool = True,
        baud_rate: int = 1200,
        data_bits: int = 8,
        parity: str = "N",
        stop_bits: float = 1,
        flow_control: str = "xonxoff",
    ) -> None:
        self.auto_ack = bool(auto_ack)
        self.strict_half_duplex = bool(strict_half_duplex)
        self.baud_rate = int(baud_rate)
        self.data_bits = int(data_bits)
        self.parity = str(parity)
        self.stop_bits = float(stop_bits)
        self.flow_control = str(flow_control)
        self._decoder = _SerialStxEtxDecoder()
        self.opened = False
        self.peer_granted = False
        self.peer_retry_window = False
        self.peer_record_attempts = 0
        self.enq_received = 0
        self.frames_received = 0
        self.keepalives_received = 0
        self.open_generation = 0
        self.last_opcode: str | None = None

    @property
    def pending(self) -> bytes:
        return self._decoder.pending

    def status(self) -> dict[str, Any]:
        if not self.opened:
            state = "closed"
        elif self.peer_granted:
            state = "peer_granted"
        elif self.peer_retry_window:
            state = "peer_retry_window"
        else:
            state = "idle"
        return {
            "transport": "serial",
            "framing": "stx_etx",
            "opened": self.opened,
            "state": state,
            "peer_granted": self.peer_granted,
            "peer_retry_window": self.peer_retry_window,
            "peer_record_attempts": self.peer_record_attempts,
            "enq_received": self.enq_received,
            "frames_received": self.frames_received,
            "keepalives_received": self.keepalives_received,
            "open_generation": self.open_generation,
            "last_opcode": self.last_opcode,
            "pending_bytes": len(self.pending),
            "serial": {
                "baud_rate": self.baud_rate,
                "data_bits": self.data_bits,
                "parity": self.parity,
                "stop_bits": self.stop_bits,
                "flow_control": self.flow_control,
            },
            "evidence_class": "legacy_source_profile_verified",
        }

    def open(self) -> None:
        self._decoder.reset()
        self.opened = True
        self.peer_granted = False
        self.peer_retry_window = False
        self.peer_record_attempts = 0
        self.last_opcode = None
        self.open_generation += 1

    def close(self) -> list[MitelSessionDiagnostic]:
        diagnostics: list[MitelSessionDiagnostic] = []
        pending = self._decoder.finish()
        if pending:
            diagnostics.append(
                MitelSessionDiagnostic(
                    code="mitel_serial_close_incomplete_frame",
                    severity="warning",
                    confidence="high",
                    evidence_class="legacy_source_profile_verified",
                    observed=f"Serial session closed with {len(pending)} buffered byte(s) of an incomplete STX/ETX frame",
                    expected="A complete STX ... ETX application record before the serial port closes",
                    corrective_action="Check serial cabling/session teardown and confirm STX/ETX framing.",
                )
            )
        self.opened = False
        self.peer_granted = False
        self.peer_retry_window = False
        self.peer_record_attempts = 0
        self.last_opcode = None
        return diagnostics

    def feed(self, chunk: bytes) -> MitelSerialFeed:
        if not self.opened:
            raise RuntimeError("Mitel serial session must be open before feeding bytes")
        result = MitelSerialFeed()
        for kind, value in self._decoder.feed(chunk):
            if kind == "control":
                self._handle_control(value[0], result)
            elif kind == "frame":
                self._handle_frame(value, result)
            else:
                self._handle_framing_error(value, result)
        return result

    def _handle_control(self, control: int, result: MitelSerialFeed) -> None:
        if control == ENQ:
            self.enq_received += 1
            if self.peer_granted or self.peer_retry_window:
                result.diagnostics.append(
                    MitelSessionDiagnostic(
                        code="mitel_serial_repeated_enq",
                        severity="info",
                        confidence="medium",
                        evidence_class="inference_not_yet_verified",
                        observed="Peer sent ENQ while a previous serial receive transaction was still open",
                        expected="Legacy MTL sequence ENQ -> ACK followed by one STX ... ETX record",
                        corrective_action="Inspect for a lost ACK or retry; do not change personalities automatically.",
                    )
                )
            self.peer_granted = True
            self.peer_retry_window = False
            self.peer_record_attempts = 0
            if self.auto_ack:
                result.actions.append(MitelSessionAction(bytes((ACK,)), "Mitel serial ACK response to ENQ"))
            return
        if control in {ACK, NAK}:
            result.response_controls.append(control)

    def _handle_frame(self, payload: bytes, result: MitelSerialFeed) -> None:
        self.frames_received += 1
        opcode, family = self._classify_opcode(payload)
        if opcode:
            self.last_opcode = opcode

        if self.strict_half_duplex and not (self.peer_granted or self.peer_retry_window):
            result.diagnostics.append(
                MitelSessionDiagnostic(
                    code="mitel_serial_frame_without_enq",
                    severity="warning",
                    confidence="high",
                    evidence_class="legacy_source_profile_verified",
                    observed=f"Received serial STX/ETX frame {opcode or '<unknown>'} without an open ENQ grant",
                    expected="Legacy MTL sequence ENQ -> ACK before STX + message + ETX",
                    corrective_action="Verify serial profile, message direction, and ENQ/ACK handshake settings.",
                )
            )
            if self.auto_ack:
                result.actions.append(MitelSessionAction(bytes((NAK,)), "Mitel serial NAK frame without ENQ"))
            return

        self.peer_granted = False
        self.peer_record_attempts += 1
        validation_error = self._validation_error(opcode, family)
        if validation_error is not None:
            result.diagnostics.append(validation_error)
            self._reject_frame(result, "Mitel serial NAK invalid application frame")
            return
        if not opcode or family not in _SERIAL_NORMAL_FAMILIES:
            result.diagnostics.append(
                MitelSessionDiagnostic(
                    code="mitel_serial_uncharacterized_message",
                    severity="warning",
                    confidence="high",
                    evidence_class="legacy_source_profile_verified",
                    observed=f"Received uncharacterized Mitel serial payload prefix {opcode or '<none>'}",
                    expected="A legacy-characterized Mitel-family CHK/NAM/WKP/MW/RST/LOC/etc. record",
                    corrective_action="Verify the selected Mitel serial dialect and capture the record before extending the profile.",
                )
            )
            self._reject_frame(result, "Mitel serial NAK uncharacterized application frame")
            return

        self.peer_retry_window = False
        if family == "AREYUTHERE":
            self.keepalives_received += 1
        evidence = "legacy_source_profile_verified"
        if family == "NAM":
            evidence = "legacy_simulator_characterized"
        result.records.append(MitelSessionRecord(opcode, family, payload, evidence))
        if self.auto_ack:
            result.actions.append(MitelSessionAction(bytes((ACK,)), f"Mitel serial ACK {opcode} application frame"))

    def _reject_frame(self, result: MitelSerialFeed, note: str) -> None:
        self.peer_retry_window = self.peer_record_attempts < 4
        if self.auto_ack:
            result.actions.append(MitelSessionAction(bytes((NAK,)), note))

    def _handle_framing_error(self, raw: bytes, result: MitelSerialFeed) -> None:
        result.diagnostics.append(
            MitelSessionDiagnostic(
                code="mitel_serial_framing_error",
                severity="warning",
                confidence="high",
                evidence_class="legacy_source_profile_verified",
                observed=f"Unexpected serial byte(s) outside STX/ETX framing: {raw.hex(' ')}",
                expected="One-byte ENQ/ACK/NAK controls or STX ... ETX application records",
                corrective_action="Check serial-vs-TCP profile selection, baud/data/parity/stop settings, and STX/ETX framing.",
            )
        )
        if self.peer_granted or self.peer_retry_window:
            self.peer_granted = False
            self.peer_record_attempts += 1
            self._reject_frame(result, "Mitel serial NAK malformed granted frame")

    @staticmethod
    def _classify_opcode(payload: bytes) -> tuple[str | None, str | None]:
        text = payload.decode("latin-1", errors="replace").strip("\x00\r\n ")
        if not text:
            return None, None
        match = _OPCODE_RE.match(text.upper())
        if not match:
            return None, None
        family = match.group(1)
        suffix = match.group(2)
        return family + suffix, family

    @staticmethod
    def _validation_error(opcode: str | None, family: str | None) -> MitelSessionDiagnostic | None:
        if family == "CHK" and opcode not in {"CHK0", "CHK1"}:
            return MitelSessionDiagnostic(
                code="mitel_serial_invalid_chk_status",
                severity="warning",
                confidence="high",
                evidence_class="operator_confirmed_behavior",
                observed=f"Received invalid Mitel serial check-in/out status {opcode or '<none>'}",
                expected="CHK1 for check-in or CHK0 for check-out",
                corrective_action="Correct the CHK status digit; CHK0 and CHK1 are normal protocol elements.",
            )
        if family == "NAM" and opcode not in {"NAM1", "NAM2", "NAM3", "NAM4"}:
            return MitelSessionDiagnostic(
                code="mitel_serial_uncharacterized_nam_status",
                severity="warning",
                confidence="medium",
                evidence_class="legacy_simulator_characterized",
                observed=f"Received uncharacterized Mitel serial name status {opcode or '<none>'}",
                expected="A characterized NAM1, NAM2, NAM3, or NAM4 record",
                corrective_action="Verify the Mitel serial dialect and name-operation status before extending the profile.",
            )
        return None
