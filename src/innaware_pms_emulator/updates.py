from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .protocol_packs import PACK_SCHEMA_VERSION, active_pack_info, protocol_packs_dir
from .storage import data_dir


REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30"
USER_AGENT = "InnAware-PMS-Emulator-Updater"
APP_SETUP_ASSET = "InnAware-PMS-Emulator-Setup.exe"
APP_PORTABLE_ASSET = "InnAware-PMS-Emulator.exe"
PROTOCOL_PACK_PREFIX = "InnAware-PMS-Protocol-Pack-"
PROTOCOL_PACK_SUFFIX = ".zip"
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class UpdateError(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION_RE.search(str(value))
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_value(value: Any) -> str | None:
    """Normalize GitHub's sha256:<hex> form and stored bare digests."""
    digest = str(value or "").strip().lower()
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1]
    return digest if re.fullmatch(r"[0-9a-f]{64}", digest) else None


def _safe_component(value: str) -> str:
    cleaned = "".join(ch for ch in str(value) if ch.isalnum() or ch in {".", "-", "_"}).strip("._-")
    if not cleaned:
        raise UpdateError("Unsafe or empty path component")
    return cleaned[:100]


class UpdateManager:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (data_dir() / "updates")
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.root / "settings.json"
        self.status_path = self.root / "status.json"
        self.downloads_dir = self.root / "downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    def default_settings(self) -> dict[str, Any]:
        return {
            "check_app_updates_on_start": True,
            "check_protocol_updates_on_start": True,
            "include_prereleases": True,
        }

    def load_settings(self) -> dict[str, Any]:
        settings = self.default_settings()
        if not self.settings_path.exists():
            return settings
        try:
            raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return settings
        if isinstance(raw, dict):
            for key in settings:
                if key in raw:
                    settings[key] = bool(raw[key])
        return settings

    def save_settings(self, incoming: dict[str, Any]) -> dict[str, Any]:
        settings = self.default_settings()
        for key in settings:
            if key in incoming:
                settings[key] = bool(incoming[key])
        self._write_json(self.settings_path, settings)
        return settings

    def load_status(self) -> dict[str, Any]:
        if not self.status_path.exists():
            return {
                "checked_at": None,
                "error": None,
                "app": None,
                "protocol_pack": self._protocol_pack_local_status(),
            }
        try:
            raw = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "checked_at": None,
                "error": "Stored update status could not be read",
                "app": None,
                "protocol_pack": self._protocol_pack_local_status(),
            }
        if isinstance(raw, dict):
            raw["protocol_pack_local"] = self._protocol_pack_local_status()
            return raw
        return {"checked_at": None, "error": "Invalid stored update status"}

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(path)

    def _request(self, url: str, *, timeout: float = 10.0) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateError(f"Unable to contact GitHub: {exc}") from exc

    def _request_json(self, url: str) -> Any:
        try:
            return json.loads(self._request(url).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateError("GitHub returned an invalid update response") from exc

    def fetch_releases(self) -> list[dict[str, Any]]:
        payload = self._request_json(RELEASES_API)
        if not isinstance(payload, list):
            raise UpdateError("Unexpected GitHub releases response")
        return [item for item in payload if isinstance(item, dict) and not item.get("draft")]

    @staticmethod
    def _public_asset(asset: dict[str, Any] | None) -> dict[str, Any] | None:
        if not asset:
            return None
        return {
            "name": asset.get("name"),
            "size": asset.get("size"),
            "digest": asset.get("digest"),
            "download_url": asset.get("browser_download_url"),
        }

    @staticmethod
    def _asset(release: dict[str, Any], name: str) -> dict[str, Any] | None:
        for asset in release.get("assets", []) or []:
            if isinstance(asset, dict) and asset.get("name") == name:
                return asset
        return None

    @staticmethod
    def _protocol_pack_asset(release: dict[str, Any]) -> dict[str, Any] | None:
        for asset in release.get("assets", []) or []:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", ""))
            if name.startswith(PROTOCOL_PACK_PREFIX) and name.endswith(PROTOCOL_PACK_SUFFIX):
                return asset
        return None

    @staticmethod
    def _protocol_pack_version(asset: dict[str, Any]) -> str | None:
        name = str(asset.get("name", ""))
        if not (name.startswith(PROTOCOL_PACK_PREFIX) and name.endswith(PROTOCOL_PACK_SUFFIX)):
            return None
        value = name[len(PROTOCOL_PACK_PREFIX):-len(PROTOCOL_PACK_SUFFIX)]
        try:
            return _safe_component(value)
        except UpdateError:
            return None

    def _latest_app_release(self, releases: list[dict[str, Any]], include_prereleases: bool) -> dict[str, Any] | None:
        candidates = [
            release
            for release in releases
            if (include_prereleases or not release.get("prerelease")) and version_tuple(str(release.get("tag_name", ""))) != (0, 0, 0)
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda release: (
                version_tuple(str(release.get("tag_name", ""))),
                str(release.get("published_at") or release.get("created_at") or ""),
            ),
        )

    def _latest_protocol_release(self, releases: list[dict[str, Any]], include_prereleases: bool) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for release in releases:
            if release.get("prerelease") and not include_prereleases:
                continue
            asset = self._protocol_pack_asset(release)
            if asset:
                return release, asset
        return None

    def _protocol_pack_local_status(self) -> dict[str, Any]:
        info = active_pack_info()
        return {
            "installed": bool(info),
            "pack_version": info.get("pack_version") if info else None,
            "source_release": info.get("source_release") if info else None,
            "source_asset": info.get("source_asset") if info else None,
            "source_digest": info.get("source_digest") if info else None,
            "installed_at": info.get("installed_at") if info else None,
        }

    def check(self, current_version: str, *, include_prereleases: bool | None = None) -> dict[str, Any]:
        settings = self.load_settings()
        if include_prereleases is None:
            include_prereleases = bool(settings["include_prereleases"])
        checked_at = utc_now()
        try:
            releases = self.fetch_releases()
            app_release = self._latest_app_release(releases, include_prereleases)
            app_status: dict[str, Any] | None = None
            if app_release:
                setup = self._asset(app_release, APP_SETUP_ASSET)
                portable = self._asset(app_release, APP_PORTABLE_ASSET)
                selected = setup or portable
                latest_tag = str(app_release.get("tag_name", ""))
                app_status = {
                    "current_version": current_version,
                    "latest_tag": latest_tag,
                    "latest_version": ".".join(str(x) for x in version_tuple(latest_tag)),
                    "update_available": version_tuple(latest_tag) > version_tuple(current_version),
                    "prerelease": bool(app_release.get("prerelease")),
                    "release_name": app_release.get("name"),
                    "release_url": app_release.get("html_url"),
                    "published_at": app_release.get("published_at"),
                    "asset": self._public_asset(selected),
                }

            pack_pair = self._latest_protocol_release(releases, include_prereleases)
            local_pack = self._protocol_pack_local_status()
            pack_status: dict[str, Any] = {"local": local_pack, "remote": None, "update_available": False}
            if pack_pair:
                release, asset = pack_pair
                remote = {
                    "release_tag": release.get("tag_name"),
                    "release_url": release.get("html_url"),
                    "published_at": release.get("published_at"),
                    "pack_version": self._protocol_pack_version(asset),
                    "asset": self._public_asset(asset),
                }
                remote_digest = _sha256_value(asset.get("digest"))
                remote_version = self._protocol_pack_version(asset)
                same_version = bool(
                    remote_version
                    and local_pack.get("pack_version") == remote_version
                )
                pack_status = {
                    "local": local_pack,
                    "remote": remote,
                    "update_available": (
                        not local_pack["installed"]
                        or (
                            not same_version
                            and (
                                local_pack.get("pack_version") != remote_version
                                or _sha256_value(local_pack.get("source_digest")) != remote_digest
                                or local_pack.get("source_asset") != asset.get("name")
                            )
                        )
                    ),
                }

            status = {
                "checked_at": checked_at,
                "error": None,
                "include_prereleases": include_prereleases,
                "app": app_status,
                "protocol_pack": pack_status,
            }
        except UpdateError as exc:
            status = {
                "checked_at": checked_at,
                "error": str(exc),
                "include_prereleases": include_prereleases,
                "app": None,
                "protocol_pack": {"local": self._protocol_pack_local_status(), "remote": None, "update_available": False},
            }
        self._write_json(self.status_path, status)
        return status

    def start_background_check(self, current_version: str) -> None:
        settings = self.load_settings()
        if not (settings["check_app_updates_on_start"] or settings["check_protocol_updates_on_start"]):
            return

        def worker() -> None:
            try:
                self.check(current_version, include_prereleases=bool(settings["include_prereleases"]))
            except Exception:
                # Update checks must never prevent application startup.
                return

        threading.Thread(target=worker, name="innaware-update-check", daemon=True).start()

    def _manifest_digest(self, release: dict[str, Any], filename: str) -> str | None:
        manifest_asset = self._asset(release, "SHA256SUMS.txt")
        if not manifest_asset:
            return None
        url = manifest_asset.get("browser_download_url")
        if not url:
            return None
        try:
            text = self._request(str(url)).decode("utf-8", errors="replace")
        except UpdateError:
            return None
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1].lstrip("*") == filename and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
                return parts[0].lower()
        return None

    def _expected_digest(self, release: dict[str, Any], asset: dict[str, Any]) -> str:
        digest = str(asset.get("digest") or "")
        if digest.lower().startswith("sha256:"):
            value = digest.split(":", 1)[1].lower()
            if re.fullmatch(r"[0-9a-f]{64}", value):
                return value
        fallback = self._manifest_digest(release, str(asset.get("name", "")))
        if fallback:
            return fallback
        raise UpdateError(f"Release asset {asset.get('name')} has no verifiable SHA-256 digest")

    def _download_verified(self, release: dict[str, Any], asset: dict[str, Any]) -> tuple[Path, str]:
        name = Path(str(asset.get("name", ""))).name
        if not name:
            raise UpdateError("Release asset has no filename")
        url = asset.get("browser_download_url")
        if not url:
            raise UpdateError(f"Release asset {name} has no download URL")
        expected = self._expected_digest(release, asset)
        destination = self.downloads_dir / name
        temp = destination.with_suffix(destination.suffix + ".tmp")
        digest = hashlib.sha256()
        request = urllib.request.Request(str(url), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30.0) as response, temp.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    output.write(chunk)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            temp.unlink(missing_ok=True)
            raise UpdateError(f"Unable to download {name}: {exc}") from exc
        actual = digest.hexdigest().lower()
        if actual != expected:
            temp.unlink(missing_ok=True)
            raise UpdateError(f"SHA-256 verification failed for {name}")
        temp.replace(destination)
        return destination, actual

    def download_app_update(self, current_version: str) -> dict[str, Any]:
        settings = self.load_settings()
        releases = self.fetch_releases()
        release = self._latest_app_release(releases, bool(settings["include_prereleases"]))
        if not release:
            raise UpdateError("No eligible application release was found")
        tag = str(release.get("tag_name", ""))
        if version_tuple(tag) <= version_tuple(current_version):
            raise UpdateError("The installed application is already current for this update channel")
        asset = self._asset(release, APP_SETUP_ASSET) or self._asset(release, APP_PORTABLE_ASSET)
        if not asset:
            raise UpdateError("The release does not contain a Windows installer or portable executable")
        path, digest = self._download_verified(release, asset)
        state = {
            "downloaded_at": utc_now(),
            "release_tag": tag,
            "release_url": release.get("html_url"),
            "asset": asset.get("name"),
            "sha256": digest,
            "path": str(path),
        }
        self._write_json(self.root / "downloaded-app-update.json", state)
        return state

    def launch_downloaded_app_update(self) -> dict[str, Any]:
        if os.name != "nt":
            raise UpdateError("Launching the Windows updater is only supported on Windows")
        state_path = self.root / "downloaded-app-update.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            path = Path(str(state["path"]))
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise UpdateError("No verified downloaded application update is available") from exc
        try:
            path.resolve().relative_to(self.downloads_dir.resolve())
        except ValueError as exc:
            raise UpdateError("Downloaded updater path is outside the managed update directory") from exc
        if not path.exists():
            raise UpdateError("The downloaded updater file no longer exists")
        subprocess.Popen([str(path)], cwd=str(path.parent), close_fds=True)
        return {**state, "launched": True}

    def install_latest_protocol_pack(self) -> dict[str, Any]:
        settings = self.load_settings()
        releases = self.fetch_releases()
        pair = self._latest_protocol_release(releases, bool(settings["include_prereleases"]))
        if not pair:
            raise UpdateError("No protocol-pack release asset was found")
        release, asset = pair
        path, digest = self._download_verified(release, asset)
        return self.install_protocol_pack_file(
            path,
            source_release=str(release.get("tag_name") or ""),
            source_asset=str(asset.get("name") or ""),
            source_digest=digest,
        )

    def install_protocol_pack_file(
        self,
        archive_path: Path,
        *,
        source_release: str,
        source_asset: str,
        source_digest: str,
    ) -> dict[str, Any]:
        try:
            archive = zipfile.ZipFile(archive_path, "r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise UpdateError("Protocol pack is not a valid ZIP archive") from exc
        with archive:
            names = archive.namelist()
            if "protocol-pack.json" not in names:
                raise UpdateError("Protocol pack is missing protocol-pack.json")
            try:
                manifest = json.loads(archive.read("protocol-pack.json").decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UpdateError("Protocol pack manifest is invalid") from exc
            if not isinstance(manifest, dict) or manifest.get("schema_version") != PACK_SCHEMA_VERSION:
                raise UpdateError(f"Unsupported protocol-pack schema; expected {PACK_SCHEMA_VERSION}")
            pack_version = _safe_component(str(manifest.get("pack_version", "")))
            profiles = manifest.get("profiles", [])
            if not isinstance(profiles, list) or any(not isinstance(item, dict) for item in profiles):
                raise UpdateError("Protocol pack profiles must be a list of objects")

            total_size = 0
            allowed_suffixes = {".json", ".txt", ".md"}
            for info in archive.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise UpdateError("Protocol pack contains an unsafe path")
                if info.is_dir():
                    continue
                total_size += info.file_size
                if total_size > 10 * 1024 * 1024:
                    raise UpdateError("Protocol pack exceeds the 10 MiB uncompressed safety limit")
                if info.filename != "protocol-pack.json":
                    if not info.filename.startswith("stubs/") or Path(info.filename).suffix.lower() not in allowed_suffixes:
                        raise UpdateError(f"Protocol pack contains unsupported file: {info.filename}")
                if Path(info.filename).suffix.lower() in {".py", ".pyc", ".pyd", ".dll", ".exe", ".ps1", ".bat", ".cmd"}:
                    raise UpdateError("Executable content is not allowed in protocol packs")

            target_root = protocol_packs_dir()
            target = target_root / pack_version
            with tempfile.TemporaryDirectory(prefix="innaware-protocol-pack-") as temp_dir:
                temp_root = Path(temp_dir)
                archive.extractall(temp_root)
                staged = temp_root
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(staged, target)

        pointer = {
            "pack_version": pack_version,
            "source_release": source_release,
            "source_asset": source_asset,
            "source_digest": source_digest,
            "installed_at": utc_now(),
        }
        pointer_path = protocol_packs_dir() / "active.json"
        self._write_json(pointer_path, pointer)
        return {**pointer, "profiles": len(profiles), "path": str(target)}


update_manager = UpdateManager()
