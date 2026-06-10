from __future__ import annotations

import json
from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown


REQUIRED_CATEGORIES = {
    "agent-loop",
    "planning-task-decomposition",
    "context-delivery-compaction",
    "tool-design",
    "skills-mcp",
    "permissions-authorization",
    "memory-state",
    "task-runners-orchestration",
    "verification-ci",
    "observability-tracing",
    "debugging-developer-experience",
    "human-in-the-loop",
    "security-sandbox-permissions",
    "evals-verification",
}


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _contains(path: Path, patterns: list[str]) -> bool:
    text = read_text(path)
    return all(pattern in text for pattern in patterns)


def evaluate_harness_reference(project_root: Path) -> dict[str, object]:
    taxonomy_path = project_root / ".harness" / "references" / "awesome-harness-engineering.json"
    taxonomy = _read_json(taxonomy_path)
    categories = taxonomy.get("categories", [])
    category_ids = {
        str(category.get("id"))
        for category in categories
        if isinstance(category, dict)
    }
    categories_without_artifacts = [
        str(category.get("id"))
        for category in categories
        if isinstance(category, dict) and not category.get("current_artifacts")
    ]

    plan_template = project_root / ".harness" / "templates" / "PLAN.md"
    implement_template = project_root / ".harness" / "templates" / "IMPLEMENT.md"
    checklist_template = project_root / ".harness" / "templates" / "HARNESS_CHECKLIST.md"
    agents_template = project_root / ".harness" / "templates" / "AGENTS.md"

    results = [
        _result(
            "reference_taxonomy_exists",
            "External harness taxonomy exists with source metadata",
            taxonomy.get("schema_version") == 1
            and taxonomy.get("source") == "https://github.com/ai-boost/awesome-harness-engineering"
            and REQUIRED_CATEGORIES.issubset(category_ids),
            [".harness/references/awesome-harness-engineering.json"],
            "\n".join(sorted(REQUIRED_CATEGORIES - category_ids)),
        ),
        _result(
            "reference_categories_have_current_artifacts",
            "All external taxonomy categories map to current project artifacts",
            not categories_without_artifacts and len(categories) >= len(REQUIRED_CATEGORIES),
            [".harness/references/awesome-harness-engineering.json"],
            "\n".join(categories_without_artifacts),
        ),
        _result(
            "awesome_templates_adapted",
            "Awesome Harness templates are adapted for Paralls",
            _contains(plan_template, ["Milestones", "verify:"])
            and _contains(implement_template, ["Implementation log", "Deviation"])
            and _contains(checklist_template, ["Tool permissions", "Verification Loop", "Removal Criteria"])
            and _contains(agents_template, ["Tool Permissions", "Verification Gates"]),
            [
                ".harness/templates/PLAN.md",
                ".harness/templates/IMPLEMENT.md",
                ".harness/templates/HARNESS_CHECKLIST.md",
                ".harness/templates/AGENTS.md",
            ],
        ),
        _result(
            "reference_docs_updated",
            "Harness docs describe the adapted external reference coverage",
            _contains(project_root / "docs" / "harness.md", ["awesome-harness-engineering", "harness-reference"])
            and _contains(project_root / "docs" / "harness-architecture.md", ["reference taxonomy", ".harness/references"])
            and _contains(project_root / "docs" / "harness-reliability.md", ["HARNESS_CHECKLIST", "reference coverage"]),
            ["docs/harness.md", "docs/harness-architecture.md", "docs/harness-reliability.md"],
        ),
    ]
    return {
        "results": results,
        "overall_harness_reference_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_harness_reference(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "harness-reference-report.json"
    md_path = log_dir / "harness-reference-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Harness Reference Verification Report", report, "overall_harness_reference_passed")

    print(f"harness_reference_report_json={json_path}")
    print(f"harness_reference_report_md={md_path}")
    print(f"overall_harness_reference_passed={report['overall_harness_reference_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_harness_reference_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
