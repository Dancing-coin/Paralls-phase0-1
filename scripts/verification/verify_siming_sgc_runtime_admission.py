from __future__ import annotations

import json
import os
import subprocess
import sys

from verify_phase3_common import root
from verify_population_continuous_runtime import backend_report, test_evidence


def main() -> int:
    name = "siming-sgc-runtime-admission"
    report = test_evidence(name, (
        "test_siming_population_capability.py", "test_siming_population_decision_routing.py",
        "test_siming_population_domain_owner_matrix.py", "test_siming_population_production_boundaries.py",
        "test_siming_population_inventory_vertical.py", "test_siming_population_social_signal_vertical.py",
        "test_siming_population_authorized_cadence_publication.py",
    ))
    command = [sys.executable, str(root() / "scripts/verification/verify_siming_population_domain_owner_adaptation.py")]
    result = subprocess.run(command, cwd=root(), env=dict(os.environ, PARALLS_HEAVENLY_GRAPH_PATH=":memory:"),
                            capture_output=True, text=True)
    report["owner_verifier"] = {"command": command, "exit_code": result.returncode,
                                "output": result.stdout + result.stderr}
    # 仅在本轮成功后读取下游报告，避免旧绿色证据掩盖失败。
    owner_report = {}
    if result.returncode == 0:
        path = root() / ".harness/verification/siming-population-domain-owner-adaptation-report.json"
        owner_report = json.loads(path.read_text(encoding="utf-8"))
    report["owner_admission"] = owner_report
    report["overall_passed"] = bool(report["overall_passed"] and owner_report.get("overall_passed"))
    return backend_report(name, report)


if __name__ == "__main__":
    raise SystemExit(main())
