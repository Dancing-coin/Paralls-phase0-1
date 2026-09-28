from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "docs" / "character" / "action-foundation-series-baseline-2026-09-28.md"
PROBE = ROOT / "scripts" / "verification" / "CharacterActionFoundationBaselineProbe.gd"


def read_active_callers() -> list[str]:
    callers: list[str] = []
    roots = [ROOT / "scenes", ROOT / "scripts", ROOT / "backend"]
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".gd", ".tscn", ".py"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "CharacterReplica" in text:
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


def test_active_replica_callers_are_registered_in_baseline_matrix() -> None:
    baseline = BASELINE.read_text(encoding="utf-8")
    registered = set(re.findall(r"`([^`]+)`", baseline))
    missing = [caller for caller in read_active_callers() if caller not in registered]
    assert not missing, f"unregistered CharacterReplica callers: {missing}"


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
