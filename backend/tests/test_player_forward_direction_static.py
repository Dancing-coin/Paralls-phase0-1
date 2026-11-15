from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_player_bridge_uses_motor_forward_convention_for_move_and_look() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    helper_source = (ROOT / "scripts" / "player" / "Phase0ViewAnchorResolver.gd").read_text(
        encoding="utf-8"
    )

    assert "func _forward_from_yaw(yaw: float) -> Vector3:" in helper_source
    assert "return -Vector3.FORWARD.rotated(Vector3.UP, yaw).normalized()" in helper_source
    assert "CharacterControllerPortRef.get_desired_facing_yaw(normalized_frame, desired_facing_yaw)" in helper_source
    assert "forward_origin = (character_c as Node3D).global_position" in helper_source
    assert "return forward_origin + _forward_from_yaw(" in helper_source
    assert "return _forward_from_yaw(" in helper_source
    assert "ViewAnchorResolverRef" in bridge_source


def test_view_anchor_resolver_normalizes_intent_frame_before_using_forward_fallback() -> None:
    helper_source = (ROOT / "scripts" / "player" / "Phase0ViewAnchorResolver.gd").read_text(
        encoding="utf-8"
    )

    assert "CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)" in helper_source
    assert "func _has_explicit_forward_intent(" in helper_source
    assert "CharacterControllerPortRef.get_actor_id(normalized_frame)" in helper_source
    assert "if not current_intent_frame.is_empty():" not in helper_source


def test_player_shell_normalizes_w_as_positive_local_forward() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "var raw_move_local := Input.get_vector(" in player_shell_source
    assert "move_forward_action" in player_shell_source
    assert "move_backward_action" in player_shell_source
    assert "return Vector2(raw_move_local.x, -raw_move_local.y)" in player_shell_source


def test_archive_door_alignment_compares_actor_forward_with_target_direction() -> None:
    host_source = (
        ROOT / "scripts" / "interaction" / "ArchiveDoorEmbodiedActionHost.gd"
    ).read_text(encoding="utf-8")

    assert "player_bridge.set_forced_look_target(contact.global_position)" in host_source
    assert "var actor_yaw_target := Basis.looking_at(facing.normalized(), Vector3.UP).get_euler().y" in host_source
    assert "if absf(wrapf(_actor_yaw(actor) - actor_yaw_target, -PI, PI)) > FACING_TOLERANCE_RAD:" in host_source
    assert "FACING_TOLERANCE_RAD" in host_source
