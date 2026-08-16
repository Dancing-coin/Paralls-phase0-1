from __future__ import annotations

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EcologySeasonalProcessPolicy,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Recipe
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _bundle() -> tuple[EnvironmentRegion, EnvironmentalState, ResourceNode, CropRecord, HazardRecord]:
    region = EnvironmentRegion(region_ref="region:process", climate_profile_ref="climate:temperate", biome_tags=("biome:field",), jurisdiction_ref="jurisdiction:process", revision=0)
    return (
        region,
        EnvironmentalState(region_ref=region.region_ref, temperature_centi_c=175, moisture_basis_points=4_000, weather_ref="weather:clear", revision=0),
        ResourceNode(node_ref="resource:process:water", region_ref=region.region_ref, substance_ref="substance:water", quantity=90, regeneration_per_tick=2, revision=0),
        CropRecord(crop_ref="crop:process:wheat", region_ref=region.region_ref, plot_ref="plot:process:1", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop"),
        HazardRecord(hazard_ref="hazard:process:frost", region_ref=region.region_ref, effect_ref="effect:frost", severity_basis_points=5_000, due_tick=3, duration_ticks=1, causal_parent_refs=("event:weather:process",), semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1", idempotency_key="ecology:process:initial"),
    )


def _envelope(*, command_id: str, key: str, expected_revision: int, tick: int, principal: str = "authority:ecology", scope: str = "project") -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=command_id,
        command_type="gameplay.ecology.seasonal_process.advance",
        command_version=1,
        principal_ref=principal,
        idempotency_key=key,
        expected_revisions={"gameplay:ecology:region:process": expected_revision},
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref=principal,
        submitted_at="2026-08-14T00:00:00Z",
        payload={"visibility_scope": scope, "tick": tick},
    )


def _record(store: GameplayEventStore) -> EcologyHazardAuthority:
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    result = authority.record_region_bundle(
        envelope=_envelope(command_id="command:initial", key="ecology:process:initial", expected_revision=0, tick=0),
        region=region,
        environment=environment,
        resource=resource,
        crop=crop,
        hazard=hazard,
    )
    assert result.committed is True
    return authority


def test_closed_seasonal_process_advances_environment_resource_and_crop_through_one_owner_batch() -> None:
    store = GameplayEventStore()
    authority = _record(store)

    result = authority.advance_seasonal_process(
        envelope=_envelope(command_id="command:advance", key="ecology:process:advance:3", expected_revision=5, tick=3),
        policy=EcologySeasonalProcessPolicy(),
        region_ref="region:process",
    )

    assert result.committed is True
    events = store.read_events()
    assert [event.event_type for event in events[-4:]] == [
        "gameplay.ecology.environment.recorded",
        "gameplay.ecology.resource.recorded",
        "gameplay.ecology.crop.recorded",
        "gameplay.ecology.seasonal_process_advanced",
    ]
    projection = authority.regional_projection(scope="authority")
    assert projection["environments"]["region:process"]["weather_ref"] == "weather:rain"
    assert projection["resources"]["resource:process:water"]["quantity"] == 96
    assert projection["crops"]["crop:process:wheat"]["growth_basis_points"] == 5_150
    assert projection["processes"]["region:process"]["last_tick"] == 3
    assert len(store.list_outbox()) == 9


def test_seasonal_process_is_idempotent_revisioned_private_rejected_and_replayable() -> None:
    store = GameplayEventStore()
    authority = _record(store)
    command = _envelope(command_id="command:advance", key="ecology:process:advance:3", expected_revision=5, tick=3)
    first = authority.advance_seasonal_process(envelope=command, policy=EcologySeasonalProcessPolicy(), region_ref="region:process")
    duplicate = authority.advance_seasonal_process(envelope=command, policy=EcologySeasonalProcessPolicy(), region_ref="region:process")
    before = len(store.read_events())
    stale = authority.advance_seasonal_process(envelope=_envelope(command_id="command:stale", key="ecology:process:stale", expected_revision=5, tick=4), policy=EcologySeasonalProcessPolicy(), region_ref="region:process")
    private = authority.advance_seasonal_process(envelope=_envelope(command_id="command:private", key="ecology:process:private", expected_revision=9, tick=4, scope="authority_only"), policy=EcologySeasonalProcessPolicy(), region_ref="region:process")
    forged = authority.advance_seasonal_process(envelope=_envelope(command_id="command:forged", key="ecology:process:forged", expected_revision=9, tick=4, principal="client:godot"), policy=EcologySeasonalProcessPolicy(), region_ref="region:process")

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert private.failure is not None and private.failure.error_code == "ecology_process_privacy_scope_denied"
    assert forged.failure is not None and forged.failure.error_code == "ecology_authority_required"
    assert len(store.read_events()) == before
    assert authority.regional_projection(scope="public")["processes"] == {"region:process": {"last_tick": 3, "policy_ref": "policy:ecology_seasonal_cycle"}}
    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=6).projection_hash


