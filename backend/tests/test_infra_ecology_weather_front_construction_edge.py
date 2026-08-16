from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Recipe,
)
from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EcologyWeatherFrontPropagationPolicy,
    EnvironmentRegion,
    EnvironmentalState,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _record_ecology(store: GameplayEventStore) -> EcologyHazardAuthority:
    authority = EcologyHazardAuthority(store=store)
    for region_ref, neighbors, weather_ref in (
        ("region:edge:source", ("region:edge:target",), "weather:rain"),
        ("region:edge:target", ("region:edge:source",), "weather:clear"),
    ):
        result = authority.record_region_bundle(
            envelope=GameplayCommandEnvelope(
                command_id=f"command:{region_ref}",
                command_type="gameplay.ecology.region_bundle.record",
                command_version=1,
                principal_ref="authority:ecology",
                idempotency_key=f"initial:{region_ref}",
                expected_revisions={authority.ecology_stream_id(region_ref=region_ref): 0},
                causation_id=f"cause:{region_ref}",
                correlation_id=f"corr:{region_ref}",
                source_ref="authority:ecology",
                submitted_at="2026-08-15T00:00:00Z",
                payload={"visibility_scope": "project"},
            ),
            region=EnvironmentRegion(
                region_ref=region_ref,
                climate_profile_ref="climate:temperate",
                biome_tags=("biome:field",),
                jurisdiction_ref=f"jurisdiction:{region_ref}",
                neighbor_region_refs=neighbors,
                revision=0,
            ),
            environment=EnvironmentalState(
                region_ref=region_ref,
                temperature_centi_c=175,
                moisture_basis_points=4_000,
                weather_ref=weather_ref,
                revision=0,
            ),
            resource=ResourceNode(
                node_ref=f"resource:{region_ref}:water",
                region_ref=region_ref,
                substance_ref="substance:water",
                quantity=90,
                regeneration_per_tick=2,
                revision=0,
            ),
            crop=CropRecord(
                crop_ref=f"crop:{region_ref}:wheat",
                region_ref=region_ref,
                plot_ref=f"plot:{region_ref}:1",
                health=100,
                growth_basis_points=5_000,
                revision=0,
                owner_ref="authority:crop",
            ),
            hazard=HazardRecord(
                hazard_ref=f"hazard:{region_ref}:frost",
                region_ref=region_ref,
                effect_ref="effect:frost",
                severity_basis_points=5_000,
                due_tick=3,
                duration_ticks=1,
                semantic_revision="semantic:1",
                rule_revision="rule:1",
                policy_revision="policy:1",
                idempotency_key=f"hazard:{region_ref}",
            ),
        )
        assert result.committed
    return authority


def _propagate(store: GameplayEventStore, ecology: EcologyHazardAuthority, *, key: str = "weather-edge:one", tick: int = 4):
    source = ecology.ecology_stream_id(region_ref="region:edge:source")
    target = ecology.ecology_stream_id(region_ref="region:edge:target")
    return ecology.propagate_weather_front(
        envelope=GameplayCommandEnvelope(
            command_id=f"command:{key}",
            command_type="gameplay.ecology.weather_front.propagate",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key=key,
            expected_revisions={source: store.get_stream_head(source), target: store.get_stream_head(target)},
            causation_id=f"cause:{key}",
            correlation_id=f"corr:{key}",
            source_ref="authority:ecology",
            submitted_at="2026-08-15T00:00:00Z",
            payload={"visibility_scope": "project", "tick": tick},
        ),
        policy=EcologyWeatherFrontPropagationPolicy(),
        source_region_ref="region:edge:source",
        target_region_ref="region:edge:target",
    )


def _setup():
    store = GameplayEventStore()
    ecology = _record_ecology(store)
    assert _propagate(store, ecology).committed
    construction = ConstructionProductionAuthority(store=store)
    run = construction.start_run(
        facility=Facility(
            facility_ref="facility:edge",
            plot_ref="plot:region:edge:target:1",
            facility_kind="mill",
            condition=1,
            revision=0,
        ),
        recipe=Recipe(recipe_ref="recipe:edge", inputs={}, output_item="item:bread", duration_ticks=1),
        run_ref="run:edge",
        tick=0,
    )
    return store, ecology, construction, run


