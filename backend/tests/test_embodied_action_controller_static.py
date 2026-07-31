from __future__ import annotations

from pathlib import Path


def test_embodied_action_controller_script_declares_local_state_machine_and_boundaries() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_path = project_root / "scripts" / "interaction" / "EmbodiedActionController.gd"
    source = controller_path.read_text(encoding="utf-8")

    for state in [
        "acquire_target",
        "reserve_stance",
        "plan_approach",
        "navigate",
        "align",
        "prepare",
        "execute_contact",
        "observe",
        "recover",
        "terminal",
    ]:
        assert state in source
    for terminal_status in [
        "contact_observed",
        "failed_navigation",
        "failed_alignment",
        "missed_contact",
        "failed_precondition",
        "interrupted",
        "aborted",
    ]:
        assert terminal_status in source
    assert "controller_grant_id" in source
    assert "connection_epoch" in source
    assert "outcome_nonce" in source
    assert "realization_route" in source
    assert "NavigationAgent3D" in source
    assert "CollisionShape3D" in source
    assert "character_actor_status" not in source
    assert "bone_stream" not in source
    assert "rigid_body_stream" not in source
    assert "apply_impulse" not in source
