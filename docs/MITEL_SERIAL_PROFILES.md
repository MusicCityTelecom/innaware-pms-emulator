# Mitel 1 and Mitel 2 Serial PMS Profiles

InnAware PMS Emulator exposes the two related serial hotel PMS compatibility profiles as **Mitel 1** and **Mitel 2**.

These names are descriptive interoperability identifiers only. They do not imply sponsorship, certification, partnership, or endorsement by Mitel.

## Built-in serial preset versus protocol evidence

The built-in technician profiles start with the legacy emulator/profile preset below. These values are convenient defaults, **not a claim that every Mitel-family PBX uses the same physical serial settings**.

- Transport: Serial / COM port
- Baud preset: 1200
- Data bits preset: 8
- Parity preset: None
- Stop bits preset: 1
- Flow-control preset: XON/XOFF
- Record framing: STX / ETX

The serial device is intentionally left unset in the profile. The technician must select the actual Windows COM port or Linux serial device and verify the PBX/site serial parameters before starting the interface.

A separate clean-room serial characterization used 9600 8N1 XON/XOFF while exercising PMS-originated ENQ/ACK plus CHK transactions. That observation is useful evidence that the application personality can appear over serial, but it also demonstrates why one observed baud rate must not be generalized into universal transport truth. Site/profile serial settings remain independently configurable.

## Application transaction behavior

The Mitel-family application transaction model uses the half-duplex sequence:

```text
ENQ -> ACK -> STX + record + ETX -> ACK
```

The emulator's transaction preset uses a 3-second ACK timeout and three bounded record retries. Public Mitel application-protocol material documents the same three-second response window and permits three frame-only retries after ENQ has already been acknowledged, but that application specification does **not** itself identify a physical transport. Therefore timeout/retry semantics and serial electrical/port parameters remain separate evidence dimensions.

If the initial ENQ is NAKed or times out, the emulator's configured transaction policy may retry the ENQ phase within its configured bound. Once ENQ has been acknowledged, a NAK or timeout on the record can retry the framed record without unnecessarily starting a second ENQ handshake.

Inbound ENQ and framed records can be acknowledged automatically when `auto_ack` is enabled. The six-dimensional compatibility matrix keeps PBX→PMS and PMS→PBX serial evidence as separate rows rather than converting these implementation capabilities into an aggregate bidirectional claim.

## Mitel 1

Mitel 1 models the classic fixed-width name layout. The guest-name field is fixed before the five-character room field.

Synthetic examples:

```text
CHK1  101
CHK0  101
NAM2 GUESTLAST,GUESTFIRST    101
WKP0630  101
RST2  101
```

The fixed name width is important because the room is located after the name field.

## Mitel 2

Mitel 2 is the compatibility form for systems where a longer guest name would otherwise move the room field. The five-character room field is placed immediately after the command/status and the variable-length name follows it.

Synthetic examples:

```text
CHK1  101 GUESTLAST,GUESTFIRST
CHK0  101
NAM2  101 EXTENDEDGUESTLAST,EXTENDEDGUESTFIRST
WKP0630  101
RST2  101
```

This mirrors the compatibility behavior historically associated with the second default profile while exposing a clear technician-facing name.

## Compatibility aliases

Old saved emulator configurations that contain the internal identifiers `DEFAULT`, `DEFAULT2`, `MITEL_1`, or `MITEL_2` can still be restored. Those aliases are intentionally hidden from the public protocol catalog and operator UI. New configurations should use **Mitel 1** or **Mitel 2**.

## Fixture privacy and provenance

Repository fixtures under `stubs/` are synthetic. They must not contain real guest, employee, technician, customer, property, hotel, account, or company names. Neutral placeholders are used instead.

Historical database dumps, vendor stubs, customer exports, screenshots, and manuals are not copied into the distributable fixture directory. The implementation is maintained as an original compatibility layer based on required wire behavior and sanitized observations.
