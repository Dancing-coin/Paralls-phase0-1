from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_recipe_production_content_schema.py",
        "backend/tests/test_recipe_production_descriptor_binding.py",
        "backend/tests/test_recipe_production_construction.py",
    ]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "recipe-production-family",
        "family_ref": "recipe_production@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Construction remains sole recipe production owner",
            "strict immutable typed recipe content only",
            "two semantically distinct immutable package contents activate and settle through the same family adapter",
            "fixed source/stream/event/privacy/revision and owner-derived idempotency",
            "append-derived receipt with full and checkpoint-tail replay",
            "historical narrow production rows remain unchanged",
            "no Inventory custody, payment, generic writer, or arbitrary cross-domain vector",
        ],
        "genericity_evidence": {
            "dual_content_test": "backend/tests/test_recipe_production_construction.py::test_recipe_production_adapter_supports_two_immutable_contents_via_same_family",
            "active_package_revisions": [
                "package:recipe-production-demo:v1",
                "package:recipe-production-kiln:v1",
            ],
            "committed_manifest_paths": [
                "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/recipe-production/package-recipe-production-demo-v1.manifest.json",
                "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/recipe-production/package-recipe-production-kiln-v1.manifest.json",
            ],
        },
    }
    artifact = ROOT / ".harness" / "verification" / "recipe-production-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"recipe_production_family_report_json={artifact}")
    print(f"overall_recipe_production_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
