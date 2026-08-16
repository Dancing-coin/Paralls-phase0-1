from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    EcologyConsumerAdmissionCheck,
    Facility,
    Recipe,
)
from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from backend.tests.test_infra_ecology_weather_front_construction_edge import (
    _propagate,
    _record_ecology,
)


REGION = "region:edge:target"
CONSTRUCTION_STREAM = "gameplay:construction_production:facility:c4"
ORGANIZATION_STREAM = "gameplay:organization:organization:c4"


def _seed_construction_stream(store: GameplayEventStore) -> None:
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="command:c4:construction-seed",
            principal_ref="actor_gameplay.construction_production_domain",
            stream_id=CONSTRUCTION_STREAM,
            expected_revision=0,
            event_specs=(
                (
                    "gameplay.construction_production.run_started",
                    {
                        "run_ref": "run:c4",
                        "facility_ref": "facility:c4",
                        "recipe_ref": "recipe:c4",
                        "started_tick": 0,
                        "finish_tick": 1,
                    },
                ),
            ),
            idempotency_key="c4:construction-seed",
            causation_id="cause:c4:construction-seed",
            correlation_id="corr:c4:construction-seed",
        )
    ).committed


def _seed_private_weather_front(store: GameplayEventStore) -> tuple[str, str, int]:
    stream_id = "gameplay:ecology:region:c4:private"
    batch = build_atomic_event_batch(
        command_id="command:c4:private-weather",
        principal_ref="authority:ecology",
        stream_id=stream_id,
        expected_revision=0,
        event_specs=(
            (
                "gameplay.ecology.weather_front.propagated",
                {
                    "source_region_ref": "region:c4:source",
                    "target_region_ref": "region:c4:target",
                    "weather_ref": "weather:storm",
                    "tick": 2,
                },
            ),
        ),
        idempotency_key="c4:private-weather",
        causation_id="cause:c4:private-weather",
        correlation_id="corr:c4:private-weather",
    )
    private_batch = batch.model_copy(
        update={
            "events": [
                event.model_copy(update={"visibility_policy": "authority_only"})
                for event in batch.events
            ]
        },
        deep=True,
    )
    assert store.append_batch(private_batch).committed
    event = store.read_events()[-1]
    return event.event_id, event.stream_id, event.stream_revision


def _setup() -> tuple[
    GameplayEventStore,
    EcologyHazardAuthority,
    ConstructionProductionAuthority,
    OrganizationAuthority,
]:
    store = GameplayEventStore()
    ecology = _record_ecology(store)
    assert _propagate(store, ecology).committed
    _seed_construction_stream(store)
    organization = OrganizationAuthority(store=store)
    assert organization.grant_commerce_budget(
        command_id="command:c4:organization-grant",
        organization_ref="organization:c4",
        grant_ref="grant:c4",
        budget_reservation_ref="reservation:c4",
        amount_minor=100,
        policy_revision="policy:c4",
        idempotency_key="c4:organization-grant",
        causation_id="cause:c4:organization-grant",
        correlation_id="corr:c4:organization-grant",
    ).committed
    construction = ConstructionProductionAuthority(store=store)
    return store, ecology, construction, organization


def _weather_front_event(store: GameplayEventStore):
    return [
        event
        for event in store.read_events()
        if event.event_type == "gameplay.ecology.weather_front.propagated"
        and event.payload.get("target_region_ref") == REGION
    ][-1]


def _run() -> tuple[Facility, Recipe]:
    facility = Facility(
        facility_ref="facility:c4",
        plot_ref="plot:region:edge:target:1",
        facility_kind="mill",
        condition=1,
        revision=0,
    )
    recipe = Recipe(
        recipe_ref="recipe:c4",
        inputs={},
        output_item="item:bread",
        duration_ticks=1,
    )
    return facility, recipe


def test_c4_adapter_admits_construction_contract_metadata_for_existing_stream() -> None:
    store, _, _, _ = _setup()
    source = _weather_front_event(store)

    check = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-construction-maintenance@1",
        target_owner_ref="actor_gameplay.construction_production_domain",
        target_stream_ids=(CONSTRUCTION_STREAM,),
        target_event_types=("gameplay.construction_production.maintenance_obligation_created",),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={CONSTRUCTION_STREAM: 1},
        idempotency_key="c4:construction-contract",
    )

    assert check.accepted
    assert check.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert check.replay_reader_ref == "GameplayProjectionReplay"


