from __future__ import annotations

import argparse
from pathlib import Path

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


PLAN_TESTS = [
    (
        "perception_query_and_percept_protocol",
        "Perception Query Frame and three-layer percept protocol enforce isolated runtime contexts",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_perception_query_frame_and_percept_protocol_enforce_context_isolation",
    ),
    (
        "godot_sampling_frontend_and_providers",
        "Godot sampling frontend exposes six sampling-only providers that feed query frames",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_godot_sampling_frontend_declares_six_sampling_only_providers",
    ),
    (
        "l1_world_fact_and_space_foundation",
        "L1 space model, occupancy field, and fact projection manifest avoid runtime rescan/voxelization",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_l1_world_fact_and_space_foundation_models_static_and_dynamic_space_without_runtime_rescan",
    ),
    (
        "character_multimodal_and_actor_scene_knowledge",
        "Character multimodal stack and Actor Scene Knowledge extend the completed mind core without rewriting it",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_character_multimodal_stack_and_actor_scene_knowledge_extend_mind_core_without_rewriting_it",
    ),
    (
        "siming_multimodal_and_global_situation",
        "Siming multimodal stack enhances fairness/global situation without sharing character context",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_siming_multimodal_stack_enhances_fairness_without_polluting_character_context",
    ),
    (
        "interaction_orchestration_layer",
        "Interaction orchestration chooses semantic/physical channels without becoming a new brain",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_interaction_orchestration_selects_channels_without_becoming_a_new_brain",
    ),
    (
        "esm_dual_channel_world_actuation",
        "ESM dual-channel manifest keeps one world-state foundation and one result protocol",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_esm_dual_channel_manifest_keeps_one_world_result_protocol",
    ),
    (
        "embodied_skeletal_state_provider",
        "Embodied skeletal provider exports high/mid state to perception while keeping low-level snapshots debug-only",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_embodied_skeletal_state_provider_excludes_low_level_snapshot_from_main_chain",
    ),
    (
        "vla_multimodal_upgrade",
        "VLA remains a non-blocking spatial visual subchain and not a shared/global brain",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_vla_multimodal_upgrade_places_vla_as_non_blocking_subchain",
    ),
    (
        "non_runtime_multimodal_tooling",
        "Non-runtime tooling and production stacks use tool contexts and do not share runtime contexts",
        "backend/tests/test_current_project_intelligence_upgrade.py::test_non_runtime_multimodal_tooling_uses_tool_contexts_and_review_only_human_role",
    ),
]


def _result(result_id: str, title: str, exit_code: int, evidence: list[str]) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if exit_code == 0 else "missing",
        "evidence": evidence if exit_code == 0 else [],
        "notes": "" if exit_code == 0 else "focused test failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    python_exe = resolve_python_exe(args.python_exe)
    log_dir = verification_dir(project_root)
    results: list[dict[str, object]] = []
    artifacts: dict[str, object] = {}

    for result_id, title, test_selector in PLAN_TESTS:
        log_path = log_dir / f"current-project-intelligence-upgrade-{result_id}.log"
        command = [python_exe, "-m", "pytest", test_selector, "-v"]
        command_result = run_command(command, project_root, log_path)
        results.append(_result(result_id, title, command_result.returncode, [str(log_path)]))
        artifacts[f"{result_id}_log"] = str(log_path)

    overall_passed = all(str(entry["status"]) == "proved" for entry in results)
    report = {
        "results": results,
        "overall_current_project_intelligence_upgrade_passed": overall_passed,
        "artifacts": artifacts,
    }

    json_path = log_dir / "current-project-intelligence-upgrade-report.json"
    md_path = log_dir / "current-project-intelligence-upgrade-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Current Project Intelligence Upgrade Verification Report",
        report,
        "overall_current_project_intelligence_upgrade_passed",
    )

    print(f"current_project_intelligence_upgrade_report_json={json_path}")
    print(f"current_project_intelligence_upgrade_report_md={md_path}")
    print(f"overall_current_project_intelligence_upgrade_passed={overall_passed}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
