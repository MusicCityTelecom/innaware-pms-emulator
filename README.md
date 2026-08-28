# InnAware PMS Emulator

**Author:** Tommy Heggie  
**Current development version:** 0.3.7
**Latest published field beta:** v0.3.0-beta  
**Primary user platform:** Windows 10/11 x64  
**Engineering/lab platform:** Linux / Debian

InnAware PMS Emulator is a Windows-first, cross-platform hotel PMS, PBX, and call-accounting integration emulator. It is intended for technicians and developers who need to test hospitality telephony integrations without requiring a live hotel PMS or billing system.

The Windows application is the primary field product. Linux uses the same protocol/property engine for development, regression testing, long-running TCP/serial laboratory work, and headless service operation.

> **Status:** the project is still field beta. Supported profiles are usable for testing, but protocol maturity is reported explicitly and not every vendor-specific variant is complete or certified.

## Download and run on Windows

### Preferred: installer

Download the current release asset:

```text
InnAware-PMS-Emulator-Setup.exe
```

Run the installer and launch **InnAware PMS Emulator** from the Start Menu.

The installer is per-user by default and installs under:

```text
%LOCALAPPDATA%\Programs\InnAware PMS Emulator
```

### Portable build

If you do not want to install it, download:

```text
InnAware-PMS-Emulator-Windows-<version>.zip
```

Extract the ZIP and run:

```text
InnAware-PMS-Emulator.exe
```

**Python is not required to run either packaged Windows distribution.**

Persistent data and logs are stored under:

```text
%LOCALAPPDATA%\InnAware\PMS Emulator
```

The local management API listens on `127.0.0.1:8080` by default. PMS and call-accounting test interfaces may bind to other local/LAN addresses as required by the test.

See [`docs/WINDOWS_QUICK_START.md`](docs/WINDOWS_QUICK_START.md) for the end-user walkthrough.

## Updates

The application includes an **Update Center**. Open it from the **Updates** button in the operator window or directly at:

```text
http://127.0.0.1:8080/updates
```

The Update Center can:

- check GitHub Releases automatically in the background at startup;
- check manually with **Check Now**;
- include or exclude beta/prerelease releases;
- download a newer `InnAware-PMS-Emulator-Setup.exe`;
- verify a release asset with SHA-256 before accepting it;
- launch the verified Windows installer;
- independently check for and install data-only protocol/stub packs;
- show the active protocol-pack version;
- manage anonymous usage telemetry;
- display the local random installation UUID for troubleshooting;
- provide direct support email and website links.

Automatic **installation** is deliberately disabled. The program may check automatically, but downloading/installing remains an explicit user action.

See [`docs/UPDATES.md`](docs/UPDATES.md) for the release/update contract.

## Anonymous usage telemetry

Beginning with 0.3.6, anonymous usage statistics are enabled by default and can be disabled from **Update Center > Preferences > Send anonymous usage statistics**.

Telemetry is best-effort, asynchronous, short-timeout, and never blocks application startup or normal offline operation. When disabled, the application makes no telemetry requests.

The production endpoint is:

```text
https://telemetry.innawareucp.com/pms-telemetry-ingest.php
```

On the first telemetry-enabled run, the emulator generates a random UUID-v4 and sends one `install` event plus one `run` event. The install event is retried on later launches until the endpoint confirms delivery; later launches reuse the UUID and send one `run` event. The Update Center shows the most recent delivery result.

The outbound JSON body contains only:

```text
event
version
platform
architecture
protocol_pack_version
install_id
```

The UUID is randomly generated and is not derived from a MAC address, hostname, username, Windows SID, machine GUID, hardware serial, IP address, or other machine identifier. The application does not put PMS data, hotel/property data, credentials, guest/room data, telephone numbers, call records, network configuration, license keys, or user filesystem paths into telemetry JSON.

The currently loaded protocol-pack version is read from the actual active pack metadata, falling back to the bundled canonical `protocol-pack.json`. If a protocol pack is updated independently, the next application run reports that new pack version.

The complete auditable privacy contract is in [`docs/PRIVACY_TELEMETRY.md`](docs/PRIVACY_TELEMETRY.md), and the implementation is intentionally visible in `src/innaware_pms_emulator/telemetry.py`.

## Support

- Email: **support@innawareucp.com**
- Website: **https://support.innawareucp.com**

Both are linked directly from the Update Center.

## Protocol / stub packs

Protocol data can be released independently of the executable as:

```text
InnAware-PMS-Protocol-Pack-<pack-version>.zip
```

A protocol pack is intentionally **data-only**. It may contain sanitized fixtures/stubs and technician profile definitions for protocol engines already compiled into the application.

It may **not** contain executable Python, DLLs, EXEs, PowerShell, batch files, or other executable code. New parsers, state machines, framing logic, or transports require a normal application release.

Downloaded packs are SHA-256 verified, path-checked, size-limited, and cannot replace built-in technician profiles.

Build the current repository protocol pack with:

```text
python scripts/build-protocol-pack.py
```

