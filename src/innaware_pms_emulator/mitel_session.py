from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .framing import ACK, ENQ, NAK, FramingMode
from .replay import StreamItem, TcpStreamDecoder


_CAPTURE_VERIFIED_FAMILIES = {"AREYUTHERE", "CHK", "NAM"}
_LEGACY_VERIFIED_FAMILIES = {
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
_NORMAL_FAMILIES = _CAPTURE_VERIFIED_FAMILIES | _LEGACY_VERIFIED_FAMILIES
_OPCODE_RE = re.compile(r"^([A-Z]+)([0-9]*)")


@dataclass(frozen=True, slots=True)
class MitelSessionAction:
    payload: bytes
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {"hex": self.payload.hex(" "), "note": self.note}


@dataclass(frozen=True, slots=True)
class MitelSessionDiagnostic:
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


@dataclass(frozen=True, slots=True)
class MitelSessionRecord:
    opcode: str
    family: str
    payload: bytes
    evidence_class: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "opcode": self.opcode,
            "family": self.family,
            "text": self.payload.decode("latin-1", errors="replace"),
            "evidence_class": self.evidence_class,
        }


@dataclass(slots=True)
class MitelSessionFeed:
    actions: list[MitelSessionAction] = field(default_factory=list)
    response_controls: list[int] = field(default_factory=list)
    records: list[MitelSessionRecord] = field(default_factory=list)
    diagnostics: list[MitelSessionDiagnostic] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "actions": [item.as_dict() for item in self.actions],
            "response_controls": list(self.response_controls),
            "records": [item.as_dict() for item in self.records],
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }


