# InnAware PMS Emulator Updates

InnAware PMS Emulator supports independent application and protocol-pack updates through the local **Update Center**.

## Authoritative update source

**GitHub is the authoritative source for InnAware PMS Emulator application updates, protocol-pack updates, release notes, checksums, and downloadable release artifacts.**

The application update system reads releases only from:

```text
https://github.com/MusicCityTelecom/innaware-pms-emulator/releases
```

The support site at `https://support.innawareucp.com` is for help using and troubleshooting the application. It is **not** an application-update, protocol-pack, release-artifact, or release-metadata source.

Development should flow through the repository and GitHub release process so the source tree, release metadata, protocol packs, packaged artifacts, and in-application updater remain aligned.

## Application updates

The application checks the public GitHub Releases feed for `MusicCityTelecom/innaware-pms-emulator`.

The preferred Windows update asset is:

```text
InnAware-PMS-Emulator-Setup.exe
```

If an installer is not present, the updater can identify the portable `InnAware-PMS-Emulator.exe`, but normal field releases should include the installer.

The Update Center can:

1. check manually for a newer GitHub release;
2. check automatically in the background when the emulator starts;
3. include or exclude prerelease/beta releases;
4. download the selected GitHub release asset;
5. verify its SHA-256 before it is accepted;
6. launch the verified Windows installer.

The application does **not** overwrite its own running one-file executable. It downloads the installer from the selected GitHub release to the managed application-data update directory and launches the installer. Windows/Inno Setup then performs the actual application replacement.

### Verification

The updater prefers the SHA-256 digest published by GitHub for the release asset. If GitHub does not expose an asset digest, the updater looks for `SHA256SUMS.txt` in the same GitHub release and matches the exact asset filename. A download without a verifiable SHA-256 is rejected.

## Protocol / stub packs

Data-only protocol packs can be distributed independently of the executable, but they are also published and discovered through the same GitHub Releases feed.

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

A protocol pack may contain sanitized JSON fixtures/stubs, text/Markdown reference notes under `stubs/`, and data-only technician profile definitions for protocol engines already compiled into the application.

A protocol pack may **not** contain executable code. The installer rejects Python, DLLs, EXEs, PowerShell, batch files, path traversal, unsupported paths, and oversized archives. Downloaded profile data also cannot replace a built-in technician profile shipped with the executable.

New protocol parsers, state machines, framing logic, transports, or other executable behavior require a normal application release.

### Active protocol-pack version

The running application resolves its protocol-pack version from the active installed pack's manifest. If no independently installed pack is active, it uses the bundled canonical repository `protocol-pack.json` embedded in the Windows build.

This same canonical value is shown in the Update Center and reported by anonymous usage telemetry. Updating a protocol pack independently therefore changes the version reported on the next application run without requiring an executable update.

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

The Update Center shows:

- application version/release state from GitHub Releases;
- installed and remote protocol-pack state from GitHub Releases;
- automatic-check settings;
- anonymous usage telemetry preference;
- the local random installation UUID for troubleshooting;
- current protocol-pack version;
- privacy documentation;
- a direct GitHub Releases link;
- support email and website links for user help.

## Defaults

The defaults are:

- application update check on startup: enabled;
- protocol-pack update check on startup: enabled;
- include prereleases: enabled during the field-beta line;
- anonymous usage statistics: enabled;
- automatic application installation: disabled.

Checks run in the background and never block normal emulator startup. Downloads/installs remain explicit user actions.

## Anonymous usage telemetry

Telemetry is independent of the GitHub updater. The preference is stored in the same application settings system under:

```text
Send anonymous usage statistics
```

When disabled, the emulator makes no telemetry requests. When enabled, telemetry is short-timeout and background-only.

See [`PRIVACY_TELEMETRY.md`](PRIVACY_TELEMETRY.md) for the exact event behavior and outbound field allowlist.

## Support

Email: **support@innawareucp.com**  
Website: **https://support.innawareucp.com**

These support channels are for help using and troubleshooting the application. They are not update-distribution endpoints; release downloads and update metadata remain on GitHub.

## Privacy and scope

The GitHub updater sends ordinary unauthenticated HTTPS requests to GitHub's public release endpoints and does not upload hotel, guest, interface, capture, or property data.

Anonymous usage telemetry is a separate HTTPS POST to the InnAware telemetry endpoint and is governed by the explicit privacy contract in `PRIVACY_TELEMETRY.md`.