def test_c4_adapter_admits_organization_contract_metadata_for_existing_stream() -> None:
    store, _, _, _ = _setup()
    source = _weather_front_event(store)

    check = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-organization-supply@1",
        target_owner_ref="actor_gameplay.organization_domain",
        target_stream_ids=(ORGANIZATION_STREAM,),
        target_event_types=("gameplay.organization.commerce_commitment_accepted",),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={ORGANIZATION_STREAM: 1},
        idempotency_key="c4:organization-contract",
    )

    assert check.accepted
    assert check.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert check.replay_reader_ref == "OrganizationAuthority.commerce_commitment_projection"


def test_c4_adapter_is_reused_by_construction_owner_without_behavior_widening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, ecology, construction, _ = _setup()
    calls: list[str] = []
    original = EcologyConsumerAdmissionCheck.verify.__func__

    def record(cls, **kwargs):
        calls.append(str(kwargs["contract_ref"]))
        return original(cls, **kwargs)

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(record))
    intent, error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref="facility:c4",
        region_ref=REGION,
    )
    assert error is None and intent is not None
    facility, recipe = _run()

    result = construction.settle_canonical_weather_front_maintenance(
        command=intent.command,
        admission=intent.admission,
        run=construction.start_run(
            facility=facility,
            recipe=recipe,
            run_ref="run:c4",
            tick=0,
        ),
        obligation_ref="obligation:c4:construction",
        command_id="command:c4:construction",
        idempotency_key="c4:construction",
        causation_id="cause:c4:construction",
        correlation_id="corr:c4:construction",
        expected_revision=1,
    )

    assert result.committed
    assert calls == ["inf:weather-front-construction-maintenance@1"]
    assert store.read_stream(CONSTRUCTION_STREAM)[-1].event_type == (
        "gameplay.construction_production.maintenance_obligation_created"
    )


def test_c4_adapter_is_reused_by_organization_owner_without_behavior_widening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, ecology, _, organization = _setup()
    calls: list[str] = []
    original = EcologyConsumerAdmissionCheck.verify.__func__

    def record(cls, **kwargs):
        calls.append(str(kwargs["contract_ref"]))
        return original(cls, **kwargs)

    monkeypatch.setattr(EcologyConsumerAdmissionCheck, "verify", classmethod(record))
    intent, error = ecology.admit_weather_front_to_organization_supply(
        organization_ref="organization:c4",
        counterparty_organization_ref="organization:supplier:c4",
        commitment_ref="commitment:c4",
        policy_revision="policy:c4",
        organization_grant_refs=("grant:c4",),
        budget_reservation_refs=("reservation:c4",),
        region_ref=REGION,
    )
    assert error is None and intent is not None

    result = organization.settle_canonical_weather_front_supply(
        command=intent.command,
        admission=intent.admission,
        expected_revision=1,
        idempotency_key="c4:organization",
        causation_id="cause:c4:organization",
        correlation_id="corr:c4:organization",
        privacy_scope="project",
    )

    assert result.committed
    assert calls == ["inf:weather-front-organization-supply@1"]
    assert store.read_stream(ORGANIZATION_STREAM)[-1].event_type == (
        "gameplay.organization.commerce_commitment_accepted"
    )


def test_c4_adapter_rejects_unregistered_forged_owner_stream_privacy_and_revision_without_write() -> None:
    store, _, _, _ = _setup()
    source = _weather_front_event(store)
    private_event_id, private_stream_id, private_revision = _seed_private_weather_front(store)
    before = store.export_snapshot()

    unknown = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-unregistered@1",
        target_owner_ref="actor_gameplay.construction_production_domain",
        target_stream_ids=(CONSTRUCTION_STREAM,),
        target_event_types=("gameplay.construction_production.maintenance_obligation_created",),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={CONSTRUCTION_STREAM: 1},
        idempotency_key="c4:unknown",
    )
    forged = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-construction-maintenance@1",
        target_owner_ref="actor_gameplay.construction_production_domain",
        target_stream_ids=(CONSTRUCTION_STREAM,),
        target_event_types=("gameplay.construction_production.maintenance_obligation_created",),
        projection_scope="project",
        source_event_id="event:forged",
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={CONSTRUCTION_STREAM: 1},
        idempotency_key="c4:forged",
    )
    wrong_owner = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-organization-supply@1",
        target_owner_ref="actor_gameplay.construction_production_domain",
        target_stream_ids=(ORGANIZATION_STREAM,),
        target_event_types=("gameplay.organization.commerce_commitment_accepted",),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={ORGANIZATION_STREAM: 1},
        idempotency_key="c4:wrong-owner",
    )
    wrong_stream = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-organization-supply@1",
        target_owner_ref="actor_gameplay.organization_domain",
        target_stream_ids=("gameplay:economy",),
        target_event_types=("gameplay.organization.commerce_commitment_accepted",),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={"gameplay:economy": 0},
        idempotency_key="c4:wrong-stream",
    )
    private = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-organization-supply@1",
        target_owner_ref="actor_gameplay.organization_domain",
        target_stream_ids=(ORGANIZATION_STREAM,),
        target_event_types=("gameplay.organization.commerce_commitment_accepted",),
        projection_scope="project",
        source_event_id=private_event_id,
        source_stream_id=private_stream_id,
        source_revision=private_revision,
        target_expected_revisions={ORGANIZATION_STREAM: 1},
        idempotency_key="c4:private",
    )
    stale = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-construction-maintenance@1",
        target_owner_ref="actor_gameplay.construction_production_domain",
        target_stream_ids=(CONSTRUCTION_STREAM,),
        target_event_types=("gameplay.construction_production.maintenance_obligation_created",),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision - 1,
        target_expected_revisions={CONSTRUCTION_STREAM: 1},
        idempotency_key="c4:stale",
    )

    assert not unknown.accepted and unknown.error_code == "governed_authority_contract_unknown"
    assert not forged.accepted and forged.error_code == "ecology_consumer_source_missing"
    assert not wrong_owner.accepted and wrong_owner.error_code == "governed_authority_contract_owner_mismatch"
    assert not wrong_stream.accepted and wrong_stream.error_code == "governed_authority_contract_stream_mismatch"
    assert not private.accepted and private.error_code == "ecology_consumer_source_pin_invalid"
    assert not stale.accepted and stale.error_code == "ecology_consumer_source_pin_invalid"
    assert store.export_snapshot() == before


