# Vendor Emulator Behavioral Results — 2026-09-01

These are original black-box observations made with synthetic data. No vendor executable, source, resource, manual, registration data, or customer data is included.

## Applications identified

- **Mitel PMSEMU / PMS Tester**: file/product version `2.01.0002`, company metadata `Mitel Corporation`. The UI exposes Hotel and Voice Mail modes; HIS and Hyatt Encore protocols; Comm Port and Telnet connections.
- **CMP Serial Simulator**: UI version `1.003`, file version `1.1.3944.17442`, company metadata `CMP`. The UI exposes ACK/NAK Receiver, PMS Sender, and HOBIS A Sender. Neither metadata nor UI identifies it as PhoneSuite, so PhoneSuite attribution remains **unknown**.

Both files were unsigned. The supplied archive copies matched the standalone executables byte-for-byte. The extracted `pms.exe.dir.zip` resource/code representation was not inspected because project policy forbids relying on decompiled implementation material.

## Mitel NAM results

The Mitel PMS Tester was observed over a COM1↔COM2 virtual null modem using its displayed defaults: 9600 baud, 8 data bits, no parity, 1 stop bit, XON/XOFF, DTR enabled, RTS disabled.

In both explicitly labeled **HIS** and **Hyatt Encore** modes, Add Name emitted this layout:

```text
STX NAM1 SP NAME-AREA(23, space padded) ROOM(3) ETX
```

For room `101` and `TEST,GUEST`:

```text
Text: NAM1 TEST,GUEST             101
Hex:  02 4e 41 4d 31 20 54 45 53 54 2c 47 55 45 53 54 20 20 20 20 20 20 20 20 20 20 20 20 20 31 30 31 03
```

The application record is 31 bytes before STX/ETX. The name UI accepted a maximum of 20 typed characters, leaving three padding spaces in the 23-character wire area. Tests with 1, 5, 10, 15, and 20 characters all retained the same 31-byte payload length. No room-first form was observed.

The session was:

```text
PMS Tester → ENQ
peer       → ACK
PMS Tester → STX record ETX
peer       → ACK
```

With ACK withheld, repeated ENQs were observed approximately every 5.1 seconds. No CR/LF or BCC followed the captured NAM frames.

The UI does not label either protocol as “Mitel 1” or “Mitel 2.” Therefore these observations must remain qualified as HIS/Hyatt Encore behavior; mapping either label to Mitel 1 or Mitel 2 would be inference.

## CMP Serial Simulator results

The CMP application defaulted to 1200 baud, 8 data bits, no parity, and 1 stop bit. It exposes no flow-control selector.

PMS Sender is a generic free-form sender. Its default payload was:

```text
CHK1  101 LASTNAME,FIRSTNAME
```

It emitted ENQ, waited for ACK, then emitted STX + the entered record + ETX and waited for a record ACK. The observed delay from receiving the ENQ ACK to starting the record was approximately 0.505 seconds. Default output had no CR/LF or BCC. Optional UI checkboxes were “Include Checksum” and “Hitachi Fmt.”

This demonstrates a useful transaction generator, but does **not** prove a PhoneSuite wire profile: the message is user-entered free-form text and there is no PhoneSuite/Mitel/Voiceware/FIAS protocol selector.

## Comparison

| Feature | Mitel 1 | Mitel 2 | PhoneSuite | Current InnAware | Corrective action |
|---|---|---|---|---|---|
| Evidence obtained | HIS/Hyatt behavior observed; exact mapping unknown | Unknown; no labeled mode exposed | Attribution of CMP tool unknown | Two clean-room adapters | Keep vendor/profile qualifiers separate from Mitel 1/2 labels |
| Startup handshake | ENQ→ACK observed | Unknown | Unknown | ENQ→ACK transaction sender | Retain handshake; obtain labeled captures |
| Initiator | PMS Tester initiated | Unknown | Unknown | PMS sender initiates | No change based on current evidence |
| Framing | STX/ETX; no CR/LF/BCC observed | Unknown | Unknown | STX/ETX recommended | Retain for captured profile |
| NAM format | Observed form is `NAM1 ` + name/padding + room | Unknown | Unknown | Mitel 1 reproduces observed payload when operation is `1` | Preserve Mitel 1 layout; review default operation semantics |
| Exact NAM length | 31-byte payload in observed HIS/Hyatt modes | Unknown | Unknown | Mitel 1 payload is 31 bytes for room 101 | Add profile-qualified test coverage |
| Name maximum | 20 typed characters; 23-character padded wire area | Owner states Mitel 2 differs by name length, exact width unknown | Unknown | Mitel 1 truncates at 20; Mitel 2 allows 40 after room | Remove the unsupported room-first claim; do not choose a Mitel 2 width without capture |
| Room position | Final three bytes in observed frames | Unknown | Unknown | Mitel 1 ends with a five-character room field; for `101` its leading spaces make the observed bytes identical | Model field semantics carefully while preserving exact wire compatibility |
| ACK requirements | ACK after ENQ and after record | Unknown | Unknown | Implemented | Retain |
| Timeout/retry | ENQ retry near 5.1 seconds observed | Unknown | Unknown | Default timeout 3 seconds, 3 attempts | Make timing profile-specific after more captures |
| Check-in/checkout | UI exposes operations; exact bytes not retained in this pass | Unknown | Unknown | Implemented | Capture before claiming equivalence |
| Wake-up/MWI/restriction/sync | UI exposes operations | Unknown | Unknown | Partially implemented | Capture each operation before changes |
| PBX-originated events | Manual ENQ/ACK/NAK/GRS/AYT/STE controls exposed | Unknown | Unknown | Partial | Capture exact records and state transitions |
| CMP behavior | N/A | N/A | Not proven PhoneSuite | OperaIP adapter exists separately | Do not associate CMP free-form behavior with PhoneSuite or Voiceware |

## Current InnAware discrepancy

`Mitel1Adapter` can reproduce the captured payload exactly when `name_operation` is explicitly `1`:

```text
NAM1 TEST,GUEST             101
```

`Mitel2Adapter` currently emits a provisional room-first variable-name form:

```text
NAM1  101 TEST,GUEST
```

No observed emulator output supports that room-first layout, and the owner reports the primary Mitel 1/Mitel 2 distinction is guest-name length. The corrective action is to remove the room-first assumption from `protocols/mitel.py` and model both variants as name-before-room with profile-specific fixed name widths. The exact Mitel 2 width must remain unresolved until a labeled Mitel 2 emulator or real-device capture establishes it.

## Still required

- A labeled Mitel 1 capture and a labeled Mitel 2 capture using identical synthetic names, especially 20–30 characters.
- Exact add/delete/replace name operation digits for each profile.
- Qualified PhoneSuite application or capture; the supplied CMP tool does not identify itself as PhoneSuite.
- Check-in, checkout, wake-up, cancel, restriction, DND, MWI, room status, synchronization, PBX-originated events, timeout exhaustion, NAK, and reconnect captures for each labeled profile.
- Whether the optional CMP checksum is XOR BCC and how “Hitachi Fmt” changes framing; those modes were not attributed to PhoneSuite and are not claimed here.
