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
from test_inf3s_government_drought_assessment_contract import _intent, _setup


TERMS = "service:municipal-drought-assessment@1"
EVIDENCE = "evidence:municipal-drought-assessment@1"
POLICY_AUTHORITY = "authority:municipal-assessment"


def _contracts(store: GameplayEventStore) -> ContractAuthorityService:
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(TERMS, "simple_service", 2, EVIDENCE))
    return ContractAuthorityService(
        store=store,
        terms_registry=terms,
        policy_authorities={POLICY_AUTHORITY},
    )


def _create_assessment_contract() -> tuple[GameplayEventStore, ContractAuthorityService, str]:
    from test_inf3s_government_drought_assessment_contract import _request, _contracts as create_contracts

    store, _ecology, government, weather_event_id = _setup()
    advisory = government.issue_drought_advisory(_intent(store, weather_event_id))
    assert advisory.committed
    creator = create_contracts(store)
    created = creator.create_municipal_drought_assessment_from_advisory(
        _request(store, advisory.committed_event_ids[0])
    )
    assert created.committed
    return store, _contracts(store), created.committed_event_ids[0]


def _request(store: GameplayEventStore, source_event_id: str, **updates: object) -> object:
    source = store.get_event(source_event_id)
    values: dict[str, object] = {
        "contract_created_event_id": source_event_id,
        "expected_contract_created_revision": source.stream_revision,
        "expected_advisory_revision": source.payload.get("advisory_stream_revision", 1),
        "expected_contract_head": store.get_stream_head("gameplay:contracts"),
        "command_id": "command:municipal-drought-fulfillment:1",
        "idempotency_key": "pending",
        "causation_id": source_event_id,
        "correlation_id": "corr:municipal-drought-fulfillment:1",
        "submitted_at": "2026-08-26T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"contract:municipal-drought-assessment:fulfillment:{source_event_id}:"
        f"{values['expected_contract_created_revision']}:"
        f"{values['expected_advisory_revision']}:"
        f"{values['expected_contract_head']}:v1"
    )
    intent_type = getattr(contract_runtime, "MunicipalDroughtAssessmentFulfillmentIntentV1", None)
    assert intent_type is not None, "missing row-specific municipal fulfillment intent"
    return intent_type.model_validate(values)


def test_exact_inf3s_assessment_contract_fulfills_with_fixed_two_event_vector_and_replay() -> None:
    store, contracts, source_event_id = _create_assessment_contract()

    result = contracts.fulfill_municipal_drought_assessment_by_policy(_request(store, source_event_id))

    assert result.committed, result.failure
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    assert [event.event_type for event in events] == [
        "gameplay.contract.service_completion_recorded",
        "gameplay.contract.record_fulfilled",
    ]
    assert all(event.visibility_policy == "authority_only" for event in events)
    assert events[0].payload["completion_evidence_kind"] == EVIDENCE
    assert events[0].payload["authority_ref"] == POLICY_AUTHORITY
    assert events[0].payload["policy_ref"] == "policy:municipal-drought-assessment-fulfillment@1"
    assert events[0].payload["completion_evidence_ref"].startswith(
        "evidence:municipal-drought-assessment:completed:"
    )
    projection = ContractProjector().rebuild(store.read_events())
    assert projection.contracts[events[0].payload["contract_id"]].status == "fulfilled"
    assert projection == ContractProjector().rebuild(store.read_events(), checkpoint_at=events[0].global_sequence - 1)


def test_fulfillment_duplicate_and_stale_or_forged_source_are_zero_write() -> None:
    store, contracts, source_event_id = _create_assessment_contract()
    request = _request(store, source_event_id)
    first = contracts.fulfill_municipal_drought_assessment_by_policy(request)
    before = store.export_snapshot()

    duplicate = contracts.fulfill_municipal_drought_assessment_by_policy(request)
    stale = contracts.fulfill_municipal_drought_assessment_by_policy(
        _request(store, source_event_id, expected_contract_head=2)
    )
    forged = contracts.fulfill_municipal_drought_assessment_by_policy(
        request.model_copy(update={"contract_created_event_id": "event:missing"})
    )
    changed = contracts.fulfill_municipal_drought_assessment_by_policy(
        request.model_copy(update={"correlation_id": "corr:changed"})
    )
    changed_command = contracts.fulfill_municipal_drought_assessment_by_policy(
        request.model_copy(update={"command_id": "command:municipal-drought-fulfillment:changed"})
    )
    changed_submission = contracts.fulfill_municipal_drought_assessment_by_policy(
        request.model_copy(update={"submitted_at": "2026-08-27T00:00:00Z"})
    )

    assert first.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not stale.committed and stale.failure is not None
    assert not forged.committed and forged.failure is not None
    assert not changed.committed and changed.failure is not None
    assert not changed_command.committed and changed_command.failure is not None
    assert not changed_submission.committed and changed_submission.failure is not None
    assert store.export_snapshot() == before


