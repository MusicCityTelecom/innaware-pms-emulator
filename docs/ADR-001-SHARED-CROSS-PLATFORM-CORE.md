# ADR-001: One cross-platform emulator core

- Status: Accepted
- Date: 2026-08-26

## Context

An earlier Windows PMS-emulator effort was started as a native C#/.NET 8 WinForms application. That work identified valid field-tool requirements including multiple concurrent endpoints, saved protocol profiles, framing/checksum controls, ACK/NAK visibility, serial-port configuration, endpoint status, logging and a technician-friendly packaged application.

The actual deployment reality is that the emulator will **primarily be used by technicians on Windows laptops in the field**. Windows is therefore the primary product/user-experience target.

Linux remains fully supported because it is valuable for engineering, automated regression testing, protocol development, long-running laboratory sessions and headless integration testing. The current server3 deployment is specifically a headless development/test appliance, not the intended end-user desktop experience.

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

The **Windows field application is the primary distribution target**. It packages this shared core so technicians do not need to install Python and must receive first-class attention for usability, COM-port workflows, saved profiles, diagnostics and distribution.

Linux is a first-class engineering/headless target using the same core. It should be easy to run under systemd, in a terminal, or in automated tests, but Linux desktop polish is not a project priority.

The browser operator console consumes the same API on both platforms and remains useful as the shared UI foundation. A future native WinUI/WinForms shell is allowed—and may be desirable for the production Windows field experience—provided that it remains an API client/launcher and does not fork or reimplement protocol behavior.

## Platform priority

When implementation priorities conflict, use this order:

1. Protocol correctness and shared-core regression safety.
2. Windows field usability and packaging.
3. Cross-platform compatibility.
4. Linux headless/lab operational quality.
5. Linux desktop-specific UX.

This ordering must not be interpreted as permission to introduce Windows-only protocol behavior. Protocol, state, framing and transaction logic remain shared.

## Consequences

### Positive

- A protocol regression test has one authoritative implementation.
- Windows field behavior and server3 lab behavior stay aligned at the protocol layer.
- Protocol fixes automatically benefit both targets.
- Windows can receive a polished technician experience without duplicating the emulator engine.
- Linux remains excellent for repeatable headless regression and long-running integration tests.
- Open-source provenance and review are simpler because there is one implementation lineage.

### Tradeoffs

- The initial Windows GUI is browser-based rather than a native WinForms/WinUI control tree.
- PyInstaller packaging must be maintained and code-signing will eventually be needed for polished Windows distribution.
- Windows serial behavior depends on the cross-platform Python serial stack and must be exercised on real field hardware.
- Linux/server3 does not need desktop GUI investment; the web/API and command-line/service interfaces are sufficient for its intended role.

## Carried-forward requirements from the earlier native Windows prototype

The following requirements remain part of the product despite the implementation change:

- multiple concurrent PMS/call-accounting endpoints;
- endpoint start/stop/restart/status;
- saved profiles/configuration;
- TCP client/server and COM-port modes;
- line settings, framing bytes, checksums and ACK/NAK controls;
- raw and decoded traffic logging;
- portable field package;
- installer/uninstaller;
- desktop and Start Menu integration;
- code signing;
- profile import/export;
- support/capture bundle export;
- simple operation by technicians without a development environment.