def test_c4_duplicate_idempotency_and_full_checkpoint_tail_replay_hold_for_construction_and_organization() -> None:
    store, ecology, construction, organization = _setup()
    construction_intent, construction_error = ecology.admit_weather_front_to_construction_maintenance(
        facility_ref="facility:c4",
        region_ref=REGION,
    )
    assert construction_error is None and construction_intent is not None
    facility, recipe = _run()
    run = construction.start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:c4",
        tick=0,
    )

    first_construction = construction.settle_canonical_weather_front_maintenance(
        command=construction_intent.command,
        admission=construction_intent.admission,
        run=run,
        obligation_ref="obligation:c4:duplicate:construction",
        command_id="command:c4:duplicate:construction",
        idempotency_key="c4:duplicate:construction",
        causation_id="cause:c4:duplicate:construction",
        correlation_id="corr:c4:duplicate:construction",
        expected_revision=1,
    )
    duplicate_construction = construction.settle_canonical_weather_front_maintenance(
        command=construction_intent.command,
        admission=construction_intent.admission,
        run=run,
        obligation_ref="obligation:c4:duplicate:construction",
        command_id="command:c4:duplicate:construction",
        idempotency_key="c4:duplicate:construction",
        causation_id="cause:c4:duplicate:construction",
        correlation_id="corr:c4:duplicate:construction",
        expected_revision=1,
    )
    assert first_construction.committed
    assert duplicate_construction.idempotency_status == "duplicate_replayed"

    organization_intent, organization_error = ecology.admit_weather_front_to_organization_supply(
        organization_ref="organization:c4",
        counterparty_organization_ref="organization:supplier:c4",
        commitment_ref="commitment:c4:duplicate",
        policy_revision="policy:c4",
        organization_grant_refs=("grant:c4",),
        budget_reservation_refs=("reservation:c4",),
        region_ref=REGION,
    )
    assert organization_error is None and organization_intent is not None
    first_organization = organization.settle_canonical_weather_front_supply(
        command=organization_intent.command,
        admission=organization_intent.admission,
        expected_revision=1,
        idempotency_key="c4:duplicate:organization",
        causation_id="cause:c4:duplicate:organization",
        correlation_id="corr:c4:duplicate:organization",
        privacy_scope="project",
    )
    duplicate_organization = organization.settle_canonical_weather_front_supply(
        command=organization_intent.command,
        admission=organization_intent.admission,
        expected_revision=1,
        idempotency_key="c4:duplicate:organization",
        causation_id="cause:c4:duplicate:organization",
        correlation_id="corr:c4:duplicate:organization",
        privacy_scope="project",
    )
    assert first_organization.committed
    assert duplicate_organization.idempotency_status == "duplicate_replayed"

    events = store.read_events()
    replay = GameplayProjectionReplay(
        projector_id="infra-c4-ecology-consumer",
        projector_version="1",
    )
    checkpoint_at = len(events) - 2
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(
        replay.create_checkpoint(events[:checkpoint_at]),
        events[checkpoint_at:],
    ).projection_hash
