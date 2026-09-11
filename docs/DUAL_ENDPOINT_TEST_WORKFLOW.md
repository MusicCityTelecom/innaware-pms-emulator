# Dual-Endpoint Test Workflow

## Goal

A single InnAware interface definition should let a technician test either side of a hotel integration without learning two different tools.

The operator must always be able to answer two questions:

1. **What is InnAware emulating?**
2. **What real/remote system is under test?**

The saved interface therefore tracks both `personality_id` (InnAware) and `peer_personality_id` (the remote endpoint).

## Test the PBX

Example:

```text
InnAware emulates: Oracle / MICROS Opera PMS
Peer under test:   Matrix SARVAM UCS PBX
Wire protocol:     FIAS
Transport:         TCP
Framing:           Matrix-observed STX/ETX
```

Technician controls should focus on PMS-originated actions:

- check in;
- check out;
- guest name update;
- room move;
- wake-up set/cancel;
- restriction / COS changes where supported;
- DND / language / message controls where supported;
- database synchronization where supported.

The receive side should decode and surface PBX-originated activity:

- room/housekeeping status;
- wake-up acknowledgement/result;
- minibar/posting data;
- call posting;
- message status;
- synchronization request;
- ACK/NAK/control behavior;
- link status and keepalive.

The property-state model should show whether the PBX actually reflected the intended change rather than treating a successful socket write as success.

## Test the PMS

The same integration can be flipped around:

```text
InnAware emulates: Matrix SARVAM UCS PBX
Peer under test:   Oracle / MICROS Opera PMS
Wire protocol:     FIAS
Transport:         TCP
Framing:           Matrix-observed STX/ETX
```

Now InnAware receives PMS-originated actions and behaves like the PBX:

- receive check in;
- receive check out;
- receive guest name update;
- receive room move;
- receive wake-up requests;
- receive restriction / DND / language controls;
- apply them to the emulated PBX/property state.

Technician controls should now expose PBX-originated actions:

- send room/housekeeping status;
- send minibar/posting event;
- send call posting;
- send wake-up result/status;
- send message status;
- initiate link start / keepalive where the PBX personality does so;
- request synchronization where supported;
- send ACK/NAK and controlled fault behavior.

## Flip Endpoint button

The UI should eventually provide a deliberate `Flip Test Direction` action.

For a compatible pair it should swap:

```text
personality_id      <-> peer_personality_id
emulation_role       PMS <-> PBX
transport defaults   server/client as recommended by the selected personalities
operator action set  PMS actions <-> PBX actions
```

It must **not** silently alter a running production interface. Flipping requires the interface to be stopped and should show the exact changes before confirmation.

## Interface creation wizard

Recommended operator flow:

```text
Create Integration Test

Domain:
  PMS / PBX Integration

Test:
  PBX
  PMS

System under test:
  Matrix SARVAM UCS
  Mitel
  Voiceware
  InnAware UCP
  Oracle / MICROS Opera
  Hilton / PEP
  Generic / Unknown

InnAware emulates:
  compatible opposite-side personalities only

Protocol / profile:
  compatible choices only

Transport:
  recommended default, overridable

Advanced:
  framing
  control bytes
  ACK behavior
  timers
  retries
  checksum
  link initiator
  strict/permissive/capture mode
```

Example selection:

```text
Test:                 PBX
System under test:    Matrix SARVAM UCS
PBX mode:             MICROS Opera
InnAware emulates:    Oracle / MICROS Opera PMS
Protocol:             FIAS
Recommended profile:  Matrix SARVAM Opera / STX-ETX
```

After flipping:

```text
Test:                 PMS
System under test:    Oracle / MICROS Opera
InnAware emulates:    Matrix SARVAM UCS PBX
Protocol:             FIAS
Recommended profile:  Matrix SARVAM Opera / STX-ETX
```

## Unified event console

The event console should be role-aware.

### When emulating PMS

Show outbound PMS operations prominently and inbound PBX events as live results.

### When emulating PBX

Show inbound PMS operations prominently and expose PBX-originated event buttons/forms.

Every event should display:

- semantic event type;
- room;
- decoded fields;
- raw bytes;
- framing;
- direction;
- timestamp;
- whether it was accepted/ACKed;
- resulting property-state change;
- diagnostic findings associated with the transaction.

## Smart diagnostics integration

Diagnostics must use both endpoint identities.

For example:

```text
Emulating:  Opera PMS
Peer:       Matrix SARVAM UCS PBX
Configured: FIAS / CRLF
Observed:   FIAS / STX-ETX
```

should produce a root-cause finding such as:

```text
CRITICAL
Matrix peer is sending STX/ETX-framed FIAS, but InnAware is replying with CRLF-framed FIAS.
The link-start text is valid but the wire framing differs, so the PBX is unlikely to accept the response.
Suggested fix: use the Matrix SARVAM MICROS Opera STX/ETX profile and repeat link negotiation.
```

When the direction is flipped, the same rule set should validate that InnAware's PBX personality sends the framing and sequencing expected by the real PMS.

## Success criteria

A test is not considered successful merely because TCP is connected.

InnAware should independently report:

1. Transport connected.
2. Framing valid.
3. Control/ACK transaction valid.
4. Link/session active.
5. Application record decoded.
6. Peer accepted/responded where applicable.
7. Expected property-state change occurred.
8. No unresolved high-confidence diagnostic findings remain.

This produces a true end-to-end answer to the field question: **is the PMS side broken, is the PBX side broken, or is the transport/protocol configuration between them wrong?**
