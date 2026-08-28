# InnAware PMS Emulator - Windows Quick Start

**Author:** Tommy Heggie  
**Current development version:** 0.3.7

## Install

### Preferred distribution: installer

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

Python is not required to run either packaged distribution. Installer and portable builds use the same persistent application-data location, so normal application upgrades retain settings and the installation UUID.

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

## Anonymous usage statistics

0.3.6 and later include anonymous usage telemetry. It is enabled by default and can be turned off from:

**Updates > Preferences > Send anonymous usage statistics**

The Update Center also displays the randomly generated installation UUID so support can confirm which anonymous installation record is being discussed.

Telemetry is asynchronous, short-timeout, best-effort, and does not prevent the emulator from starting or working offline. When disabled, no telemetry request is made.

The telemetry JSON contains only:

```text
event
version
platform
architecture
protocol_pack_version
install_id
```

The UUID is randomly generated and is not derived from Windows, hardware, network, or user identifiers. PMS traffic, hotel/property information, credentials, guest/room information, telephone numbers, call records, and network configuration are not included in telemetry JSON.

See `PRIVACY-TELEMETRY.md` in packaged Windows distributions or [`PRIVACY_TELEMETRY.md`](PRIVACY_TELEMETRY.md) in the source tree.

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

## Common technician profiles

- Generic FIAS PMS TCP Server
- Hilton / PEP FIAS TCP Server
- OperaIP / legacy Opera TCP
- Mitel 1 Serial
- Mitel 2 Serial
- TelElectronics InnForm XL TCP Server
- HOBIS-A / Holidex TCP Server
- Blind SMDR TCP Server

Other protocol names may appear as encoder-only or planned. The application deliberately reports maturity instead of claiming every listed integration is complete.

## Serial / COM ports

Available Windows serial devices are enumerated automatically. Typical names are `COM1`, `COM3`, `COM7`, and `COM12`.

Configure baud, data bits, parity, stop bits, and flow control to match the device being tested.

## Windows Firewall

When a PMS/call-accounting interface listens on a LAN address, Windows Defender Firewall may ask whether the application should accept inbound connections. Permit only the network scopes required for the test. The management API itself should normally remain on localhost.

## Updates and protocol packs

Open **Updates** from the main operator window. The Update Center can check for application releases and independent data-only protocol packs, display the currently loaded protocol-pack version, show the telemetry UUID/preference, and provide support links.

Application and protocol-pack downloads are SHA-256 verified before use. Application installation remains an explicit user action.

## Support

Email: **support@innawareucp.com**  
Website: **https://support.innawareucp.com**

Both are available directly from the Update Center.

## Support bundle

While the application is running, a privacy-aware support bundle can be generated from:

```text
http://127.0.0.1:8080/api/v1/support-bundle
```

It contains runtime/platform information, interface configuration/status, property summaries, serial-port inventory, captures, transaction history, and logs when available.

Full guest/property state is **not** included unless explicitly requested.

## Capture export

A particular interface capture can be downloaded as CSV, JSON, or text:

```text
http://127.0.0.1:8080/api/v1/interfaces/INTERFACE_NAME/captures/export?format=csv
```

Replace `INTERFACE_NAME` with the configured interface name.

## Troubleshooting startup

Application diagnostics are written to:

```text
%LOCALAPPDATA%\InnAware\PMS Emulator\logs\emulator.log
```

If TCP/8080 is already owned by another application, InnAware PMS Emulator refuses to take the port and displays an error instead of silently colliding with the other service.

## Safety

This is an interoperability/test instrument. It can send real PMS and call-accounting traffic. Do not point it at a production hotel PMS, billing endpoint, PBX, or customer system unless the test traffic is explicitly intended and authorized.

---

InnAware PMS Emulator was created and is maintained by **Tommy Heggie**.