def test_seasonal_process_proposes_only_one_admitted_construction_maintenance_fragment() -> None:
    store = GameplayEventStore()
    ecology = _record(store)
    assert ecology.advance_seasonal_process(
        envelope=_envelope(command_id="command:edge:seasonal", key="ecology:edge:seasonal", expected_revision=5, tick=3),
        policy=EcologySeasonalProcessPolicy(),
        region_ref="region:process",
    ).committed
    intent, error = ecology.admit_seasonal_process_to_construction_maintenance(region_ref="region:process")
    assert error is None and intent is not None
    construction = ConstructionProductionAuthority(store=store)
    run = construction.start_run(
        facility=Facility(facility_ref="facility:process", plot_ref="plot:process:1", facility_kind="mill", condition=1, revision=0),
        recipe=Recipe(recipe_ref="recipe:process", inputs={}, output_item="item:bread", duration_ticks=1),
        run_ref="run:process", tick=0,
    )
    result = construction.settle_canonical_seasonal_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:maintenance:process",
        command_id="command:construction:seasonal-maintenance",
        idempotency_key="construction:seasonal-maintenance",
        causation_id="event:seasonal",
        correlation_id="corr:seasonal",
        expected_revision=0,
    )
    assert result.committed is True
    event = store.read_stream("gameplay:construction_production:facility:process")[-1]
    assert event.event_type == "gameplay.construction_production.maintenance_obligation_created"
    assert event.payload["seasonal_ecology_propagation"]["edge_ref"] == "ecology-process:seasonal-to-construction-maintenance:v1"


def _seasonal_intent(store: GameplayEventStore):
    ecology = _record(store)
    assert ecology.advance_seasonal_process(
        envelope=_envelope(command_id="command:edge:seasonal", key="ecology:edge:seasonal", expected_revision=5, tick=3),
        policy=EcologySeasonalProcessPolicy(), region_ref="region:process",
    ).committed
    intent, error = ecology.admit_seasonal_process_to_construction_maintenance(region_ref="region:process")
    assert error is None and intent is not None
    construction = ConstructionProductionAuthority(store=store)
    run = construction.start_run(
        facility=Facility(facility_ref="facility:process", plot_ref="plot:process:1", facility_kind="mill", condition=1, revision=0),
        recipe=Recipe(recipe_ref="recipe:process", inputs={}, output_item="item:bread", duration_ticks=1), run_ref="run:process", tick=0,
    )
    return ecology, construction, run, intent


def test_seasonal_maintenance_requires_exact_closed_admission_without_writes() -> None:
    store = GameplayEventStore()
    _, construction, run, intent = _seasonal_intent(store)
    before = len(store.read_events())
    denied = construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=None, run=run, obligation_ref="obligation:denied",
        command_id="command:denied", idempotency_key="seasonal:denied", causation_id="cause", correlation_id="corr", expected_revision=0,
    )
    assert denied.committed is False and denied.failure is not None
    assert denied.failure.error_code == "seasonal_maintenance_admission_required"
    assert len(store.read_events()) == before


def test_seasonal_maintenance_rejects_stale_ecology_source_without_target_write() -> None:
    store = GameplayEventStore()
    ecology, construction, run, intent = _seasonal_intent(store)
    assert ecology.advance_seasonal_process(
        envelope=_envelope(command_id="command:edge:stale", key="ecology:edge:stale", expected_revision=9, tick=4),
        policy=EcologySeasonalProcessPolicy(), region_ref="region:process",
    ).committed
    denied = construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:stale",
        command_id="command:stale", idempotency_key="seasonal:stale", causation_id="cause", correlation_id="corr", expected_revision=0,
    )
    assert denied.committed is False and denied.failure is not None
    assert denied.failure.error_code == "seasonal_maintenance_source_revision_conflict"
    assert store.read_stream("gameplay:construction_production:facility:process") == []


def test_seasonal_maintenance_is_idempotent() -> None:
    store = GameplayEventStore()
    _, construction, run, intent = _seasonal_intent(store)
    first = construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:one",
        command_id="command:one", idempotency_key="seasonal:one", causation_id="cause", correlation_id="corr", expected_revision=0,
    )
    duplicate = construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:one",
        command_id="command:one", idempotency_key="seasonal:one", causation_id="cause", correlation_id="corr", expected_revision=0,
    )
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"


def test_seasonal_maintenance_rejects_stale_target_revision_without_writes() -> None:
    store = GameplayEventStore()
    _, construction, run, intent = _seasonal_intent(store)
    assert construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:one",
        command_id="command:one", idempotency_key="seasonal:one", causation_id="cause", correlation_id="corr", expected_revision=0,
    ).committed
    before = len(store.read_events())
    stale = construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:two",
        command_id="command:two", idempotency_key="seasonal:two", causation_id="cause", correlation_id="corr", expected_revision=0,
    )
    assert stale.committed is False and stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_seasonal_maintenance_project_outbox_redacts_ecology_provenance() -> None:
    store = GameplayEventStore()
    _, construction, run, intent = _seasonal_intent(store)
    assert construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:replay",
        command_id="command:replay", idempotency_key="seasonal:replay", causation_id="cause", correlation_id="corr", expected_revision=0,
    ).committed
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "project" and "seasonal_ecology_propagation" not in outbox.payload_projection


def test_seasonal_maintenance_checkpoint_tail_replay_matches_full_replay() -> None:
    store = GameplayEventStore()
    _, construction, run, intent = _seasonal_intent(store)
    assert construction.settle_canonical_seasonal_maintenance(
        command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:replay",
        command_id="command:replay", idempotency_key="seasonal:replay", causation_id="cause", correlation_id="corr", expected_revision=0,
    ).committed
    events = store.read_events()
    assert ecology_replay_hash(events) == ecology_replay_hash(events, checkpoint_at=5)


def ecology_replay_hash(events, *, checkpoint_at: int | None = None) -> str:
    from app.gameplay.replay import GameplayProjectionReplay

    replay = GameplayProjectionReplay(projector_id="infra-seasonal-maintenance", projector_version="1")
    if checkpoint_at is None:
        return replay.full_replay(events).projection_hash
    checkpoint = replay.create_checkpoint(events[:checkpoint_at])
    return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:]).projection_hash
