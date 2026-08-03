from __future__ import annotations

import pytest

from app.gameplay.contract_runtime import ContractAuthorityService, ContractProjector, ContractRuntimeError, ContractTermsDefinition, ContractTermsRegistry
from app.gameplay.event_store import GameplayEventStore


def _service() -> tuple[GameplayEventStore, ContractAuthorityService]:
    store = GameplayEventStore()
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition("terms:delivery:v1", "simple_service", 2, completion_evidence_kind="delivery_proof"))
    return store, ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={"authority:contracts"})


def _create(service: ContractAuthorityService, *, command_id: str = "cmd:create", idempotency_key: str = "create"):
    return service.create_contract(
        command_id=command_id,
        contract_id="contract:delivery:1",
        contract_type="simple_service",
        terms_ref="terms:delivery:v1",
        party_refs=("actor:buyer", "actor:carrier"),
        idempotency_key=idempotency_key,
        causation_id="cause",
        correlation_id="corr",
    )


def test_registered_typed_contract_terms_create_replayable_active_record() -> None:
    store, service = _service()
    result = _create(service)
    assert result.committed
    projection = ContractProjector().rebuild(store.read_events())
    record = projection.contracts["contract:delivery:1"]
    assert record.status == "active"
    assert record.party_refs == ("actor:buyer", "actor:carrier")
    assert record.terms_ref == "terms:delivery:v1"


def test_unknown_or_mismatched_terms_reject_without_contract_event() -> None:
    store, service = _service()
    before = store.read_events()
    with pytest.raises(ContractRuntimeError, match="contract_terms_unknown"):
        service.create_contract(command_id="cmd:unknown", contract_id="contract:unknown", contract_type="simple_service", terms_ref="terms:unknown", party_refs=("actor:a", "actor:b"), idempotency_key="unknown", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before
    with pytest.raises(ContractRuntimeError, match="contract_terms_type_mismatch"):
        service.create_contract(command_id="cmd:mismatch", contract_id="contract:mismatch", contract_type="simple_transfer", terms_ref="terms:delivery:v1", party_refs=("actor:a", "actor:b"), idempotency_key="mismatch", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before


def test_policy_authority_can_fulfill_or_terminate_but_untrusted_cannot() -> None:
    store, service = _service()
    _create(service)
    before = store.read_events()
    with pytest.raises(ContractRuntimeError, match="contract_policy_denied"):
        service.fulfill_contract_by_policy(command_id="cmd:bad", contract_id="contract:delivery:1", authority_ref="actor:carrier", idempotency_key="bad", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before
    fulfilled = service.fulfill_contract_by_policy(command_id="cmd:fulfill", contract_id="contract:delivery:1", authority_ref="authority:contracts", idempotency_key="fulfill", causation_id="cause", correlation_id="corr")
    assert fulfilled.committed
    assert ContractProjector().rebuild(store.read_events()).contracts["contract:delivery:1"].status == "fulfilled"
    replay = service.fulfill_contract_by_policy(command_id="cmd:fulfill", contract_id="contract:delivery:1", authority_ref="authority:contracts", idempotency_key="fulfill", causation_id="cause", correlation_id="corr")
    assert replay.idempotency_status == "duplicate_replayed"

    second_store, second_service = _service()
    _create(second_service)
    terminated = second_service.terminate_contract_by_policy(command_id="cmd:terminate", contract_id="contract:delivery:1", authority_ref="authority:contracts", reason="impossible", idempotency_key="terminate", causation_id="cause", correlation_id="corr")
    assert terminated.committed
    assert ContractProjector().rebuild(second_store.read_events()).contracts["contract:delivery:1"].status == "terminated"


def test_registered_service_completion_evidence_fulfills_contract_in_one_batch() -> None:
    store, service = _service()
    _create(service)
    before = store.read_events()
    with pytest.raises(ContractRuntimeError, match="contract_completion_evidence_invalid"):
        service.complete_simple_service_by_policy(
            command_id="cmd:wrong-evidence",
            contract_id="contract:delivery:1",
            authority_ref="authority:contracts",
            completion_evidence_kind="arrival_photo",
            completion_evidence_ref="evidence:wrong",
            idempotency_key="wrong-evidence",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before

    with pytest.raises(ContractRuntimeError, match="contract_policy_denied"):
        service.complete_simple_service_by_policy(
            command_id="cmd:untrusted",
            contract_id="contract:delivery:1",
            authority_ref="actor:carrier",
            completion_evidence_kind="delivery_proof",
            completion_evidence_ref="evidence:untrusted",
            idempotency_key="untrusted",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before

    completed = service.complete_simple_service_by_policy(
        command_id="cmd:complete",
        contract_id="contract:delivery:1",
        authority_ref="authority:contracts",
        completion_evidence_kind="delivery_proof",
        completion_evidence_ref="evidence:delivered:1",
        idempotency_key="complete",
        causation_id="cause",
        correlation_id="corr",
    )
    assert completed.committed
    assert [event.event_type for event in store.read_transactions()[-1].events] == [
        "gameplay.contract.service_completion_recorded",
        "gameplay.contract.record_fulfilled",
    ]
    record = ContractProjector().rebuild(store.read_events()).contracts["contract:delivery:1"]
    assert record.status == "fulfilled"
    assert record.completion_evidence_ref == "evidence:delivered:1"

    replay = service.complete_simple_service_by_policy(
        command_id="cmd:complete",
        contract_id="contract:delivery:1",
        authority_ref="authority:contracts",
        completion_evidence_kind="delivery_proof",
        completion_evidence_ref="evidence:delivered:1",
        idempotency_key="complete",
        causation_id="cause",
        correlation_id="corr",
    )
    assert replay.idempotency_status == "duplicate_replayed"
