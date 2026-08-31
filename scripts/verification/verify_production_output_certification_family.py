from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_production_output_certification_family.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "production-output-certification-family",
        "family_ref": "production_output_certification@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Construction remains sole certification owner",
            "typed package recipe/output/quantity slots only",
            "committed project-visible run_finished source and exact revision fence",
            "separate production_output_certified@1 event and reducer",
            "owner-derived idempotency, append-derived receipt, full/checkpoint-tail replay",
            "no Inventory custody, payment, transfer, compensation, or generic writer",
            "historical mill_flour_output_certified@1 row remains unchanged",
        ],
        "genericity_evidence": {
            "dual_content_test": "backend/tests/test_production_output_certification_family.py::test_output_certification_family_consumes_multiple_admitted_content_instances_through_one_adapter",
            "active_package_revisions": [
                "package:output-certification-demo@1",
                "package:output-certification-mill-demo@1",
            ],
            "committed_manifest_paths": [
                "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/production-output-certification/package-production-output-certification-demo-v1.manifest.json",
                "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/production-output-certification/package-production-output-certification-mill-demo-v1.manifest.json",
            ],
        },
    }
    artifact = ROOT / ".harness" / "verification" / "production-output-certification-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"production_output_certification_family_report_json={artifact}")
    print(f"overall_production_output_certification_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
