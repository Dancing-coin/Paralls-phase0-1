from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "docs" / "character" / "action-foundation-series-baseline-2026-09-28.md"
PROBE = ROOT / "scripts" / "verification" / "CharacterActionFoundationBaselineProbe.gd"
RETIREMENT_MATRIX = ROOT / "docs" / "character" / "character-replica-retirement-matrix-2026-09-29.md"
sys.path.insert(0, str(ROOT / "scripts" / "verification"))
import verify_character_replica_retirement as retirement_verifier


def read_active_callers() -> list[str]:
    callers: list[str] = []
    historical_tests = {
        "backend/tests/test_character_final_actor_contracts_static.py",
        "backend/tests/test_character_replica_forwarding_contract.py",
        "backend/tests/test_character_runtime_state_extraction_static.py",
        "backend/tests/test_character_replica_convergence_static.py",
    }
    roots = [ROOT / "scenes", ROOT / "scripts", ROOT / "backend"]
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".gd", ".tscn", ".py"}:
                continue
            if path.relative_to(ROOT).as_posix() in historical_tests:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "CharacterReplica" in text or "legacy_character_replica" in text:
                callers.append(path.relative_to(ROOT).as_posix())
    return sorted(set(callers))


def test_baseline_doc_and_probe_define_required_evidence_fields() -> None:
    assert BASELINE.exists(), BASELINE
    assert PROBE.exists(), PROBE
    baseline = BASELINE.read_text(encoding="utf-8")
    probe = PROBE.read_text(encoding="utf-8")
    for field in ("actor_id", "source_kind", "state", "clip", "velocity_world", "position", "action_locked", "root_policy", "caller_path"):
        assert field in baseline
        assert field in probe
    for source_kind in ("player", "agent", "program", "perception", "interaction", "authority", "probe"):
        assert source_kind in baseline


def read_retirement_matrix() -> list[dict[str, object]]:
    source = RETIREMENT_MATRIX.read_text(encoding="utf-8")
    match = re.search(r"```json\s*(\[.*?\])\s*```", source, re.DOTALL)
    assert match is not None, "retirement matrix needs a JSON array"
    return json.loads(match.group(1))


def test_active_replica_callers_are_registered_in_retirement_matrix() -> None:
    rows = read_retirement_matrix()
    required = {"caller_path", "category", "current_state", "target_entry", "owner_lane", "compatibility_allowed", "evidence_command"}
    assert all(required <= row.keys() for row in rows)
    registered = [str(row["caller_path"]) for row in rows]
    assert len(registered) == len(set(registered)), "duplicate caller paths"
    missing = sorted(set(read_active_callers()) - set(registered))
    assert not missing, f"unregistered CharacterReplica callers: {missing}"


def test_final_retirement_matrix_has_no_active_or_compatibility_states() -> None:
    rows = read_retirement_matrix()
    forbidden_states = {
        "active_reference",
        "active_legacy_route",
        "compatibility_shell",
    }
    offenders = [
        (str(row["caller_path"]), str(row["current_state"]))
        for row in rows
        if str(row["current_state"]) in forbidden_states
    ]
    assert offenders == [], f"final retirement matrix still has active states: {offenders}"


def test_runtime_caller_requires_explicit_migration_owner() -> None:
    rows = read_retirement_matrix()
    for row in rows:
        if row["compatibility_allowed"]:
            assert row["category"] in {"compatibility", "migration_test"}, row
        if row["category"] not in {"compatibility", "migration_test", "verification", "comment_only"}:
            assert row["owner_lane"] not in {"", "none"}, row
            if row["category"] == "authority":
                assert row["target_entry"] == "embodied_controller_v1", row
            else:
                assert str(row["target_entry"]).startswith("CharacterActor"), row
            assert row["compatibility_allowed"] is False, row


