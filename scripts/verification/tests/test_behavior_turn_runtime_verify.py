from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import harness
from registry import load_profile_registry


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_RESULT_IDS = {
    "focused_pytest_pass",
    "complete_stage_chain",
    "accepted_committed",
    "rejected_retained",
    "actor_private_scope",
    "idempotent_replay",
}


def test_behavior_turn_runtime_profile_is_registered() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    assert "behavior-turn-runtime" in registry.profiles
    profile = registry.profiles["behavior-turn-runtime"]
    assert profile["script"] == "scripts/verification/verify_behavior_turn_runtime.py"
    assert profile["requires_godot"] is False
    assert profile["result_artifact"] == (
        ".harness/verification/behavior-turn-runtime-report.json"
    )
    assert harness._profiles_for_selection("behavior-turn-runtime", registry) == [
        "behavior-turn-runtime"
    ]


def test_behavior_turn_runtime_verifier_proves_required_results() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_behavior_turn_runtime.py"],
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
        / "behavior-turn-runtime-report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_behavior_turn_runtime_passed"] is True
    assert {entry["id"] for entry in report["results"]} == REQUIRED_RESULT_IDS
    assert all(entry["status"] == "proved" for entry in report["results"])

    trace = json.loads(Path(report["artifacts"]["trace"]).read_text(encoding="utf-8"))
    assert trace["accepted_stages"] == [
        "context",
        "interpretation",
        "goal",
        "intent",
        "execution",
        "settlement",
        "evaluation",
        "policy",
    ]
    assert trace["accepted_settlement_outcome"] == "committed"
    assert trace["rejected_settlement_outcome"] == "rejected"
    assert trace["other_actor_visible_node_count"] == 0
    assert trace["replayed"] is True
