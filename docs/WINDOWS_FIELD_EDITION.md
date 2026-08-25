# InnAware PMS Emulator - Windows Field Edition

## Goal

The Windows edition is not a separate emulator implementation. It packages the same protocol, framing, state-machine, TCP, and serial code used by the Linux/server3 laboratory edition.

This prevents protocol behavior from diverging between engineering and field tools.

## Intended field workflow

A technician should eventually be able to:

1. Download a signed `InnAware-PMS-Emulator.exe` or installer.
2. Launch it without installing Python.
3. Choose a PMS profile such as Hilton PEP/FIAS, Opera/FIAS, OnQ, Choice Advantage, HotelKey, or a legacy profile.
4. Choose TCP Client, TCP Server, or a Windows COM port.
5. Configure the independent call-accounting interface.
6. Start the interfaces.
7. Perform guest operations from the GUI.
8. Generate or receive call records.
9. View raw ASCII/hex captures and decoded protocol events.
10. Export a support bundle for engineering.

## Shared architecture

The following remain shared across Linux and Windows:

- protocol adapters
- framing and checksums
- FIAS state machine
- call-accounting state machines
- transaction/retry engine
- TCP client/server transports
- serial transport abstraction
- REST API
- operator GUI
- scenario runner
- captures and protocol decoding

Only packaging, OS integration, COM-port presentation, and installer behavior should be platform-specific.

## Windows launcher

The Windows entry point is:

`src/innaware_pms_emulator/windows_launcher.py`

Default behavior:

- binds the management UI/API to `127.0.0.1:8080`
- opens the default browser after the local service is ready
- refuses to start if the requested HTTP port is already occupied

Useful command-line options:

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

The shared serial configuration supports baud rate, data bits, parity, stop bits, and flow control. Future GUI work should enumerate available COM ports rather than requiring technicians to type them manually.

## Local build

Requirements on a build workstation:

- supported Windows version
- Python 3.13
- PowerShell
- Git

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1
```

The build script:

1. creates an isolated Windows build venv
2. installs the emulator and PyInstaller
3. runs the regression suite
4. creates `InnAware-PMS-Emulator.exe`
5. computes SHA-256
6. creates `README-WINDOWS.txt`
7. creates `InnAware-PMS-Emulator-Windows.zip`

## Automated build

`.github/workflows/windows-build.yml` runs on a Windows GitHub Actions runner and uploads the field build as a workflow artifact.

This is initially a development artifact, not a public release artifact.

## Release path

Before a public release, add:

- production operator GUI
- persistent property/interface configuration
- COM-port discovery
- protocol profile editor/import/export
- captures export and support bundles
- scenario runner
- installer/uninstaller
- code signing
- versioned release process
- reproducible release notes and checksums
- public documentation
- security guidance
- final licensing review

## Open-source direction

The project is being designed so the useful protocol emulator can eventually be released publicly without depending on InnAware UCP itself.

Before selecting a public license, audit all protocol definitions and reference-derived material so the repository contains only code and documentation that can legally be redistributed. Do not copy proprietary PMS specifications or copyrighted source from reference implementations merely because the emulator can interoperate with those systems.

The emulator should document observable/interoperable protocol behavior in original code and original documentation.