def test_weather_front_construction_edge_writes_existing_maintenance_event_only() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref=run.facility_ref,
        region_ref="region:edge:target",
    )
    assert error is None and intent is not None
    result = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:edge",
        command_id="command:construction:weather-edge",
        idempotency_key="construction:weather-edge",
        causation_id="event:weather-edge",
        correlation_id="corr:weather-edge",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )
    assert result.committed
    event = store.read_stream("gameplay:construction_production:facility:edge")[-1]
    assert event.event_type == "gameplay.construction_production.maintenance_obligation_created"
    assert event.payload["weather_front_ecology_propagation"]["edge_ref"] == "ecology-weather:front-to-construction-maintenance:v1"


def test_weather_front_construction_edge_rejects_missing_or_forged_admission_without_writes() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref=run.facility_ref,
        region_ref="region:edge:target",
    )
    assert error is None and intent is not None
    before = len(store.read_events())
    denied = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=None,
        run=run,
        obligation_ref="obligation:denied",
        command_id="command:denied",
        idempotency_key="construction:denied",
        causation_id="cause",
        correlation_id="corr",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )
    forged = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=object(),
        run=run,
        obligation_ref="obligation:forged",
        command_id="command:forged",
        idempotency_key="construction:forged",
        causation_id="cause",
        correlation_id="corr",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )
    assert denied.failure is not None and denied.failure.error_code == "weather_front_maintenance_admission_required"
    assert forged.failure is not None and forged.failure.error_code == "weather_front_maintenance_admission_required"
    assert len(store.read_events()) == before


def test_weather_front_construction_catalog_mismatch_rejects_before_append(monkeypatch) -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref=run.facility_ref,
        region_ref="region:edge:target",
    )
    assert error is None and intent is not None
    before = len(store.read_events())

    def reject_contract(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_event_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)
    result = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:catalog",
        command_id="command:construction:weather-catalog",
        idempotency_key="construction:weather-catalog",
        causation_id="event:weather-catalog",
        correlation_id="corr:weather-catalog",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "governed_authority_contract_event_mismatch"
    assert len(store.read_events()) == before


def test_weather_front_construction_edge_is_revisioned_idempotent_private_and_replayable() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref=run.facility_ref,
        region_ref="region:edge:target",
    )
    assert error is None and intent is not None
    first = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:edge",
        command_id="command:construction:weather-edge",
        idempotency_key="construction:weather-edge",
        causation_id="event:weather-edge",
        correlation_id="corr:weather-edge",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )
    duplicate = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:edge",
        command_id="command:construction:weather-edge",
        idempotency_key="construction:weather-edge",
        causation_id="event:weather-edge",
        correlation_id="corr:weather-edge",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )
    before = len(store.read_events())
    stale = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:stale",
        command_id="command:construction:weather-stale",
        idempotency_key="construction:weather-stale",
        causation_id="event:weather-edge",
        correlation_id="corr:weather-edge",
        expected_revision=0,
    )
    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before
    assert store.list_outbox()[-1].audience == "project"
    from app.gameplay.replay import GameplayProjectionReplay

    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="infra-weather-construction-edge", projector_version="1")
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(
        replay.create_checkpoint(events[: len(events) - 1]), events[len(events) - 1 :]
    ).projection_hash


def test_weather_front_construction_edge_rejects_stale_ecology_source_without_target_write() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref=run.facility_ref,
        region_ref="region:edge:target",
    )
    assert error is None and intent is not None
    assert _propagate(store, ecology, key="weather-edge:two", tick=5).committed
    before = len(store.read_events())
    denied = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:stale-source",
        command_id="command:stale-source",
        idempotency_key="construction:weather-stale-source",
        causation_id="cause",
        correlation_id="corr",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )
    assert denied.failure is not None and denied.failure.error_code == "weather_front_maintenance_source_revision_conflict"
    assert len(store.read_events()) == before


