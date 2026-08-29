# InnAware PMS Emulator 0.3.7

## Field-beta maintenance release

0.3.7 is the current InnAware PMS Emulator field-beta release. It focuses on release consistency, update-status correctness, and keeping the Windows distribution aligned with the canonical repository version.

### Fixed

- corrects Update Center version-state handling so cached status from an earlier runtime cannot report a contradictory installed/latest state;
- always compares the actual running application version with the selected GitHub release before displaying whether an update is available;
- keeps application version metadata aligned across the Python package, Windows build, installer, release tag, and release manifest;
- keeps GitHub Releases as the authoritative source for application updates, release assets, release notes, and checksums.

### Release metadata

- Application version: `0.3.7`
- Release tag: `v0.3.7`
- Protocol-pack version: `2026.08.27.1`
- Primary field platform: Windows 10/11 x64
- Release channel: field beta

### Windows installation

Preferred installation:

1. Download `InnAware-PMS-Emulator-Setup.exe` from this release.
2. Run the installer.
3. Launch **InnAware PMS Emulator** from the Start Menu.

Portable use remains available through `InnAware-PMS-Emulator-Windows-0.3.7.zip`.

Python is not required for either packaged Windows distribution.

### Upgrade behavior

Upgrading over an earlier InnAware PMS Emulator installation preserves the normal per-user application-data directory and existing local settings. The Update Center should report `0.3.7` as both the installed and latest version after the upgrade and a successful release check.

### Verification

Release assets are built by GitHub Actions from the tagged source revision. Windows application artifacts and protocol-pack artifacts include SHA-256 verification material in the release assets.

For operating instructions, see `docs/WINDOWS_QUICK_START.md`. For update behavior and release-source policy, see `docs/UPDATES.md`.
