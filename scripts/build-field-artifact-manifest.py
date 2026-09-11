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

from innaware_pms_emulator.field_candidate_artifacts import ArtifactManifestError, build_field_artifact_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed exact-SHA artifact manifest for an InnAware PMS Emulator Windows candidate"
    )
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = build_field_artifact_manifest(source_sha=args.source_sha, artifact_zip=args.artifact_zip)
    except ArtifactManifestError as exc:
        print(f"artifact manifest rejected: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "source_sha": result["source_sha"],
                "application_version": result["application_version"],
                "artifact_bundle_sha256": result["artifacts"]["artifact_bundle"]["sha256"],
                "field_executable_sha256": result["artifacts"]["field_executable"]["sha256"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
