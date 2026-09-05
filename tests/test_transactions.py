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


def test_mitel_enq_timeout_returns_structured_diagnostic():
    async def send_control(data, note): pass
    async def send_record(data, note): raise AssertionError("record must not be sent without ENQ grant")

    async def wait_response(timeout):
        raise asyncio.TimeoutError

    sender = MitelTransactionSender(timeout=.1, max_attempts=2)
    result = asyncio.run(sender.run(
        b"CHK1ROOM101",
        send_control=send_control,
        send_record=send_record,
        wait_response=wait_response,
    ))

    payload = result.as_dict()
    assert result.success is False
    assert result.stage == "enq"
    assert result.attempts == 2
    assert payload["diagnostic"]["code"] == "mitel_transaction_enq_timeout"
    assert payload["diagnostic"]["confidence"] == "high"
    assert payload["diagnostic"]["evidence_class"] == "vendor_public_specification"
    assert "ACK/NAK" in payload["diagnostic"]["expected"]
    assert "auto-switch" not in payload["diagnostic"]["corrective_action"]


def test_mitel_enq_nak_diagnostic_does_not_overclaim_collision_semantics():
    replies = asyncio.Queue()
    replies.put_nowait(NAK)

    async def send_control(data, note): pass
    async def send_record(data, note): raise AssertionError("record must not be sent after rejected ENQ")
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(MitelTransactionSender(timeout=.1, max_attempts=1).run(
        b"NAM2JOHNSMITH101",
        send_control=send_control,
        send_record=send_record,
        wait_response=wait_response,
    ))

    diagnostic = result.as_dict()["diagnostic"]
    assert diagnostic["code"] == "mitel_transaction_enq_nak"
    assert diagnostic["confidence"] == "medium"
    assert diagnostic["evidence_class"] == "inference_not_yet_verified"
    assert "simultaneous" in diagnostic["corrective_action"]
    assert "do not auto-switch" in diagnostic["corrective_action"]


def test_mitel_record_nak_exhaustion_explains_message_profile_without_flagging_normal_statuses():
    replies = asyncio.Queue()
    for value in (ACK, NAK, NAK):
        replies.put_nowait(value)

    async def send_control(data, note): pass
    async def send_record(data, note): pass
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(MitelTransactionSender(timeout=.1, max_record_retries=1).run(
        b"CHK1ROOM101",
        send_control=send_control,
        send_record=send_record,
        wait_response=wait_response,
    ))

    diagnostic = result.as_dict()["diagnostic"]
    assert result.success is False
    assert result.stage == "record"
    assert result.attempts == 2
    assert diagnostic["code"] == "mitel_transaction_record_nak_exhausted"
    assert diagnostic["evidence_class"] == "vendor_public_specification"
    assert "CHK0/CHK1" in diagnostic["corrective_action"]
    assert "NAM1/NAM2/NAM3/NAM4" in diagnostic["corrective_action"]


def test_mitel_success_does_not_emit_fault_diagnostic():
    replies = asyncio.Queue()
    replies.put_nowait(ACK)
    replies.put_nowait(ACK)

    async def send_control(data, note): pass
    async def send_record(data, note): pass
    async def wait_response(timeout): return await asyncio.wait_for(replies.get(), timeout)

    result = asyncio.run(MitelTransactionSender(timeout=.1).run(
        b"CHK1ROOM101",
        send_control=send_control,
        send_record=send_record,
        wait_response=wait_response,
    ))

    assert result.success is True
    assert "diagnostic" not in result.as_dict()
