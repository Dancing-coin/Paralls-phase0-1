from __future__ import annotations

import pytest

from app.gameplay import contract_runtime
from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    FacilityOperationalVerificationIntentV1,
    Plot,
    Recipe,
)
from app.gameplay.contract_runtime import (
    ContractAuthorityService,
    ContractProjector,
    ContractRuntimeError,
    ContractTermsDefinition,
    ContractTermsRegistry,
)
from app.gameplay.event_store import GameplayEventStore


SERVICE = "service:industrial-facility-public-workshop-session@1"
EVIDENCE = "evidence:industrial-facility-public-workshop-session@1"
POLICY = "policy:industrial-facility-public-workshop-session@1"
POLICY_AUTHORITY = "authority:municipal-assessment"
PROVIDER = "organization:municipal-assessment-office"
RECEIVER = "organization:mill"


def _source() -> tuple[GameplayEventStore, ConstructionProductionAuthority, object]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:inf2ag",
        plot_ref="plot:inf2ag",
        facility_kind="oven",
        condition=1.0,
    )
    recipe = Recipe(
        recipe_ref="recipe:inf2ag",
        inputs={},
        output_item="item:inf2ag",
        duration_ticks=1,
    )
    assert authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref=facility.plot_ref,
            jurisdiction_ref="jurisdiction:inf2ag",
            owner_ref=RECEIVER,
        ),
        facility=facility,
        command_id="inf2ag:acquire",
        idempotency_key="inf2ag:acquire",
        causation_id="cause:inf2ag",
        correlation_id="corr:inf2ag",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:inf2ag",
        tick=1,
        command_id="inf2ag:start",
        idempotency_key="inf2ag:start",
        causation_id="cause:inf2ag",
        correlation_id="corr:inf2ag",
    ).committed
    run = authority.projector().runs["run:inf2ag"]
    assert authority.settle_finish_run(
        run,
        tick=2,
        recipe=recipe,
        command_id="inf2ag:finish",
        idempotency_key="inf2ag:finish",
        causation_id="cause:inf2ag",
        correlation_id="corr:inf2ag",
    ).committed
    verified = authority.verify_facility_operationally(
        FacilityOperationalVerificationIntentV1(
            run_finished_event_id="event:inf2ag:finish:1",
            expected_run_finished_revision=3,
            expected_run_started_revision=2,
            expected_facility_revision=0,
            expected_stream_revision=3,
            command_id="inf2ag:verify",
            idempotency_key="construction:facility-operational-verification:event:inf2ag:finish:1:3:0:3:v1",
            causation_id="cause:inf2ag",
            correlation_id="corr:inf2ag",
            submitted_at="2026-08-27T12:00:00Z",
        )
    )
    assert verified.committed
    verification = store.get_event(verified.committed_event_ids[0])
    enabled = authority.enable_facility_public_use(
        verification_event_id=verification.event_id,
        expected_verification_revision=verification.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=verification.stream_revision,
        command_id="inf2ag:enable",
        idempotency_key=(
            f"construction:facility-public-use-enable:{verification.event_id}:"
            f"{verification.stream_revision}:0:{verification.stream_revision}:v1"
        ),
        causation_id="cause:inf2ag",
        correlation_id="corr:inf2ag",
        submitted_at="2026-08-27T12:01:00Z",
    )
    assert enabled.committed
    return store, authority, store.get_event(enabled.committed_event_ids[0])


def _contracts(store: GameplayEventStore) -> ContractAuthorityService:
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(SERVICE, "simple_service", 2, EVIDENCE))
    return ContractAuthorityService(
        store=store,
        terms_registry=terms,
        policy_authorities={POLICY_AUTHORITY},
    )


def _request(store: GameplayEventStore, source_event_id: str, **updates: object) -> object:
    source = store.get_event(source_event_id)
    values: dict[str, object] = {
        "public_use_event_id": source_event_id,
        "expected_public_use_revision": source.stream_revision,
        "expected_contract_revision": store.get_stream_head("gameplay:contracts"),
        "command_id": "command:facility-public-workshop:contract",
        "idempotency_key": "pending",
        "causation_id": source_event_id,
        "correlation_id": "corr:facility-public-workshop",
        "submitted_at": "2026-08-27T12:02:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"contract:public-workshop-session:{source_event_id}:"
        f"{values['expected_public_use_revision']}:{values['expected_contract_revision']}:v1"
    )
    intent_type = getattr(contract_runtime, "PublicWorkshopSessionContractIntentV1", None)
    assert intent_type is not None, "missing facility public workshop contract intent"
    return intent_type.model_validate(values)


