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
        "character-model-live",
        "script-evolution-proof",
        "l1-world-fact-runtime",
        "llm-integration-closure",
        "phase1-slice",
        "mainline-unified-runtime",
        "model-provider-readiness",
        "godot-sampling-production-grade-providers",
        "embodied-skeletal-debug-replay",
        "tts-voice-profile-adapter",
        "vla-provider-backend",
        "actor-scene-knowledge-lifecycle",
        "siming-global-situation-layer",
        "interaction-orchestration-service",
        "esm-physical-channel-world-actuation",
        "non-runtime-production-pipeline",
        "perception-input-alignment",
        "embodied-interaction-contracts",
        "siming-heavenly-graph-foundation",
        "embodied-affordance-registry",
        "siming-six-domain-memory",
        "embodied-bridge-attestation",
        "siming-actor-memory-read",
        "embodied-action-controller",
        "siming-story-runtime",
        "embodied-authority-settlement",
        "siming-resource-staging",
        "embodied-interaction-replay",
        "siming-adaptive-bridge",
        "gameplay-foundation-contract",
        "siming-heavenly-runtime",
        "gameplay-event-replay",
        "gameplay-foundation-event-spine",
        "gameplay-state-groups",
        "embodied-interaction-session",
        "gameplay-resource-body",
        "embodied-handoff-authority",
        "gameplay-effective-stats",
        "embodied-grab-carry-place-authority",
        "gameplay-status-tags",
        "embodied-interaction-foundation-all",
        "gameplay-ability-affordance",
        "godot-gameplay-mirror",
        "gameplay-inventory",
        "gameplay-possession-equipment",
        "gameplay-ownership-authority",
        "gameplay-economy-authority",
        "gameplay-patch-runtime",
        "adventure-basic",
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
    assert registry.profiles["character-model-live"]["script"] == "scripts/verification/verify_character_model_live.py"
    assert registry.profiles["character-model-live"]["include_in_all"] is False
    assert registry.profiles["llm-integration-closure"]["script"] == "scripts/verification/verify_llm_integration_closure.py"
    assert registry.profiles["llm-integration-closure"]["include_in_all"] is False
    assert registry.profiles["model-provider-readiness"]["script"] == "scripts/verification/verify_model_provider_readiness.py"
    assert registry.profiles["tts-voice-profile-adapter"]["script"] == "scripts/verification/verify_tts_voice_profile_adapter.py"
    assert registry.profiles["vla-provider-backend"]["script"] == "scripts/verification/verify_vla_provider_backend.py"
    assert registry.profiles["actor-scene-knowledge-lifecycle"]["script"] == "scripts/verification/verify_actor_scene_knowledge_runtime.py"
    assert registry.profiles["siming-global-situation-layer"]["script"] == "scripts/verification/verify_siming_global_situation_runtime.py"
    assert registry.profiles["interaction-orchestration-service"]["script"] == "scripts/verification/verify_interaction_orchestration_runtime_service.py"
    assert registry.profiles["esm-physical-channel-world-actuation"]["script"] == "scripts/verification/verify_esm_physical_channel_runtime.py"
    assert registry.profiles["non-runtime-production-pipeline"]["script"] == "scripts/verification/verify_non_runtime_production_pipeline.py"
    assert registry.profiles["perception-input-alignment"]["script"] == "scripts/verification/verify_perception_input_alignment.py"
    assert registry.profiles["embodied-interaction-contracts"]["script"] == "scripts/verification/verify_embodied_interaction_contracts.py"
    assert registry.profiles["siming-actor-memory-read"]["script"] == "scripts/verification/verify_siming_actor_memory_read.py"
    assert registry.profiles["siming-story-runtime"]["script"] == "scripts/verification/verify_siming_story_runtime.py"
    assert registry.profiles["embodied-affordance-registry"]["script"] == "scripts/verification/verify_embodied_affordance_registry.py"
    assert registry.profiles["embodied-bridge-attestation"]["script"] == "scripts/verification/verify_embodied_bridge_attestation.py"
    assert registry.profiles["embodied-action-controller"]["script"] == "scripts/verification/verify_embodied_action_controller.py"
    assert registry.profiles["embodied-authority-settlement"]["script"] == "scripts/verification/verify_embodied_authority_settlement.py"
    assert registry.profiles["embodied-interaction-replay"]["script"] == "scripts/verification/verify_embodied_interaction_replay.py"
    assert registry.profiles["gameplay-foundation-contract"]["script"] == "scripts/verification/verify_gameplay_foundation_contract.py"
    assert registry.profiles["gameplay-event-replay"]["script"] == "scripts/verification/verify_gameplay_event_replay.py"
    assert registry.profiles["gameplay-foundation-event-spine"]["script"] == "scripts/verification/verify_gameplay_foundation_event_spine.py"
    assert registry.profiles["adventure-basic"]["script"] == "scripts/verification/verify_adventure_basic.py"
    assert registry.profiles["gameplay-state-groups"]["script"] == "scripts/verification/verify_gameplay_state_groups.py"
    assert registry.profiles["gameplay-possession-equipment"]["script"] == "scripts/verification/verify_gameplay_possession_equipment.py"
    assert registry.profiles["gameplay-ownership-authority"]["script"] == "scripts/verification/verify_gameplay_ownership_authority.py"
    assert registry.profiles["embodied-interaction-session"]["script"] == "scripts/verification/verify_embodied_interaction_session.py"
    assert registry.profiles["embodied-handoff-authority"]["script"] == "scripts/verification/verify_embodied_handoff_authority.py"
    assert registry.profiles["embodied-grab-carry-place-authority"]["script"] == "scripts/verification/verify_embodied_grab_carry_place_authority.py"
    assert registry.profiles["embodied-interaction-foundation-all"]["script"] == "scripts/verification/verify_embodied_interaction_foundation_all.py"
    assert registry.profiles["phase0"]["requires_godot"] is True
    assert registry.profiles["mainline-unified-runtime"]["script"] == "scripts/verification/verify_mainline_unified_runtime.py"
    assert "not a product L1 runtime" in registry.profiles["l1-world-fact-runtime"]["description"]
    assert int(registry.profiles["mainline-unified-runtime"].get("max_attempts", 1)) >= 2
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
    assert mapping["harness-evolution.evolution_config_valid"]["profile"] == "harness-evolution"


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


