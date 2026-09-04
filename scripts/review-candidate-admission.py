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

from innaware_pms_emulator.candidate_admission_review import (
    build_candidate_admission_review,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review one pre-admission candidate-observation JSON artifact against the "
            "current fail-closed evidence gate. This command never registers a matrix "
            "row, promotes compatibility, or sends traffic."
        )
    )
    parser.add_argument(
        "candidate",
        help="Candidate-observation JSON created by record-candidate-observation.py.",
    )
    parser.add_argument(
        "--expected-source-sha",
        required=True,
        help="Exact 40-character Emulator SHA that must match the candidate artifact.",
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
        candidate_path = Path(args.candidate)
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        review = build_candidate_admission_review(
            candidate,
            expected_source_sha=args.expected_source_sha,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    encoded = json.dumps(review, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        sys.stdout.write(encoded)
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
