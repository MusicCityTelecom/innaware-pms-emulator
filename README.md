# InnAware PMS Emulator

InnAware PMS Emulator is a cross-platform hotel PMS, PBX and call-accounting integration laboratory. It is designed to test hospitality interfaces without requiring a live hotel PMS or billing system.

The project is intentionally separate from the InnAware UCP runtime. The emulator can test InnAware, but the emulator core is designed to remain useful as a standalone interoperability tool.

> **Development status:** 0.2.0 alpha. Protocol entries carry explicit maturity labels; `implemented` does not mean every vendor-specific edge case has been certified.

## Platform targets

**Windows is the primary technician/product target.** The normal end-user deployment is expected to be a Windows field laptop running a portable EXE or installed/signed desktop package with COM-port discovery, saved profiles, captures, scenarios and technician-oriented controls.

**Linux is the primary headless engineering/laboratory target.** It uses the exact same core for protocol development, automated regression testing, long-running TCP/serial integration tests and systemd-hosted simulated PMS/call-accounting endpoints. The server3 deployment is intentionally headless and is not the target desktop user experience.

Protocol adapters, property state, framing, checksums, state machines, retries, scenarios and capture logic must remain shared across platforms. Windows-specific polish must not fork protocol behavior. See `docs/ADR-001-SHARED-CROSS-PLATFORM-CORE.md` and `docs/WINDOWS_FIELD_EDITION.md`.

## What 0.2.0 adds

- Persistent multi-property hotel state.
- Room inventory with room type, building/floor, housekeeping and out-of-order state.
- Guest and stay/occupancy state kept separately from room operational state.
- Check-in, check-out and room-move workflows.
- Calling restriction, DND, MWI count, language and voicemail lifecycle state.
- Wake-up scheduling/cancellation; scheduled wakeups follow room moves and cancel at checkout.
- Call-accounting history and property audit events.
- Property-bound PMS interfaces.
- FIAS database resync (`DR`) generated from actual active stays (`DS -> GI... -> DE`).
- Cross-platform browser operator console with a room board.
- Automatic serial-port discovery (`COMx` on Windows, tty devices on Linux when exposed by the OS).
- Windows one-file EXE build and GitHub Actions artifact workflow.
- Hardened Debian systemd service template.

## Architecture

The emulator deliberately separates hotel business state from wire protocols:

```text
Property State / Hotel Operations
  properties, rooms, guests, stays, wakeups, calls
                 |
                 v
        Normalized Operations
                 |
        Protocol Adapter Layer
   FIAS / Hilton / legacy / CA formats
                 |
       Framing + State Machines
 ACK/NAK, ENQ, STX/ETX, BCC, retries
                 |
          Session Manager
       TCP client/server / serial
                 |
        External PBX or PMS
```

The same core is used on Debian and Windows. The browser console is only a client of the local REST API; protocol/session behavior does not live in the GUI.

## Property model

Each property owns its own room, guest, stay, wake-up, call and event collections. Operations are property-scoped to prevent accidental cross-property state leakage.

A room tracks room type, building/floor, housekeeping/out-of-order state, occupancy, default/current calling restriction, DND, MWI count, language, voicemail lifecycle, call-billing enabled state and a rate-plan label.

Guest identity and stay/occupancy are separate objects. A room continues to exist after checkout and its room-level defaults survive guest turnover.

## Current protocol matrix

| Protocol | Purpose | Maturity | Notes |
| --- | --- | --- | --- |
| FIAS | PMS | stateful | Link negotiation, posting answer and property-backed database resync |
| HILTON_PEP_FIAS | PMS | stateful | Combined guest-name behavior; no separate `GF` field |
| ONQ | PMS | encoder | Legacy message-generation foundation; session behavior still expanding |
| CHOICE_ADVANTAGE | PMS | encoder | Legacy message-generation foundation |
| OPERA_LEGACY | PMS | encoder | Legacy Opera-style foundation; FIAS is used for FIAS-family testing |
| INNFORM_XL | Call accounting | transactional | Field-tested InnForm XL/TEL-family record plus ENQ/ACK transaction mode |
| HOBIS | Call accounting | transactional | Verified 54-character HOBIS-A fixed layout; ENQ/ACK then STX/record/ETX/XOR-BCC and ACK |
| HOBIS_A | Call accounting | transactional | Explicit compatibility name for the verified HOBIS-A layout |
| HOLIDEX | Call accounting | transactional | HOBIS/Holidex compatibility alias using the verified HOBIS-A transaction family |
| BLIND_SMDR | Call accounting | encoder | Line-oriented blind-send output |
| HOTELKEY | PMS | planned | HTTP/JSON transport work remains pending |
| HOBIC / HOBIS2 / HOBIS_B / MICROS_CA / ROOMKEY / PROFITWATCH / RAW_SMDR | Call accounting | planned | Requirements identified; exact byte fixtures still required before claiming implementation |

The API exposes the same maturity information at `GET /api/v1/protocols`.

The compatibility requirements and historical edge cases being tracked are documented in `docs/PROTOCOL_COMPATIBILITY_ROADMAP.md`.

## Supported transports

- TCP server
- TCP client with reconnect
- Serial
- HTTP server placeholder for future HotelKey-style work

Serial settings include baud rate, 5/6/7/8 data bits, N/E/O/M/S parity, 1/1.5/2 stop bits and none/RTS-CTS/XON-XOFF flow control.

## Framing and transactions

Available framing includes raw, CR, LF, CRLF, STX/ETX and STX/ETX with XOR BCC.

The call-accounting transaction engine supports:

```text
ENQ -> wait ACK -> send record -> wait ACK
```