def test_retirement_verifier_fails_closed_on_missing_marker_digest_or_active_caller() -> None:
    absent = retirement_verifier.evaluate(ROOT, None, True)
    assert "missing_godot_marker" in absent["failed_checks"]
    marker = {
        "source_digest": absent["source_digest"],
        "matrix_digest": absent["matrix_digest"],
        "unregistered_callers": absent["unregistered_callers"],
        "passed": True,
    }
    stale = retirement_verifier.evaluate(ROOT, {**marker, "source_digest": "stale"}, True)
    assert "source_digest_mismatch" in stale["failed_checks"]
    active = retirement_verifier.evaluate(ROOT, {**marker, "active_scene_instances": 1}, True)
    assert "nonzero_active_scene_instances" in active["failed_checks"]
    stale_matrix = retirement_verifier.evaluate(ROOT, {**marker, "matrix_digest": "stale"}, True)
    assert "matrix_digest_mismatch" in stale_matrix["failed_checks"]
    backend_route = retirement_verifier.evaluate(ROOT, {**marker, "backend_production_references": 1}, True)
    assert "nonzero_backend_production_references" in backend_route["failed_checks"]


def test_retirement_verifier_rejects_unregistered_runtime_caller(tmp_path: Path) -> None:
    for directory in ("scenes", "scripts", "backend", "docs/character"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "docs/character/character-replica-retirement-matrix-2026-09-29.md").write_text(
        "```json\n[]\n```\n", encoding="utf-8"
    )
    (tmp_path / "scripts/NewCaller.gd").write_text(
        'extends Node\nvar replica = get_node_or_null("CharacterReplica")\n', encoding="utf-8"
    )
    result = retirement_verifier.evaluate(tmp_path, None, True)
    assert result["unregistered_callers"] == ["scripts/NewCaller.gd"]
    assert "unregistered_callers" in result["failed_checks"]


def test_retirement_verifier_rejects_active_matrix_state(tmp_path: Path) -> None:
    for directory in ("scenes", "scripts", "backend", "docs/character"):
        (tmp_path / directory).mkdir(parents=True)
    row = {
        "caller_path": "scripts/legacy.gd",
        "category": "scene",
        "current_state": "active_reference",
        "target_entry": "CharacterActor",
        "owner_lane": "Contract",
        "compatibility_allowed": False,
        "evidence_command": "pytest",
    }
    (tmp_path / "docs/character/character-replica-retirement-matrix-2026-09-29.md").write_text(
        "```json\n" + json.dumps([row]) + "\n```\n", encoding="utf-8"
    )
    result = retirement_verifier.evaluate(tmp_path, None, True)
    assert result["matrix_state_errors"] == [
        {"caller_path": "scripts/legacy.gd", "current_state": "active_reference"}
    ]
    assert "matrix_active_states" in result["failed_checks"]


def test_retirement_matrix_rejects_mislabeled_comment_and_production_route(tmp_path: Path) -> None:
    matrix = tmp_path / "docs/character/character-replica-retirement-matrix-2026-09-29.md"
    matrix.parent.mkdir(parents=True)
    source = tmp_path / "scripts/character/GenericRoleSkin.gd"
    source.parent.mkdir(parents=True)
    source.write_text('var replica = get_node_or_null("CharacterReplica")\n', encoding="utf-8")
    row = {
        "caller_path": "scripts/character/GenericRoleSkin.gd",
        "category": "comment_only", "current_state": "comment_only",
        "target_entry": "CharacterActor", "owner_lane": "Contract",
        "compatibility_allowed": False, "evidence_command": "pytest",
    }
    matrix.write_text("```json\n" + json.dumps([row]) + "\n```\n", encoding="utf-8")
    with pytest.raises(ValueError, match="comment_only"):
        retirement_verifier.matrix_rows(tmp_path)
    row.update(caller_path="backend/app/models/embodied_interaction.py", category="compatibility", compatibility_allowed=True)
    matrix.write_text("```json\n" + json.dumps([row]) + "\n```\n", encoding="utf-8")
    with pytest.raises(ValueError, match="compatibility"):
        retirement_verifier.matrix_rows(tmp_path)
    matrix.unlink()
    missing = retirement_verifier.evaluate(tmp_path, None, True)
    assert missing["overall_character_replica_retirement_passed"] is False
    assert missing["matrix_digest"] == ""


