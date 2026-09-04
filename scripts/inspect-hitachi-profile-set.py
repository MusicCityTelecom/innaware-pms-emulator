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

from innaware_pms_emulator.hitachi_profile_intake import build_hitachi_profile_intake


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the exact Epitome/EPIT-HIT/EPIT-HIT2 profile set in place and "
            "write a deterministic sanitized intake report without copying raw profiles."
        )
    )
    parser.add_argument("--source-sha", required=True, help="exact 40-character emulator Git SHA")
    parser.add_argument(
        "--profile-dir",
        required=True,
        help="directory containing psip-pbx-protocol.Epitome, EPIT-HIT, and EPIT-HIT2",
    )
    parser.add_argument("--output", required=True, help="sanitized JSON report path")
    args = parser.parse_args()

    try:
        report = build_hitachi_profile_intake(
            profile_dir=args.profile_dir,
            source_sha=args.source_sha,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output}")
    print(f"evidence_bundle_sha256={report['evidence_bundle_sha256']}")
    for protocol, admission in report["admissions"].items():
        print(
            f"{protocol}: observed_transport={admission['observed_transport']} "
            f"matrix_change_required={str(admission['matrix_change_required']).lower()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