def test_write_harness_report_archives_matching_suite_identity(tmp_path: Path) -> None:
    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "siming-heavenly-runtime",
                "command": ["python", "scripts/verification/verify_siming_heavenly_runtime.py"],
                "exit_code": 0,
            }
        ],
        overall_passed=True,
        run_id="run_suite_identity",
        suite_id="siming-heavenly-runtime",
    )

    latest_report = json.loads(report_paths["json"].read_text(encoding="utf-8"))
    archived_report = json.loads(
        (report_paths["run_dir"] / "harness-run-report.json").read_text(encoding="utf-8")
    )
    latest_manifest = json.loads(report_paths["manifest"].read_text(encoding="utf-8"))
    archived_manifest = json.loads(
        (report_paths["run_dir"] / "run-manifest.json").read_text(encoding="utf-8")
    )

    assert latest_report["suite_id"] == "siming-heavenly-runtime"
    assert archived_report["suite_id"] == "siming-heavenly-runtime"
    assert latest_manifest["suite_id"] == "siming-heavenly-runtime"
    assert archived_manifest["suite_id"] == "siming-heavenly-runtime"
    assert "- Suite ID: `siming-heavenly-runtime`" in report_paths["markdown"].read_text(encoding="utf-8")
    assert "- Suite ID: `siming-heavenly-runtime`" in (
        report_paths["run_dir"] / "harness-run-report.md"
    ).read_text(encoding="utf-8")
