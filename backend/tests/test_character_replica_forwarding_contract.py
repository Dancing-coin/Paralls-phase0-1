from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_character_replica_compatibility_assets_and_forwarding_probe_are_retired() -> None:
    replica = "Character" + "Replica"
    for relative_path in (
        f"scripts/character/{replica}.gd",
        f"scenes/phase0/{replica}.tscn",
        f"scenes/phase0/Validation{replica}.tscn",
        f"scripts/verification/{replica}ForwardingProbe.gd",
    ):
        assert not (ROOT / relative_path).exists(), relative_path


def test_actor_owns_control_pose_action_and_asset_seams() -> None:
    actor = _read("scripts/character/CharacterActor.gd")
    for method in (
        "begin_embodied_control_frame",
        "apply_embodied_pose_sync",
        "perform_action",
        "play_reviewed_action_atom",
        "restore_reviewed_action_playback",
        "apply_presentation_asset_binding",
    ):
        assert f"func {method}(" in actor
    assert "func apply_compatibility_pose_sync(" in actor
    assert "func perform_compatibility_action(" in actor
    assert "func apply_compatibility_presentation_asset_binding(" in actor


def test_actor_compatibility_seams_do_not_reference_deleted_shell() -> None:
    actor = _read("scripts/character/CharacterActor.gd")
    for method in (
        "apply_compatibility_pose_sync",
        "perform_compatibility_action",
        "play_compatibility_reviewed_action_atom",
        "restore_compatibility_reviewed_action_playback",
        "apply_compatibility_presentation_asset_binding",
    ):
        start = actor.index(f"func {method}(")
        end = actor.find("\nfunc ", start + 5)
        body = actor[start:] if end < 0 else actor[start:end]
        assert ("Character" + "Replica") not in body


def _method(source: str, name: str) -> str:
    start = source.index(f"func {name}(")
    end = source.find("\nfunc ", start + 5)
    return source[start:] if end < 0 else source[start:end]


def test_action_admission_preserves_backend_request_and_live_tick_occupancy() -> None:
    actor = _read("scripts/character/CharacterActor.gd")
    submit = _method(actor, "submit_action_intent")
    admit = _method(actor, "_admit_and_realize_action")
    interact = _method(actor, "_handle_interact_goal_command")
    assert '"occupancy": _action_occupancy' in submit
    assert "_action_occupancy_tick" in submit
    assert "_action_occupancy[claim]" in submit
    assert "submit_action_intent(StringName(action_name)" in admit
    assert 'if not bool(admission.get("accepted", false))' in admit
    assert "return admission" in admit
    assert "_realize_action_request(action_name)" in admit
    assert '_admit_and_realize_action(' in interact
    assert '"interact",' in interact


def test_actor_has_no_local_body_or_authority_writes_outside_motor_and_backend() -> None:
    actor = "\n".join(
        line
        for line in _read("scripts/character/CharacterActor.gd").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "move_and_slide(" not in actor
    assert "append_authority_event(" not in actor
    assert "global_position +=" not in actor
