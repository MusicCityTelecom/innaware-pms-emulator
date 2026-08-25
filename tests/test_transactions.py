import asyncio

from innaware_pms_emulator.framing import ACK, NAK
from innaware_pms_emulator.transactions import CallAccountingTransactionSender


def test_transaction_success():
    sent = []
    replies = asyncio.Queue()
    replies.put_nowait(ACK)
    replies.put_nowait(ACK)

    async def send_control(data, note): sent.append((data, note))
    async def send_record(data, note): sent.append((data, note))
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(CallAccountingTransactionSender(timeout=.1, max_attempts=3).run(
        b"record", send_control=send_control, send_record=send_record, wait_response=wait_response
    ))
    assert result.success is True
    assert result.stage == "complete"
    assert result.attempts == 1
    assert sent[0][0] == b"\x05"
    assert sent[1][0] == b"record"


def test_transaction_retries_after_enq_nak():
    sent = []
    replies = asyncio.Queue()
    for value in (NAK, ACK, ACK): replies.put_nowait(value)

    async def send_control(data, note): sent.append((data, note))
    async def send_record(data, note): sent.append((data, note))
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(CallAccountingTransactionSender(timeout=.1, max_attempts=3).run(
        b"record", send_control=send_control, send_record=send_record, wait_response=wait_response
    ))
    assert result.success is True
    assert result.attempts == 2


def test_transaction_fails_after_record_naks():
    replies = asyncio.Queue()
    for value in (ACK, NAK, ACK, NAK): replies.put_nowait(value)

    async def send_control(data, note): pass
    async def send_record(data, note): pass
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(CallAccountingTransactionSender(timeout=.1, max_attempts=2).run(
        b"record", send_control=send_control, send_record=send_record, wait_response=wait_response
    ))
    assert result.success is False
    assert result.stage == "record"
    assert result.attempts == 2
