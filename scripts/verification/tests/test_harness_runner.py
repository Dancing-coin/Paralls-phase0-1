from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import _write_harness_report


def test_write_harness_report_outputs_json_and_markdown(tmp_path: Path) -> None:
    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "boundaries",
                "command": ["python", "scripts/verification/check_boundaries.py"],
                "exit_code": 0,
            }
        ],
        overall_passed=True,
    )

    payload = json.loads(report_paths["json"].read_text(encoding="utf-8"))
    assert payload["overall_harness_passed"] is True
    assert payload["profiles"][0]["profile"] == "boundaries"
    assert payload["profiles"][0]["exit_code"] == 0
    assert report_paths["markdown"].read_text(encoding="utf-8").startswith("# Harness Run Report")
    assert report_paths["manifest"].exists()
    assert report_paths["baseline"].exists()
    assert report_paths["diff"].exists()


def test_write_harness_report_records_previous_run_diff(tmp_path: Path) -> None:
    _write_harness_report(
        tmp_path,
        [
            {
                "profile": "docs",
                "command": ["python", "scripts/verification/check_docs.py"],
                "exit_code": 0,
            }
        ],
        overall_passed=True,
        run_id="run_previous",
    )

    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "docs",
                "command": ["python", "scripts/verification/check_docs.py"],
                "exit_code": 1,
            }
        ],
        overall_passed=False,
        run_id="run_current",
    )

    diff = json.loads(report_paths["diff"].read_text(encoding="utf-8"))

    assert diff["previous_run_id"] == "run_previous"
    assert diff["current_run_id"] == "run_current"
    assert diff["overall_changed"] is True
    assert diff["profile_exit_code_changes"] == [
        {
            "profile": "docs",
            "previous_exit_code": 0,
            "current_exit_code": 1,
        }
    ]


def test_write_harness_report_default_run_ids_do_not_collide(tmp_path: Path) -> None:
    first_paths = _write_harness_report(
        tmp_path,
        [{"profile": "docs", "command": ["python", "check_docs.py"], "exit_code": 0}],
        overall_passed=True,
    )
    second_paths = _write_harness_report(
        tmp_path,
        [{"profile": "drift", "command": ["python", "check_drift.py"], "exit_code": 0}],
        overall_passed=True,
    )

    assert first_paths["run_dir"] != second_paths["run_dir"]
