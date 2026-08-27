# InnAware PMS Emulator - Windows Field Edition

## Product priority

The Windows field edition is the **primary end-user distribution target** for InnAware PMS Emulator. The normal real-world user is expected to be a technician carrying a Windows laptop to a hotel/property and using the emulator for PMS/PBX/call-accounting testing.

Linux remains supported from the same codebase, but its primary role is headless engineering, development, regression testing and laboratory integration. The server3 installation is intentionally a headless development/test appliance; it is not the target desktop user experience.

The Windows edition is not a separate emulator implementation. It packages the same protocol, framing, state-machine, property-state, TCP, and serial code used by Linux/server3. This prevents protocol behavior from diverging between engineering and field tools.

## Intended field workflow

A technician should eventually be able to:

1. Download a signed portable `InnAware-PMS-Emulator.exe` or normal Windows installer.
2. Launch it without installing Python.
3. Open a polished field console automatically.
4. Choose a saved PMS profile such as Hilton PEP/FIAS, Opera/FIAS, OnQ, Choice Advantage, HotelKey, or an implemented legacy profile.
5. Choose TCP Client, TCP Server, or a discovered Windows COM port.
6. Configure an independent call-accounting interface where required.
7. Start one or more endpoints.
8. Perform guest/property operations from the GUI.
9. Generate or receive call records.
10. View raw ASCII/hex captures and decoded protocol events.
11. Inject controlled protocol faults for troubleshooting and resilience testing.
12. Export a support/capture bundle for engineering.
13. Save/export the working profile for another technician or future visit.

The normal field path should not require a command prompt, PowerShell, Python, manual JSON editing or knowledge of server3.

## Windows UX requirements

Windows-specific usability receives priority once shared protocol correctness is protected. The production field experience should include:

- portable single-EXE build;
- signed installer/uninstaller;
- optional desktop shortcut;
- Start Menu integration;
- visible application version/build information;
- automatic COM-port discovery with friendly device descriptions;
- refresh/rescan COM-port control;
- saved profiles and recent profiles;
- profile import/export;
- explicit TCP client/server terminology;
- connection status and peer address;
- start/stop/restart per endpoint;
- clear raw/decoded RX/TX capture view;
- copy/export capture operations;
- support bundle generation;
- scenario presets;
- fault-injection controls;
- safe defaults that do not accidentally expose the management API to a customer LAN;
- useful error messages for occupied ports, missing COM devices and malformed settings;
- no Python installation requirement on technician machines.

A future native WinUI/WinForms shell is permitted if it materially improves technician usability. If added, it must remain a client/launcher for the shared emulator API/core rather than reimplementing protocols.

## Shared architecture

The following remain shared across Linux and Windows:

- property, room, guest and stay state;
- protocol adapters;
- framing and checksums;
- FIAS state machine;
- call-accounting state machines;
- transaction/retry engine;
- TCP client/server transports;
- serial transport abstraction;
- REST API;
- scenario engine;
- captures and protocol decoding;
- regression fixtures and tests.

Only packaging, OS integration, COM-port presentation, native-shell behavior, installer behavior and other operating-system UX concerns should be platform-specific.

## Linux/server3 role

The Linux version should remain reliable but deliberately headless-friendly. Its primary uses are:

- protocol development;
- automated pytest/regression runs;
- long-running TCP/serial laboratory tests;
- deterministic integration scenarios;
- systemd restart/persistence testing;
- physical serial adapter testing;
- testing InnAware UCP against a stable simulated PMS/call-accounting endpoint;
- CI-like validation when hosted CI is unavailable.

A Linux desktop GUI is not required for the product roadmap. The REST API, browser console, systemd service and terminal diagnostics are sufficient for the intended Linux role.

## Windows launcher

The Windows entry point is:

`src/innaware_pms_emulator/windows_launcher.py`

Default behavior:

- binds the management UI/API to `127.0.0.1:8080`;
- starts the shared emulator service locally;
- opens the field console after the local service is ready;
- refuses to start if the requested HTTP port is already occupied.

Useful command-line options for engineering/advanced field use:

```text
InnAware-PMS-Emulator.exe --no-browser
InnAware-PMS-Emulator.exe --port 8081
InnAware-PMS-Emulator.exe --host 0.0.0.0
```

Normal field use should keep the management interface on `127.0.0.1`. PMS test sockets may independently listen on LAN addresses as required.

## Serial ports

Windows serial interfaces use COM device names such as:

```text
COM1
COM3
COM7
COM12
```

The shared serial configuration supports baud rate, data bits, parity, stop bits, and flow control. The current API can enumerate available serial devices; the Windows field UI should present the friendly device description and COM name rather than requiring technicians to type them manually.

Serial hardware testing on actual Windows field laptops is a release gate because the cross-platform serial layer may behave differently under Windows than Linux.

## Local build

Requirements on a build workstation:

- supported Windows version;
- Python 3.11+ (3.13 is the current build target);
- PowerShell;
- Git.

From the repository root using the Windows Python Launcher:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -Python py
```

Or with `python.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -Python python
```

The build script:

1. creates an isolated Windows build venv;
2. installs the emulator, test dependencies and PyInstaller;
3. runs the regression suite and refuses to package on test failure;
4. creates `InnAware-PMS-Emulator.exe`;
5. computes SHA-256;
6. creates `README-WINDOWS.txt`;
7. creates `InnAware-PMS-Emulator-Windows.zip`;
8. creates a clean source ZIP using `git archive`.

Expected outputs:

```text
dist-windows\InnAware-PMS-Emulator.exe
dist-windows\README-WINDOWS.txt
dist-windows\SHA256SUMS.txt
InnAware-PMS-Emulator-Windows.zip
InnAware-PMS-Emulator-Source.zip
```

## Automated build

`.github/workflows/windows-build.yml` runs on a Windows GitHub Actions runner and uploads the field build as a workflow artifact when GitHub provisions a runner successfully.

This remains a development artifact until Windows smoke testing, installer work and code signing are complete.

## Release path

Before the first public Windows release, complete at minimum:

- production field console;
- profile editor/import/export;
- capture export and support bundles;
- deterministic scenario runner;
- fault injection;
- real Windows COM-port smoke tests;
- installer/uninstaller;
- code signing;
- Windows Defender/SmartScreen packaging review;
- versioned release process;
- reproducible release notes and checksums;
- public documentation;
- security guidance;
- dependency/SBOM review;
- final licensing/provenance review.

## Open-source direction

The project is being designed so the useful protocol emulator can eventually be released publicly without depending on InnAware UCP itself.

Before selecting a public license, audit all protocol definitions and reference-derived material so the repository contains only code and documentation that can legally be redistributed. Do not copy proprietary PMS specifications or copyrighted source from reference implementations merely because the emulator can interoperate with those systems.

The emulator should document observable/interoperable protocol behavior in original code and original documentation.
