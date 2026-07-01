from app.world_runtime.models import WorldEntityRef, WorldRuntimeEnvelope, WorldStateDelta


def test_world_entity_ref_supports_actor_object_environment_and_zone() -> None:
    ref = WorldEntityRef(entity_type="actor", entity_id="char_a", zone_id="zone_focus")

    assert ref.entity_type == "actor"
    assert ref.zone_id == "zone_focus"


def test_world_state_delta_tracks_changed_fields() -> None:
    delta = WorldStateDelta(
        entity=WorldEntityRef(entity_type="environment", entity_id="env_lamp"),
        changed_fields={"light_level": "low", "visibility_level": "reduced"},
        producer_ts=9,
    )

    assert delta.changed_fields["light_level"] == "low"


def test_world_runtime_envelope_groups_refs_and_deltas() -> None:
    envelope = WorldRuntimeEnvelope(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        facts=["visual_fact"],
        deltas=[],
    )

    assert envelope.scene_id == "scene_demo"
