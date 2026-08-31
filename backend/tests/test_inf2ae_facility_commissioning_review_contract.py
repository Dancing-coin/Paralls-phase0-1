from __future__ import annotations

import pytest

from app.gameplay import contract_runtime
from app.gameplay.contract_runtime import (
    ContractAuthorityService,
    ContractProjector,
    ContractRuntimeError,
    ContractTermsDefinition,
    ContractTermsRegistry,
)
from app.gameplay.event_store import GameplayEventStore
from test_inf1ai_facility_operational_verification import _intent as _verification_intent, _setup


SERVICE = "service:industrial-facility-commissioning-review@1"
EVIDENCE = "evidence:industrial-facility-commissioning-review@1"
POLICY = "authority:municipal-assessment"
PROVIDER = "organization:municipal-assessment-office"


def _contracts(store: GameplayEventStore) -> ContractAuthorityService:
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(SERVICE, "simple_service", 2, EVIDENCE))
    return ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={POLICY})


def _source() -> tuple[GameplayEventStore, object, str]:
    store, construction = _setup()
    verification = construction.verify_facility_operationally(_verification_intent(store))
    assert verification.committed
    return store, construction, verification.committed_event_ids[0]


def _request(store: GameplayEventStore, source_event_id: str, **updates: object) -> object:
    source = store.get_event(source_event_id)
    values: dict[str, object] = {
        "operational_verification_event_id": source_event_id,
        "expected_operational_verification_revision": source.stream_revision,
        "expected_contract_revision": store.get_stream_head("gameplay:contracts"),
        "command_id": "command:facility-commissioning-review:contract",
        "idempotency_key": "pending",
        "causation_id": source_event_id,
        "correlation_id": "corr:facility-commissioning-review",
        "submitted_at": "2026-08-27T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"contract:facility-commissioning-review:{source_event_id}:"
        f"{values['expected_operational_verification_revision']}:"
        f"{values['expected_contract_revision']}:v1"
    )
    intent_type = getattr(contract_runtime, "FacilityCommissioningReviewContractIntentV1", None)
    assert intent_type is not None, "missing facility commissioning contract intent"
    return intent_type.model_validate(values)


def test_operational_verification_creates_fixed_commissioning_review_contract() -> None:
    store, _construction, source_event_id = _source()
    contracts = _contracts(store)

    result = contracts.create_facility_commissioning_review_from_verification(
        _request(store, source_event_id)
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.contract.record_created"
    assert event.visibility_policy == "authority_only"
    assert event.payload["terms_ref"] == SERVICE
    assert event.payload["party_refs"] == [PROVIDER, "organization:mill"]
    assert event.payload["operational_verification_event_id"] == source_event_id
    assert ContractProjector().rebuild(store.read_events()) == ContractProjector().rebuild(
        store.read_events(), checkpoint_at=event.global_sequence
    )


def test_commissioning_review_fulfillment_has_fixed_evidence_and_replay() -> None:
    store, _construction, source_event_id = _source()
    contracts = _contracts(store)
    created = contracts.create_facility_commissioning_review_from_verification(
        _request(store, source_event_id)
    )
    assert created.committed
    created_event_id = created.committed_event_ids[0]
    created_event = store.get_event(created_event_id)
    fulfillment_intent_type = getattr(contract_runtime, "FacilityCommissioningReviewFulfillmentIntentV1", None)
    assert fulfillment_intent_type is not None, "missing facility commissioning fulfillment intent"
    head = store.get_stream_head("gameplay:contracts")
    request = fulfillment_intent_type.model_validate(
        {
            "contract_created_event_id": created_event_id,
            "expected_contract_created_revision": created_event.stream_revision,
            "expected_operational_verification_revision": store.get_event(source_event_id).stream_revision,
            "expected_contract_head": head,
            "command_id": "command:facility-commissioning-review:fulfill",
            "idempotency_key": f"contract:facility-commissioning-review:fulfillment:{created_event_id}:{created_event.stream_revision}:{store.get_event(source_event_id).stream_revision}:{head}:v1",
            "causation_id": created_event_id,
            "correlation_id": "corr:facility-commissioning-review",
            "submitted_at": "2026-08-27T00:00:00Z",
        }
    )

    result = contracts.fulfill_facility_commissioning_review_by_policy(request)

    assert result.committed, result.failure
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    assert [event.event_type for event in events] == [
        "gameplay.contract.service_completion_recorded",
        "gameplay.contract.record_fulfilled",
    ]
    assert events[0].payload["completion_evidence_kind"] == EVIDENCE
    assert events[0].payload["completion_evidence_ref"].startswith(
        "evidence:industrial-facility-commissioning-review:completed:"
    )
    assert ContractProjector().rebuild(store.read_events()) == ContractProjector().rebuild(
        store.read_events(), checkpoint_at=events[0].global_sequence - 1
    )


def test_commissioning_review_source_and_generic_contract_paths_are_zero_write() -> None:
    store, _construction, source_event_id = _source()
    contracts = _contracts(store)
    request = _request(store, source_event_id)
    first = contracts.create_facility_commissioning_review_from_verification(request)
    assert first.committed
    before = store.export_snapshot()

    changed = contracts.create_facility_commissioning_review_from_verification(
        request.model_copy(update={"correlation_id": "corr:changed"})
    )
    forged = contracts.create_facility_commissioning_review_from_verification(
        request.model_copy(update={"operational_verification_event_id": "event:missing"})
    )

    assert not changed.committed and changed.failure is not None
    assert not forged.committed and forged.failure is not None
    assert store.export_snapshot() == before

    created_event = store.get_event(first.committed_event_ids[0])
    with pytest.raises(ContractRuntimeError, match="facility_commissioning_review_row_required"):
        contracts.create_contract(
            command_id="command:generic-commissioning-create",
            contract_id=str(created_event.payload["contract_id"]),
            contract_type="simple_service",
            terms_ref=SERVICE,
            party_refs=tuple(created_event.payload["party_refs"]),
            idempotency_key="generic-commissioning-create",
            causation_id=source_event_id,
            correlation_id="corr:generic-commissioning-create",
        )
    assert store.export_snapshot() == before