## Typical technician workflow

1. Launch **InnAware PMS Emulator**.
2. Create a property or select **Seed Demo Hotel**.
3. Configure a PMS interface.
4. Configure call accounting independently when needed.
5. Choose TCP Server, TCP Client, or an available Windows COM port.
6. Start the interface(s).
7. Generate check-ins, check-outs, room moves, wakeups, room-state changes, or call records.
8. Inspect the live RX/TX capture and protocol state.
9. Export captures or generate a support bundle when troubleshooting.
10. Use **Updates** to check application/protocol-pack status, telemetry preference, and support information.

## Built-in technician profiles

Current built-in profiles include:

- Generic FIAS PMS - TCP Server
- Hilton / PEP FIAS - TCP Server
- OperaIP / legacy Opera TCP compatibility profile
- **Mitel 1** - Serial
- **Mitel 2** - Serial
- TelElectronics InnForm XL - TCP Server
- HOBIS-A / Holidex - TCP Server
- Blind SMDR - TCP Server

Downloaded data-only protocol packs may add additional technician presets for protocol engines already present in the executable.

## Mitel serial PMS profiles

The user-facing profile names are simply:

```text
Mitel 1
Mitel 2
```

Historical/internal DEFAULT and DEFAULT2 identifiers are retained only as hidden restore aliases for old saved emulator configuration.

**Mitel 1** uses the classic fixed-width guest-name layout where the room field follows the name field.

**Mitel 2** uses the compatibility layout where the five-character room field appears before the variable-length guest name, avoiding long guest names shifting the room position.

Default serial preset:

```text
1200 baud
8 data bits
No parity
1 stop bit
XON/XOFF
STX/ETX framing
ENQ -> ACK -> record -> ACK transaction flow
```

See [`docs/MITEL_SERIAL_PROFILES.md`](docs/MITEL_SERIAL_PROFILES.md).

## Current protocol matrix

| Protocol | Purpose | Maturity | Notes |
| --- | --- | --- | --- |
| FIAS | PMS | stateful | Link negotiation, posting answer, guest events, and property-backed database resync |
| HILTON_PEP_FIAS | PMS | stateful | Combined Hilton/PEP guest-name behavior and FIAS-family state handling |
| OperaIP / legacy Opera | PMS | compatibility | Voiceware-era TCP handshake/control behavior and legacy operational masks |
| Mitel 1 | PMS | fixture-backed | Classic serial hotel PMS layout with fixed-width name/room placement |
| Mitel 2 | PMS | fixture-backed | Serial compatibility layout with room before variable guest name |
| ONQ | PMS | encoder | Message-generation foundation; additional session behavior remains under development |
| CHOICE_ADVANTAGE | PMS | encoder | Legacy message-generation foundation |
| OPERA_LEGACY | PMS | encoder | Legacy Opera-style foundation; FIAS is used for FIAS-family testing |
| INNFORM_XL | Call accounting | transactional | Field-tested InnForm XL/TEL-family record plus ENQ/ACK transaction mode |
| HOBIS | Call accounting | transactional | Verified HOBIS-A layout with ENQ/ACK and STX/ETX/XOR-BCC transaction |
| HOBIS_A | Call accounting | transactional | Explicit compatibility name for the verified HOBIS-A layout |
| HOLIDEX | Call accounting | transactional | HOBIS/Holidex compatibility alias using the verified transaction family |
| BLIND_SMDR | Call accounting | encoder | Line-oriented blind-send SMDR output |
| HOTELKEY | PMS | planned | HTTP/JSON transport/profile work remains pending |
| HOBIC / HOBIS2 / HOBIS_B / MICROS_CA / ROOMKEY / PROFITWATCH / RAW_SMDR | Call accounting | planned | Requirements identified; exact fixtures still required before implementation claims |

Compatibility requirements and historical edge cases are tracked in [`docs/PROTOCOL_COMPATIBILITY_ROADMAP.md`](docs/PROTOCOL_COMPATIBILITY_ROADMAP.md).

## Sanitized stub policy

Repository stubs are synthetic fixtures only. They must not contain real guest/customer names, hotel/company names, credentials, customer-specific data, concrete customer dates, addresses, phone numbers, or deployment identifiers.

The test suite scans the stub set so accidental identifying data is caught before release.

## Property-state model

The emulator maintains persistent hotel state instead of treating protocol messages as isolated text records. Each property can contain rooms, housekeeping state, guests/stays, room moves, wakeups, calling restrictions, DND, MWI, language, voicemail lifecycle, call-accounting history, and property audit events.

FIAS database resynchronization can therefore be generated from the actual active occupancy database rather than hard-coded test messages.

## Supported transports

- TCP server
- TCP client with reconnect
- Serial / Windows COM port
- HTTP server framework for future HTTP/JSON PMS integrations

Serial configuration supports baud rate, 5/6/7/8 data bits, N/E/O/M/S parity, 1/1.5/2 stop bits, and none / RTS-CTS / XON-XOFF flow control.

## Framing and transactions

