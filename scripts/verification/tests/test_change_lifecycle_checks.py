from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_change_lifecycle import evaluate_change_lifecycle
from common import repo_root


def test_change_lifecycle_profile_proves_ai_engineering_workflow() -> None:
    report = evaluate_change_lifecycle(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    expected_result_ids = {
        "workflow_doc_exists",
        "change_lifecycle_profile_registered",
        "design_superpowers_harness_goal_chain_documented",
        "goal_owns_project_workflow_state",
        "workflow_templates_gate_execution",
        "agents_entry_map_routes_goal_superpowers_native_subagents",
    }
    assert set(statuses) == expected_result_ids
    assert all(status == "proved" for status in statuses.values())
