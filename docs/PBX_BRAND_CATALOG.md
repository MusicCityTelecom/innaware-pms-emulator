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

Do not silently substitute a Mitel adapter when the technician selects Hitachi. Until sanitized field captures or fixtures characterize the exact target, Hitachi should operate in capture/learn maturity with explicit diagnostics that its wire profile is not yet proven.

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

The existing field-observed OperaIP/Voiceware behavior remains useful and should remain selectable under PhoneSuite alongside Mitel-family profiles.

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