Supported framing includes raw, CR, LF, CRLF, STX/ETX, and STX/ETX with XOR BCC.

Transactional flows include:

```text
ENQ -> ACK -> record -> ACK
```

with timeout handling, NAK handling, and bounded retries.

## Capture export and support bundle

Per-interface captures can be exported as CSV, JSON, or text:

```text
/api/v1/interfaces/<interface-name>/captures/export?format=csv
/api/v1/interfaces/<interface-name>/captures/export?format=json
/api/v1/interfaces/<interface-name>/captures/export?format=txt
```

A privacy-aware support bundle is available while the application is running:

```text
http://127.0.0.1:8080/api/v1/support-bundle
```

It includes runtime information, interface configuration/status, property summaries, serial-port inventory, captures, transaction history, and available logs. Full guest/property detail is excluded by default.

## Build the Windows field edition

End users do **not** need Python. These instructions are only for developers building distributable artifacts.

### Build prerequisites

Install Git, Python 3.13, and Inno Setup 6 if you want `Setup.exe`.

Using Winget:

```powershell
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
winget install --id JRSoftware.InnoSetup -e --accept-source-agreements --accept-package-agreements
```

Then build from PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force

cd C:\path\to\innaware-pms-emulator

git fetch origin main
git pull --ff-only origin main

powershell -ExecutionPolicy Bypass `
  -File .\scripts\build-windows.ps1 `
  -Python py
```

The builder runs the full Python test suite, creates the one-file/windowed EXE, embeds the canonical protocol-pack manifest, launches the actual frozen EXE for a runtime smoke test with telemetry disabled, builds the installer when Inno Setup is available, copies the privacy document, and generates release ZIP/checksum artifacts.

Expected 0.3.7 application outputs:

```text
dist-windows\InnAware-PMS-Emulator.exe
dist-windows\InnAware-PMS-Emulator-Setup.exe
dist-windows\README-WINDOWS.txt
dist-windows\PRIVACY-TELEMETRY.md
dist-windows\SHA256SUMS.txt

InnAware-PMS-Emulator-Windows-0.3.7.zip
InnAware-PMS-Emulator-Source-0.3.7.zip
SHA256SUMS-WINDOWS-0.3.7.txt
```

Build the independent protocol pack with:

```powershell
py .\scripts\build-protocol-pack.py
```

which produces:

```text
InnAware-PMS-Protocol-Pack-<pack-version>.zip
InnAware-PMS-Protocol-Pack-<pack-version>.sha256.txt
```

## Windows application diagnostics

Runtime diagnostics are written to:

```text
%LOCALAPPDATA%\InnAware\PMS Emulator\logs\emulator.log
```

The Windows launcher is built without a console window. Uvicorn logging is file-backed and does not depend on `stdout`/`stderr` being attached.

## Linux / Debian engineering lab

Linux is supported for headless interoperability testing and automated regression. It is not the primary technician desktop experience.

Development start:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . pytest
pytest -q
uvicorn innaware_pms_emulator.main:app --app-dir src --host 127.0.0.1 --port 8080
```

The repository also contains `packaging/systemd/innaware-pms-emulator.service`, `scripts/install-systemd.sh`, and `scripts/verify-server3.sh`.

## Architecture

```text
             Shared InnAware PMS Emulator Core
                         |
       +-----------------+-----------------+
       |                 |                 |
 Property State      Protocols         Sessions
       |          framing/state        TCP/Serial
       +-----------------+-----------------+
                         |
                       REST API
                         |
             +-----------+-----------+
             |                       |
      Windows Desktop            Linux Lab
      primary product          headless testing
```

The protocol engine is deliberately shared. A future WinUI/WinForms shell may improve Windows usability, but it should remain a client/launcher for the shared engine rather than duplicating protocol behavior.

## Verification status

`v0.3.0-beta` passed the Linux/server laboratory regression gate and the actual Windows frozen-EXE/installer build gate.

The 0.3.7 development line corrects telemetry delivery by separating public ingestion from the protected dashboard, retrying unacknowledged install events, migrating 0.3.6 telemetry state, and surfacing delivery diagnostics. It remains a field-beta prerelease until the normal Windows build/install gates are completed for this version.

## Safety

This is a test/emulation instrument. It can generate real PMS and call-accounting traffic. Do not point it at a production hotel PMS, billing endpoint, PBX, or customer system unless test traffic is explicitly intended and authorized.

The management UI/API should normally remain bound to localhost. Expose it to a LAN only when that is intentionally required for the laboratory setup.

## Author

**Tommy Heggie**

InnAware PMS Emulator was created and is maintained by Tommy Heggie.

## Open-source / compatibility boundary

Third-party product and protocol names are descriptive compatibility references and do not imply sponsorship, certification, partnership, or endorsement.

Do not add copied vendor manuals, proprietary source, third-party logos, customer data, credentials, or other material without a clear right to redistribute it.

The public-release checklist is documented in [`docs/OPEN_SOURCE_READINESS.md`](docs/OPEN_SOURCE_READINESS.md).
