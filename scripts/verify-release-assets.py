"""Verify the complete built release and write a commit-bound asset inventory."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(root: Path, source_sha: str, *, flat: bool = False) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("A full source commit SHA is required")
    release = json.loads((root / "release-manifest.json").read_text(encoding="utf-8-sig"))
    version = release["application_version"]
    if release["release_tag"] != f"v{version}":
        raise ValueError("Release tag/version mismatch")
    output = root if flat else root / "dist-windows"
    info = json.loads((output / "build-info.json").read_text(encoding="utf-8-sig"))
    if info["source_sha"] != source_sha or info["application_version"] != version:
        raise ValueError("Build provenance does not match the release")
    pack = f"InnAware-PMS-Protocol-Pack-{release['protocol_pack_version']}"
    evidence = f"InnAware-PMS-Interop-Evidence-{source_sha}.json"
    exe = "InnAware-PMS-Emulator.exe"
    product_names = [exe, "InnAware-PMS-Emulator-Setup.exe", "README-WINDOWS.txt",
                     "PRIVACY-TELEMETRY.md", "SHA256SUMS.txt", "build-info.json"]
    source_name = f"InnAware-PMS-Emulator-Source-{version}.zip"
    portable_name = f"InnAware-PMS-Emulator-Windows-{version}.zip"
    paths = [output / name for name in product_names] + [root / name for name in (
        source_name, portable_name, f"SHA256SUMS-WINDOWS-{version}.txt",
        pack + ".zip", pack + ".sha256.txt", evidence, evidence + ".sha256.txt",
        "release-manifest.json")]
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing or empty release asset: {path.name}")
    by_name = {path.name: path for path in paths}
    for path in paths:
        if path.name.startswith("SHA256SUMS") or path.name.endswith(".sha256.txt"):
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                match = re.fullmatch(r"([0-9a-f]{64})\s+\*?([^/\\]+)", line)
                if not match or match[2] not in by_name or digest(by_name[match[2]]) != match[1]:
                    raise ValueError(f"Invalid checksum entry in {path.name}: {line}")
    with zipfile.ZipFile(root / portable_name) as archive:
        required = {exe, "README-WINDOWS.txt", "PRIVACY-TELEMETRY.md", "SHA256SUMS.txt", "build-info.json"}
        if set(archive.namelist()) != required or archive.testzip():
            raise ValueError("Portable ZIP contents are incomplete or corrupt")
        for name in required:
            if hashlib.sha256(archive.read(name)).hexdigest() != digest(output / name):
                raise ValueError(f"Portable ZIP differs from release asset: {name}")
        for line in archive.read("SHA256SUMS.txt").decode("utf-8-sig").splitlines():
            expected, name = line.split(None, 1)
            if name not in required or hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("Portable checksum references an absent or mismatched file")
    with zipfile.ZipFile(root / source_name) as archive:
        if archive.comment.decode("ascii") != source_sha or archive.testzip():
            raise ValueError("Source ZIP is corrupt or belongs to another commit")
        if json.loads(archive.read("release-manifest.json")) != release:
            raise ValueError("Source ZIP release identity differs")
        if any(name.lower().endswith((".exe", ".dll")) for name in archive.namelist()):
            raise ValueError("Source ZIP unexpectedly contains executable binaries")
    producer = json.loads((root / evidence).read_text(encoding="utf-8"))["producer"]
    if producer["source_sha"] != source_sha:
        raise ValueError("Interop evidence belongs to another source commit")
    return {"schema_version": 1, "source_sha": source_sha, "application_version": version,
            "assets": [{"name": p.name, "size_bytes": p.stat().st_size, "sha256": digest(p)}
                       for p in sorted(paths, key=lambda p: p.name)]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--flat", action="store_true", help="Verify downloaded release assets in a flat directory")
    args = parser.parse_args()
    result = verify(args.root, args.source_sha, flat=args.flat)
    name = f"release-assets-{result['application_version']}.json"
    path = args.root / name
    if args.flat:
        if json.loads(path.read_text(encoding="utf-8")) != result:
            raise ValueError("Published release inventory differs from downloaded assets")
        expected = (args.root / f"{name}.sha256.txt").read_text().split()[0]
        if digest(path) != expected:
            raise ValueError("Release inventory checksum mismatch")
    else:
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (args.root / f"{name}.sha256.txt").write_text(f"{digest(path)}  {name}\n", encoding="ascii")
    print(f"Verified {len(result['assets'])} release assets for {args.source_sha}")


if __name__ == "__main__":
    main()
