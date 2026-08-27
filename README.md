# InnAware PMS Emulator

**Author:** Tommy Heggie  
**Current version:** 0.3.0 field beta  
**Primary user platform:** Windows 10/11 x64  
**Engineering/lab platform:** Linux / Debian

InnAware PMS Emulator is a Windows-first, cross-platform hotel PMS, PBX, and call-accounting integration emulator. It is intended for technicians and developers who need to test hospitality telephony integrations without requiring a live hotel PMS or billing system.

The Windows application is the primary field product. Linux uses the same protocol/property engine for development, regression testing, long-running TCP/serial laboratory work, and headless service operation.

> **Status:** 0.3.0 is a field-beta milestone. Supported profiles are usable for testing, but protocol maturity is reported explicitly and not every vendor-specific variant is complete or certified.

## Download and run on Windows

### Preferred: installer

When a release includes the installer, download:

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

The application starts its local engine automatically and opens the operator console in a native Windows application window.

Persistent data and logs are stored under:

```text
%LOCALAPPDATA%\InnAware\PMS Emulator
```

The local management API listens on:

```text
127.0.0.1:8080
```

by default. PMS and call-accounting test interfaces may bind to other local/LAN addresses as required by the test.

See [`docs/WINDOWS_QUICK_START.md`](docs/WINDOWS_QUICK_START.md) for the end-user walkthrough.

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

## Built-in technician profiles in 0.3.0

- Generic FIAS PMS - TCP Server
- Hilton / PEP FIAS - TCP Server
- TelElectronics InnForm XL - TCP Server
- HOBIS-A / Holidex - TCP Server
- Blind SMDR - TCP Server

Other profiles may appear as **encoder** or **planned**. The emulator intentionally reports maturity rather than presenting every known protocol name as production-complete.

## Current protocol matrix

| Protocol | Purpose | Maturity | Notes |
| --- | --- | --- | --- |
| FIAS | PMS | stateful | Link negotiation, posting answer, guest events, and property-backed database resync |
| HILTON_PEP_FIAS | PMS | stateful | Combined Hilton/PEP guest-name behavior and FIAS-family state handling |
| ONQ | PMS | encoder | Message-generation foundation; additional session behavior remains under development |
| CHOICE_ADVANTAGE | PMS | encoder | Legacy message-generation foundation |
| OPERA_LEGACY | PMS | encoder | Legacy Opera-style foundation; FIAS is used for FIAS-family testing |
| INNFORM_XL | Call accounting | transactional | Field-tested InnForm XL/TEL-family record plus ENQ/ACK transaction mode |
| HOBIS | Call accounting | transactional | Verified 54-character HOBIS-A layout with ENQ/ACK and STX/ETX/XOR-BCC record transaction |
| HOBIS_A | Call accounting | transactional | Explicit compatibility name for the verified HOBIS-A layout |
| HOLIDEX | Call accounting | transactional | HOBIS/Holidex compatibility alias using the verified HOBIS-A transaction family |
| BLIND_SMDR | Call accounting | encoder | Line-oriented blind-send SMDR output |
| HOTELKEY | PMS | planned | HTTP/JSON transport/profile work remains pending |
| HOBIC / HOBIS2 / HOBIS_B / MICROS_CA / ROOMKEY / PROFITWATCH / RAW_SMDR | Call accounting | planned | Requirements identified; exact fixtures still required before implementation claims |

Compatibility requirements and historical edge cases are tracked in [`docs/PROTOCOL_COMPATIBILITY_ROADMAP.md`](docs/PROTOCOL_COMPATIBILITY_ROADMAP.md).

## Property-state model

The emulator maintains persistent hotel state instead of treating protocol messages as isolated text records.

Each property can contain:

- rooms and room types;
- building/floor information;
- housekeeping and out-of-order state;
- guests and stays;
- check-in/check-out state;
- room moves;
- wakeups;
- calling restrictions;
- DND;
- MWI count;
- language;
- voicemail lifecycle state;
- call-accounting history;
- property audit events.

FIAS database resynchronization can therefore be generated from the actual active occupancy database rather than hard-coded test messages.

## Supported transports

- TCP server
- TCP client with reconnect
- Serial / Windows COM port
- HTTP server framework for future HTTP/JSON PMS integrations

Serial configuration supports:

