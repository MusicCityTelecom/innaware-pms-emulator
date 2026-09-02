import asyncio

from innaware_pms_emulator.framing import ACK, NAK
from innaware_pms_emulator.transactions import CallAccountingTransactionSender, MitelTransactionSender


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


def test_mitel_retries_record_without_second_enq():
    sent = []
    replies = asyncio.Queue()
    for value in (ACK, NAK, ACK):
        replies.put_nowait(value)

    async def send_control(data, note): sent.append(("control", data, note))
    async def send_record(data, note): sent.append(("record", data, note))
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(MitelTransactionSender(timeout=.1, max_attempts=3).run(
        b"record", send_control=send_control, send_record=send_record, wait_response=wait_response
    ))
    assert result.success is True
    assert [kind for kind, _, _ in sent] == ["control", "record", "record"]
    assert sent[0][1] == b"\x05"


def test_mitel_retries_enq_before_record_phase():
    sent = []
    replies = asyncio.Queue()
    for value in (NAK, ACK, ACK):
        replies.put_nowait(value)

    async def send_control(data, note): sent.append(("control", data, note))
    async def send_record(data, note): sent.append(("record", data, note))
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(MitelTransactionSender(timeout=.1, max_attempts=3).run(
        b"record", send_control=send_control, send_record=send_record, wait_response=wait_response
    ))
    assert result.success is True
    assert [kind for kind, _, _ in sent] == ["control", "control", "record"]


def test_mitel_default_allows_initial_record_plus_three_message_only_retries():
    sent = []
    replies = asyncio.Queue()
    for value in (ACK, NAK, NAK, NAK, ACK):
        replies.put_nowait(value)

    async def send_control(data, note): sent.append(("control", data, note))
    async def send_record(data, note): sent.append(("record", data, note))
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    sender = MitelTransactionSender(timeout=.1)
    result = asyncio.run(sender.run(
        b"record", send_control=send_control, send_record=send_record, wait_response=wait_response
    ))

    assert result.success is True
    assert result.attempts == 4
    assert sender.max_record_retries == 3
    assert sender.max_record_attempts == 4
    assert [kind for kind, _, _ in sent] == ["control", "record", "record", "record", "record"]


def test_mitel_record_retry_budget_can_be_reduced_without_changing_enq_budget():
    sent = []
    replies = asyncio.Queue()
    for value in (NAK, ACK, NAK, ACK):
        replies.put_nowait(value)

    async def send_control(data, note): sent.append(("control", data, note))
    async def send_record(data, note): sent.append(("record", data, note))
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    sender = MitelTransactionSender(timeout=.1, max_attempts=3, max_record_retries=1)
    result = asyncio.run(sender.run(
        b"record", send_control=send_control, send_record=send_record, wait_response=wait_response
    ))

    assert result.success is True
    assert result.attempts == 2
    assert [kind for kind, _, _ in sent] == ["control", "control", "record", "record"]
