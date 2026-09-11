#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from innaware_pms_emulator.compatibility_matrix import Direction, SupportStatus
from innaware_pms_emulator.technician_acceptance import build_technician_acceptance_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic technician acceptance plan for exact PMS-PBX "
            "compatibility rows without executing traffic or promoting claims."
        )
    )
    parser.add_argument(
        "--source-sha",
        required=True,
        help="Exact 40-character Git SHA for the emulator revision under acceptance.",
    )
    parser.add_argument("--pbx-family", help="Optional exact PBX-family filter.")
    parser.add_argument("--transport", help="Optional exact transport filter.")
    parser.add_argument("--pms-protocol", help="Optional exact PMS-protocol filter.")
    parser.add_argument(
        "--direction",
        choices=[item.value for item in Direction],
        help="Optional exact direction filter.",
    )
    parser.add_argument(
        "--status",
        action="append",
        choices=[item.value for item in SupportStatus],
        help="Optional support-status filter; repeat to include multiple statuses.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path, or '-' for stdout (default).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        plan = build_technician_acceptance_plan(
            source_sha=args.source_sha,
            pbx_family=args.pbx_family,
            transport=args.transport,
            pms_protocol=args.pms_protocol,
            direction=args.direction,
            statuses=args.status,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    encoded = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        sys.stdout.write(encoded)
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
