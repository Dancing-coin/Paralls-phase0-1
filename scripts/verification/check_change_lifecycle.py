from __future__ import annotations

import json
from pathlib import Path

from check_change_state import evaluate_change_state
from common import read_text, repo_root, verification_dir, write_json, write_markdown
from registry import load_profile_registry, load_rule_registry, rule_evidence_map


REQUIRED_RULE_IDS = {
    "workflow_doc_exists",
    "change_lifecycle_profile_registered",
    "openspec_superpowers_harness_goal_chain_documented",
    "goal_owns_project_workflow_state",
    "workflow_templates_gate_execution",
    "agents_entry_map_routes_goal_superpowers_native_subagents",
    "archived_changes_have_state_closure",
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


def evaluate_change_lifecycle(project_root: Path) -> dict[str, object]:
    workflow_doc = project_root / "docs" / "ai-engineering-workflow.md"
    workflow_text = read_text(workflow_doc)
    agents_md = project_root / "AGENTS.md"
    agents_text = read_text(agents_md)
    plan_template = project_root / ".harness" / "templates" / "PLAN.md"
    implement_template = project_root / ".harness" / "templates" / "IMPLEMENT.md"
    checklist_template = project_root / ".harness" / "templates" / "HARNESS_CHECKLIST.md"
    profile_manifest = project_root / ".harness" / "profiles" / "change-lifecycle.json"
    rule_manifest = project_root / ".harness" / "rules" / "change-lifecycle-rules.json"
    design_spec = project_root / "docs" / "superpowers" / "specs" / "2026-06-10-ai-engineering-workflow-integration-design.md"
    implementation_plan = project_root / "docs" / "superpowers" / "plans" / "2026-06-10-ai-engineering-workflow-integration-implementation-plan.md"
    change_state_report = evaluate_change_state(project_root)

    profile_registry = load_profile_registry(project_root)
    rule_registry = load_rule_registry(project_root)
    rule_mapping = rule_evidence_map(rule_registry)
    profile_payload = _read_json(profile_manifest)
    rule_payload = _read_json(rule_manifest)
    manifest_rule_ids = {
        str(rule.get("id"))
        for rule in rule_payload.get("rules", [])
        if isinstance(rule, dict)
    }

    results = [
        _result(
            "workflow_doc_exists",
            "AI engineering workflow doc and matching design/plan artifacts exist",
            workflow_doc.exists()
            and design_spec.exists()
            and implementation_plan.exists()
            and _contains(workflow_doc, ["OpenSpec", "Superpowers", "Harness", "Goal", "native subagents", "change-lifecycle"]),
            [
                "docs/ai-engineering-workflow.md",
                "docs/superpowers/specs/2026-06-10-ai-engineering-workflow-integration-design.md",
                "docs/superpowers/plans/2026-06-10-ai-engineering-workflow-integration-implementation-plan.md",
            ],
        ),
        _result(
            "change_lifecycle_profile_registered",
            "change-lifecycle profile and rule manifest are registered",
            profile_payload.get("schema_version") == 1
            and profile_payload.get("name") == "change-lifecycle"
            and profile_payload.get("script") == "scripts/verification/check_change_lifecycle.py"
            and profile_payload.get("requires_godot") is False
            and "change-lifecycle" in profile_registry.profile_order
            and rule_payload.get("schema_version") == 1
            and rule_payload.get("profile") == "change-lifecycle"
            and REQUIRED_RULE_IDS.issubset(manifest_rule_ids)
            and all(f"change-lifecycle.{rule_id}" in rule_mapping for rule_id in REQUIRED_RULE_IDS),
            [".harness/profiles/change-lifecycle.json", ".harness/rules/change-lifecycle-rules.json"],
            "\n".join(sorted(REQUIRED_RULE_IDS - manifest_rule_ids)),
        ),
        _result(
            "openspec_superpowers_harness_goal_chain_documented",
            "OpenSpec, Superpowers, Harness, and Goal handoff chain is documented",
            all(
                marker in workflow_text
                for marker in [
                    "OpenSpec controls what changes",
                    "Superpowers controls how changes are executed",
                    "Harness controls whether the result is accepted",
                    "Goal tracks long-running execution state",
                    "python scripts/verification/harness.py --profile all",
                    "verification-before-completion",
                ]
            ),
            ["docs/ai-engineering-workflow.md"],
        ),
        _result(
            "goal_owns_project_workflow_state",
            "Goal owns active project workflow continuity",
            all(
                marker in workflow_text
                for marker in [
                    "Goal is the long-running objective ledger",
                    "durable acceptance evidence in `.harness`",
                    "create_goal",
                    "update_goal",
                ]
            )
            and ".harness/verification/" in agents_text,
            ["docs/ai-engineering-workflow.md", "AGENTS.md"],
        ),
        _result(
            "workflow_templates_gate_execution",
            "Harness templates require the OpenSpec/Superpowers/Harness/Goal execution gates",
            _contains(plan_template, ["OpenSpec", "Goal", "Superpowers", "Harness"])
            and _contains(implement_template, ["Goal status", "verification-before-completion", "change-lifecycle"])
            and _contains(checklist_template, ["OpenSpec", "Goal", "Superpowers", "change-lifecycle"]),
            [
                ".harness/templates/PLAN.md",
                ".harness/templates/IMPLEMENT.md",
                ".harness/templates/HARNESS_CHECKLIST.md",
            ],
        ),
        _result(
            "agents_entry_map_routes_goal_superpowers_native_subagents",
            "AGENTS.md routes large work through Goal, Superpowers, Harness, and native subagents",
            _contains(agents_md, ["docs/ai-engineering-workflow.md", "Goal", "Superpowers", "native subagents", ".harness/verification/"]),
            ["AGENTS.md"],
        ),
        _result(
            "archived_changes_have_state_closure",
            "Archived OpenSpec changes retain required files, closed tasks, delta specs, and workflow evidence",
            bool(change_state_report.get("overall_change_state_passed")),
            [
                "openspec/changes/archive/",
                "docs/superpowers/specs/",
                "docs/superpowers/plans/",
                ".harness/verification/",
            ],
            "\n".join(
                str(entry.get("notes", ""))
                for entry in change_state_report.get("results", [])
                if entry.get("status") != "proved" and entry.get("notes")
            ),
        ),
    ]
    return {
        "results": results,
        "overall_change_lifecycle_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_change_lifecycle(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "change-lifecycle-report.json"
    md_path = log_dir / "change-lifecycle-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Change Lifecycle Verification Report", report, "overall_change_lifecycle_passed")

    print(f"change_lifecycle_report_json={json_path}")
    print(f"change_lifecycle_report_md={md_path}")
    print(f"overall_change_lifecycle_passed={report['overall_change_lifecycle_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_change_lifecycle_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
