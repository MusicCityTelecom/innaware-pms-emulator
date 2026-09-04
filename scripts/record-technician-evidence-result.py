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

from innaware_pms_emulator.technician_evidence_result import (
    AcceptanceResultStatus,
    EvidenceOrigin,
    OBSERVATION_CODES,
    build_technician_evidence_result,
)


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
            "Record a deterministic technician/Codex evidence result for exactly one "
            "pre-built PMS-PBX acceptance-plan row. No traffic is generated and no "
            "compatibility claim is promoted."
        )
    )
    parser.add_argument(
        "--source-sha",
        required=True,
        help="Exact 40-character emulator Git SHA used to build the acceptance plan.",
    )
    parser.add_argument(
        "--plan",
        required=True,
        help="Path to a technician acceptance-plan JSON containing exactly one matrix row.",
    )
    parser.add_argument(
        "--result",
        required=True,
        choices=[item.value for item in AcceptanceResultStatus],
        help="Observed acceptance outcome.",
    )
    parser.add_argument(
        "--transport-fact",
        action="append",
        type=_fact,
        default=[],
        metavar="KEY=VALUE",
        help="Exact transport fact required by the plan; repeat for every required fact.",
    )
    parser.add_argument(
        "--evidence-origin",
        choices=[item.value for item in EvidenceOrigin],
        default=EvidenceOrigin.UNSPECIFIED.value,
        help=(
            "Provenance class for this observation. Pass results must explicitly identify "
            "synthetic replay, emulator lab, real PBX lab, real PMS lab, or both real endpoints."
        ),
    )
    parser.add_argument("--pbx-model", help="Real PBX model; required for real_pbx_lab origins.")
    parser.add_argument("--pbx-firmware", help="Real PBX firmware/version; required for real_pbx_lab origins.")
    parser.add_argument("--pms-product", help="Real PMS product; required for real_pms_lab origins.")
    parser.add_argument("--pms-version", help="Real PMS version; required for real_pms_lab origins.")
    parser.add_argument(
        "--observation",
        action="append",
        choices=sorted(OBSERVATION_CODES),
        default=[],
        help="Normalized observation code; repeat as needed.",
    )
    parser.add_argument(
        "--wire-artifact-sha256",
        action="append",
        default=[],
        help="SHA-256 of a sanitized/synthetic wire artifact; repeat as needed. Raw bytes are not embedded.",
    )
    parser.add_argument("--deterministic-tests-passed", action="store_true")
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
        help="Confirm the referenced reusable evidence contains only synthetic/redacted wire bytes.",
    )
    parser.add_argument(
        "--no-guest-pii",
        action="store_true",
        help="Confirm no guest PII is present in the reusable evidence.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path, or '-' for stdout (default).",
    )
    return parser


def _load_plan(path: str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("unable to read a valid acceptance-plan JSON document") from exc
    if not isinstance(value, dict):
        raise ValueError("acceptance plan must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        plan = _load_plan(args.plan)
        transport_facts = dict(args.transport_fact)
        if len(transport_facts) != len(args.transport_fact):
            raise ValueError("transport facts may not repeat the same key")
        endpoint_provenance = {
            "evidence_origin": args.evidence_origin,
        }
        optional_provenance = {
            "pbx_model": args.pbx_model,
            "pbx_firmware": args.pbx_firmware,
            "pms_product": args.pms_product,
            "pms_version": args.pms_version,
        }
        endpoint_provenance.update(
            {key: value for key, value in optional_provenance.items() if value is not None}
        )
        result = build_technician_evidence_result(
            source_sha=args.source_sha,
            acceptance_plan=plan,
            result_status=args.result,
            transport_facts=transport_facts,
            endpoint_provenance=endpoint_provenance,
            observation_codes=args.observation,
            wire_artifact_sha256s=args.wire_artifact_sha256,
            deterministic_tests_passed=args.deterministic_tests_passed,
            exact_head_test_matrix_green=args.exact_head_test_matrix_green,
            exact_head_windows_build_green=args.exact_head_windows_build_green,
            operator_authorized=args.operator_authorized,
            synthetic_or_redacted_wire_bytes=args.synthetic_or_redacted_wire_bytes,
            guest_pii_present=not args.no_guest_pii,
        )
    except (ValueError, TypeError) as exc:
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
