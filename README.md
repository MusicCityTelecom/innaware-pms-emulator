# InnAware PMS Emulator

A cross-platform PMS and call-accounting emulator for testing hospitality PBX integrations without requiring a live hotel PMS.

The same protocol, transport, state-machine and operator-console code is used on the Debian lab appliance and the Windows field edition.

## Current scope

The service can model multiple independent interfaces and is designed for:

- PMS: Hilton OnQ-style legacy framing, Hilton PEP/FIAS, Oracle/Opera FIAS and legacy Opera-style profiles, Choice Advantage-style legacy interfaces, HotelKey-style HTTP/JSON, and generic profile-driven hotel PMS protocols.
- Call accounting: TelElectronics InnForm XL, HOBIS/HOBIC/Holidex-style ACK/NAK feeds, blind-send/SMDR feeds, and additional fixed-field profiles.
- Transport roles: TCP server, TCP client, serial, and protocol-specific HTTP endpoints.
- Test operations: check-in, check-out, guest-name update, room move, wake-up set/cancel, room status, dialing restriction, DND, message waiting, language, link negotiation, and raw message injection.
- PBX-originated traffic capture: call records, room status, message-count/status, synchronization requests, heartbeats, and arbitrary raw frames.
- Stateful FIAS negotiation and posting/database-sync responses.
- Transactional InnForm/HOBIS-style call-accounting exchange with ENQ/ACK, record ACK, timeout, NAK and retry behavior.

This repository is intentionally separate from `innaware-ucp`: it is a test instrument, not runtime PBX code.

## Architecture

`InterfaceManager` owns transport sessions. Protocol adapters encode/decode application records and never own sockets directly. State machines observe received wire data and issue protocol responses. The transactional sender handles acknowledgement-driven call-accounting delivery. The browser operator console consumes the same REST API used by automated tests and external tooling.

Interface definitions are persisted as JSON and restored at startup. On Linux the default data directory is `~/.local/share/innaware-pms-emulator`; on Windows it is under `%LOCALAPPDATA%\InnAware\PMS Emulator`. Set `INNAWARE_PMS_DATA_DIR` to override the location.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e . pytest
pytest
uvicorn innaware_pms_emulator.main:app --app-dir src --host 0.0.0.0 --port 8080
```

Then open `http://SERVER:8080/` for the operator console.

For a local-only workstation launch:

```bash
innaware-pms-emulator
```

The application entry point binds the management UI to `127.0.0.1:8080` by default. Individual PMS/call-accounting interfaces may still bind to LAN addresses as required.

## Windows field edition

See `docs/WINDOWS_FIELD_EDITION.md`. `scripts/build-windows.ps1` creates a standalone EXE, ZIP package and SHA-256 manifest. The Windows launcher starts the same application core and opens the operator console automatically.

## Safety

Use this only on isolated lab/test interfaces. Do not point an emulator instance at production PMS or billing endpoints unless you explicitly intend to generate test transactions. Keep the management HTTP service bound to localhost unless remote administration is explicitly required and appropriately protected.
