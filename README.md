# InnAware PMS Emulator

A laboratory PMS and call-accounting emulator for testing InnAware UCP hospitality integrations without requiring a live hotel PMS.

## Initial scope

The service can model multiple independent interfaces and is designed for:

- PMS: Hilton OnQ-style legacy framing, Hilton PEP/FIAS, Oracle/Opera FIAS and legacy Opera-style profiles, Choice Advantage-style legacy interfaces, HotelKey-style HTTP/JSON, and generic profile-driven hotel PMS protocols.
- Call accounting: TelElectronics InnForm XL, HOBIS/HOBIC/Holidex-style ACK/NAK feeds, blind-send/SMDR feeds, and additional fixed-field profiles.
- Transport roles: TCP server, TCP client, and serial.
- Test operations: check-in, check-out, guest-name update, room move, wake-up set/cancel, room status, dialing restriction, DND, message waiting, language, link negotiation, and raw message injection.
- PBX-originated traffic capture: call records, room status, message-count/status, synchronization requests, heartbeats, and arbitrary raw frames.

This repository is intentionally separate from `innaware-ucp`: it is a test instrument, not runtime PBX code.

## Architecture

`InterfaceManager` owns transport sessions. Protocol adapters encode/decode application records and never own sockets directly. This permits the same protocol to run over TCP client, TCP server, or serial without duplicating protocol logic.

The initial API exposes health/protocol discovery plus protocol encoding. Network session persistence and the operator GUI are the next implementation layer.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e . pytest
pytest
uvicorn innaware_pms_emulator.main:app --app-dir src --host 0.0.0.0 --port 8080
```

Then open `http://SERVER:8080/`.

## Safety

Use this only on isolated lab/test interfaces. Do not point an emulator instance at production PMS or billing endpoints unless you explicitly intend to generate test transactions.
