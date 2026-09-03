# PBX Brand Catalog and Compatibility Families

## Technician-facing PBX brands

The v0.4 interface wizard should present these PBX brands as first-class systems:

- Mitel SX-200
- Mitel MiVoice
- PhoneSuite
- Matrix
- Hitachi
- InnAware UCP

`Mitel 1`, `Mitel 2`, `FIAS`, `OperaIP`, `Matrix Type 1`, and similar labels are protocol/profile choices or product modes. They are not PBX manufacturers and should not appear in the PBX-brand selector.

## Mitel-derived hospitality family

For InnAware interoperability modeling, treat the following PBX brands as members of the Mitel-derived hospitality compatibility family:

- Mitel SX-200
- Mitel MiVoice
- PhoneSuite
- Matrix
- InnAware UCP

This does **not** mean every model, firmware version, transport, framing choice, or PMS mode is byte-for-byte identical. The common lineage is used to organize compatibility profiles and diagnostics. Exact behavior remains profile- and fixture-qualified.

Examples of selectable profile variants underneath these brands include:

- Mitel 1
- Mitel 2
- FIAS where the PBX/product supports it
- PhoneSuite/Voiceware-era OperaIP
- Matrix MICROS Opera
- Matrix Type 1
- Matrix Type 2
- Matrix Extended Starlight

## Hitachi

Hitachi is modeled as a separate hospitality protocol family.

Legacy PhoneSuite/Voiceware documentation identifies `EPIT-HIT` as an Epitome Hitachi-emulation interface and `EPIT-HIT2` as a room/name-layout correction used when normal check-ins fail. That is sufficient to index a real Hitachi/Epitome integration lineage, but not to qualify byte-level wire behavior.

Hitachi therefore remains **evidence-indexed and wire-unqualified**. Do not silently substitute a Mitel adapter, serial transport, TCP transport, framing mode, control-byte handshake, checksum method, or serial settings when the technician selects Hitachi. Until a sanitized profile definition or field capture supplies those facts, the wizard should require explicit capture/characterization rather than fabricate a working default.

## Matrix

Matrix is one PBX brand with multiple modes, not multiple PBX brands.

A Matrix PBX may expose modes such as:

- MICROS Opera
- Type 1
- Type 2
- Extended Starlight

Field observation from a live SARVAM UCS in MICROS Opera mode showed FIAS `LS` inside STX/ETX framing over TCP. That observation belongs to the Matrix brand + MICROS Opera profile combination; it must not be generalized to every Matrix mode.

## PhoneSuite

`Voiceware` should be treated as a PhoneSuite compatibility/product-era profile where relevant to the observed interface behavior, not as a separate PBX manufacturer in the technician-facing brand list.

The existing field-observed OperaIP/Voiceware behavior remains useful and should remain selectable under PhoneSuite alongside Mitel-family application profiles.

PhoneSuite serial is a separate evidence boundary from generic Mitel serial. The current clean-room PhoneSuite characterization supports the dedicated ENQ/ACK plus STX/ETX `CHK0`, `CHK1`, and `NAM2` path, but it does **not** qualify PhoneSuite-specific baud rate, data bits, parity, stop bits, or flow control. For that reason the PhoneSuite personality intentionally has no automatically recommended serial profile. A technician may explicitly choose a Mitel-family profile when appropriate for a site, but its `1200/8/N/1/XON-XOFF` defaults remain Mitel-profile defaults rather than PhoneSuite evidence.

Series2/Voiceware TDMoE, PRI, Q.921/Q.931, D-channel, or `0x0E` station-programming behavior remains outside this PBX↔PMS serial/application evidence boundary.

## Interface wizard hierarchy

Recommended hierarchy:

```text
What are you testing?
  PBX | PMS

PBX Brand
  Mitel SX-200
  Mitel MiVoice
  PhoneSuite
  Matrix
  Hitachi
  InnAware UCP

PBX Mode / Interface Family
  values filtered by selected brand

Wire Protocol / Profile
  Mitel 1
  Mitel 2
  FIAS
  product-specific mode

Transport
  TCP Server
  TCP Client
  Serial

Advanced
  framing
  ENQ/ACK behavior
  checksum/BCC
  acknowledgement timer
  retries
  link initiator
```

The same hierarchy applies in reverse when InnAware is emulating the PBX and the real PMS is under test.

## Diagnostics

Diagnostics should use the brand plus profile plus observed wire evidence. For example:

```text
Peer brand:       Matrix
Peer mode:        MICROS Opera
Configured wire:  FIAS / CRLF
Observed wire:    FIAS / STX-ETX
```

The resulting diagnostic should identify the mismatch without incorrectly claiming that `Matrix` itself is a protocol.
