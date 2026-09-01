from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

ACK = 0x06
ENQ = 0x05
ETX = 0x03
NAK = 0x15
STX = 0x02

_CONTROL_NAMES = {ENQ: "ENQ", ACK: "ACK", NAK: "NAK"}
_FIAS_CODES = {
    "LS", "LD", "LR", "LA", "LE", "GI", "GO", "GC", "RE",
    "WR", "WA", "WU", "WC", "PS", "PA", "DR", "DS", "DE",
}
_LEGACY_PREFIXES = {
    "AREYUTHERE", "RQINZ", "CHK", "NAM", "MOV", "WKP", "RST",
    "DND", "LNG", "LMT", "MSG", "MW", "SDD", "STE", "VIP", "STS",
}


@dataclass(slots=True)
class WireObservation:
    direction: str
    data: bytes
    timestamp: str | None = None
    peer: str | None = None
    note: str | None = None
    framing: str = "raw"
    payload: bytes = b""
    control: str | None = None
    record_family: str | None = None
    record_code: str | None = None
    bcc_valid: bool | None = None

    def evidence(self) -> str:
        text = self.payload.decode("latin-1", errors="replace")
        text = text.replace("\r", "\\r").replace("\n", "\\n")
        if len(text) > 120:
            text = text[:117] + "..."
        return (
            f"{self.direction.upper()} {self.framing}"
            + (f" {self.record_family}:{self.record_code}" if self.record_code else "")
            + (f" [{self.control}]" if self.control else "")
            + (f" peer={self.peer}" if self.peer else "")
            + (f" payload={text!r}" if self.payload else "")
        )


@dataclass(slots=True)
class DiagnosticFinding:
    id: str
    severity: str
    confidence: str
    title: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiagnosticReport:
    interface_name: str
    protocol: str
    configured_framing: str
    personality_id: str | None
    emulation_role: str | None
    observations: dict[str, Any]
    findings: list[DiagnosticFinding]

    def as_dict(self) -> dict[str, Any]:
        return {
            "interface_name": self.interface_name,
            "protocol": self.protocol,
            "configured_framing": self.configured_framing,
            "personality_id": self.personality_id,
            "emulation_role": self.emulation_role,
            "observations": self.observations,
            "findings": [item.as_dict() for item in self.findings],
        }


