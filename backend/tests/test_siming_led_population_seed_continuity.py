from app.population_continuity.vertical import SimingLedPopulationFixture
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import PopulationWorldPlan
from app.models.authority_event import AuthorityEvent


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


def test_duplicate_batch_ref_with_changed_plan_is_zero_write_and_has_no_settled_seed() -> None:
    fixture = SimingLedPopulationFixture.create()
    fixture.bus.publish(fixture.cadence_event)
    first = fixture.capability.last_result
    assert first is not None and first.seed_candidates

    tampered = fixture.cadence_event.model_dump(mode="json")
    tampered["event_id"] = "event:population-cadence:bakery:tampered-duplicate"
    plan = tampered["payload"]["population_world_plan"]
    plan["candidates"][0]["payload"]["commitment_ref"] = "commitment:tampered"
    tampered_plan = PopulationWorldPlan.model_validate(plan)
    activation = ProfileActivationAuthority(
        registry=fixture.bakery.registry,
        store=fixture.bakery.store,
    )
    fixture.bakery._admit_released_schedule_gated_supply(
        activation=activation,
        batch_ref="batch:siming-led:game-start:tampered-admission",
        recipient_ref="character:char_a",
        plan=tampered_plan,
    )
    tampered["payload"]["activation_pending_projection"] = (
        activation.pending_projection(tampered_plan.world_ref)
    )
    before_events = len(fixture.bakery.store.read_events())

    fixture.bus.publish(AuthorityEvent.model_validate(tampered))
    duplicate = fixture.capability.last_result
    assert duplicate is not None
    assert all(
        seed.owner_effect_status != "settled"
        for seed in duplicate.seed_candidates
    )
    assert duplicate.production_append_count == 0
    assert duplicate.owner_receipts
    assert duplicate.owner_receipts[0].committed is False
    assert duplicate.owner_receipts[0].zero_write is True
    assert len(fixture.bakery.store.read_events()) == before_events
