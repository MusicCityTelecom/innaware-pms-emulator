from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "protocol-pack.json"
STUBS = ROOT / "stubs"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = str(manifest["pack_version"])
    output = ROOT / f"InnAware-PMS-Protocol-Pack-{version}.zip"
    checksum = ROOT / f"InnAware-PMS-Protocol-Pack-{version}.sha256.txt"

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(MANIFEST, "protocol-pack.json")
        for path in sorted(STUBS.glob("*.json")):
            archive.write(path, f"stubs/{path.name}")

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"Protocol pack: {output}")
    print(f"SHA-256:      {digest}")
    print(f"Checksum:     {checksum}")


if __name__ == "__main__":
    main()
