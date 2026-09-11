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

from innaware_pms_emulator.interop_evidence_pack import build_interop_evidence_pack


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build the deterministic, data-only PMS-PBX interoperability evidence pack "
            "for use by separate consumers without importing emulator runtime code."
        )
    )
    parser.add_argument(
        "--source-sha",
        required=True,
        help="Exact 40-character Git SHA for the emulator revision that produced the evidence pack.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path, or '-' for stdout (default).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    pack = build_interop_evidence_pack(repo_root=REPO_ROOT, source_sha=args.source_sha)
    encoded = json.dumps(pack, indent=2, sort_keys=True) + "\n"

    if args.output == "-":
        sys.stdout.write(encoded)
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
