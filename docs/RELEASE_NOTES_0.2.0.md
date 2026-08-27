# InnAware PMS Emulator 0.2.0 - development milestone

This is an alpha development milestone, not yet a public production release.

## Major changes

### Hospitality property state

The emulator now has persistent, multi-property hotel state rather than treating all PMS traffic as isolated wire messages. Properties contain rooms, guests, stays, wakeups, call-accounting records and a bounded audit event stream.

Room state includes room type, building/floor, housekeeping and out-of-order state, calling restriction, DND, MWI count, language, voicemail lifecycle, call-billing flag and rate-plan label.

Check-in, checkout and room move operations update the property state first. PMS wire transmission is an optional side effect, allowing the emulator to continue modeling the hotel even when a simulated PBX link is offline.

Wakeups follow an active stay during a room move and are cancelled at checkout.

### Stateful FIAS

A FIAS interface can be bound to a property. A received database-resync request now returns:

```text
DR
DS
GI ... active room 1
GI ... active room 2
...
DE
```

from the actual property occupancy database.

Hilton/PEP FIAS guest-name generation was corrected to use a combined guest-name field and omit a separate first-name `GF` field.

FIAS room move generation now emits a `GC` record with old/new room identity.

### Call accounting

The sender-side transactional engine remains available for InnForm XL/HOBIS-style flows:

```text
ENQ -> ACK -> record -> ACK
```

with timeout/NAK retries. Transactional TCP-server sending now requires exactly one connected client, preventing an ACK from one peer from satisfying a transaction sent to another.

HOBIS metadata recommends STX/ETX plus XOR BCC for the record transaction.

### Operator console

The cross-platform browser console now includes:

- property create/select and deterministic demo-property seeding;
- visual room board;
- bulk room creation;
- check-in, checkout, room move and wake-up controls;
- housekeeping and room-control state;
- protocol maturity and recommended framing presets;
- TCP server/client and serial interface creation;
- serial port enumeration and full line settings;
- property-bound interfaces;
- call generator and billing history;
- property event audit;
- live RX/TX capture.

### Windows field build

The PowerShell builder was corrected so both the Windows Python Launcher (`py`) and `python.exe` work. It runs pytest before packaging and creates:

```text
dist-windows/InnAware-PMS-Emulator.exe
dist-windows/README-WINDOWS.txt
dist-windows/SHA256SUMS.txt
InnAware-PMS-Emulator-Windows.zip
InnAware-PMS-Emulator-Source.zip
```

The Windows launcher continues to bind the management UI to localhost by default.

### Debian/service deployment

A systemd unit and installation helper were added. The service uses a dedicated account, persistent `/var/lib/innaware-pms-emulator` state, `dialout` access for serial adapters, restart-on-failure, and systemd hardening.

## Verification added

Regression coverage now includes property isolation, occupancy lifecycle, wakeup movement/cancellation, persistence, property-backed FIAS resync, Hilton combined-name behavior, FIAS room moves, and serial-configuration validation.

The repository also contains Linux/Windows CI workflows. At the time this milestone was prepared, GitHub was terminating the private-repository jobs before assigning a runner (`runner_id=0`, no executed steps), so a green hosted CI claim must not be made until GitHub actually provisions those jobs. Bare-metal/server3 and local Windows verification remain the immediate release gates.

## Public release boundary

0.2.0 should remain private/alpha until the open-source provenance checklist in `docs/OPEN_SOURCE_READINESS.md` is completed and a deliberate project license is chosen.