def test_fulfillment_rejects_non_municipal_active_service_without_write() -> None:
    store = GameplayEventStore()
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition("service:other-assessment@1", "simple_service", 2, "evidence:other-assessment@1"))
    contracts = ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={POLICY_AUTHORITY})
    created = contracts.create_contract(
        command_id="other:create",
        contract_id="contract:other",
        contract_type="simple_service",
        terms_ref="service:other-assessment@1",
        party_refs=("organization:other-provider", "organization:other-receiver"),
        idempotency_key="other:create",
        causation_id="cause:other",
        correlation_id="corr:other",
    )
    assert created.committed
    before = store.export_snapshot()
    result = contracts.fulfill_municipal_drought_assessment_by_policy(_request(store, created.committed_event_ids[0]))
    assert not result.committed and result.failure is not None
    assert store.export_snapshot() == before


def test_fulfillment_rejects_when_fixed_policy_principal_is_not_configured() -> None:
    store, _configured_contracts, source_event_id = _create_assessment_contract()
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(TERMS, "simple_service", 2, EVIDENCE))
    contracts = ContractAuthorityService(store=store, terms_registry=terms, policy_authorities=set())
    before = store.export_snapshot()

    result = contracts.fulfill_municipal_drought_assessment_by_policy(_request(store, source_event_id))

    assert not result.committed and result.failure is not None
    assert store.export_snapshot() == before


def test_generic_simple_service_completion_cannot_bypass_municipal_fulfillment_row() -> None:
    store, contracts, source_event_id = _create_assessment_contract()
    source = store.get_event(source_event_id)
    contract_id = str(source.payload["contract_id"])
    before = store.export_snapshot()

    with pytest.raises(ContractRuntimeError, match="municipal_drought_fulfillment_row_required"):
        contracts.complete_simple_service_by_policy(
            command_id="command:generic-bypass",
            contract_id=contract_id,
            authority_ref=POLICY_AUTHORITY,
            completion_evidence_kind=EVIDENCE,
            completion_evidence_ref="evidence:forged-generic-completion",
            idempotency_key="generic-bypass",
            causation_id=source_event_id,
            correlation_id="corr:generic-bypass",
        )

    assert store.export_snapshot() == before


@pytest.mark.parametrize("operation", ("fulfill", "terminate"))
def test_generic_contract_transition_cannot_bypass_municipal_fulfillment_row(operation: str) -> None:
    store, contracts, source_event_id = _create_assessment_contract()
    source = store.get_event(source_event_id)
    contract_id = str(source.payload["contract_id"])
    before = store.export_snapshot()

    with pytest.raises(ContractRuntimeError, match="municipal_drought_fulfillment_row_required"):
        if operation == "fulfill":
            contracts.fulfill_contract_by_policy(
                command_id="command:generic-fulfill",
                contract_id=contract_id,
                authority_ref=POLICY_AUTHORITY,
                idempotency_key="generic-fulfill",
                causation_id=source_event_id,
                correlation_id="corr:generic-fulfill",
            )
        else:
            contracts.terminate_contract_by_policy(
                command_id="command:generic-terminate",
                contract_id=contract_id,
                authority_ref=POLICY_AUTHORITY,
                reason="generic",
                idempotency_key="generic-terminate",
                causation_id=source_event_id,
                correlation_id="corr:generic-terminate",
            )

    assert store.export_snapshot() == before


def test_generic_contract_creation_cannot_reserve_municipal_fulfillment_row() -> None:
    store = GameplayEventStore()
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(TERMS, "simple_service", 2, EVIDENCE))
    contracts = ContractAuthorityService(
        store=store,
        terms_registry=terms,
        policy_authorities={POLICY_AUTHORITY},
    )
    before = store.export_snapshot()

    with pytest.raises(ContractRuntimeError, match="municipal_drought_contract_admission_required"):
        contracts.create_contract(
            command_id="command:generic-municipal-create",
            contract_id="contract:municipal-drought-assessment:reserved",
            contract_type="simple_service",
            terms_ref=TERMS,
            party_refs=(
                "organization:municipal-assessment-office",
                "organization:district-works",
            ),
            idempotency_key="generic-municipal-create",
            causation_id="cause:generic-municipal-create",
            correlation_id="corr:generic-municipal-create",
        )

    assert store.export_snapshot() == before