def _value(config: Any, name: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def _config_options(config: Any) -> dict[str, Any]:
    options = _value(config, "options", {})
    return options if isinstance(options, dict) else {}


def _capture_bytes(item: Any) -> bytes:
    if isinstance(item, dict):
        data = item.get("data")
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        raw_hex = item.get("hex")
        if isinstance(raw_hex, str) and raw_hex.strip():
            try:
                return bytes.fromhex(raw_hex)
            except ValueError:
                pass
        text = item.get("text")
        if isinstance(text, str):
            return text.encode("latin-1", errors="replace")
        return b""
    data = getattr(item, "data", b"")
    return bytes(data) if isinstance(data, (bytes, bytearray)) else b""


def _capture_value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _xor_bcc(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
    return value


def _classify_wire(data: bytes) -> tuple[str, bytes, str | None, bool | None]:
    if len(data) == 1 and data[0] in _CONTROL_NAMES:
        return "control", b"", _CONTROL_NAMES[data[0]], None
    if len(data) >= 3 and data[0] == STX and data[-2] == ETX:
        body = data[1:-1]
        return "stx_etx_bcc", data[1:-2], None, _xor_bcc(body) == data[-1]
    if len(data) >= 2 and data[0] == STX and data[-1] == ETX:
        return "stx_etx", data[1:-1], None, None
    if data.endswith(b"\r\n"):
        return "crlf", data[:-2], None, None
    if data.endswith(b"\r"):
        return "cr", data[:-1], None, None
    if data.endswith(b"\n"):
        return "lf", data[:-1], None, None
    return "raw", data, None, None


def _classify_record(payload: bytes) -> tuple[str | None, str | None]:
    stripped = payload.strip(b"\x00\r\n ")
    if not stripped:
        return None, None
    text = stripped.decode("latin-1", errors="replace")
    if len(text) >= 3 and text[2:3] == "|" and text[:2].upper() in _FIAS_CODES:
        return "fias", text[:2].upper()
    upper = text.upper()
    for prefix in sorted(_LEGACY_PREFIXES, key=len, reverse=True):
        if upper.startswith(prefix):
            return "legacy_hotel", prefix
    return None, None


def observe_capture(item: Any) -> WireObservation:
    data = _capture_bytes(item)
    framing, payload, control, bcc_valid = _classify_wire(data)
    family, code = _classify_record(payload)
    return WireObservation(
        direction=str(_capture_value(item, "direction", "unknown")).lower(),
        data=data,
        timestamp=_capture_value(item, "timestamp"),
        peer=_capture_value(item, "peer"),
        note=_capture_value(item, "note"),
        framing=framing,
        payload=payload,
        control=control,
        record_family=family,
        record_code=code,
        bcc_valid=bcc_valid,
    )


def _dominant_framing(observations: Iterable[WireObservation], direction: str) -> tuple[str | None, int]:
    values = [
        item.framing
        for item in observations
        if item.direction == direction and item.framing not in {"control", "raw"} and item.record_code
    ]
    if not values:
        return None, 0
    counter = Counter(values)
    framing, count = counter.most_common(1)[0]
    return framing, count


def _sample(observations: Iterable[WireObservation], predicate, limit: int = 3) -> list[str]:
    out: list[str] = []
    for item in observations:
        if predicate(item):
            out.append(item.evidence())
        if len(out) >= limit:
            break
    return out


def diagnose_interface(config: Any, captures: Iterable[Any]) -> DiagnosticReport:
    observations = [observe_capture(item) for item in captures]
    options = _config_options(config)
    protocol = str(_value(config, "protocol", "")).upper()
    configured_framing = str(options.get("framing", "raw")).lower()
    personality_id = _value(config, "personality_id")
    role_obj = _value(config, "emulation_role")
    emulation_role = getattr(role_obj, "value", role_obj)
    name = str(_value(config, "name", "interface"))

    findings: list[DiagnosticFinding] = []
    rx_framing, rx_framing_count = _dominant_framing(observations, "rx")
    tx_framing, _ = _dominant_framing(observations, "tx")
    rx_fias = [item for item in observations if item.direction == "rx" and item.record_family == "fias"]
    tx_fias = [item for item in observations if item.direction == "tx" and item.record_family == "fias"]
    rx_ls = [item for item in rx_fias if item.record_code == "LS"]
    tx_ls = [item for item in tx_fias if item.record_code == "LS"]

    if rx_fias and protocol not in {"FIAS", "HILTON_PEP_FIAS"}:
        findings.append(DiagnosticFinding(
            id="protocol-observation-mismatch",
            severity="error",
            confidence="high",
            title="Peer traffic looks like FIAS but this interface is configured for another protocol",
            summary=(
                f"Observed {len(rx_fias)} FIAS-style record(s) while the configured protocol is {protocol or 'unknown'}. "
                "Using a fixed-command Opera/Voiceware adapter for FIAS traffic will produce incompatible payloads."
            ),
            evidence=_sample(observations, lambda item: item.direction == "rx" and item.record_family == "fias"),
            suggested_actions=[
                "Switch the wire protocol to FIAS while preserving the framing actually observed from the peer.",
                "Choose a product personality separately from the wire protocol instead of using a product name as the protocol.",
            ],
            tags=["protocol", "fias", "configuration"],
        ))

    if rx_framing and configured_framing not in {"raw", rx_framing}:
        findings.append(DiagnosticFinding(
            id="configured-framing-mismatch",
            severity="error",
            confidence="high",
            title=f"Peer uses {rx_framing.upper()} framing but this interface is configured for {configured_framing.upper()}",
            summary=(
                f"The peer sent {rx_framing_count} recognized record(s) using {rx_framing}, "
                f"but InnAware is configured to transmit using {configured_framing}. "
                "This commonly prevents link negotiation even when the application record itself is correct."
            ),
            evidence=_sample(observations, lambda item: item.direction == "rx" and item.framing == rx_framing and item.record_code),
            suggested_actions=[
                f"Set interface framing to {rx_framing}.",
                "Reconnect the peer and verify that the same application record is returned with matching wire framing.",
            ],
            tags=["framing", "configuration", "handshake"],
        ))

    if rx_framing and tx_framing and rx_framing != tx_framing:
        findings.append(DiagnosticFinding(
            id="wire-framing-asymmetry",
            severity="error",
            confidence="high",
            title="InnAware replies are framed differently from the peer",
            summary=(
                f"Observed peer records primarily as {rx_framing} and InnAware records primarily as {tx_framing}. "
                "The application text can look correct in a capture while the remote system still rejects the reply."
            ),
            evidence=(
                _sample(observations, lambda item: item.direction == "rx" and item.framing == rx_framing and item.record_code, 2)
                + _sample(observations, lambda item: item.direction == "tx" and item.framing == tx_framing and item.record_code, 2)
            ),
            suggested_actions=[
                f"Make outbound framing match the observed peer framing ({rx_framing}).",
                "Retest link establishment before troubleshooting guest-event field semantics.",
            ],
            tags=["framing", "directionality", "handshake"],
        ))

    if rx_ls and tx_ls and rx_ls[0].framing != tx_ls[0].framing:
        findings.append(DiagnosticFinding(
            id="fias-link-start-framing-mismatch",
            severity="critical",
            confidence="high",
            title="FIAS Link Start reply uses the wrong framing",
            summary=(
                f"The peer sent LS using {rx_ls[0].framing}, but InnAware replied to LS using {tx_ls[0].framing}. "
                "The peer is likely to remain in Link Start or retry rather than enter an active FIAS session."
            ),
            evidence=[rx_ls[0].evidence(), tx_ls[0].evidence()],
            suggested_actions=[
                f"Send the LS reply using {rx_ls[0].framing}.",
                "Wait for LD/LR/LA or an Up/Active link state before sending guest check-in/check-out traffic.",
            ],
            tags=["fias", "link-start", "framing"],
        ))

    if len(rx_ls) >= 2 and not any(
        item.direction == "rx" and item.record_family == "fias" and item.record_code in {"LD", "LR", "LA"}
        for item in observations
    ):
        findings.append(DiagnosticFinding(
            id="fias-link-start-retrying",
            severity="warning",
            confidence="medium",
            title="Peer is retrying FIAS Link Start without progressing",
            summary=(
                f"Observed {len(rx_ls)} inbound LS records but no inbound LD/LR/LA progress. "
                "This usually indicates that the peer did not accept the link-start response or is waiting for different session behavior."
            ),
            evidence=[item.evidence() for item in rx_ls[:3]],
            suggested_actions=[
                "Verify framing, required ACK behavior, role/initiator settings, and whether the peer expects a specific LS/LD/LR sequence.",
                "Do not troubleshoot room-event payloads until link negotiation is active.",
            ],
            tags=["fias", "link-start", "retry"],
        ))

    rx_enq = sum(1 for item in observations if item.direction == "rx" and item.control == "ENQ")
    tx_ack = sum(1 for item in observations if item.direction == "tx" and item.control == "ACK")
    if rx_enq > tx_ack:
        findings.append(DiagnosticFinding(
            id="unanswered-enq",
            severity="error",
            confidence="medium",
            title="One or more peer ENQ controls were not answered with ACK",
            summary=f"Observed {rx_enq} inbound ENQ control(s) and {tx_ack} outbound ACK control(s).",
            evidence=_sample(observations, lambda item: item.direction == "rx" and item.control == "ENQ"),
            suggested_actions=[
                "Enable ACK-on-ENQ for personalities that require transactional ENQ/ACK behavior.",
                "Check whether ACK timing is within the peer's configured acknowledgement timer.",
            ],
            tags=["control", "enq", "ack", "transaction"],
        ))

    rx_nak = [item for item in observations if item.direction == "rx" and item.control == "NAK"]
    if rx_nak:
        findings.append(DiagnosticFinding(
            id="peer-nak",
            severity="warning",
            confidence="high",
            title="Peer explicitly rejected one or more transmissions with NAK",
            summary=f"Observed {len(rx_nak)} inbound NAK control(s). The remote endpoint rejected a transaction.",
            evidence=[item.evidence() for item in rx_nak[:3]],
            suggested_actions=[
                "Inspect the immediately preceding TX frame for framing, checksum, record type, field layout, and sequencing errors.",
                "Correlate the NAK with retry behavior before changing unrelated transport settings.",
            ],
            tags=["control", "nak", "rejection"],
        ))

    bad_bcc = [item for item in observations if item.bcc_valid is False]
    if bad_bcc:
        findings.append(DiagnosticFinding(
            id="invalid-bcc",
            severity="error",
            confidence="high",
            title="Invalid XOR BCC detected",
            summary=f"Observed {len(bad_bcc)} STX/ETX/BCC frame(s) whose checksum does not match the payload plus ETX.",
            evidence=[item.evidence() for item in bad_bcc[:3]],
            suggested_actions=[
                "Verify that BCC is calculated over the protocol-defined bytes, including ETX when required.",
                "Do not retransmit the same malformed frame unchanged.",
            ],
            tags=["framing", "checksum", "bcc"],
        ))

    framed_tx_with_crlf = [
        item for item in observations
        if item.direction == "tx"
        and item.framing in {"stx_etx", "stx_etx_bcc"}
        and item.payload.endswith(b"\r\n")
        and item.record_family == "fias"
    ]
    peer_framed_without_crlf = any(
        item.direction == "rx"
        and item.framing in {"stx_etx", "stx_etx_bcc"}
        and item.record_family == "fias"
        and not item.payload.endswith((b"\r", b"\n"))
        for item in observations
    )
    if framed_tx_with_crlf and peer_framed_without_crlf:
        findings.append(DiagnosticFinding(
            id="embedded-line-ending-in-stx-etx-fias",
            severity="warning",
            confidence="high",
            title="Outbound framed FIAS contains CR/LF that the peer does not use inside STX/ETX",
            summary=(
                "The peer's framed FIAS payloads end at ETX, but one or more InnAware payloads contain CR/LF before ETX. "
                "Some implementations tolerate this and others treat it as a different or malformed record."
            ),
            evidence=[item.evidence() for item in framed_tx_with_crlf[:3]],
            suggested_actions=[
                "For this personality, strip CR/LF from the FIAS payload before applying STX/ETX framing.",
                "Keep CRLF only for line-oriented FIAS profiles that actually use CRLF as the record delimiter.",
            ],
            tags=["fias", "framing", "terminator"],
        ))

    coalesced = [
        item for item in observations
        if item.data.count(bytes((STX,))) > 1
        or (len(item.data) > 1 and item.data[0] in _CONTROL_NAMES and STX in item.data[1:])
    ]
    if coalesced:
        findings.append(DiagnosticFinding(
            id="tcp-message-coalescing-observed",
            severity="info",
            confidence="high",
            title="Multiple protocol elements arrived in a single transport read",
            summary="TCP does not preserve application-message boundaries. The parser must handle control bytes and/or multiple frames coalesced in one read.",
            evidence=[item.evidence() for item in coalesced[:3]],
            suggested_actions=["Keep stream parsing incremental; never assume one socket read equals one protocol record."],
            tags=["tcp", "stream", "parser"],
        ))

    matrix_signature = [
        item for item in observations
        if item.direction == "rx"
        and item.framing == "stx_etx"
        and item.record_family == "fias"
        and item.record_code == "LS"
    ]
    if matrix_signature:
        already_matrix = str(personality_id or "").startswith("pbx-matrix")
        findings.append(DiagnosticFinding(
            id="matrix-sarvam-opera-signature",
            severity="info",
            confidence="high" if already_matrix else "medium",
            title=(
                "Traffic is consistent with the Matrix SARVAM MICROS Opera field profile"
                if already_matrix else
                "Traffic matches the field-observed Matrix SARVAM MICROS Opera signature"
            ),
            summary=(
                "Observed PBX-to-PMS FIAS Link Start inside STX/ETX framing. "
                "This matches the field-observed Matrix SARVAM UCS MICROS Opera behavior, but the signature is not globally unique."
            ),
            evidence=[matrix_signature[0].evidence()],
            suggested_actions=[
                "If the connected system is Matrix SARVAM UCS in MICROS Opera mode, use the dedicated Matrix personality instead of Generic CRLF FIAS."
            ],
            tags=["fingerprint", "matrix", "fias", "stx-etx"],
        ))

    frame_counts = Counter(item.framing for item in observations if item.framing != "control")
    record_counts = Counter(
        f"{item.record_family}:{item.record_code}" for item in observations if item.record_code
    )
    controls = Counter(item.control for item in observations if item.control)

    return DiagnosticReport(
        interface_name=name,
        protocol=protocol,
        configured_framing=configured_framing,
        personality_id=personality_id,
        emulation_role=str(emulation_role) if emulation_role is not None else None,
        observations={
            "capture_count": len(observations),
            "framing_counts": dict(frame_counts),
            "record_counts": dict(record_counts),
            "control_counts": dict(controls),
            "dominant_rx_framing": rx_framing,
            "dominant_tx_framing": tx_framing,
        },
        findings=findings,
    )
