#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from innaware_pms_emulator.matrix_fias_live_acceptance import build_matrix_fias_live_acceptance


def _load(path: Path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(document, dict):
        captures = document.get("captures")
        if not isinstance(captures, list):
            raise ValueError("capture document must contain a captures list")
        return captures
    if isinstance(document, list):
        return document
    raise ValueError("capture document must be a JSON list or object with captures")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed Matrix SARVAM FIAS live-capture review artifact without changing compatibility claims."
    )
    parser.add_argument("capture", type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--transport", required=True, choices=("tcp",))
    parser.add_argument("--pbx-direction", required=True, choices=("rx", "tx"))
    parser.add_argument("--evidence-class", required=True)
    parser.add_argument("--evidence-origin", required=True)
    parser.add_argument("--matrix-model", required=True)
    parser.add_argument("--matrix-version", required=True)
    parser.add_argument("--local-endpoint", required=True)
    parser.add_argument("--remote-endpoint", required=True)
    parser.add_argument("--tcp-initiator", required=True, choices=("pbx", "pms"))
    parser.add_argument("--operator-authorized", action="store_true")
    parser.add_argument("--synthetic-or-redacted", action="store_true")
    parser.add_argument("--no-guest-pii", action="store_true")
    parser.add_argument("--source-material-synthetic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = build_matrix_fias_live_acceptance(
            _load(args.capture),
            source_sha=args.source_sha,
            transport=args.transport,
            pbx_direction=args.pbx_direction,
            evidence_class=args.evidence_class,
            evidence_origin=args.evidence_origin,
            matrix_model=args.matrix_model,
            matrix_version=args.matrix_version,
            local_endpoint=args.local_endpoint,
            remote_endpoint=args.remote_endpoint,
            tcp_initiator=args.tcp_initiator,
            operator_authorized=args.operator_authorized,
            synthetic_or_redacted=args.synthetic_or_redacted,
            no_guest_pii=args.no_guest_pii,
            source_material_synthetic=args.source_material_synthetic,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
