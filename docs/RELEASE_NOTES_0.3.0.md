# InnAware PMS Emulator 0.3.0 - Windows Field Beta

**Author:** Tommy Heggie

0.3.0 is the first productization milestone intended to be packaged for normal Windows users without requiring Python or a development environment.

It remains a prerelease because several protocol families are still encoder-only or planned and broader field validation/code signing remain pending.

## Verified milestone status

The 0.3.0 shared core has passed the Linux/server laboratory regression and persistence gate.

The Windows portable build has also completed successfully on an actual Windows 10 x64 workstation, including:

- complete Python regression suite;
- PyInstaller one-file/windowed EXE generation;
- frozen-EXE startup;
- health endpoint verification;
- application metadata verification;
- technician-profile verification;
- 30-room demo-property creation;
- privacy-aware support-bundle generation;
- frozen process-tree cleanup;
- portable ZIP creation;
- clean source ZIP creation;
- SHA-256 manifest generation.

A development build may omit `InnAware-PMS-Emulator-Setup.exe` when Inno Setup 6 is not installed or detected; that does not invalidate the already smoke-tested portable EXE/ZIP. The build script now searches `PATH`, Program Files, Program Files (x86), and the common per-user `%LOCALAPPDATA%\Programs\Inno Setup 6` installation path.

## Primary product target

Windows is the primary technician/user distribution. Debian/Linux remains fully supported for headless engineering, regression, serial/TCP laboratory work and long-running integration tests.

Both platforms use the exact same protocol, property-state, framing, transaction and transport engine.

## Windows desktop application

The Windows launcher:

- starts the emulator engine as a managed child process;
- opens the operator console in a native Windows WebView window;
- stores persistent state and logs under `%LOCALAPPDATA%\InnAware\PMS Emulator`;
- detects an already-running emulator on the requested management port;
- detects a management-port conflict with another application;
- shuts down the child engine when the native application window closes;
- records startup/runtime diagnostics in `logs\emulator.log`;
- supports browser/foreground modes for diagnostics;
- uses file-backed Uvicorn logging so a `--windowed` frozen build does not depend on `stdout`/`stderr`.

## Distribution

The Windows build can produce:

- `InnAware-PMS-Emulator.exe` - portable one-file application;
- `InnAware-PMS-Emulator-Setup.exe` - per-user installer when Inno Setup 6 is available;
- `InnAware-PMS-Emulator-Windows-0.3.0.zip` - portable field package;
- `InnAware-PMS-Emulator-Source-0.3.0.zip` - source archive;
- SHA-256 checksum manifests.

The installer defaults to `%LOCALAPPDATA%\Programs\InnAware PMS Emulator`, creates Start Menu integration, offers an optional desktop shortcut, and does not require administrator privileges for a normal per-user installation.

Saved application data is outside the installation directory and is intentionally retained when the application is uninstalled.

Windows executable and installer metadata attribute the project to **Tommy Heggie**.

## Technician profiles

Built-in interface profiles cover the primary tested workflows:

- Generic FIAS PMS TCP server;
- Hilton/PEP FIAS TCP server;
- TelElectronics InnForm XL TCP server;
- HOBIS-A/Holidex transactional TCP server;
- Blind SMDR TCP server.

Profiles can be instantiated through the API with property binding and safe per-site overrides.

## Supportability

0.3.0 adds:

- `GET /api/v1/app-info`;
- `GET /api/v1/profiles`;
- profile instantiation API;
- capture export as JSON, CSV or text;
- privacy-aware support-bundle ZIP generation.

The default support bundle includes runtime/platform metadata, interface configuration/status, property summaries, protocol catalog, serial-port inventory, captures, transaction history and application logs when available.

Full guest/property state is excluded by default. It is included only when `include_property_state=true` is explicitly requested.

## Existing core functionality retained

- persistent multi-property hotel model;
- room inventory and occupancy;
- check-in/check-out/room move;
- wakeups;
- housekeeping, restriction, DND, MWI, language and voicemail state;
- FIAS database synchronization from actual occupancy;
- Hilton combined-name behavior;
- TCP server/client and serial transports;
- raw/CR/LF/CRLF/STX-ETX/STX-ETX-BCC framing;
- InnForm XL transactional call accounting;
- HOBIS/HOBIS-A/Holidex transactional call accounting;
- blind SMDR output;
- RX/TX captures and transaction history;
- systemd-backed Linux laboratory deployment.

## Still intentionally incomplete

The following are not claimed complete in 0.3.0:

- HotelKey HTTP/JSON implementation;
- full stateful OnQ/Choice/legacy Opera session behavior;
- HOBIS2;
- HOBIS-B;
- HOBIC;
- MICROS-specific call accounting;
- RoomKey;
- ProfitWatch exact formatter;
- advanced capture replay;
- deliberate fault-injection UI;
- public code signing;
- final public-source license selection.

The protocol catalog reports these distinctions at runtime.

## Remaining release gate

Before treating `v0.3.0` as a broadly downloadable field beta:

1. build `Setup.exe` with Inno Setup 6 and smoke-test install/launch/uninstall;
2. launch the native application window manually and exercise saved-state reopen behavior;
3. exercise at least one Windows TCP PMS interface against another endpoint;
4. confirm real Windows COM-port enumeration on field hardware;
5. open and inspect a generated support bundle;
6. retain the final SHA-256 outputs with the release;
7. choose the final public-source license before making the repository public.

Once those gates pass, the `v0.3.0` prerelease assets are suitable for normal technician download/testing. Public code signing remains recommended before broad external distribution.
