from app.population_continuity.vertical import SimingLedPopulationFixture


def test_game_start_to_player_activation_closes_the_seed_vertical() -> None:
    fixture = SimingLedPopulationFixture.create()
    result = fixture.run()

    assert result["cadence"]["status"] == "accepted"
    assert result["population"]["seed_count"] == 1
    assert result["owner"]["owner_ref"] == "actor_gameplay.organization_domain"
    assert result["character"]["continuity_status"] == "committed"
    assert result["activation"]["status"] == "active"
    assert result["activation"]["same_character_identity"] is True
    assert result["activation"]["actual_player_input_path"] is True
    assert result["activation"]["local_structured_intent"] == "observe"
    assert result["activation"]["cognition_status"] == "continuity_floor"
    assert result["replay"]["full_equals_checkpoint_tail"] is True
    assert result["replay"]["independent_character_rebuilds"] is True
    assert result["rejections"]["stale_read_set_zero_write"] is True
    assert result["rejections"]["private_memory_without_exposure_zero_write"] is True
    assert result["rejections"]["duplicate_status"] == "accepted"
    assert result["rejections"]["duplicate_owner_idempotency_status"] == "duplicate_replayed"
    assert result["rejections"]["duplicate_continuity_status"] == "idempotent_replay"
    assert result["rejections"]["duplicate_continuity_projection_unchanged"] is True
    assert result["architecture"]["authority_bus_publish_count"] >= 1
    assert result["architecture"]["population_tick_count"] == 4
