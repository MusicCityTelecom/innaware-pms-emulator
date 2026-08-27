# InnAware PMS Emulator Updates

InnAware PMS Emulator supports two independent update paths beginning with the 0.3.1 development line.

## Application updates

The application checks the public GitHub Releases feed for `MusicCityTelecom/innaware-pms-emulator`.

The preferred Windows update asset is always:

```text
InnAware-PMS-Emulator-Setup.exe
```

If an installer is not present, the updater can identify the portable `InnAware-PMS-Emulator.exe`, but normal field releases should include the installer.

The Update Center can:

1. check manually for a newer release;
2. check automatically in the background when the emulator starts;
3. include or exclude prerelease/beta releases;
4. download the selected release asset;
5. verify its SHA-256 before it is accepted;
6. launch the verified Windows installer.

The application does **not** overwrite its own running one-file executable. It downloads the installer to the managed application-data update directory and launches the installer. Windows/Inno Setup then performs the actual application replacement.

### Verification

The updater prefers the SHA-256 digest published by GitHub for the release asset. If GitHub does not expose an asset digest, the updater looks for:

```text
SHA256SUMS.txt
```

in the same release and matches the exact asset filename. A download without a verifiable SHA-256 is rejected.

## Protocol / stub packs

Data-only protocol packs can be distributed independently of the executable.

Release asset naming:

```text
InnAware-PMS-Protocol-Pack-<pack-version>.zip
```

Each ZIP must contain:

```text
protocol-pack.json
stubs/*.json
```

The current manifest schema is:

```json
{
  "schema_version": 1,
  "pack_version": "2026.08.27.1",
  "minimum_app_version": "0.3.1",
  "description": "Sanitized protocol fixture pack",
  "profiles": []
}
```

A protocol pack may contain:

- sanitized JSON fixtures/stubs;
- text/Markdown reference notes under `stubs/`;
- data-only technician profile definitions for protocol engines already compiled into the application.

A protocol pack may **not** contain executable code. The installer rejects Python, DLLs, EXEs, PowerShell, batch files, path traversal, unsupported paths, and oversized archives. Downloaded profile data also cannot replace a built-in technician profile shipped with the executable.

New protocol parsers, state machines, framing logic, transports, or other executable behavior require a normal application release.

## Building a protocol pack

From the repository root:

```text
python scripts/build-protocol-pack.py
```

The builder reads `protocol-pack.json`, includes all sanitized `stubs/*.json`, and produces:

```text
InnAware-PMS-Protocol-Pack-<pack-version>.zip
InnAware-PMS-Protocol-Pack-<pack-version>.sha256.txt
```

Attach the ZIP to the GitHub release. The separate checksum text file is useful for humans and archival records; GitHub's release-asset digest can also be used by the application automatically.

## Update Center

Within a running emulator, open:

```text
http://127.0.0.1:8080/updates
```

The main operator screen also exposes an **Updates** button.

The Update Center shows application version/release state, installed protocol-pack state, and the automatic-check settings.

## Defaults

The defaults are:

- application update check on startup: enabled;
- protocol-pack update check on startup: enabled;
- include prereleases: enabled during the field-beta line;
- automatic installation: disabled.

Checks run in the background and never block normal emulator startup. Downloads/installs remain explicit user actions.

## Privacy and scope

The updater sends ordinary unauthenticated HTTPS requests to GitHub's public release endpoints. It does not upload hotel, guest, interface, capture, or property data.
