from __future__ import annotations

import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyRuntimeError
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.organization_government_runtime import OrganizationAuthority
from test_inf4aj_public_project_execution import (
    _prepared_execution_case,
    _request as execution_request,
)


ORGANIZATION_STREAM = "gameplay:organization:organization:municipal-assessment-office"


def _prepared_close_case():
    store, activity, consumed = _prepared_execution_case()
    execution_result = OrganizationAuthority(store=store).record_public_project_execution(
        **execution_request(store, activity, consumed)
    )
    assert execution_result.committed
    execution = store.get_event(execution_result.committed_event_ids[0])
    economy = EconomyAuthorityService(store=store)
    return store, economy, consumed, execution


def _request(store, consumed, execution, **updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "budget_consumed_event_id": consumed.event_id,
        "expected_budget_consumed_revision": consumed.stream_revision,
        "execution_event_id": execution.event_id,
        "expected_execution_revision": execution.stream_revision,
        "expected_economy_stream_revision": store.get_stream_head("gameplay:economy"),
        "expected_execution_stream_revision": store.get_stream_head(ORGANIZATION_STREAM),
        "command_id": "inf2ak:close",
        "idempotency_key": "pending",
        "causation_id": execution.event_id,
        "correlation_id": "corr:inf2ak:close",
        "submitted_at": "2026-08-28T10:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"economy:public-project-budget-close:{consumed.event_id}:"
        f"{consumed.stream_revision}:{execution.event_id}:{execution.stream_revision}:"
        f"{values['expected_economy_stream_revision']}:{execution.stream_id}:"
        f"{values['expected_execution_stream_revision']}:v1"
    )
    return values


def test_inf2ak_closes_consumed_budget_after_matching_project_execution() -> None:
    store, economy, consumed, execution = _prepared_close_case()

    result = economy.close_public_project_budget(
        **_request(store, consumed, execution)
    )

    assert result.committed, result.failure
    assert len(result.committed_event_ids) == 1
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.economy.public_project_budget_closed"
    assert event.stream_id == "gameplay:economy"
    assert event.visibility_policy == "authority_only"
    assert event.payload["status"] == "closed"
    assert event.payload["terminal"] == "v1_terminal_no_compensation"
    assert event.payload["project_ref"] == "plot:inf1ak"
    assert event.payload["facility_ref"] == "facility:inf1ak"
    assert event.payload["source_budget_consumed_event_id"] == consumed.event_id
    assert event.payload["source_execution_event_id"] == execution.event_id
    assert "account_id" not in event.payload
    assert "amount_minor" not in event.payload
    assert "currency_ref" not in event.payload

    receipt = economy.public_project_budget_close_receipt_for(
        result=result, scope="authority"
    )
    assert receipt.committed_event_ids == (event.event_id,)
    full = economy.public_project_budget_close_projection(scope="authority")
    tail = economy.public_project_budget_close_projection(
        scope="authority", checkpoint_at=consumed.global_sequence
    )
    assert full == tail
    assert full["closure_refs"] == (
        "budget-closure:public-project:workshop-bench:plot:inf1ak",
    )


def test_inf2ak_exact_duplicate_replays_and_changed_or_semantic_duplicate_is_zero_write() -> None:
    store, economy, consumed, execution = _prepared_close_case()
    request = _request(store, consumed, execution)
    first = economy.close_public_project_budget(**request)
    assert first.committed
    before = store.export_snapshot()

    replay = economy.close_public_project_budget(
        **{**request, "command_id": "inf2ak:replay"}
    )
    changed = economy.close_public_project_budget(
        **{**request, "correlation_id": "corr:changed"}
    )
    semantic_duplicate = economy.close_public_project_budget(
        **{
            **_request(store, consumed, execution),
            "idempotency_key": "economy:public-project-budget-close:other",
        }
    )
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure and changed.failure.error_code.endswith("idempotency_key_reused")
    assert not semantic_duplicate.committed
    assert semantic_duplicate.failure and semantic_duplicate.failure.error_code.endswith("duplicate")
    assert store.export_snapshot() == before


