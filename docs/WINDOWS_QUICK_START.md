# InnAware PMS Emulator - Windows Quick Start

**Author:** Tommy Heggie  
**Current field-beta version:** 0.3.0

## Install

### Preferred distribution: installer

When the release includes it:

1. Download `InnAware-PMS-Emulator-Setup.exe` from the current GitHub release.
2. Run the installer.
3. Launch **InnAware PMS Emulator** from the Start Menu.

The installer defaults to a per-user installation under:

```text
%LOCALAPPDATA%\Programs\InnAware PMS Emulator
```

### Portable distribution

1. Download `InnAware-PMS-Emulator-Windows-<version>.zip`.
2. Extract it to a writable folder.
3. Run `InnAware-PMS-Emulator.exe`.

Python is not required to run either packaged distribution.

If a development build was made without Inno Setup 6, the portable EXE/ZIP can still be complete and smoke-tested even though `Setup.exe` is absent.

## First launch

The application starts its local engine automatically and opens the operator console in a native Windows window.

Persistent data and logs are stored under:

```text
%LOCALAPPDATA%\InnAware\PMS Emulator
```

The management interface listens on localhost only by default:

```text
127.0.0.1:8080
```

PMS and call-accounting test interfaces are configured separately and may listen on LAN addresses when required.

## Basic test workflow

1. Create a property or choose **Seed Demo Hotel**.
2. Configure the PMS side:
   - protocol;
   - TCP Server, TCP Client, or COM port;
   - host/bind address and port, or serial settings;
   - property binding.
3. Configure call accounting independently if needed.
4. Start the interfaces.
5. Use guest operations, wakeups, room controls, or the call generator.
6. Inspect **Live Wire Capture** for raw ASCII/hex traffic and protocol state.

## Supported technician profiles in 0.3.0

- Generic FIAS PMS TCP Server
- Hilton / PEP FIAS TCP Server
- TelElectronics InnForm XL TCP Server
- HOBIS-A / Holidex TCP Server
- Blind SMDR TCP Server

Other protocol names may appear as encoder-only or planned. The application deliberately reports maturity instead of claiming that every listed integration is complete.

## Serial / COM ports

Available Windows serial devices are enumerated automatically. Typical names are:

```text
COM1
COM3
COM7
COM12
```

Configure baud, data bits, parity, stop bits and flow control to match the device being tested.

## Windows Firewall

When a PMS/call-accounting interface listens on a LAN address, Windows Defender Firewall may ask whether the application should accept inbound connections. Permit only the network scopes required for the test. The management API itself should normally remain on localhost.

## Support bundle

While the application is running, a privacy-aware support bundle can be generated from:

```text
http://127.0.0.1:8080/api/v1/support-bundle
```

It contains runtime/platform information, interface configuration/status, property summaries, serial-port inventory, captures, transaction history, and logs when available.

Full guest/property state is **not** included unless explicitly requested.

## Capture export

A particular interface capture can be downloaded as CSV, JSON or text:

```text
http://127.0.0.1:8080/api/v1/interfaces/INTERFACE_NAME/captures/export?format=csv
```

Replace `INTERFACE_NAME` with the configured interface name.

## Troubleshooting startup

Application diagnostics are written to:

```text
%LOCALAPPDATA%\InnAware\PMS Emulator\logs\emulator.log
```

If TCP/8080 is already owned by another application, InnAware PMS Emulator will refuse to take the port and display an error instead of silently colliding with the other service.

## Safety

This is an interoperability/test instrument. It can send real PMS and call-accounting traffic. Do not point it at a production hotel PMS, billing endpoint, PBX, or customer system unless the test traffic is explicitly intended and authorized.

---

InnAware PMS Emulator was created and is maintained by **Tommy Heggie**.