with timeout, NAK detection and retry limits. HOBIS/HOBIS-A/Holidex recommend STX/ETX+BCC for the record stage. Transactional TCP-server sending requires exactly one connected client so an ACK cannot be ambiguously attributed to the wrong peer.

## Quick development start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . pytest
pytest -q
uvicorn innaware_pms_emulator.main:app --app-dir src --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`.

For an isolated lab server where remote browser access is intentional, bind to the lab address or `0.0.0.0`. Do not expose the management API to an untrusted/customer network.

## Server3 deterministic verification

The repository contains a self-contained verification gate that uses an isolated temporary data directory and port 18080, so it will not touch configured PMS/call-accounting interfaces:

```bash
cd /opt/innaware/innaware-pms-emulator
bash scripts/verify-server3.sh
```

It runs compile checks, pytest, an isolated API smoke test, property scenario checks, a Hilton combined-name fixture, and creates a source ZIP under `/tmp` with a SHA-256 hash.

## Server3 / Debian systemd installation

The repository includes `packaging/systemd/innaware-pms-emulator.service` and `scripts/install-systemd.sh`.

After tests pass and any manually launched copy on port 8080 has been stopped:

```bash
cd /opt/innaware/innaware-pms-emulator
sudo INNAWARE_PMS_BIND=0.0.0.0 sh scripts/install-systemd.sh
```

The service uses:

- source: `/opt/innaware/innaware-pms-emulator`
- virtual environment: `/opt/innaware/innaware-pms-emulator/.venv`
- persistent service data: `/var/lib/innaware-pms-emulator`
- service account: `innaware-pms-emulator`
- supplementary `dialout` group for physical serial adapters

Check it with:

```bash
systemctl status innaware-pms-emulator.service --no-pager
journalctl -u innaware-pms-emulator.service -n 100 --no-pager
```

## Windows field edition

The Windows edition uses the exact same Python core and operator console. The architectural decision to keep one protocol engine is documented in `docs/ADR-001-SHARED-CROSS-PLATFORM-CORE.md`.

### Build locally

From PowerShell with Python installed:

```powershell
git clone https://github.com/MusicCityTelecom/innaware-pms-emulator.git
cd innaware-pms-emulator
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -Python py
```

If `python.exe` rather than the Python Launcher is your command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -Python python
```

The build runs the full pytest suite before packaging and creates:

```text
dist-windows\InnAware-PMS-Emulator.exe
dist-windows\README-WINDOWS.txt
dist-windows\SHA256SUMS.txt
InnAware-PMS-Emulator-Windows.zip
InnAware-PMS-Emulator-Source.zip
```

### GitHub Actions build

The repository contains a **Windows Build** workflow which will create the same artifacts on a Windows hosted runner. A separate **Test** workflow covers Ubuntu and Windows with Python 3.11 and 3.13.

At the time of the 0.2.0 consolidation, GitHub was terminating the private-repository jobs before assigning a runner (no steps executed). Do not treat those failed run badges as test failures; run the deterministic server3 gate and/or local Windows builder until GitHub runner provisioning is restored.

## Persistent data

Default paths:

- Linux: `~/.local/share/innaware-pms-emulator/`
- Windows: `%LOCALAPPDATA%\InnAware\PMS Emulator\`
- systemd service: `/var/lib/innaware-pms-emulator/`

Override with `INNAWARE_PMS_DATA_DIR`.

Persistent files currently include interface definitions and property state. Captures and transaction history are intentionally runtime-bounded at this stage; durable capture export is a future feature.

## Useful API areas

```text
GET    /api/v1/health
GET    /api/v1/protocols
GET    /api/v1/serial-ports

GET    /api/v1/properties
POST   /api/v1/properties
GET    /api/v1/properties/{property}
POST   /api/v1/properties/{property}/rooms/bulk
POST   /api/v1/properties/{property}/checkin
POST   /api/v1/properties/{property}/checkout
POST   /api/v1/properties/{property}/move
POST   /api/v1/properties/{property}/wakeups
POST   /api/v1/properties/{property}/calls
GET    /api/v1/properties/{property}/events
POST   /api/v1/scenarios/small-hotel

GET    /api/v1/interfaces
POST   /api/v1/interfaces
POST   /api/v1/interfaces/{name}/start
POST   /api/v1/interfaces/{name}/stop
GET    /api/v1/interfaces/{name}/captures
GET    /api/v1/interfaces/{name}/transactions
POST   /api/v1/interfaces/{name}/send/raw
POST   /api/v1/interfaces/{name}/send/control
POST   /api/v1/interfaces/{name}/send/guest-event
POST   /api/v1/interfaces/{name}/send/call-record
POST   /api/v1/interfaces/{name}/send/call-record-transaction
```

## Demo scenario

The operator console can seed a deterministic small hotel with 30 rooms, two occupied rooms, one dirty room and one scheduled wake-up. The same scenario is available through:

```text
POST /api/v1/scenarios/small-hotel?property_id=demo-hotel
```

This is the beginning of a larger deterministic scenario runner for reconnect, resync, malformed-frame, retry and recovery testing.

## Safety

This is a test instrument. It can generate real protocol traffic. Do not point it at production PMS, billing or customer endpoints unless test transactions are explicitly intended.

The management UI/API binds to localhost by default in the Windows launcher and application entry point. LAN exposure should be deliberate.

## Compatibility and open-source boundary

Third-party product/protocol names are descriptive compatibility references and do not imply sponsorship or endorsement. Do not add vendor logos, copied manuals, proprietary source or distinctive third-party documentation to this repository.

The intended public-release provenance process is documented in `docs/OPEN_SOURCE_READINESS.md`. A final public-source `LICENSE` has **not** been selected yet and should be chosen deliberately before making the repository public.
