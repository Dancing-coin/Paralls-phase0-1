from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "verify_character_turn_embodied_episode",
    ROOT / "scripts" / "verification" / "verify_character_turn_embodied_episode.py",
)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def test_profile_requires_live_backend_godot_and_overall_artifact() -> None:
    profile = json.loads((ROOT / ".harness" / "profiles" / "character-turn-embodied-episode.json").read_text())
    assert profile["requires_godot"] is True
    assert profile["result_artifact"].endswith("character-turn-embodied-episode-report.json")
    assert profile["script"] == "scripts/verification/verify_character_turn_embodied_episode.py"


def test_verifier_rejects_missing_backend_replay_or_scenario_matrix() -> None:
    passed, notes = verifier.episode_result_ok({
        "overall_obj_archive_door_physical_embodiment_passed": True,
        "selected_scenarios_passed": True,
        "selected_scenarios": ["success"],
        "artifacts": {},
    })
    assert passed is False
    assert "incomplete_scenario_matrix" in notes
    assert "missing_backend_or_replay_trace" in notes


def test_verifier_accepts_complete_live_evidence_manifest() -> None:
    passed, notes = verifier.episode_result_ok({
        "overall_obj_archive_door_physical_embodiment_passed": True,
        "selected_scenarios_passed": True,
        "selected_scenarios": ["success", "distance_failure", "revision_failure", "stance_failure"],
        "artifacts": {
            "backend_trace": "backend.json",
            "replay_trace": "replay.json",
            "runtime": "runtime.json",
            "screenshots": {"success": "success.png"},
        },
    })
    assert passed is True
    assert notes == []


def test_verifier_rejects_nonzero_live_verifier_exit_even_with_stale_report() -> None:
    passed, notes = verifier.episode_result_ok({
        "overall_obj_archive_door_physical_embodiment_passed": True,
        "selected_scenarios_passed": True,
        "selected_scenarios": ["success", "distance_failure", "revision_failure", "stance_failure"],
        "artifacts": {"backend_trace": "backend.json", "replay_trace": "replay.json"},
    }, legacy_exit_code=1)
    assert passed is False
    assert "legacy_verifier_failed" in notes


def test_probe_records_pre_post_episode_and_recovery_evidence() -> None:
    text = (ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd").read_text()
    for marker in ("pre_capture_ref", "post_capture_ref", "authority_result_ref", "recovery_evidence", "post_observation_mismatch"):
        assert marker in text
