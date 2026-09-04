from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Iterable

from .diagnostics import observe_capture


_ALLOWED_TRANSPORTS = {"tcp", "serial", "unknown"}
_ALLOWED_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_TRANSACTION_BOUNDARY_CONTROLS = {"ACK", "NAK", "ENQ"}


@dataclass(frozen=True, slots=True)
class RejectedTransaction:
    nak_index: int
    preceding_tx_index: int | None
    confidence: str
    tx_sha256: str | None
    tx_length: int | None
    tx_framing: str | None
    tx_record_family: str | None
    tx_record_code: str | None
    tx_control: str | None
    corrective_actions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["corrective_actions"] = list(self.corrective_actions)
        return payload


def _is_transaction_boundary(item: Any) -> bool:
    if item.direction != "rx":
        return False
    if item.control in _TRANSACTION_BOUNDARY_CONTROLS:
        return True
    return item.record_code is not None


def _find_preceding_tx(observations: list[Any], nak_index: int) -> tuple[int, Any] | None:
    """Return the nearest attributable TX without crossing a new inbound transaction.

    A NAK is useful evidence that the peer rejected *something*, but attributing it to
    an older frame after another inbound control/record would manufacture transaction
    semantics. Fail closed instead.
    """

    for index in range(nak_index - 1, -1, -1):
        item = observations[index]
        if item.direction == "tx" and item.data:
            return index, item
        if _is_transaction_boundary(item):
            break
    return None


def _actions_for(item: Any | None, *, transport: str) -> tuple[str, ...]:
    if item is None:
        actions = [
            "Capture the outbound bytes immediately preceding the NAK before changing protocol settings.",
            "Do not infer a checksum, framing, field-layout, or personality fault from an uncorrelated NAK.",
        ]
    else:
        actions = [
            "Inspect the exact correlated TX frame first; compare its framing, record type, field layout, and any documented checksum behavior with the selected personality.",
            "Replay the same synthetic/redacted transaction after changing one variable at a time so the rejection remains attributable.",
            "Do not switch protocol personality or transport solely because a NAK was observed.",
        ]

    if transport == "serial":
        actions.append(
            "Record the actual adapter/device, baud, data bits, parity, stop bits, and flow control separately; a received NAK does not prove universal serial defaults."
        )
    elif transport == "tcp":
        actions.append(
            "Record the actual TCP endpoint roles and site port separately; a received NAK does not make a site port a protocol constant."
        )
    else:
        actions.append(
            "Resolve the transport from independent evidence before recommending transport-specific corrective action."
        )

    return tuple(actions)


def analyze_peer_naks(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
) -> dict[str, Any]:
    """Correlate inbound NAK controls with the nearest defensible outbound element.

    This diagnostic deliberately does not infer transport, select a personality, mutate
    the compatibility matrix, or authorize a compatibility claim. Raw payload bytes are
    represented only by SHA-256/length plus parser metadata so the result is safe to
    retain as reusable support evidence when the caller used synthetic/redacted input.
    """

    normalized_transport = str(transport).strip().lower()
    if normalized_transport not in _ALLOWED_TRANSPORTS:
        raise ValueError(f"transport must be one of: {', '.join(sorted(_ALLOWED_TRANSPORTS))}")

    normalized_evidence = str(evidence_class).strip().lower()
    if normalized_evidence not in _ALLOWED_EVIDENCE_CLASSES:
        raise ValueError(
            "evidence_class must be one of: "
            + ", ".join(sorted(_ALLOWED_EVIDENCE_CLASSES))
        )

    observations = [observe_capture(item) for item in captures]
    rejections: list[RejectedTransaction] = []

    for nak_index, item in enumerate(observations):
        if item.direction != "rx" or item.control != "NAK":
            continue

        correlated = _find_preceding_tx(observations, nak_index)
        if correlated is None:
            rejections.append(
                RejectedTransaction(
                    nak_index=nak_index,
                    preceding_tx_index=None,
                    confidence="low",
                    tx_sha256=None,
                    tx_length=None,
                    tx_framing=None,
                    tx_record_family=None,
                    tx_record_code=None,
                    tx_control=None,
                    corrective_actions=_actions_for(None, transport=normalized_transport),
                )
            )
            continue

        tx_index, tx = correlated
        rejections.append(
            RejectedTransaction(
                nak_index=nak_index,
                preceding_tx_index=tx_index,
                confidence="high" if tx_index == nak_index - 1 else "medium",
                tx_sha256=sha256(tx.data).hexdigest(),
                tx_length=len(tx.data),
                tx_framing=tx.framing,
                tx_record_family=tx.record_family,
                tx_record_code=tx.record_code,
                tx_control=tx.control,
                corrective_actions=_actions_for(tx, transport=normalized_transport),
            )
        )

    correlated_count = sum(1 for item in rejections if item.preceding_tx_index is not None)
    return {
        "schema_version": "1.0",
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "claim_policy": {
            "transport_inferred": False,
            "personality_switch_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "capture_count": len(observations),
        "peer_nak_count": len(rejections),
        "correlated_rejection_count": correlated_count,
        "uncorrelated_rejection_count": len(rejections) - correlated_count,
        "rejections": [item.as_dict() for item in rejections],
    }
