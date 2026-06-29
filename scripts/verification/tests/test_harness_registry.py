from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import _write_harness_report
from registry import load_profile_registry, load_rule_registry, rule_evidence_map


def test_load_profile_registry_reads_project_profiles() -> None:
    registry = load_profile_registry(Path(__file__).resolve().parents[3])

    assert registry.profile_order == [
        "docs",
        "boundaries",
        "drift",
        "backend-contract",
        "godot-project",
        "character-agent-execution",
        "release-gate",
        "harness-lifecycle",
        "change-lifecycle",
        "harness-reference",
        "harness-evolution",
        "phase0",
        "siming-backend-chain",
        "phase1-slice",
    ]
    assert registry.profiles["docs"]["script"] == "scripts/verification/check_docs.py"
    assert registry.profiles["backend-contract"]["script"] == "scripts/verification/check_backend_contract.py"
    assert registry.profiles["godot-project"]["script"] == "scripts/verification/check_godot_project.py"
    assert registry.profiles["character-agent-execution"]["script"] == "scripts/verification/verify_character_agent_execution.py"
    assert registry.profiles["release-gate"]["script"] == "scripts/verification/check_release_gate.py"
    assert registry.profiles["harness-lifecycle"]["script"] == "scripts/verification/check_harness_lifecycle.py"
    assert registry.profiles["change-lifecycle"]["script"] == "scripts/verification/check_change_lifecycle.py"
    assert registry.profiles["harness-reference"]["script"] == "scripts/verification/check_harness_reference.py"
    assert registry.profiles["harness-evolution"]["script"] == "scripts/verification/check_harness_evolution.py"
    assert registry.profiles["siming-backend-chain"]["script"] == "scripts/verification/verify_siming_backend_chain.py"
    assert registry.profiles["siming-backend-chain"]["include_in_all"] is False
    assert registry.profiles["phase0"]["requires_godot"] is True
    assert int(registry.profiles["phase0"].get("max_attempts", 1)) >= 2
    assert all(profile["schema_version"] == 1 for profile in registry.profiles.values())


def test_load_rule_registry_reads_versioned_rule_manifests() -> None:
    registry = load_rule_registry(Path(__file__).resolve().parents[3])

    assert sorted(registry.rules) == [
        "backend-contract-rules",
        "boundary-rules",
        "change-lifecycle-rules",
        "docs-rules",
        "drift-rules",
        "godot-project-rules",
        "harness-evolution-rules",
        "harness-lifecycle-rules",
        "harness-reference-rules",
        "release-gate-rules",
    ]
    assert all(manifest["schema_version"] == 1 for manifest in registry.rules.values())


def test_rule_registry_exposes_rule_to_evidence_mapping() -> None:
    mapping = rule_evidence_map(load_rule_registry(Path(__file__).resolve().parents[3]))

    assert mapping["docs.docs_index_paths_exist"]["profile"] == "docs"
    assert mapping["backend-contract.backend_protocol_models_exist"]["profile"] == "backend-contract"
    assert mapping["godot-project.scene_resource_paths_exist"]["profile"] == "godot-project"
    assert mapping["release-gate.ci_runs_full_harness_profile"]["profile"] == "release-gate"
    assert mapping["harness-lifecycle.lifecycle_retention_policy_exists"]["profile"] == "harness-lifecycle"
    assert mapping["change-lifecycle.workflow_doc_exists"]["profile"] == "change-lifecycle"
    assert mapping["harness-reference.reference_taxonomy_exists"]["profile"] == "harness-reference"


def test_write_harness_report_creates_run_id_archive(tmp_path: Path) -> None:
    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "docs",
                "command": ["python", "scripts/verification/check_docs.py"],
                "exit_code": 0,
            }
        ],
        overall_passed=True,
        run_id="run_test",
    )

    latest_payload = json.loads(report_paths["json"].read_text(encoding="utf-8"))
    archived_payload = json.loads((tmp_path / ".harness" / "verification" / "runs" / "run_test" / "harness-run-report.json").read_text(encoding="utf-8"))

    assert latest_payload["run_id"] == "run_test"
    assert archived_payload["run_id"] == "run_test"
    assert report_paths["run_dir"] == tmp_path / ".harness" / "verification" / "runs" / "run_test"