def test_probe_tracks_verified_runtime_writers_and_scene_instance_nodes() -> None:
    probe = (ROOT / "scripts/verification/CharacterReplicaRetirementProbe.gd").read_text(encoding="utf-8")
    assert "_count_scene_instances" in probe
    assert "instance=ExtResource" in probe
    assert 'path.begins_with("scripts/verification/")' not in probe
    assert "backend_production_references" in probe


def test_only_character_motor_owns_move_and_slide() -> None:
    owners: list[str] = []
    excluded_legacy = {"scripts/street_combat/streetdemo.gd"}
    for path in (ROOT / "scripts").rglob("*.gd"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(ROOT).as_posix()
        if relative in excluded_legacy:
            continue
        if "move_and_slide(" in text:
            owners.append(relative)
    assert owners == ["scripts/character/CharacterMotor.gd"], owners


def test_street_skin_does_not_call_animation_playback_directly() -> None:
    skin = (ROOT / "scripts" / "street_combat" / "StreetCharacterSkin.gd").read_text(encoding="utf-8")
    assert re.search(r"\.(play|travel|seek)\s*\(", skin) is None



def test_semantic_control_intent_contract_exists_with_deterministic_defaults():
    intent = (ROOT / "scripts" / "character" / "CharacterControlIntent.gd").read_text(encoding="utf-8")
    port = (ROOT / "scripts" / "character" / "CharacterControllerPort.gd").read_text(encoding="utf-8")
    actor = (ROOT / "scripts" / "character" / "CharacterActor.gd").read_text(encoding="utf-8")
    assert "class_name CharacterControlIntent" in intent
    assert "static func create(" in intent
    for field in ("source_digest", "physics_tick", "intent_digest", "target_ref", "jump_type", "action_id"):
        assert field in intent
    assert "normalize_control_intent" in port
    assert "submit_control_intent" in actor
    assert "begin_embodied_control_frame" in actor
    assert "apply_embodied_pose_sync" in actor


def test_embodied_control_callers_only_stage_intent_and_preserve_compatibility():
    actor = (ROOT / "scripts" / "character" / "CharacterActor.gd").read_text(encoding="utf-8")
    begin = actor.split("func begin_embodied_control_frame", 1)[1].split("func consume_player_root_motion_request", 1)[0]
    sync = actor.split("func apply_embodied_pose_sync", 1)[1].split("func clear_embodied_control_frame", 1)[0]
    for section in (begin, sync):
        assert "submit_control_intent" in section
        assert "_set_role_asset" not in section
        assert "play_" not in section
    assert 'func begin_embodied_control_frame(' in actor
    assert 'func apply_embodied_pose_sync(' in actor


def test_player_agent_program_share_controller_port_normalization():
    port = (ROOT / "scripts" / "character" / "CharacterControllerPort.gd").read_text(encoding="utf-8")
    for source_kind in ("player", "agent", "program", "compatibility"):
        assert source_kind in port
    assert "CharacterControlIntentRef" in port


def test_role_animation_controller_owns_lock_hold_cancel_and_recovery():
    controller = (ROOT / "scripts" / "character" / "RoleAnimationController.gd").read_text(encoding="utf-8")
    skin = (ROOT / "scripts" / "street_combat" / "StreetCharacterSkin.gd").read_text(encoding="utf-8")
    assert 'extends "res://scripts/character/CharacterPackagePresentationAdapter.gd"' in skin
    presenter = (ROOT / "scripts" / "character" / "CharacterPackagePresentationAdapter.gd").read_text(encoding="utf-8")
    for name in ("apply_presentation_state", "hold_state", "release_hold", "cancel_action", "recover_to_locomotion", "action_locked"):
        assert name in controller
    for name in ("_action_locked", "_action_unlock_time"):
        assert name not in skin
        assert name not in presenter
    assert "func set_guard_stance" in presenter
    assert "animation_controller.hold_state" in presenter
    assert "RoleAnimationControllerRef" in presenter


def test_presentation_runtime_is_semantic_adapter_only():
    path = ROOT / "scripts" / "character" / "CharacterPresentationRuntime.gd"
    assert path.exists()
    source = path.read_text(encoding="utf-8")
    assert "apply_presentation_input" in source
    assert "clip" not in source.lower()
    assert "animation_player.play" not in source
