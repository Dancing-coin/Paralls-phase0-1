"""Focused evidence runner for the federated Organization/Government/Social platform."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = (
        "backend/tests/test_organization_government_social_manifest_v3.py",
        "backend/tests/test_organization_government_social_content.py",
        "backend/tests/test_organization_government_social_catalog.py",
        "backend/tests/test_organization_government_social_event_schema.py",
        "backend/tests/test_organization_government_social_descriptor_binding.py",
        "backend/tests/test_organization_government_social_platform_runtime.py",
        "backend/tests/test_organization_government_social_recipes.py",
        "backend/tests/test_organization_government_social_presentation.py",
        "backend/tests/test_organization_government_social_content_matrix.py",
        "backend/tests/test_organization_government_social_family_matrix.py",
        "backend/tests/test_organization_government_social_family_success_matrix.py",
        "backend/tests/test_organization_government_social_recipe_acceptance.py",
    )
    result = subprocess.run((sys.executable, "-m", "pytest", "-q", *tests), cwd=ROOT, check=False)
    report = {
        "overall_organization_government_social_platform_passed": result.returncode == 0,
        "scope": "v3/2.0 typed content, immutable owner-bound contracts, source-controlled events, Population signal-only boundary, owner-local projection and full/checkpoint-tail replay.",
        "tests": tests,
        "exit_code": result.returncode,
    }
    output = ROOT / ".harness" / "verification" / "organization-government-social-generic-platform-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"organization_government_social_generic_platform_report={output}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
