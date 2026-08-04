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
    "typed_proposal",
    "existing_fact_only",
    "char_b_observation_gate",
    "open_o6_gate",
    "resource_gate",
    "no_terminal_resurrection",
    "no_actor_memory_write",
    "new_runtime_node_committed",
}


def test_siming_adaptive_bridge_profile_is_registered() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    assert "siming-adaptive-bridge" in registry.profiles
    profile = registry.profiles["siming-adaptive-bridge"]
    assert profile["script"] == "scripts/verification/verify_siming_adaptive_bridge.py"
    assert profile["requires_godot"] is False
    assert (
        profile["result_artifact"]
        == ".harness/verification/siming-adaptive-bridge-report.json"
    )
    assert harness._profiles_for_selection("siming-adaptive-bridge", registry) == [
        "siming-adaptive-bridge"
    ]


def test_adaptive_bridge_verifier_proves_all_required_results() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_siming_adaptive_bridge.py"],
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
        / "siming-adaptive-bridge-report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_siming_adaptive_bridge_passed"] is True
    assert {entry["id"] for entry in report["results"]} == REQUIRED_RESULT_IDS
    assert len(report["results"]) == len(REQUIRED_RESULT_IDS)
    assert all(entry["status"] == "proved" for entry in report["results"])

    trace = json.loads(Path(report["artifacts"]["trace"]).read_text(encoding="utf-8"))
    assert trace["proposal_type"] == "AdaptiveBridgeNodeProposal"
    assert trace["accepted_validation"]["accepted"] is True
    assert trace["runtime_node"]["lifecycle"] == "latent"
    assert (
        trace["char_b_private_node_ids_before"]
        == trace["char_b_private_node_ids_after"]
    )
