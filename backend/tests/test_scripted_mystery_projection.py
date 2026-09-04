from __future__ import annotations

from pathlib import Path

from app.gameplay.action_consequence_runtime import ActionConsequenceBoundary, WorldDeathConfirmationIntent
from app.gameplay.event_store import GameplayEventStore


ROOT = Path(__file__).resolve().parents[2]


def test_reference_scene_is_procedural_and_projection_surface_is_read_only() -> None:
    scene = (ROOT / "scenes" / "phase0" / "ScriptedMysteryActionProbe.tscn").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "verification" / "ScriptedMysteryActionProbe.gd").read_text(encoding="utf-8")
    assert "ScriptedMysteryActionProbe.gd" in scene
    for marker in ("ROOMS", "Occluder", "Door", "Clue", "HideSpot", "sound_zone_ref"):
        assert marker in script
    for method in ("apply_committed_projection", "reject_speculative_state", "get_read_only_projection"):
        assert f"func {method}" in script
    assert "append_batch" not in script
    assert "BackendBridge" not in script


def test_consequence_boundary_has_no_write_path_for_missing_source() -> None:
    store = GameplayEventStore()
    result = ActionConsequenceBoundary(store).validate_world_death(
        WorldDeathConfirmationIntent(
            source_event_id="event:missing",
            target_actor_ref="character:survivor",
            expected_source_revision=1,
            confirmation_ref="confirmation:probe",
            confirmed=True,
            policy_revision="policy:death@1",
        )
    )
    assert result.accepted is False
    assert store.read_events() == []
