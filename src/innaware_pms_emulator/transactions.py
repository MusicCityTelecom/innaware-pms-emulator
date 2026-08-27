from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from .framing import ACK, ENQ, NAK


@dataclass(slots=True)
class TransactionResult:
    success: bool
    stage: str
    attempts: int
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "stage": self.stage,
            "attempts": self.attempts,
            "detail": self.detail,
        }


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

    The link is opened with ENQ/ACK. Once the initial ENQ is acknowledged, a
    STX/ETX-framed record may be retried after NAK/timeout without repeating the
    ENQ handshake. This keeps the retry behavior separate from call-accounting
    transaction assumptions.
    """

    def __init__(self, *, timeout: float = 3.0, max_attempts: int = 3) -> None:
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
        enq_attempt = 0
        for enq_attempt in range(1, self.max_attempts + 1):
            await send_control(bytes((ENQ,)), f"Mitel ENQ attempt {enq_attempt}")
            response = await self._wait(wait_response)
            if response == ACK:
                break
            if enq_attempt == self.max_attempts:
                reason = "NAK" if response == NAK else "timeout"
                return TransactionResult(False, "enq", enq_attempt, f"ENQ not acknowledged: {reason}")

        for record_attempt in range(1, self.max_attempts + 1):
            await send_record(record, f"Mitel record attempt {record_attempt}")
            response = await self._wait(wait_response)
            if response == ACK:
                return TransactionResult(True, "complete", record_attempt, "record acknowledged")
            if record_attempt == self.max_attempts:
                reason = "NAK" if response == NAK else "timeout"
                return TransactionResult(False, "record", record_attempt, f"record not acknowledged: {reason}")

        return TransactionResult(False, "unknown", self.max_attempts, "transaction exhausted")

    async def _wait(self, wait_response: Callable[[float], Awaitable[int]]) -> int:
        try:
            return await wait_response(self.timeout)
        except (asyncio.TimeoutError, TimeoutError):
            return -1
