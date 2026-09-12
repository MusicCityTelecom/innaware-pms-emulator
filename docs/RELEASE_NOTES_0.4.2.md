# InnAware PMS Emulator 0.4.2

This field-beta feature release adds an experimental Philips / TP Vision CMND guest-TV interface. Windows 10/11 x64 remains the primary platform. This is a prerelease, not a claim of vendor certification or live TV qualification.

## New features and safeguards

- Built-in `philips-cmnd-htng-guest-tv` profile with HTNG 2011B SOAP check-in and checkout, a dedicated operator-console setup panel, and property-workflow integration.
- Exact room and guest identities, escaped Unicode names, explicit site mappings, property isolation, and checkout without guest-name leakage.
- Writes disabled by default. Sending requires an explicit endpoint, execution opt-in, and an exact room allowlist. HTTPS certificate verification is enabled; non-loopback plain HTTP needs a separate opt-in. Optional authorization is read from an environment variable over HTTPS.
- No automatic redirects, retries, TV discovery, or room-suffix fan-out. An ambiguous response is reported as unconfirmed delivery; inspect before retrying. A matching CMND success response is not proof that a TV applied the operation.
- Multiple TVs sharing one CMND Room ID use one room-level notification. Check every TV separately. TVs with different CMND Room IDs require explicit mapping; automatic multi-ID fan-out is not implemented.
- Read-only developer tools inspect locally supplied CMND deployment descriptors and validate synthetic requests against locally supplied schemas. Proprietary CMND files and vendor executables are not included or redistributed.

## Download and run

Use `InnAware-PMS-Emulator-Setup.exe` for per-user installation, or extract `InnAware-PMS-Emulator-Windows-0.4.2.zip` and run the EXE. Python and application libraries are bundled. Native hosting uses Microsoft Edge WebView2 and .NET Framework 4.8; the default-browser fallback remains available. Serial adapters need their manufacturer's driver; virtual COM drivers are not bundled.

Persistent data stays in `%LOCALAPPDATA%\InnAware\PMS Emulator`. The local console defaults to `http://127.0.0.1:8080`; use `--port 8081` for a conflict, `--browser` for browser mode, or `--no-browser` for headless use. Existing privacy preferences are preserved; see the bundled privacy notice for details.

For CMND setup, read the [guest-TV profile guide](https://github.com/MusicCityTelecom/innaware-pms-emulator/blob/v0.4.2/docs/CMND_GUEST_TV_PROFILE.md). Confirm the deployed StayNotification endpoint, site field values, authentication and room mapping before enabling writes. The descriptor-derived candidate `/SmartInstall/services/StayNotification` is not a verified live endpoint.

## Verification and remaining limits

Development Windows regression: **590 passed, 4 skipped**. Synthetic check-in and checkout requests validate against the supplied reference schemas. Tests cover loopback HTTP/SOAP, XML safety, response/action matching, disabled-write and room guards, guest continuity, cross-property rejection, and endpoint inspection. Release CI additionally runs Windows/Linux regressions, frozen-EXE checks, installation, reinstallation and uninstall preservation checks.

No live CMND server or physical TV was contacted for qualification. Mitel 2 exact labeled NAM widths, broader PhoneSuite behavior and Hitachi layouts retain their existing evidence gaps. No undocumented wire-format differences are promoted to verified support.

## Release contents and provenance

The release provides the standalone Windows EXE, Setup.exe, portable ZIP, exact-commit source ZIP, Windows README, privacy notice, build dependency/source identity, interoperability evidence, protocol-pack assets, release manifest and SHA-256 manifests. The running app-info API and `build-info.json` identify the source commit; the release inventory verifies all published assets.

The data-only protocol pack remains `2026.08.27.1`: CMND is built into application 0.4.2 and cannot be added to an older EXE by installing this pack. Prerelease updates must be enabled to discover this field beta. The stable release channel is not changed.
