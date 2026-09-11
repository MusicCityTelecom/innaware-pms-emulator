from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .framing import ACK, ENQ, ETX, NAK, STX


_OPCODE_RE = re.compile(r"^([A-Z]+)([0-9]*)")
_CHARACTERIZED_OPCODES = {"CHK0", "CHK1", "NAM2"}


@dataclass(frozen=True, slots=True)
class PhoneSuiteSerialAction:
    payload: bytes
    note: str


@dataclass(frozen=True, slots=True)
class PhoneSuiteSerialRecord:
    opcode: str
    family: str
    payload: bytes
    evidence_class: str = "simulator_characterization"


@dataclass(frozen=True, slots=True)
class PhoneSuiteSerialDiagnostic:
    code: str
    severity: str
    confidence: str
    evidence_class: str
    observed: str
    expected: str
    corrective_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "confidence": self.confidence,
            "evidence_class": self.evidence_class,
            "observed": self.observed,
            "expected": self.expected,
            "corrective_action": self.corrective_action,
        }


@dataclass(slots=True)
class PhoneSuiteSerialFeed:
    actions: list[PhoneSuiteSerialAction] = field(default_factory=list)
    response_controls: list[int] = field(default_factory=list)
    records: list[PhoneSuiteSerialRecord] = field(default_factory=list)
    diagnostics: list[PhoneSuiteSerialDiagnostic] = field(default_factory=list)


class _PhoneSuiteSerialDecoder:
    """Incrementally separate one-byte controls from STX/ETX records."""

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
                items.append(("error", bytes((self._buffer.pop(0),))))
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


class PhoneSuiteSerialSessionStateMachine:
    """Clean-room PhoneSuite PMS-serial receive-session characterization.

    The qualified PhoneSuite simulator evidence currently supports ENQ/ACK
    session control and STX/ETX framing around CHK/NAM-family records. Only the
    exact CHK0, CHK1, and NAM2 examples represented by the sanitized fixture
    are treated as characterized application records here.

    Serial baud/data/parity/stop-bit settings are deliberately not assigned by
    this class. Those are transport configuration supplied by the operator
    until PhoneSuite-specific evidence qualifies defaults.
    """

    def __init__(self, *, auto_ack: bool = True, strict_enq: bool = True) -> None:
        self.auto_ack = bool(auto_ack)
        self.strict_enq = bool(strict_enq)
        self._decoder = _PhoneSuiteSerialDecoder()
        self.opened = False
        self.peer_granted = False
        self.enq_received = 0
        self.frames_received = 0
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
        else:
            state = "idle"
        return {
            "transport": "serial",
            "pbx_family": "PhoneSuite",
            "framing": "stx_etx",
            "state": state,
            "opened": self.opened,
            "peer_granted": self.peer_granted,
            "enq_received": self.enq_received,
            "frames_received": self.frames_received,
            "open_generation": self.open_generation,
            "last_opcode": self.last_opcode,
            "pending_bytes": len(self.pending),
            "serial_defaults": "unqualified_configurable",
            "evidence_class": "simulator_characterization",
        }

    def open(self) -> None:
        self._decoder.reset()
        self.opened = True
        self.peer_granted = False
        self.last_opcode = None
        self.open_generation += 1

    def close(self) -> list[PhoneSuiteSerialDiagnostic]:
        diagnostics: list[PhoneSuiteSerialDiagnostic] = []
        pending = self._decoder.finish()
        if pending:
            diagnostics.append(
                PhoneSuiteSerialDiagnostic(
                    code="phonesuite_serial_close_incomplete_frame",
                    severity="warning",
                    confidence="high",
                    evidence_class="simulator_characterization",
                    observed=f"Serial session closed with {len(pending)} buffered byte(s) of an incomplete STX/ETX frame",
                    expected="A complete STX ... ETX PhoneSuite PMS application record before port close",
                    corrective_action="Check the serial link and capture the peer traffic; confirm STX/ETX framing before changing the selected personality.",
                )
            )
        self.opened = False
        self.peer_granted = False
        self.last_opcode = None
        return diagnostics

    def feed(self, chunk: bytes) -> PhoneSuiteSerialFeed:
        if not self.opened:
            raise RuntimeError("PhoneSuite serial session must be open before feeding bytes")
        result = PhoneSuiteSerialFeed()
        for kind, value in self._decoder.feed(chunk):
            if kind == "control":
                self._handle_control(value[0], result)
            elif kind == "frame":
                self._handle_frame(value, result)
            else:
                self._handle_framing_error(value, result)
        return result

    def _handle_control(self, control: int, result: PhoneSuiteSerialFeed) -> None:
        if control == ENQ:
            self.enq_received += 1
            self.peer_granted = True
            if self.auto_ack:
                result.actions.append(PhoneSuiteSerialAction(bytes((ACK,)), "PhoneSuite serial ACK response to ENQ"))
            return
        if control in {ACK, NAK}:
            result.response_controls.append(control)

    def _handle_frame(self, payload: bytes, result: PhoneSuiteSerialFeed) -> None:
        self.frames_received += 1
        opcode, family = self._classify_opcode(payload)
        if opcode:
            self.last_opcode = opcode

        if self.strict_enq and not self.peer_granted:
            result.diagnostics.append(
                PhoneSuiteSerialDiagnostic(
                    code="phonesuite_serial_frame_without_enq",
                    severity="warning",
                    confidence="high",
                    evidence_class="simulator_characterization",
                    observed=f"Received PhoneSuite serial STX/ETX frame {opcode or '<unknown>'} without a preceding ENQ grant",
                    expected="Characterized PhoneSuite sequence ENQ -> ACK -> STX + CHK/NAM record + ETX",
                    corrective_action="Verify role/direction and ENQ/ACK handling. Do not substitute Mitel TCP or Series2 D-channel behavior for this PMS serial session.",
                )
            )
            return

        self.peer_granted = False
        if opcode not in _CHARACTERIZED_OPCODES:
            result.diagnostics.append(
                PhoneSuiteSerialDiagnostic(
                    code="phonesuite_serial_uncharacterized_record",
                    severity="warning",
                    confidence="high",
                    evidence_class="simulator_characterization",
                    observed=f"Received PhoneSuite serial application record {opcode or '<unknown>'} outside the clean-room characterized set",
                    expected="Current evidence-backed examples are CHK0, CHK1, and NAM2 records",
                    corrective_action="Capture and qualify this PhoneSuite PMS record before extending the personality; do not infer semantics from another PBX family.",
                )
            )
            return

        result.records.append(PhoneSuiteSerialRecord(opcode, family or "", payload))
        if self.auto_ack:
            result.actions.append(PhoneSuiteSerialAction(bytes((ACK,)), f"PhoneSuite serial ACK {opcode} application frame"))

    def _handle_framing_error(self, raw: bytes, result: PhoneSuiteSerialFeed) -> None:
        result.diagnostics.append(
            PhoneSuiteSerialDiagnostic(
                code="phonesuite_serial_framing_error",
                severity="warning",
                confidence="high",
                evidence_class="simulator_characterization",
                observed=f"Unexpected PhoneSuite serial byte(s) outside one-byte controls or STX/ETX framing: {raw.hex(' ')}",
                expected="ENQ/ACK/NAK controls or STX ... ETX PMS application records",
                corrective_action="Check serial-vs-TCP selection and operator-configured baud/data/parity/stop settings; PhoneSuite serial defaults are not yet evidence-qualified.",
            )
        )
        self.peer_granted = False

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
