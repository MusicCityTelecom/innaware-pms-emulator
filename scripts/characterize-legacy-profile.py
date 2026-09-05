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

from innaware_pms_emulator.legacy_profile_evidence import characterize_legacy_profile_file


def _safe_error(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "profile could not be read"
    return str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a sanitized interoperability summary from authorized textual "
            "Voiceware/PSIP legacy PBX profile files."
        )
    )
    parser.add_argument("profiles", nargs="+", help="legacy profile file(s) to inspect read-only")
    parser.add_argument(
        "--include-record-layouts",
        action="store_true",
        help=(
            "include exact values for recognized protocol record keys and bounded "
            "[pbx-masks] room/name layout keys; leave off for the safest metadata-only "
            "characterization"
        ),
    )
    args = parser.parse_args()

    results: list[dict[str, object]] = []
    failed = False
    for raw_path in args.profiles:
        path = Path(raw_path)
        try:
            evidence = characterize_legacy_profile_file(
                path,
                include_record_layouts=args.include_record_layouts,
            )
        except (OSError, ValueError) as exc:
            failed = True
            results.append(
                {
                    "source_name": path.name,
                    "error": _safe_error(exc),
                }
            )
            continue
        results.append(evidence.as_dict())

    json.dump(results, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
