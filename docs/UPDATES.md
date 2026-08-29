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

## Canonical release metadata

The source tree contains `release-manifest.json`. It records the application version, release tag, release channel, protocol-pack version, repository, and authoritative update source for the release being prepared.

For the current release it must agree with `pyproject.toml` and `protocol-pack.json`:

```text
application version: 0.3.7
release tag:         v0.3.7
protocol pack:       2026.08.27.1
```

The automated test suite verifies this alignment before a release is published.

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

### Installed/latest version state

Remote release information may be cached between runs, but the installed version is always derived from the application package that is actually running. When cached update status is loaded, the Update Center replaces any cached installed-version value with the running version and recomputes whether an update is available.

This prevents contradictory status such as showing an older installed version while simultaneously claiming that the newer release is already current.

For example:

```text
Installed 0.3.6 + Latest v0.3.7 = Update available
Installed 0.3.7 + Latest v0.3.7 = Current
```

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
- current protocol-pack version;
- a direct GitHub Releases link;
- support email and website links for user help.

## Defaults

The defaults are:

- application update check on startup: enabled;
- protocol-pack update check on startup: enabled;
- include prereleases: enabled during the field-beta line;
- automatic application installation: disabled.

Checks run in the background and never block normal emulator startup. Downloads/installs remain explicit user actions.

## Release publication

The Windows build workflow verifies that `release-manifest.json`, `pyproject.toml`, and `protocol-pack.json` agree. When the manifest marks a version for publication and its release tag does not yet exist, the successful `main` build creates the canonical tag. The tag build then repeats the tests/build gates and publishes the GitHub release from the version-specific release-notes document.

Existing release tags are never moved automatically.

## Support

Email: **support@innawareucp.com**  
Website: **https://support.innawareucp.com**

These support channels are for help using and troubleshooting the application. They are not update-distribution endpoints; release downloads and update metadata remain on GitHub.

## Privacy and scope

The GitHub updater sends ordinary unauthenticated HTTPS requests to GitHub's public release endpoints and does not upload hotel, guest, interface, capture, or property data.
