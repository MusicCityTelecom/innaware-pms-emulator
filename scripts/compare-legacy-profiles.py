#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from innaware_pms_emulator.legacy_profile_compare import compare_legacy_profile_evidence
from innaware_pms_emulator.legacy_profile_evidence import characterize_legacy_profile_file


def _safe_error(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "profile could not be read"
    return str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare authorized textual Voiceware/PSIP legacy PBX profiles and emit "
            "only sanitized interoperability deltas."
        )
    )
    parser.add_argument("baseline", help="baseline legacy profile to inspect read-only")
    parser.add_argument(
        "candidates",
        nargs="+",
        help="one or more candidate/variant legacy profiles to compare against the baseline",
    )
    parser.add_argument(
        "--include-record-layouts",
        action="store_true",
        help=(
            "compare exact values for recognized protocol record keys and bounded "
            "[pbx-masks] room/name layout keys; leave off to compare only safe key "
            "membership and other default characterization metadata"
        ),
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    try:
        baseline = characterize_legacy_profile_file(
            baseline_path,
            include_record_layouts=args.include_record_layouts,
        )
    except (OSError, ValueError) as exc:
        json.dump(
            {
                "baseline": baseline_path.name,
                "error": _safe_error(exc),
                "comparisons": [],
            },
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
        return 2

    comparisons: list[dict[str, object]] = []
    failed = False
    for raw_path in args.candidates:
        candidate_path = Path(raw_path)
        try:
            candidate = characterize_legacy_profile_file(
                candidate_path,
                include_record_layouts=args.include_record_layouts,
            )
            delta = compare_legacy_profile_evidence(baseline, candidate)
        except (OSError, ValueError) as exc:
            failed = True
            comparisons.append(
                {
                    "candidate_source_name": candidate_path.name,
                    "error": _safe_error(exc),
                }
            )
            continue
        comparisons.append(delta.as_dict())

    json.dump(
        {
            "baseline": {
                "source_name": baseline.source_name,
                "sha256": baseline.sha256,
                "evidence_class": baseline.evidence_class,
            },
            "comparisons": comparisons,
        },
        sys.stdout,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
