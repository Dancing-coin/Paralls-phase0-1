from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import harness
from registry import load_profile_registry


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_siming_resource_staging_profile_is_registered() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    assert "siming-resource-staging" in registry.profiles
    profile = registry.profiles["siming-resource-staging"]
    assert profile["script"] == "scripts/verification/verify_siming_resource_staging.py"
    assert profile["requires_godot"] is False
    assert profile["result_artifact"] == ".harness/verification/siming-resource-staging-report.json"
    assert harness._profiles_for_selection("siming-resource-staging", registry) == [
        "siming-resource-staging"
    ]


def test_resource_staging_verifier_proves_all_required_results() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_siming_resource_staging.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout
    report_path = (
        PROJECT_ROOT
        / ".harness"
        / "verification"
        / "siming-resource-staging-report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_siming_resource_staging_passed"] is True
    required_result_ids = {
        "existing_resource_package",
        "hard_gate_precedes_resource_score",
        "semantic_reuse",
        "exact_signature_fatigue",
        "all_ack_staged",
        "refusal_aborted",
        "obligation_remains_open",
    }
    assert {entry["id"] for entry in report["results"]} == required_result_ids
    assert len(report["results"]) == len(required_result_ids)
    assert all(entry["status"] == "proved" for entry in report["results"])

    trace_path = Path(report["artifacts"]["trace"])
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["matched_candidate_ids"] == ["fact_confirmed"]
    assert trace["staged_obligation"] == "open"
    assert all(trace["static_resources"].values())
    assert {
        "main_demo_wiring",
        "player_character_instance",
        "player_char_c_binding",
        "player_camera_voice_wiring",
        "dialogue_to_voice_delivery",
    }.issubset(trace["static_resources"])
    assert trace["hard_gate_rejections"] == [
        ["confirmed_fact_rejected", "fact_gate_failed"],
        ["player_choice_rejected", "player_choice_gate_failed"],
        ["actor_autonomy_rejected", "actor_autonomy_gate_failed"],
        ["world_feasibility_rejected", "world_feasibility_gate_failed"],
        ["safety_rejected", "safety_gate_failed"],
        ["playability_fairness_rejected", "playability_fairness_gate_failed"],
        ["open_obligation_rejected", "open_obligation_gate_failed"],
        ["reachable_attractor_rejected", "reachable_attractor_gate_failed"],
    ]
