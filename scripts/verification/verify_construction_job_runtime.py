from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    command = [sys.executable, "-m", "pytest", "-q", "backend/tests/test_construction_job_runtime.py"]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    report = {
        "profile": "construction-job-runtime",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "overall_passed": completed.returncode == 0,
    }
    output = root / ".harness" / "verification" / "construction-job-runtime-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"construction_job_runtime_report_json={output}")
    print(f"overall_construction_job_runtime_passed={report['overall_passed']}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
