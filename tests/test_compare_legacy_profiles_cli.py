import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare-legacy-profiles.py"


def test_compare_cli_reports_only_sanitized_delta(tmp_path):
    baseline = tmp_path / "psip-pbx-protocol.EPIT-HIT"
    candidate = tmp_path / "psip-pbx-protocol.EPIT-HIT2"
    baseline.write_text(
        "[pbx-protocol]\n"
        "protocol=EPIT-HIT\n"
        "site_secret=never-emit-base\n"
        "[pbx-masks]\n"
        "namroom=8 3 MASK_NUMBER\n"
        "namname=11 20 MASK_LITERAL\n",
        encoding="utf-8",
    )
    candidate.write_text(
        "[pbx-protocol]\n"
        "protocol=EPIT-HIT2\n"
        "site_secret=never-emit-candidate\n"
        "[pbx-masks]\n"
        "namroom=4 3 MASK_NUMBER\n"
        "namname=7 20 MASK_LITERAL\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--include-record-layouts",
            str(baseline),
            str(candidate),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["baseline"]["source_name"] == "psip-pbx-protocol.EPIT-HIT"
    assert len(payload["comparisons"]) == 1
    delta = payload["comparisons"][0]
    assert delta["candidate_source_name"] == "psip-pbx-protocol.EPIT-HIT2"
    assert delta["record_mask_layout_changes"] == {
        "NAMNAME": {
            "baseline": "11 20 MASK_LITERAL",
            "candidate": "7 20 MASK_LITERAL",
        },
        "NAMROOM": {
            "baseline": "8 3 MASK_NUMBER",
            "candidate": "4 3 MASK_NUMBER",
        },
    }
    assert "never-emit" not in result.stdout


def test_compare_cli_fails_closed_when_baseline_is_missing(tmp_path):
    missing = tmp_path / "missing-profile"
    candidate = tmp_path / "candidate"
    candidate.write_text("[pbx-protocol]\nprotocol=SYNTHETIC\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing), str(candidate)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["baseline"] == "missing-profile"
    assert payload["comparisons"] == []
    assert "error" in payload
