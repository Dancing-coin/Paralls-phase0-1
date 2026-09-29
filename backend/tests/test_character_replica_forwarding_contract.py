from pathlib import Path
import os
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
REPLICA = ROOT / "scripts/character" / ("Character" + "Replica.gd")
ACTOR = ROOT / "scripts/character/CharacterActor.gd"


def _method(source: str, name: str) -> str:
    match = re.search(rf"^func {name}\([^\n]*", source, re.MULTILINE)
    assert match, name
    next_method = re.search(r"^func |^static func ", source[match.end():], re.MULTILINE)
    end = match.end() + next_method.start() if next_method else len(source)
    return source[match.start():end]


def test_legacy_pose_and_control_forward_normalized_intent_to_actor():
    replica = REPLICA.read_text(encoding="utf-8")
    actor = ACTOR.read_text(encoding="utf-8")
    begin = _method(replica, "begin_embodied_control_frame")
    sync = _method(replica, "apply_embodied_pose_sync")
    assert "CharacterControlIntentRef.normalize" in begin
    assert '"source_kind": "compatibility"' in begin
    assert "apply_control_intent(intent" in begin
    assert "CharacterControlIntentRef.normalize" in sync
    assert "apply_compatibility_pose_sync(intent" in sync
    assert "func apply_control_intent(" in actor
    assert "func apply_compatibility_pose_sync(" in actor


def test_action_and_reviewed_playback_forward_through_actor_owned_seams():
    replica = REPLICA.read_text(encoding="utf-8")
    actor = ACTOR.read_text(encoding="utf-8")
    action = _method(replica, "perform_action")
    play = _method(replica, "play_reviewed_action_atom")
    restore = _method(replica, "restore_reviewed_action_playback")
    assert "perform_compatibility_action(intent)" in action
    assert "return play_compatibility_reviewed_action_atom(" in play
    assert "restore_compatibility_reviewed_action_playback()" in restore
    for seam in (
        "perform_compatibility_action",
        "play_compatibility_reviewed_action_atom",
        "restore_compatibility_reviewed_action_playback",
    ):
        assert f"func {seam}(" in actor
    assert "submit_action_intent" in _method(actor, "perform_compatibility_action")
    assert "return _play_reviewed_action_atom(" in _method(actor, "play_compatibility_reviewed_action_atom")


def test_asset_binding_returns_actor_result_and_all_compat_calls_have_diagnostics():
    replica = REPLICA.read_text(encoding="utf-8")
    actor = ACTOR.read_text(encoding="utf-8")
    binding = _method(replica, "apply_presentation_asset_binding")
    assert "return apply_compatibility_presentation_asset_binding(binding)" in binding
    assert "func apply_compatibility_presentation_asset_binding(" in actor
    assert "return _apply_presentation_asset_binding(binding)" in _method(actor, "apply_compatibility_presentation_asset_binding")
    for method in (
        "begin_embodied_control_frame",
        "apply_embodied_pose_sync",
        "perform_action",
        "play_reviewed_action_atom",
        "restore_reviewed_action_playback",
        "apply_presentation_asset_binding",
    ):
        assert "_record_compatibility_call(" in _method(replica, method), method
    diagnostics = _method(replica, "_record_compatibility_call")
    for field in ("caller_path", "method", "actor_id", "source_kind", "intent_digest", "forwarded_to"):
        assert f'"{field}"' in diagnostics
    assert "compatibility_call.emit(" in diagnostics


def test_shell_has_no_body_animation_or_authority_writes_and_strict_guard_exists():
    replica = REPLICA.read_text(encoding="utf-8")
    executable = "\n".join(line for line in replica.splitlines() if not line.lstrip().startswith("#"))
    assert re.search(r"\b(?:global_position|velocity)\b\s*(?:[+\-*/]?=)", executable) is None
    assert "move_and_slide(" not in executable
    assert re.search(r"\b(?:animation_player|animation_state_playback|playback)\.(?:play|travel|seek)\(", executable) is None
    assert "append_authority_event(" not in executable
    assert "compatibility_strict_mode" in replica
    assert "assert(" in _method(replica, "_record_compatibility_call")


def test_compatibility_diagnostics_keep_total_count_without_unbounded_history():
    replica = REPLICA.read_text(encoding="utf-8")
    diagnostics = _method(replica, "_record_compatibility_call")
    assert "compatibility_call_count += 1" in diagnostics
    assert "compatibility_call_diagnostics.pop_front()" in diagnostics
    assert "compatibility_call.emit(diagnostic)" in diagnostics


def test_empty_action_and_internal_actor_action_keep_original_semantics():
    actor = ACTOR.read_text(encoding="utf-8")
    compatibility = _method(actor, "perform_compatibility_action")
    interaction = _method(actor, "_handle_interact_goal_command")
    assert '_realize_action_request("")' in compatibility
    assert '_realize_action_request("interact")' in interaction


def test_action_admission_uses_live_tick_occupancy():
    actor = ACTOR.read_text(encoding="utf-8")
    submit = _method(actor, "submit_action_intent")
    assert '"occupancy": _action_occupancy' in submit
    assert "_action_occupancy_tick" in submit
    assert "_action_occupancy[claim]" in submit


def test_godot_forwarding_and_strict_guard_runtime_probe():
    godot = Path(os.environ.get("GODOT_EXE", r"D:\godot\Godot_v4.6.3-stable_win64.exe"))
    assert godot.exists(), godot
    probe = ROOT / "scripts/verification" / ("Character" + "ReplicaForwardingProbe.gd")
    assert probe.exists(), probe
    result = subprocess.run(
        [str(godot), "--headless", "--path", str(ROOT), "--script", str(probe)],
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CHARACTER_REPLICA_FORWARDING_PROBE_PASS" in result.stdout, result.stdout + result.stderr