def test_weather_front_construction_edge_rejects_changed_duplicate_without_writes() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref=run.facility_ref,
        region_ref="region:edge:target",
    )
    assert error is None and intent is not None
    assert construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:one",
        command_id="command:weather-one",
        idempotency_key="construction:weather-changed",
        causation_id="cause",
        correlation_id="corr",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    ).committed
    before = len(store.read_events())
    changed = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=run,
        obligation_ref="obligation:weather:changed",
        command_id="command:weather-changed",
        idempotency_key="construction:weather-changed",
        causation_id="cause",
        correlation_id="corr",
        expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge"),
    )
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before


def test_weather_front_construction_edge_exact_duplicate_replays_without_second_write() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(facility_ref=run.facility_ref, region_ref="region:edge:target")
    assert error is None and intent is not None
    expected = store.get_stream_head("gameplay:construction_production:facility:edge")
    first = construction.settle_canonical_weather_front_maintenance(command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:duplicate", command_id="command:duplicate", idempotency_key="construction:duplicate", causation_id="cause", correlation_id="corr", expected_revision=expected)
    before = len(store.read_events())
    duplicate = construction.settle_canonical_weather_front_maintenance(command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:duplicate", command_id="command:duplicate", idempotency_key="construction:duplicate", causation_id="cause", correlation_id="corr", expected_revision=expected)
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before


def test_weather_front_construction_edge_rejects_stale_target_revision_without_writes() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(facility_ref=run.facility_ref, region_ref="region:edge:target")
    assert error is None and intent is not None
    expected = store.get_stream_head("gameplay:construction_production:facility:edge")
    assert construction.settle_canonical_weather_front_maintenance(command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:target", command_id="command:target", idempotency_key="construction:target", causation_id="cause", correlation_id="corr", expected_revision=expected).committed
    before = len(store.read_events())
    stale = construction.settle_canonical_weather_front_maintenance(command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:target-stale", command_id="command:target-stale", idempotency_key="construction:target-stale", causation_id="cause", correlation_id="corr", expected_revision=expected)
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_weather_front_construction_edge_outbox_is_project_scoped_and_redacted() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(facility_ref=run.facility_ref, region_ref="region:edge:target")
    assert error is None and intent is not None
    assert construction.settle_canonical_weather_front_maintenance(command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:outbox", command_id="command:outbox", idempotency_key="construction:outbox", causation_id="cause", correlation_id="corr", expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge")).committed
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "project" and "weather_front_ecology_propagation" not in outbox.payload_projection


def test_weather_front_construction_edge_full_and_checkpoint_tail_replay_match() -> None:
    store, ecology, construction, run = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance(facility_ref=run.facility_ref, region_ref="region:edge:target")
    assert error is None and intent is not None
    assert construction.settle_canonical_weather_front_maintenance(command=intent.command, admission=intent.admission, run=run, obligation_ref="obligation:replay", command_id="command:replay", idempotency_key="construction:replay", causation_id="cause", correlation_id="corr", expected_revision=store.get_stream_head("gameplay:construction_production:facility:edge")).committed
    from app.gameplay.replay import GameplayProjectionReplay

    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="infra-weather-construction-edge", projector_version="1")
    checkpoint_at = len(events) - 1
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(replay.create_checkpoint(events[:checkpoint_at]), events[checkpoint_at:]).projection_hash


def test_weather_front_construction_edge_rejects_private_source_without_writes() -> None:
    store = GameplayEventStore()
    ecology = _record_ecology(store)
    source = ecology.ecology_stream_id(region_ref="region:edge:source")
    target = ecology.ecology_stream_id(region_ref="region:edge:target")
    result = ecology.propagate_weather_front(
        envelope=GameplayCommandEnvelope(
            command_id="command:weather-private",
            command_type="gameplay.ecology.weather_front.propagate",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="weather-edge:private",
            expected_revisions={source: store.get_stream_head(source), target: store.get_stream_head(target)},
            causation_id="cause:private",
            correlation_id="corr:private",
            source_ref="authority:ecology",
            submitted_at="2026-08-15T00:00:00Z",
            payload={"visibility_scope": "authority_only", "tick": 4},
        ),
        policy=EcologyWeatherFrontPropagationPolicy(),
        source_region_ref="region:edge:source",
        target_region_ref="region:edge:target",
    )
    assert result.failure is not None and result.failure.error_code == "ecology_front_privacy_scope_denied"
