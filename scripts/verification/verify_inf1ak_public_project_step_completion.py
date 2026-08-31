from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    test_file = ROOT / "backend" / "tests" / "test_inf1ak_public_project_step_completion.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(test_file), "--basetemp=.pytest-tmp/harness-inf1ak"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf1ak-public-project-step-completion",
        "row": "exact Organization public-project work-order fulfillment -> Construction project-step completion",
        "focused_tests": str(test_file.relative_to(ROOT)).replace("\\", "/"),
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "one existing Construction owner",
            "one literal public-project work-order source",
            "facility/project binding",
            "source/target stream revision pins",
            "project privacy and append-derived receipt",
            "owner-derived idempotency",
            "full/checkpoint-tail replay",
            "terminal no-reopen/no-compensation",
            "no generic task/payment/material/output semantics",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf1ak-public-project-step-completion-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf1ak_report_json={artifact}")
    print(f"overall_inf1ak_public_project_step_completion_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