class MitelTcpSessionStateMachine:
    """Evidence-qualified Mitel-compatible TCP half-duplex receive session.

    This component owns TCP stream/session interpretation only. It deliberately
    does not encode room/guest semantics and it does not replace the outbound
    ``MitelTransactionSender`` retry engine.

    Packet-capture evidence establishes ENQ/ACK/NAK controls, STX/ETX records,
    AREYUTHERE, CHK*, NAM*, arbitrary TCP fragmentation/coalescing, and TCP
    reconnects. Public Mitel-compatible specification evidence establishes the
    ENQ -> ACK -> STX/message/ETX -> ACK/NAK half-duplex exchange and permits
    three message-only retries after a record NAK.
    """

    def __init__(self, *, auto_ack: bool = True, strict_half_duplex: bool = True) -> None:
        self.auto_ack = bool(auto_ack)
        self.strict_half_duplex = bool(strict_half_duplex)
        self._decoder = TcpStreamDecoder(FramingMode.STX_ETX)
        self.connected = False
        self.peer_granted = False
        self.peer_retry_window = False
        self.peer_record_attempts = 0
        self.enq_received = 0
        self.frames_received = 0
        self.keepalives_received = 0
        self.connection_generation = 0
        self.last_opcode: str | None = None

    @property
    def pending(self) -> bytes:
        return self._decoder.pending

    def status(self) -> dict[str, Any]:
        if not self.connected:
            state = "disconnected"
        elif self.peer_granted:
            state = "peer_granted"
        elif self.peer_retry_window:
            state = "peer_retry_window"
        else:
            state = "idle"
        return {
            "transport": "tcp",
            "framing": "stx_etx",
            "connected": self.connected,
            "state": state,
            "peer_granted": self.peer_granted,
            "peer_retry_window": self.peer_retry_window,
            "peer_record_attempts": self.peer_record_attempts,
            "enq_received": self.enq_received,
            "frames_received": self.frames_received,
            "keepalives_received": self.keepalives_received,
            "connection_generation": self.connection_generation,
            "last_opcode": self.last_opcode,
            "pending_bytes": len(self.pending),
            "expected_ack_timeout_seconds": 3.0,
            "max_message_only_retries": 3,
        }

    def connect(self) -> None:
        # A TCP reconnect is a new protocol session. Never carry an ENQ grant,
        # message-retry window, or partial frame into the next connection.
        self._decoder = TcpStreamDecoder(FramingMode.STX_ETX)
        self.connected = True
        self.peer_granted = False
        self.peer_retry_window = False
        self.peer_record_attempts = 0
        self.last_opcode = None
        self.connection_generation += 1

    def disconnect(self) -> list[MitelSessionDiagnostic]:
        diagnostics: list[MitelSessionDiagnostic] = []
        for item in self._decoder.finish():
            diagnostics.append(
                MitelSessionDiagnostic(
                    code="mitel_tcp_disconnect_incomplete_frame",
                    severity="warning",
                    confidence="high",
                    evidence_class="packet_capture_verified",
                    observed=f"TCP session ended with {len(item.raw)} buffered byte(s) of an incomplete frame",
                    expected="A complete STX ... ETX application frame before disconnect",
                    corrective_action=(
                        "Check TCP resets/reconnect timing and whether the peer truncated an application frame."
                    ),
                )
            )
        self._decoder = TcpStreamDecoder(FramingMode.STX_ETX)
        self.connected = False
        self.peer_granted = False
        self.peer_retry_window = False
        self.peer_record_attempts = 0
        self.last_opcode = None
        return diagnostics

    def feed(self, chunk: bytes) -> MitelSessionFeed:
        if not self.connected:
            raise RuntimeError("Mitel TCP session must be connected before feeding bytes")
        result = MitelSessionFeed()
        for item in self._decoder.feed(chunk):
            if item.kind == "control":
                self._handle_control(item, result)
            elif item.kind == "frame":
                self._handle_frame(item, result)
            else:
                self._handle_stream_error(item, result)
        return result

    def _handle_control(self, item: StreamItem, result: MitelSessionFeed) -> None:
        if item.control == "ENQ":
            self.enq_received += 1
            if self.peer_granted or self.peer_retry_window:
                result.diagnostics.append(
                    MitelSessionDiagnostic(
                        code="mitel_tcp_repeated_enq",
                        severity="info",
                        confidence="medium",
                        evidence_class="inference_not_yet_verified",
                        observed="Peer sent ENQ while a previous receive transaction was still open",
                        expected="ENQ -> ACK followed by one STX ... ETX application transaction",
                        corrective_action=(
                            "Inspect for a lost ACK or peer retry; do not change personalities automatically."
                        ),
                    )
                )
            self.peer_granted = True
            self.peer_retry_window = False
            self.peer_record_attempts = 0
            if self.auto_ack:
                result.actions.append(MitelSessionAction(bytes((ACK,)), "Mitel ACK response to ENQ"))
            return

        if item.control == "ACK":
            result.response_controls.append(ACK)
            return
        if item.control == "NAK":
            result.response_controls.append(NAK)
            return

    def _handle_frame(self, item: StreamItem, result: MitelSessionFeed) -> None:
        self.frames_received += 1
        opcode, family = self._classify_opcode(item.payload)
        evidence_class = self._family_evidence(family)
        if opcode:
            self.last_opcode = opcode

        transaction_open = self.peer_granted or self.peer_retry_window
        if self.strict_half_duplex and not transaction_open:
            result.diagnostics.append(
                MitelSessionDiagnostic(
                    code="mitel_tcp_frame_without_enq",
                    severity="warning",
                    confidence="high",
                    evidence_class="vendor_public_specification",
                    observed=f"Received STX/ETX frame {opcode or '<unknown>'} without an open ENQ grant",
                    expected="ENQ -> ACK before STX + message + ETX",
                    corrective_action=(
                        "Verify half-duplex session initiation, message direction, and whether the peer is using "
                        "the Mitel-compatible profile."
                    ),
                )
            )
            if self.auto_ack:
                result.actions.append(
                    MitelSessionAction(bytes((NAK,)), "Mitel NAK frame received without ENQ grant")
                )
            return

        self.peer_granted = False
        self.peer_record_attempts += 1

        validation_error = self._opcode_validation_error(opcode, family)
        if validation_error is not None:
            result.diagnostics.append(validation_error)
            self._reject_frame(result, "Mitel NAK invalid application frame")
            return

        if not opcode or family not in _NORMAL_FAMILIES:
            result.diagnostics.append(
                MitelSessionDiagnostic(
                    code="mitel_tcp_uncharacterized_message",
                    severity="warning",
                    confidence="high",
                    evidence_class="legacy_source_profile_verified",
                    observed=f"Received uncharacterized Mitel application payload prefix {opcode or '<none>'}",
                    expected=(
                        "A characterized Mitel-family message such as CHK*, NAM*, WKP*, MW*, RST*, LOC*, "
                        "or AREYUTHERE"
                    ),
                    corrective_action=(
                        "Verify the selected PBX/PMS dialect and field layout; capture the frame before extending "
                        "the profile."
                    ),
                )
            )
            self._reject_frame(result, "Mitel NAK uncharacterized application frame")
            return

        self.peer_retry_window = False
        if family == "AREYUTHERE":
            self.keepalives_received += 1

        result.records.append(MitelSessionRecord(opcode, family, item.payload, evidence_class))
        if self.auto_ack:
            result.actions.append(MitelSessionAction(bytes((ACK,)), f"Mitel ACK {opcode} application frame"))

    def _reject_frame(self, result: MitelSessionFeed, note: str) -> None:
        # Public Mitel-compatible evidence permits the sender to retry the
        # message alone three times after the first rejected application frame.
        self.peer_retry_window = self.peer_record_attempts < 4
        if not self.peer_retry_window:
            result.diagnostics.append(
                MitelSessionDiagnostic(
                    code="mitel_tcp_record_retry_budget_exhausted",
                    severity="warning",
                    confidence="high",
                    evidence_class="vendor_public_specification",
                    observed="Peer application frame remained invalid through four total frame attempts",
                    expected="Initial frame plus no more than three message-only retries",
                    corrective_action=(
                        "Stop replaying the same frame and correct the message status/field layout before retrying."
                    ),
                )
            )
        if self.auto_ack:
            result.actions.append(MitelSessionAction(bytes((NAK,)), note))

    def _handle_stream_error(self, item: StreamItem, result: MitelSessionFeed) -> None:
        result.diagnostics.append(
            MitelSessionDiagnostic(
                code="mitel_tcp_framing_error",
                severity="warning",
                confidence="high",
                evidence_class="packet_capture_verified",
                observed=item.error or "Malformed bytes outside the configured STX/ETX framing",
                expected="One-byte ENQ/ACK/NAK controls or STX ... ETX application frames",
                corrective_action=(
                    "Check selected TCP-vs-serial profile, STX/ETX framing, stream corruption, and byte alignment."
                ),
            )
        )
        if self.peer_granted or self.peer_retry_window:
            self.peer_granted = False
            self.peer_record_attempts += 1
            self._reject_frame(result, "Mitel NAK malformed granted frame")

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
    def _family_evidence(family: str | None) -> str:
        if family in _CAPTURE_VERIFIED_FAMILIES:
            return "packet_capture_verified"
        if family in _LEGACY_VERIFIED_FAMILIES:
            return "legacy_source_profile_verified"
        return "uncharacterized"

    @staticmethod
    def _opcode_validation_error(
        opcode: str | None,
        family: str | None,
    ) -> MitelSessionDiagnostic | None:
        if family == "CHK" and opcode not in {"CHK0", "CHK1"}:
            return MitelSessionDiagnostic(
                code="mitel_tcp_invalid_chk_status",
                severity="warning",
                confidence="high",
                evidence_class="vendor_public_specification",
                observed=f"Received invalid Mitel check-in/out status {opcode or '<none>'}",
                expected="CHK1 for check-in or CHK0 for check-out",
                corrective_action="Correct the CHK status digit; do not treat CHK0/CHK1 as anomalies.",
            )
        if family == "NAM" and opcode not in {"NAM1", "NAM2", "NAM3", "NAM4"}:
            return MitelSessionDiagnostic(
                code="mitel_tcp_uncharacterized_nam_status",
                severity="warning",
                confidence="medium",
                evidence_class="legacy_simulator_characterized",
                observed=f"Received uncharacterized Mitel name status {opcode or '<none>'}",
                expected="A characterized NAM1, NAM2, NAM3, or NAM4 record",
                corrective_action=(
                    "Verify the selected Mitel dialect and name-operation status before changing the profile."
                ),
            )
        return None