def test_inf2ak_missing_private_stale_and_mismatched_sources_are_zero_write() -> None:
    store, economy, consumed, execution = _prepared_close_case()
    before = store.export_snapshot()

    missing = economy.close_public_project_budget(
        **_request(
            store,
            consumed,
            execution,
            execution_event_id="event:missing",
            idempotency_key="economy:public-project-budget-close:missing",
        )
    )
    assert not missing.committed
    assert missing.failure and missing.failure.error_code.endswith("execution_missing")
    assert store.export_snapshot() == before

    private = execution.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[execution.event_id] = private
    denied = economy.close_public_project_budget(
        **_request(
            store,
            consumed,
            private,
            idempotency_key="economy:public-project-budget-close:private",
        )
    )
    assert not denied.committed
    assert denied.failure and denied.failure.error_code.endswith("execution_invalid")
    assert store.export_snapshot() == before
    store._events_by_id[execution.event_id] = execution

    stale = economy.close_public_project_budget(
        **_request(
            store,
            consumed,
            execution,
            expected_execution_stream_revision=store.get_stream_head(execution.stream_id) - 1,
            idempotency_key="economy:public-project-budget-close:stale",
        )
    )
    assert not stale.committed
    assert stale.failure and stale.failure.error_code.endswith("revision_conflict")
    assert store.export_snapshot() == before

    mismatched = execution.model_copy(
        update={"payload": {**execution.payload, "project_ref": "plot:other"}},
        deep=True,
    )
    store._events_by_id[execution.event_id] = mismatched
    conflict = economy.close_public_project_budget(
        **_request(
            store,
            consumed,
            mismatched,
            idempotency_key="economy:public-project-budget-close:mismatch",
        )
    )
    assert not conflict.committed
    assert conflict.failure and conflict.failure.error_code.endswith("binding_invalid")
    assert store.export_snapshot() == before


def test_inf2ak_projector_rejects_forged_execution_provenance() -> None:
    store, economy, consumed, execution = _prepared_close_case()
    result = economy.close_public_project_budget(
        **_request(store, consumed, execution)
    )
    assert result.committed
    forged = execution.model_copy(
        update={
            "payload": {
                **execution.payload,
                "source_budget_consumed_event_id": "event:forged-budget",
            }
        },
        deep=True,
    )
    events = [
        forged if event.event_id == execution.event_id else event
        for event in store.read_events()
    ]
    with pytest.raises(Exception, match="economy_public_project_budget_close_source_invalid"):
        economy._projector.rebuild(events)


def test_inf2ak_catalog_pins_exact_economy_owner_contract_and_descriptor() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:economy-public-project-budget-close@1",
        contract_kind="lifecycle",
    )
    assert contract.owner_ref == "actor_gameplay.economy_domain"
    assert contract.stream_patterns == ("gameplay:economy",)
    assert contract.event_types == (
        "gameplay.economy.public_project_budget_closed",
    )
    assert contract.projection_scope == "authority_only"
    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref == "descriptor:economy-public-project-budget-close@1"
    )
    assert descriptor.capability_ref == "capability:economy-public-project-budget-close@1"
    assert descriptor.outcome_family_ref == (
        "outcome:economy-public-project-budget-closed@1"
    )


def test_inf2ak_projection_rejects_forged_execution_provenance() -> None:
    store, economy, consumed, execution = _prepared_close_case()
    result = economy.close_public_project_budget(**_request(store, consumed, execution))
    assert result.committed
    store._events_by_id[execution.event_id] = execution.model_copy(
        update={"payload": {**execution.payload, "source_budget_consumed_event_id": "event:forged"}},
        deep=True,
    )
    with pytest.raises(EconomyRuntimeError, match="public_project_budget_close_projection_provenance_invalid"):
        economy.public_project_budget_close_projection(scope="authority")
