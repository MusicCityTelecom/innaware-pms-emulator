from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from .framing import ACK, ENQ, NAK


@dataclass(frozen=True, slots=True)
class TransactionDiagnostic:
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
class TransactionResult:
    success: bool
    stage: str
    attempts: int
    detail: str
    diagnostic: TransactionDiagnostic | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "success": self.success,
            "stage": self.stage,
            "attempts": self.attempts,
            "detail": self.detail,
        }
        if self.diagnostic is not None:
            result["diagnostic"] = self.diagnostic.as_dict()
        return result


class CallAccountingTransactionSender:
    """Sender-side ENQ -> ACK -> record -> ACK transaction engine."""

    def __init__(self, *, timeout: float = 5.0, max_attempts: int = 3) -> None:
        self.timeout = max(0.1, float(timeout))
        self.max_attempts = max(1, int(max_attempts))

    async def run(
        self,
        record: bytes,
        *,
        send_control: Callable[[bytes, str], Awaitable[None]],
        send_record: Callable[[bytes, str], Awaitable[None]],
        wait_response: Callable[[float], Awaitable[int]],
    ) -> TransactionResult:
        for attempt in range(1, self.max_attempts + 1):
            await send_control(bytes((ENQ,)), f"transaction ENQ attempt {attempt}")
            response = await self._wait(wait_response)
            if response != ACK:
                if attempt == self.max_attempts:
                    reason = "NAK" if response == NAK else "timeout"
                    return TransactionResult(False, "enq", attempt, f"ENQ not acknowledged: {reason}")
                continue

            await send_record(record, f"transaction record attempt {attempt}")
            response = await self._wait(wait_response)
            if response == ACK:
                return TransactionResult(True, "complete", attempt, "record acknowledged")
            if attempt == self.max_attempts:
                reason = "NAK" if response == NAK else "timeout"
                return TransactionResult(False, "record", attempt, f"record not acknowledged: {reason}")

        return TransactionResult(False, "unknown", self.max_attempts, "transaction exhausted")

    async def _wait(self, wait_response: Callable[[float], Awaitable[int]]) -> int:
        try:
            return await wait_response(self.timeout)
        except (asyncio.TimeoutError, TimeoutError):
            return -1


