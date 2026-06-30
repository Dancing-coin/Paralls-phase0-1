from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot


def test_private_snapshot_tracks_modality_and_quality_specific_fields() -> None:
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1,
        updated_at=1,
        olfactory_entities=["smoke_trace"],
        thermal_entities=["heat_bloom"],
        tactile_entities=["nearby_brush_contact"],
        partial_observations=["char_b motion silhouette only"],
        distorted_details=["voice direction uncertain"],
        missed_details=["speaker identity lost in noise"],
    )

    assert snapshot.olfactory_entities == ["smoke_trace"]
    assert snapshot.partial_observations == ["char_b motion silhouette only"]
