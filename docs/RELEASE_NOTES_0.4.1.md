# InnAware PMS Emulator 0.4.1

This field-beta maintenance release improves installation, startup recovery, and release integrity. Windows 10/11 x64 is the primary platform. Python and application libraries are bundled in both the installer and portable EXE.

## Fixes and improvements

- Windows PowerShell UTF-8 settings files now preserve update and anonymous-usage opt-outs correctly.
- If the native desktop host cannot start, the application cleans up its child service and opens the same console in the default browser. A Browser Start Menu shortcut is included.
- Installer upgrades use Windows Restart Manager rather than terminating every process with the same executable name. Uninstall preserves user-added files and persistent application data.
- The portable ZIP contains a checksum file that references only included files. Complete release builds require Inno Setup and reject uncommitted tracked source changes or unsafe output paths.
- The executable, installer, and ZIP include build-info.json with the source commit, Python version, and installed dependency inventory. The running app-info API reports the embedded source commit.
- Every release asset is checked for presence, hashes, ZIP consistency, and source provenance before upload. Published tags and artifacts cannot be silently replaced by a later build.
- Windows CI exercises the portable executable, installation, reinstallation, installed executable, and uninstall file preservation. Linux and Windows source regression suites remain required.

## Running the release

Download Setup.exe for a per-user installation, or extract the Windows ZIP. Double-click the application. Native hosting uses Microsoft Edge WebView2 and .NET Framework 4.8; the browser fallback is available when those components are absent. A current Edge, Chrome, or Firefox browser can use the local console. Local simulation works offline; updates require Internet access. USB serial adapters require their manufacturer's Windows driver and a configured COM port. Virtual COM drivers are not bundled.

Data remains under `%LOCALAPPDATA%\InnAware\PMS Emulator`. The console defaults to `http://127.0.0.1:8080`. Use `--port 8081` when another application owns port 8080. Use `--browser` to select browser mode explicitly or `--no-browser` for headless operation.

## Scope of verification

This is a prerelease. Hardware interoperability gaps remain as documented in the compatibility matrix. In particular, exact labeled Mitel 2 NAM widths, broader PhoneSuite hardware behavior, and Hitachi profile layouts require external evidence. This maintenance release does not change those wire-format claims or promote partial compatibility to certified support.

The protocol pack remains version 2026.08.27.1. Vendor executables and proprietary resources are excluded from the source distribution.