def test_public_use_creates_and_fulfills_fixed_public_workshop_contract() -> None:
    store, _authority, source_event = _source()
    contracts = _contracts(store)

    created = contracts.create_public_workshop_session_from_public_use(
        _request(store, source_event.event_id)
    )
    assert created.committed, created.failure
    created_event = store.get_event(created.committed_event_ids[0])
    assert created_event.event_type == "gameplay.contract.record_created"
    assert created_event.visibility_policy == "authority_only"
    assert created_event.payload["terms_ref"] == SERVICE
    assert created_event.payload["party_refs"] == [PROVIDER, RECEIVER]
    assert created_event.payload["public_use_event_id"] == source_event.event_id

    fulfillment_type = getattr(contract_runtime, "PublicWorkshopSessionFulfillmentIntentV1", None)
    assert fulfillment_type is not None, "missing facility public workshop fulfillment intent"
    head = store.get_stream_head("gameplay:contracts")
    fulfilled = contracts.fulfill_public_workshop_session_by_policy(
        fulfillment_type.model_validate(
            {
                "contract_created_event_id": created_event.event_id,
                "expected_contract_created_revision": created_event.stream_revision,
                "expected_public_use_revision": source_event.stream_revision,
                "expected_contract_head": head,
                "command_id": "command:facility-public-workshop:fulfill",
                "idempotency_key": (
                    f"contract:public-workshop-session:fulfillment:{created_event.event_id}:"
                    f"{created_event.stream_revision}:{source_event.stream_revision}:{head}:v1"
                ),
                "causation_id": created_event.event_id,
                "correlation_id": "corr:facility-public-workshop",
                "submitted_at": "2026-08-27T12:03:00Z",
            }
        )
    )
    assert fulfilled.committed, fulfilled.failure
    events = [store.get_event(event_id) for event_id in fulfilled.committed_event_ids]
    assert [event.event_type for event in events] == [
        "gameplay.contract.service_completion_recorded",
        "gameplay.contract.record_fulfilled",
    ]
    assert all(event.visibility_policy == "authority_only" for event in events)
    assert events[0].payload["completion_evidence_kind"] == EVIDENCE
    assert events[0].payload["completion_evidence_ref"].startswith(
        "evidence:industrial-facility-public-workshop-session:completed:"
    )
    projection = ContractProjector().rebuild(store.read_events())
    assert projection.contracts[created_event.payload["contract_id"]].status == "fulfilled"
    assert projection == ContractProjector().rebuild(
        store.read_events(), checkpoint_at=events[0].global_sequence - 1
    )


def test_public_workshop_contract_duplicate_and_generic_paths_are_zero_write() -> None:
    store, _authority, source_event = _source()
    contracts = _contracts(store)
    request = _request(store, source_event.event_id)
    first = contracts.create_public_workshop_session_from_public_use(request)
    assert first.committed
    before = store.export_snapshot()

    duplicate = contracts.create_public_workshop_session_from_public_use(request)
    changed = contracts.create_public_workshop_session_from_public_use(
        request.model_copy(update={"correlation_id": "corr:changed"})
    )
    forged = contracts.create_public_workshop_session_from_public_use(
        request.model_copy(update={"public_use_event_id": "event:missing"})
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed and changed.failure is not None
    assert not forged.committed and forged.failure is not None
    assert store.export_snapshot() == before

    created_event = store.get_event(first.committed_event_ids[0])
    with pytest.raises(ContractRuntimeError, match="public_workshop_session_row_required"):
        contracts.create_contract(
            command_id="command:generic-public-workshop-create",
            contract_id=str(created_event.payload["contract_id"]),
            contract_type="simple_service",
            terms_ref=SERVICE,
            party_refs=tuple(created_event.payload["party_refs"]),
            idempotency_key="generic-public-workshop-create",
            causation_id=source_event.event_id,
            correlation_id="corr:generic-public-workshop-create",
        )
    assert store.export_snapshot() == before


def test_public_workshop_requires_exact_operational_verification_pin() -> None:
    store, _authority, source_event = _source()
    source = store.get_event(source_event.event_id)
    store._events_by_id[source.event_id] = source.model_copy(
        update={"payload": {**source.payload, "verification_event_id": "event:missing"}},
        deep=True,
    )
    contracts = _contracts(store)
    result = contracts.create_public_workshop_session_from_public_use(
        _request(store, source.event_id)
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "public_workshop_verification_missing"
    assert store.read_stream("gameplay:contracts") == []
