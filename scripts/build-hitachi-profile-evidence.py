#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from innaware_pms_emulator.hitachi_profile_evidence import (
    build_hitachi_profile_evidence_bundle,
    hitachi_bundle_digest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic sanitized evidence bundle from authorized read-only "
            "Epitome, EPIT-HIT, and EPIT-HIT2 textual PBX profiles."
        )
    )
    parser.add_argument("--source-sha", required=True, help="exact 40-character emulator Git SHA")
    parser.add_argument("--epitome", required=True, help="path to psip-pbx-protocol.Epitome")
    parser.add_argument("--epit-hit", required=True, help="path to psip-pbx-protocol.EPIT-HIT")
    parser.add_argument("--epit-hit2", required=True, help="path to psip-pbx-protocol.EPIT-HIT2")
    parser.add_argument("--output", required=True, help="output JSON path")
    args = parser.parse_args()

    try:
        bundle = build_hitachi_profile_evidence_bundle(
            epitome_path=args.epitome,
            epit_hit_path=args.epit_hit,
            epit_hit2_path=args.epit_hit2,
            source_sha=args.source_sha,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output}")
    print(f"bundle_sha256={hitachi_bundle_digest(bundle)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
