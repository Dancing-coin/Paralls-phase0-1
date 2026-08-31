from __future__ import annotations

from app.gameplay.contract_runtime import ContractAuthorityService, ContractProjector, ContractTermsDefinition, ContractTermsRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.contract_runtime import GovernmentDroughtAssessmentContractIntentV1
from test_infra_weather_front_government_drought_advisory import JURISDICTION, _intent, _setup


TERMS = "service:municipal-drought-assessment@1"
EVIDENCE = "evidence:municipal-drought-assessment@1"


def _contracts(store: GameplayEventStore) -> ContractAuthorityService:
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(TERMS, "simple_service", 2, EVIDENCE))
    return ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={"authority:municipal-assessment"})


def _request(store: GameplayEventStore, advisory_event_id: str, **updates: object) -> GovernmentDroughtAssessmentContractIntentV1:
    advisory = store.get_event(advisory_event_id)
    values: dict[str, object] = {
        "advisory_event_id": advisory_event_id,
        "expected_advisory_revision": advisory.stream_revision,
        "expected_contract_revision": store.get_stream_head("gameplay:contracts"),
        "command_id": "command:municipal-drought-contract:1",
        "idempotency_key": "pending",
        "causation_id": advisory_event_id,
        "correlation_id": "corr:municipal-drought-contract:1",
        "submitted_at": "2026-08-26T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = f"contract:municipal-drought-assessment:{advisory_event_id}:{values['expected_advisory_revision']}:{JURISDICTION}:{values['expected_contract_revision']}:v1"
    return GovernmentDroughtAssessmentContractIntentV1.model_validate(values)


def test_project_visible_government_advisory_creates_one_fixed_authority_only_assessment_contract() -> None:
    store, _ecology, government, weather_event_id = _setup()
    advisory = government.issue_drought_advisory(_intent(store, weather_event_id))
    assert advisory.committed
    contracts = _contracts(store)

    result = contracts.create_municipal_drought_assessment_from_advisory(_request(store, advisory.committed_event_ids[0]))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.contract.record_created"
    assert event.visibility_policy == "authority_only"
    assert event.payload["terms_ref"] == TERMS
    assert event.payload["party_refs"] == ["organization:municipal-assessment-office", "organization:district-works"]
    assert event.payload["advisory_event_id"] == advisory.committed_event_ids[0]
    assert ContractProjector().rebuild(store.read_events()) == ContractProjector().rebuild(store.read_events(), checkpoint_at=event.global_sequence)


def test_foreign_or_stale_advisory_and_changed_duplicate_are_zero_write() -> None:
    store, _ecology, government, weather_event_id = _setup()
    advisory = government.issue_drought_advisory(_intent(store, weather_event_id))
    assert advisory.committed
    contracts = _contracts(store)
    request = _request(store, advisory.committed_event_ids[0])
    first = contracts.create_municipal_drought_assessment_from_advisory(request)
    before = store.export_snapshot()

    stale = contracts.create_municipal_drought_assessment_from_advisory(_request(store, advisory.committed_event_ids[0], expected_advisory_revision=2))
    changed = contracts.create_municipal_drought_assessment_from_advisory(request.model_copy(update={"correlation_id": "corr:changed"}))

    assert first.committed
    assert not stale.committed and stale.failure is not None
    assert not changed.committed and changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before
