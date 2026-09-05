#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from innaware_pms_emulator.hitachi_evidence_admission import (
    admit_hitachi_profile_evidence,
    validate_hitachi_profile_evidence_bundle,
)
from innaware_pms_emulator.hitachi_profile_evidence import (
    PRODUCER_REPOSITORY,
    hitachi_bundle_digest,
)


_SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_PROTOCOLS = ("EPIT-HIT", "EPIT-HIT2")


def _emit(payload: object, *, output: str | None = None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")
    print(f"wrote {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and admit a sanitized Hitachi profile evidence bundle without "
            "changing compatibility status or importing emulator runtime code into a consumer."
        )
    )
    parser.add_argument("--bundle", required=True, help="sanitized Hitachi evidence JSON bundle")
    parser.add_argument(
        "--expected-source-sha",
        required=True,
        help="exact 40-character emulator Git SHA recorded when the bundle was produced",
    )
    parser.add_argument(
        "--output",
        help="optional deterministic admission-report JSON path; stdout is used when omitted",
    )
    args = parser.parse_args()

    expected_sha = args.expected_source_sha.strip().casefold()
    if not _SHA40_RE.fullmatch(expected_sha):
        _emit({"error": "expected source SHA must be exactly 40 hexadecimal characters"})
        return 2

    try:
        bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    except OSError:
        _emit({"error": "evidence bundle could not be read"})
        return 2
    except json.JSONDecodeError:
        _emit({"error": "evidence bundle is not valid JSON"})
        return 2

    if not isinstance(bundle, dict):
        _emit({"error": "evidence bundle must be a JSON object"})
        return 2

    try:
        _, _, producer_sha = validate_hitachi_profile_evidence_bundle(bundle)
        if producer_sha != expected_sha:
            raise ValueError("producer.source_sha does not match --expected-source-sha")
        admissions = {
            protocol: admit_hitachi_profile_evidence(bundle, pms_protocol=protocol).as_dict()
            for protocol in _PROTOCOLS
        }
    except ValueError as exc:
        _emit({"error": str(exc)})
        return 2

    report = {
        "schema_version": 1,
        "sanitized": True,
        "data_only": True,
        "producer": {
            "repository": PRODUCER_REPOSITORY,
            "source_sha": producer_sha,
        },
        "bundle_sha256": hitachi_bundle_digest(bundle),
        "claim_policy": {
            "compatibility_promotion_authorized": False,
            "matrix_changes_require_separate_review": True,
            "runtime_dependency_on_emulator": False,
            "partial_or_planned_evidence_is_not_production_support": True,
        },
        "admissions": admissions,
    }
    _emit(report, output=args.output)
    if args.output is not None:
        print(f"bundle_sha256={report['bundle_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
