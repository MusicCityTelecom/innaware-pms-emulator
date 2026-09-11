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

from innaware_pms_emulator.candidate_observation_result import (
    CANDIDATE_OBSERVATION_CODES,
    CandidateObservationStatus,
    build_candidate_observation_result,
)
from innaware_pms_emulator.compatibility_matrix import Direction, EvidenceClass
from innaware_pms_emulator.technician_evidence_result import EvidenceOrigin


def _fact(value: str) -> tuple[str, str]:
    key, separator, raw = value.partition("=")
    key = key.strip()
    raw = raw.strip()
    if not separator or not key or not raw:
        raise argparse.ArgumentTypeError("transport facts must use non-empty key=value syntax")
    return key, raw


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record deterministic pre-admission evidence for exactly one unregistered "
            "PBX/PMS compatibility combination. This command never sends traffic, "
            "registers a matrix row, or promotes compatibility."
        )
    )
    parser.add_argument(
        "--source-sha",
        required=True,
        help="Exact 40-character Emulator Git SHA used during the observation.",
    )
    parser.add_argument("--pbx-family", required=True)
    parser.add_argument("--pbx-dialect", required=True)
    parser.add_argument(
        "--transport",
        required=True,
        choices=("tcp", "serial"),
        help="Explicit evidence-qualified wire transport; unknown is intentionally rejected.",
    )
    parser.add_argument("--pms-family", required=True)
    parser.add_argument("--pms-protocol", required=True)
    parser.add_argument(
        "--direction",
        required=True,
        choices=[item.value for item in Direction],
    )
    parser.add_argument(
        "--result",
        required=True,
        choices=[item.value for item in CandidateObservationStatus],
        help="Candidate observation outcome. There is deliberately no PASS status.",
    )
    parser.add_argument(
        "--evidence-class",
        required=True,
        choices=[
            item.value
            for item in EvidenceClass
            if item not in {EvidenceClass.INFERENCE, EvidenceClass.NONE}
        ],
    )
    parser.add_argument(
        "--transport-fact",
        action="append",
        type=_fact,
        default=[],
        metavar="KEY=VALUE",
        help="Exact transport fact for this capture; repeat for every required fact.",
    )
    parser.add_argument(
        "--evidence-origin",
        required=True,
        choices=[
            item.value
            for item in EvidenceOrigin
            if item is not EvidenceOrigin.UNSPECIFIED
        ],
    )
    parser.add_argument("--pbx-model")
    parser.add_argument("--pbx-firmware")
    parser.add_argument("--pms-product")
    parser.add_argument("--pms-version")
    parser.add_argument(
        "--observation",
        action="append",
        choices=sorted(CANDIDATE_OBSERVATION_CODES),
        default=[],
        help="Normalized candidate observation code; repeat as needed.",
    )
    parser.add_argument(
        "--wire-artifact-sha256",
        action="append",
        default=[],
        help="SHA-256 of sanitized/synthetic wire evidence; raw bytes are not embedded.",
    )
    parser.add_argument(
        "--diagnostic-report-sha256",
        action="append",
        default=[],
        help="Optional SHA-256 of a payload-safe diagnostic report; repeat as needed.",
    )
    parser.add_argument("--candidate-diagnostics-tests-passed", action="store_true")
    parser.add_argument("--exact-head-test-matrix-green", action="store_true")
    parser.add_argument("--exact-head-windows-build-green", action="store_true")
    parser.add_argument(
        "--operator-authorized",
        action="store_true",
        help="Confirm the lab/test endpoint was explicitly authorized.",
    )
    parser.add_argument(
        "--synthetic-or-redacted-wire-bytes",
        action="store_true",
        help="Confirm referenced reusable wire evidence is synthetic or redacted.",
    )
    parser.add_argument(
        "--no-guest-pii",
        action="store_true",
        help="Confirm no guest PII is present in reusable evidence.",
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
        transport_facts = dict(args.transport_fact)
        if len(transport_facts) != len(args.transport_fact):
            raise ValueError("transport facts may not repeat the same key")

        endpoint_provenance = {"evidence_origin": args.evidence_origin}
        optional_provenance = {
            "pbx_model": args.pbx_model,
            "pbx_firmware": args.pbx_firmware,
            "pms_product": args.pms_product,
            "pms_version": args.pms_version,
        }
        endpoint_provenance.update(
            {key: value for key, value in optional_provenance.items() if value is not None}
        )

        result = build_candidate_observation_result(
            source_sha=args.source_sha,
            pbx_family=args.pbx_family,
            pbx_dialect=args.pbx_dialect,
            transport=args.transport,
            pms_family=args.pms_family,
            pms_protocol=args.pms_protocol,
            direction=args.direction,
            result_status=args.result,
            evidence_class=args.evidence_class,
            transport_facts=transport_facts,
            endpoint_provenance=endpoint_provenance,
            observation_codes=args.observation,
            wire_artifact_sha256s=args.wire_artifact_sha256,
            diagnostic_report_sha256s=args.diagnostic_report_sha256,
            candidate_diagnostics_tests_passed=args.candidate_diagnostics_tests_passed,
            exact_head_test_matrix_green=args.exact_head_test_matrix_green,
            exact_head_windows_build_green=args.exact_head_windows_build_green,
            operator_authorized=args.operator_authorized,
            synthetic_or_redacted_wire_bytes=args.synthetic_or_redacted_wire_bytes,
            guest_pii_present=not args.no_guest_pii,
        )
    except (TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        sys.stdout.write(encoded)
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