class MitelTransactionSender:
    """Mitel-style half-duplex PMS transaction sender.

    Evidence-backed Mitel-compatible behavior is ENQ -> ACK followed by a
    STX/ETX-framed application record -> ACK/NAK. The public Mitel-compatible
    specification indexed in issue #4 allows three message-only retries after
    the initial frame, without sending another ENQ. ``max_attempts`` therefore
    continues to bound ENQ acquisition while ``max_record_retries`` controls
    the post-ENQ application retry budget.

    The 3-second default ACK timeout is evidence-backed for this compatibility
    profile; callers may override it for separately characterized variants.
    Failed transactions include structured diagnostics suitable for the
    emulator API/GUI. They report the observed handshake failure without
    guessing the peer model or silently changing the configured personality.
    """

    def __init__(
        self,
        *,
        timeout: float = 3.0,
        max_attempts: int = 3,
        max_record_retries: int = 3,
    ) -> None:
        self.timeout = max(0.1, float(timeout))
        self.max_attempts = max(1, int(max_attempts))
        self.max_record_retries = max(0, int(max_record_retries))
        self.max_record_attempts = 1 + self.max_record_retries

    async def run(
        self,
        record: bytes,
        *,
        send_control: Callable[[bytes, str], Awaitable[None]],
        send_record: Callable[[bytes, str], Awaitable[None]],
        wait_response: Callable[[float], Awaitable[int]],
    ) -> TransactionResult:
        enq_attempt = 0
        for enq_attempt in range(1, self.max_attempts + 1):
            await send_control(bytes((ENQ,)), f"Mitel ENQ attempt {enq_attempt}")
            response = await self._wait(wait_response)
            if response == ACK:
                break
            if enq_attempt == self.max_attempts:
                return self._enq_failure(enq_attempt, response)

        for record_attempt in range(1, self.max_record_attempts + 1):
            await send_record(record, f"Mitel record attempt {record_attempt}")
            response = await self._wait(wait_response)
            if response == ACK:
                return TransactionResult(True, "complete", record_attempt, "record acknowledged")
            if record_attempt == self.max_record_attempts:
                return self._record_failure(record_attempt, response)

        return TransactionResult(False, "unknown", self.max_record_attempts, "transaction exhausted")

    def _enq_failure(self, attempt: int, response: int) -> TransactionResult:
        if response == NAK:
            diagnostic = TransactionDiagnostic(
                code="mitel_transaction_enq_nak",
                severity="warning",
                confidence="medium",
                evidence_class="inference_not_yet_verified",
                observed=f"Peer returned standalone NAK to ENQ on acquisition attempt {attempt}",
                expected="Standalone ACK to ENQ before the STX/ETX application frame is sent",
                corrective_action=(
                    "Verify endpoint role and Mitel-compatible personality. Inspect for simultaneous half-duplex "
                    "contention or a peer that does not grant this transaction; do not auto-switch profiles."
                ),
            )
            return TransactionResult(False, "enq", attempt, "ENQ not acknowledged: NAK", diagnostic)

        diagnostic = TransactionDiagnostic(
            code="mitel_transaction_enq_timeout",
            severity="warning",
            confidence="high",
            evidence_class="vendor_public_specification",
            observed=(
                f"No standalone ACK/NAK was received within {self.timeout:g} second(s) after ENQ "
                f"on acquisition attempt {attempt}"
            ),
            expected=(
                "A Mitel-compatible peer to answer ENQ with a standalone ACK/NAK within the configured "
                "transaction timeout (3 seconds by default)"
            ),
            corrective_action=(
                "Verify the TCP session is connected, the message direction/profile is correct, and the peer "
                "uses the ENQ/ACK half-duplex handshake. Compare configured timing before increasing timeouts."
            ),
        )
        return TransactionResult(False, "enq", attempt, "ENQ not acknowledged: timeout", diagnostic)

    def _record_failure(self, attempt: int, response: int) -> TransactionResult:
        if response == NAK:
            diagnostic = TransactionDiagnostic(
                code="mitel_transaction_record_nak_exhausted",
                severity="warning",
                confidence="high",
                evidence_class="vendor_public_specification",
                observed=(
                    f"Peer returned NAK through {attempt} total STX/ETX application-frame transmission(s) "
                    "after the ENQ grant"
                ),
                expected=(
                    "ACK for a valid application frame, with no more than three message-only retries after "
                    "the initial frame for this characterized Mitel-compatible profile"
                ),
                corrective_action=(
                    "Stop replaying the same frame. Verify STX/ETX framing and the selected Mitel dialect/field "
                    "layout. CHK0/CHK1 and NAM1/NAM2/NAM3/NAM4 are normal protocol elements and should not be "
                    "treated as anomalies solely because of their status digit."
                ),
            )
            return TransactionResult(False, "record", attempt, "record not acknowledged: NAK", diagnostic)

        diagnostic = TransactionDiagnostic(
            code="mitel_transaction_record_timeout_exhausted",
            severity="warning",
            confidence="high",
            evidence_class="vendor_public_specification",
            observed=(
                f"No standalone ACK/NAK was received within {self.timeout:g} second(s) for the application "
                f"frame through {attempt} total transmission(s)"
            ),
            expected="A standalone ACK or NAK after each complete STX/ETX application frame",
            corrective_action=(
                "Verify TCP stream health, STX/ETX framing, configured direction/personality, and timeout/retry "
                "settings. Do not assume a timeout means the peer applied or rejected the message."
            ),
        )
        return TransactionResult(False, "record", attempt, "record not acknowledged: timeout", diagnostic)

    async def _wait(self, wait_response: Callable[[float], Awaitable[int]]) -> int:
        try:
            return await wait_response(self.timeout)
        except (asyncio.TimeoutError, TimeoutError):
            return -1
