from __future__ import annotations

from app.gameplay.economy_platform_runtime import EconomyPlatformAuthority, EconomyPlatformProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent
from app.gameplay.contract_runtime import ContractAuthorityService, ContractTermsRegistry


def _source(event_type: str, visibility: str, revision: int = 1) -> GameplayEvent:
    return GameplayEvent(
        event_id=f"event:source:{event_type}", event_type=event_type, schema_version=1,
        stream_id="gameplay:organization:millers@1" if event_type.startswith("gameplay.organization") else "gameplay:government:case:mill@1",
        stream_revision=revision, global_sequence=revision, transaction_id="tx:source", command_id="cmd:source",
        causation_id="cause:source", correlation_id="corr:source", visibility_policy=visibility,
        payload={"source": "committed"},
    )


def test_economy_accepts_exact_ogs_recipe_source_and_pins_it() -> None:
    store = GameplayEventStore()
    source = _source("gameplay.organization.commitment_budget_proposed@1", "project")
    store._events.append(source)  # noqa: SLF001 - fixture source is committed evidence
    store._events_by_id[source.event_id] = source  # noqa: SLF001
    store._stream_heads[source.stream_id] = 1  # noqa: SLF001
    authority = EconomyPlatformAuthority(store=store)
    result = authority.accept_ogs_organization_commitment(source_event=source, expected_source_revision=1, command_id="cmd:accept", idempotency_key="idem:accept", expected_revision=0, causation_id=source.event_id, correlation_id="corr:accept")
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["source_event_id"] == source.event_id
    assert event.payload["source_stream_revision"] == 1


def test_economy_recipe_acceptance_rejects_private_or_stale_source_before_write() -> None:
    store = GameplayEventStore()
    source = _source("gameplay.government.permit_inspection_case_recorded@1", "authority_only")
    store._events.append(source)  # noqa: SLF001
    store._events_by_id[source.event_id] = source  # noqa: SLF001
    store._stream_heads[source.stream_id] = 1  # noqa: SLF001
    authority = EconomyPlatformAuthority(store=store)
    try:
        authority.accept_ogs_government_enforcement(source_event=source, expected_source_revision=1, command_id="cmd:accept", idempotency_key="idem:accept", expected_revision=0, causation_id=source.event_id, correlation_id="corr:accept")
    except ValueError as exc:
        assert str(exc) == "ogs_government_recipe_source_invalid"
    assert store.get_stream_head("gameplay:economy:recipe:recipe:government-enforcement-obligation@1") == 0


def test_contract_accepts_exact_social_conflict_recipe_as_eligibility_marker() -> None:
    store = GameplayEventStore()
    source = _source("gameplay.social.norm_conflict_recorded@1", "project")
    source = source.model_copy(update={"stream_id": "gameplay:social:case:case:conflict@1"})
    store._events.append(source)  # noqa: SLF001
    store._events_by_id[source.event_id] = source  # noqa: SLF001
    store._stream_heads[source.stream_id] = 1  # noqa: SLF001
    authority = ContractAuthorityService(store=store, terms_registry=ContractTermsRegistry(), policy_authorities=set())
    result = authority.accept_ogs_social_conflict_eligibility(source_event=source, expected_source_revision=1, command_id="cmd:contract-accept", idempotency_key="idem:contract-accept", expected_contract_revision=0, causation_id=source.event_id, correlation_id="corr:contract-accept")
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.contract.ogs_social_conflict_eligibility_accepted@1"
