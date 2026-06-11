from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_change_lifecycle import evaluate_change_lifecycle
from common import repo_root


def test_change_lifecycle_profile_proves_ai_engineering_workflow() -> None:
    report = evaluate_change_lifecycle(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["workflow_doc_exists"] == "proved"
    assert statuses["change_lifecycle_profile_registered"] == "proved"
    assert statuses["openspec_superpowers_harness_goal_chain_documented"] == "proved"
    assert statuses["goal_owns_project_workflow_state"] == "proved"
    assert statuses["workflow_templates_gate_execution"] == "proved"
    assert statuses["agents_entry_map_routes_goal_superpowers_native_subagents"] == "proved"
    assert statuses["archived_changes_have_state_closure"] == "proved"
