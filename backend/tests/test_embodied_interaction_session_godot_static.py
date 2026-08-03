from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_interaction_session_slot_consumer_uses_safe_projection_without_world_truth_controls() -> None:
    source = (ROOT / "scripts" / "interaction" / "InteractionSessionSlotConsumer.gd").read_text(encoding="utf-8")

    assert "class_name InteractionSessionSlotConsumer" in source
    assert "func consume_authority_event(payload: Dictionary) -> Dictionary:" in source
    assert "participant_private_terms" in source
    assert "private_terms_rejected" in source
    assert "character_actor_status" not in source
    assert "bone_transforms" not in source
    assert "rigid_body_velocity" not in source
    assert "applied_world_state" not in source


def test_interaction_session_runtime_probe_records_slot_observation_and_privacy_rejection() -> None:
    probe = (ROOT / "scripts" / "verification" / "EmbodiedInteractionSessionProbe.gd").read_text(encoding="utf-8")
    scene = (ROOT / "scenes" / "phase0" / "EmbodiedInteractionSessionProbe.tscn").read_text(encoding="utf-8")

    assert "InteractionSessionSlotConsumer.gd" in probe
    assert "embodied_interaction_session_probe:verified=true" in probe
    assert "participant_observation_emitted" in probe
    assert "private_terms_rejected" in probe
    assert "res://scripts/verification/EmbodiedInteractionSessionProbe.gd" in scene