- baud rate;
- 5/6/7/8 data bits;
- N/E/O/M/S parity;
- 1/1.5/2 stop bits;
- none / RTS-CTS / XON-XOFF flow control.

## Framing and call-accounting transactions

Supported framing includes:

- raw;
- CR;
- LF;
- CRLF;
- STX/ETX;
- STX/ETX with XOR BCC.

The transactional call-accounting sender supports flows such as:

```text
ENQ -> ACK -> record -> ACK
```

with timeout handling, NAK handling, and bounded retries.

Transactional TCP-server sending requires exactly one connected client so an ACK from one peer cannot satisfy a transaction intended for another peer.

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

End users do **not** need Python. These instructions are only for developers building the distributable artifacts.

### Build prerequisites

Install:

- Git
- Python 3.13
- Inno Setup 6 if you want `Setup.exe`

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

The builder performs the release gate automatically:

1. installs/updates build dependencies;
2. runs the complete pytest suite;
3. builds the one-file, windowed EXE with PyInstaller;
4. launches the **actual frozen EXE** on an isolated port/data directory;
5. verifies health, application metadata, technician profiles, demo-property creation, and support-bundle generation;
6. terminates the frozen process tree;
7. creates checksums and the portable ZIP;
8. creates `Setup.exe` when Inno Setup 6 is available;
9. creates a clean source ZIP with `git archive`.

Expected outputs:

```text
dist-windows\InnAware-PMS-Emulator.exe
dist-windows\InnAware-PMS-Emulator-Setup.exe      # when Inno Setup is available
dist-windows\README-WINDOWS.txt
dist-windows\SHA256SUMS.txt

InnAware-PMS-Emulator-Windows-0.3.0.zip
InnAware-PMS-Emulator-Source-0.3.0.zip
SHA256SUMS-WINDOWS-0.3.0.txt
```

If Inno Setup is not installed/detected, the build still produces the tested portable EXE, portable ZIP, source ZIP, and checksums.

## Windows application diagnostics

Runtime diagnostics are written to:

```text
%LOCALAPPDATA%\InnAware\PMS Emulator\logs\emulator.log
```

The Windows launcher is built without a console window. Uvicorn logging is therefore file-backed and does not depend on `stdout`/`stderr` being attached.

## Linux / Debian engineering lab

Linux is supported because it is valuable for headless interoperability testing and automated regression. It is not the primary technician desktop experience.

Development start:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . pytest
pytest -q
uvicorn innaware_pms_emulator.main:app --app-dir src --host 127.0.0.1 --port 8080
```

The repository also contains:

```text
packaging/systemd/innaware-pms-emulator.service
scripts/install-systemd.sh
scripts/verify-server3.sh
```

The deterministic Linux verification script uses an isolated data directory/port and tests the same shared protocol/property core used by Windows.

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

See [`docs/ADR-001-SHARED-CROSS-PLATFORM-CORE.md`](docs/ADR-001-SHARED-CROSS-PLATFORM-CORE.md).

## Verification status for 0.3.0

The 0.3.0 shared tree has passed the Linux/server laboratory regression gate, including persistent property/interface restore. The Windows frozen EXE has also passed the automated frozen-binary smoke test used by the build process.

Public releases should still be treated as prerelease/field-beta until the remaining protocol variants, broader field testing, code signing, and open-source release checklist are completed.

## Safety

This is a test/emulation instrument. It can generate real PMS and call-accounting traffic. Do not point it at a production hotel PMS, billing endpoint, PBX, or customer system unless test traffic is explicitly intended and authorized.

The management UI/API should normally remain bound to localhost. Expose it to a LAN only when that is intentionally required for the laboratory setup.

## Author

**Tommy Heggie**

InnAware PMS Emulator was created and is maintained by Tommy Heggie. Contributions may be accepted as the project moves toward a public open-source release.

## Open-source / compatibility boundary

Third-party product and protocol names are descriptive compatibility references and do not imply sponsorship, certification, partnership, or endorsement.

Do not add copied vendor manuals, proprietary source, third-party logos, customer data, credentials, or other material without a clear right to redistribute it.

The public-release checklist is documented in [`docs/OPEN_SOURCE_READINESS.md`](docs/OPEN_SOURCE_READINESS.md). A final public-source `LICENSE` should be selected deliberately before the repository is made public.
