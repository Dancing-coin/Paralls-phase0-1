from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "backend/tests/test_construction_production_generic_content.py",
        "backend/tests/test_production_output_certification_family.py",
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    report = {
        "profile": "construction-production-generic-content",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "overall_passed": completed.returncode == 0,
    }
    output = root / ".harness" / "verification" / "construction-production-generic-content-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"construction_production_generic_content_report_json={output}")
    print(f"overall_construction_production_generic_content_passed={report['overall_passed']}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
