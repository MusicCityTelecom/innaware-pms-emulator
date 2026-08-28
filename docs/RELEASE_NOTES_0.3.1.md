# InnAware PMS Emulator 0.3.1 - Development Release Notes

## Legacy Voiceware / OperaIP interoperability

The built-in profile catalog now keeps three FIAS transport behaviors distinct:

- Generic FIAS uses CRLF records.
- Hilton/PEP FIAS retains its working STX/ETX and combined-name behavior.
- Legacy OperaIP FIAS uses the field-observed ENQ/ACK handshake, STX/ETX framing,
  no checksum, and explicit PMS/PBX message-mask metadata.

TCP interface shutdown now closes and cancels active client sessions before the
runtime is marked stopped. This also fixes deletion of an online interface and
prevents a late disconnect callback from changing a stopped interface back to
listening. The operator console suppresses duplicate Stop/Delete submissions.

**Author:** Tommy Heggie

0.3.1 is the planned second field-beta release following `v0.3.0-beta`.

## Added

- Mitel 1 serial PMS profile.
- Mitel 2 serial PMS profile.
- Historical DEFAULT/DEFAULT2 compatibility aliases hidden from the user-facing protocol catalog.
- Sanitized synthetic protocol stubs with automated checks intended to prevent real person/company/customer names from being committed to stub data.
- Application Update Center.
- Automatic background update checks at startup.
- Manual **Check Now** update action.
- Beta/prerelease update channel control.
- Verified GitHub release download using SHA-256.
- Launch of a verified Windows `Setup.exe` update.
- Independent data-only protocol/stub packs.
- Protocol-pack SHA-256 verification and safe extraction.
- Downloaded protocol packs may add technician profiles for already-installed protocol engines.
- Downloaded protocol packs cannot replace built-in profiles or contain executable code.
- Protocol-pack builder: `python scripts/build-protocol-pack.py`.

## Update behavior

A 0.3.1 installation can automatically check GitHub Releases for later application versions. Installation remains explicit: the emulator downloads and verifies the new installer, then the user chooses **Launch Installer**.

Protocol/stub packs can be released separately from the executable. The emulator scans GitHub Releases for assets matching:

```text
InnAware-PMS-Protocol-Pack-<pack-version>.zip
```

This lets sanitized fixtures and data-only profile presets evolve without forcing an application rebuild. New executable protocol logic still requires a normal application release.

## Important upgrade note

`v0.3.0-beta` predates the Update Center, so existing 0.3.0 users must install 0.3.1 manually once. After 0.3.1 is installed, later releases can be discovered from inside the application.

## Planned release assets

```text
InnAware-PMS-Emulator-Setup.exe
InnAware-PMS-Emulator.exe
InnAware-PMS-Emulator-Windows-0.3.1.zip
InnAware-PMS-Emulator-Source-0.3.1.zip
SHA256SUMS.txt
InnAware-PMS-Protocol-Pack-2026.08.27.1.zip
```

The exact protocol-pack version may be incremented again if more sanitized stubs are added before the release is published.
