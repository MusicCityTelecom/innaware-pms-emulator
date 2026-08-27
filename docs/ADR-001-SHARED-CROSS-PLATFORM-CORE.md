# ADR-001: One cross-platform emulator core

- Status: Accepted
- Date: 2026-08-26

## Context

An earlier Windows PMS-emulator effort was started as a native C#/.NET 8 WinForms application. That work identified valid field-tool requirements including multiple concurrent endpoints, saved protocol profiles, framing/checksum controls, ACK/NAK visibility, serial-port configuration, endpoint status, logging and a technician-friendly packaged application.

The current emulator also needs to run continuously on Debian as a laboratory appliance and to exercise the same hospitality protocol behavior from automated tests.

Maintaining a Python/Linux protocol implementation and a separate C#/Windows protocol implementation would duplicate the highest-risk code in the project: byte framing, state machines, legacy field layouts, retry semantics and property-state transitions. The two implementations would inevitably drift and could produce different test results for the same supposed PMS profile.

## Decision

The authoritative emulator implementation is one Python 3.11+ cross-platform core containing:

- hospitality property state;
- normalized hotel operations;
- protocol adapters;
- framing/checksum code;
- session state machines;
- TCP/serial transports;
- transaction/retry behavior;
- capture/audit logic;
- REST API.

The browser operator console consumes that same API on both Debian and Windows.

The Windows field edition packages the shared core as a standalone EXE so technicians do not need to install Python. A future native WinUI/WinForms shell is allowed if field usability requires it, but such a shell must remain an API client/launcher and must not fork or reimplement protocol behavior.

## Consequences

### Positive

- A protocol regression test has one authoritative implementation.
- Debian/server3 and Windows field behavior stay aligned.
- Protocol fixes automatically benefit both targets.
- Open-source provenance and review are simpler because there is one implementation lineage.
- A native Windows UI remains possible without duplicating the emulator engine.

### Tradeoffs

- The initial Windows GUI is browser-based rather than a native WinForms control tree.
- PyInstaller packaging must be maintained and code-signing will eventually be needed for polished Windows distribution.
- Windows serial behavior depends on the cross-platform Python serial stack and must be exercised on real field hardware.

## Carried-forward requirements from the earlier native Windows prototype

The following requirements remain part of the product despite the implementation change:

- multiple concurrent PMS/call-accounting endpoints;
- endpoint start/stop/restart/status;
- saved profiles/configuration;
- TCP client/server and COM-port modes;
- line settings, framing bytes, checksums and ACK/NAK controls;
- raw and decoded traffic logging;
- portable field package;
- eventual installer, shortcuts and code signing;
- simple operation by technicians without a development environment.
