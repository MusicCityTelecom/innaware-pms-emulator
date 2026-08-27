# Mitel 1 and Mitel 2 Serial PMS Profiles

InnAware PMS Emulator exposes the two related serial hotel PMS compatibility profiles as **Mitel 1** and **Mitel 2**.

These names are descriptive interoperability identifiers only. They do not imply sponsorship, certification, partnership, or endorsement by Mitel.

## Shared serial defaults

The built-in technician profiles use the field-tested legacy defaults below. They can be overridden when the system being tested requires different serial settings.

- Transport: Serial / COM port
- Baud: 1200
- Data bits: 8
- Parity: None
- Stop bits: 1
- Flow control: XON/XOFF
- Record framing: STX / ETX
- ACK timeout: 3 seconds
- Bounded retries: 3

The serial device is intentionally left unset in the profile. The technician must select the actual Windows COM port or Linux serial device before starting the interface.

## Transaction behavior

Outbound PMS events use the half-duplex transaction sequence:

```text
ENQ -> ACK -> STX + record + ETX -> ACK
```

If the initial ENQ is NAKed or times out, the ENQ phase is retried within the configured bound. Once ENQ has been acknowledged, a NAK or timeout on the record retries the framed record without unnecessarily starting a second ENQ handshake.

Inbound ENQ and framed records can be acknowledged automatically when `auto_ack` is enabled.

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
