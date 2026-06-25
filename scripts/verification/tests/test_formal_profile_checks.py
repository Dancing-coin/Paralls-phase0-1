from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_backend_contract import evaluate_backend_contract
from check_change_lifecycle import evaluate_change_lifecycle
from check_godot_project import evaluate_godot_project
from check_harness_lifecycle import evaluate_harness_lifecycle
from check_harness_evolution import evaluate_harness_evolution
from check_harness_reference import evaluate_harness_reference
from check_release_gate import evaluate_release_gate
from common import repo_root
from registry import load_profile_registry


def test_backend_contract_profile_proves_protocol_contracts() -> None:
    report = evaluate_backend_contract(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["backend_protocol_models_exist"] == "proved"
    assert statuses["cross_boundary_models_are_pydantic"] == "proved"
    assert statuses["backend_tests_cover_protocol_contracts"] == "proved"
    assert statuses["authority_event_contract_exists"] == "proved"


def test_godot_project_profile_proves_static_project_integrity() -> None:
    report = evaluate_godot_project(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["project_main_scene_exists"] == "proved"
    assert statuses["autoload_scripts_exist"] == "proved"
    assert statuses["scene_resource_paths_exist"] == "proved"
    assert statuses["blend_import_is_noninteractive"] == "proved"


def test_release_gate_profile_proves_ci_entrypoint() -> None:
    report = evaluate_release_gate(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["release_gate_metadata_exists"] == "proved"
    assert statuses["ci_harness_workflow_exists"] == "proved"
    assert statuses["ci_runs_full_harness_profile"] == "proved"
    assert statuses["ci_runs_mainline_unified_runtime_profile"] == "proved"
    assert statuses["local_ci_gate_exists"] == "proved"
    assert statuses["local_ci_gate_matches_release_profile"] == "proved"
    assert statuses["local_ci_gate_runs_mainline_unified_runtime_profile"] == "proved"


def test_harness_lifecycle_profile_proves_project06_hardening_artifacts() -> None:
    project_root = repo_root()
    report = evaluate_harness_lifecycle(project_root)
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["lifecycle_feature_ledger_exists"] == "proved"
    assert statuses["lifecycle_local_ci_gate_exists"] == "proved"
    assert statuses["lifecycle_templates_exist"] == "proved"
    assert statuses["lifecycle_decision_manifest_surface_exists"] == "proved"
    assert statuses["lifecycle_decision_observability_docs_exist"] == "proved"
    assert statuses["lifecycle_retention_policy_exists"] == "proved"
    assert statuses["lifecycle_quality_docs_exist"] == "proved"

    features = json.loads((project_root / ".harness" / "features.json").read_text(encoding="utf-8"))["features"]
    decision_feature = next(entry for entry in features if entry["id"] == "decision-observability")
    assert decision_feature["name"] == "Harness decision observability records active change intent and failed-profile digests"
    assert "title" not in decision_feature

    harness_doc = (project_root / "docs" / "harness.md").read_text(encoding="utf-8")
    for profile in load_profile_registry(project_root).profile_order:
        assert f"`{profile}`" in harness_doc
    assert "`godot-project`, `character-agent-execution`, `release-gate`" in harness_doc


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


def test_harness_reference_profile_proves_awesome_harness_coverage() -> None:
    report = evaluate_harness_reference(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["reference_taxonomy_exists"] == "proved"
    assert statuses["reference_categories_have_current_artifacts"] == "proved"
    assert statuses["awesome_templates_adapted"] == "proved"
    assert statuses["reference_docs_updated"] == "proved"


def test_harness_evolution_profile_proves_governed_evolution_surface() -> None:
    report = evaluate_harness_evolution(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["evolution_config_valid"] == "proved"
    assert statuses["evolution_replay_set_valid"] == "proved"
    assert statuses["evolution_candidates_governed"] == "proved"
    assert statuses["evolution_report_exists"] == "proved"


def test_phase1_slice_probe_counts_only_accepted_authority_acks() -> None:
    probe_source = (repo_root() / "scripts" / "verification" / "Phase1SliceRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )

    assert 'bool(payload.get("accepted", false))' in probe_source
    assert "_ack_counts_by_route[route]" in probe_source
