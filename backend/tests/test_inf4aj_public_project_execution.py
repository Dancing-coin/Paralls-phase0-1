from __future__ import annotations

import pytest

from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.organization_government_runtime import OrganizationAuthority
from test_inf2ai_public_project_budget_consumption import (
    _prepared_consumption_case,
    _request as consumption_request,
)


ORGANIZATION = "organization:municipal-assessment-office"
ORGANIZATION_STREAM = f"gameplay:organization:{ORGANIZATION}"


def _prepared_execution_case():
    store, economy, commitment, reservation, activity = _prepared_consumption_case()
    consumed_result = economy.consume_public_project_budget(
        **consumption_request(store, commitment, reservation, activity)
    )
    assert consumed_result.committed
    consumed = store.get_event(consumed_result.committed_event_ids[0])
    return store, activity, consumed


def _request(store, activity, consumed, **updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "activity_event_id": activity.event_id,
        "expected_activity_revision": activity.stream_revision,
        "budget_consumed_event_id": consumed.event_id,
        "expected_budget_consumed_revision": consumed.stream_revision,
        "expected_economy_stream_revision": store.get_stream_head("gameplay:economy"),
        "expected_organization_revision": store.get_stream_head(ORGANIZATION_STREAM),
        "command_id": "inf4aj:execution",
        "idempotency_key": "pending",
        "causation_id": consumed.event_id,
        "correlation_id": "corr:inf4aj:execution",
        "submitted_at": "2026-08-28T09:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"organization:public-project-execution:{activity.event_id}:"
        f"{values['expected_activity_revision']}:{consumed.event_id}:"
        f"{values['expected_budget_consumed_revision']}:"
        f"{values['expected_economy_stream_revision']}:"
        f"{values['expected_organization_revision']}:v1"
    )
    return values


def test_inf4aj_records_one_funded_and_executed_project_fact() -> None:
    store, activity, consumed = _prepared_execution_case()
    result = OrganizationAuthority(store=store).record_public_project_execution(
        **_request(store, activity, consumed)
    )
    assert result.committed, result.failure
    assert len(result.committed_event_ids) == 1
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.organization.public_project_execution_recorded"
    assert event.stream_id == ORGANIZATION_STREAM
    assert event.visibility_policy == "project"
    assert event.payload["organization_ref"] == ORGANIZATION
    assert event.payload["facility_ref"] == "facility:inf1ak"
    assert event.payload["project_ref"] == "plot:inf1ak"
    assert event.payload["status"] == "funded_and_executed"
    assert event.payload["source_activity_event_id"] == activity.event_id
    assert event.payload["source_budget_consumed_event_id"] == consumed.event_id
    assert event.payload["source_activity_catalog_ref"] == "inf:organization-public-workshop-activity@1"
    assert event.payload["source_budget_consumed_catalog_ref"] == "inf:economy-public-project-budget-consumption@1"
    assert "amount_minor" not in event.payload
    assert "currency_ref" not in event.payload
    assert "account_id" not in event.payload

    receipt = OrganizationAuthority.public_project_execution_receipt_for(
        result=result, scope="project"
    )
    assert receipt.committed_event_ids == (event.event_id,)
    full = OrganizationAuthority(store=store).public_project_execution_view_for(
        organization_ref=ORGANIZATION
    )
    tail = OrganizationAuthority(store=store).public_project_execution_view_for(
        organization_ref=ORGANIZATION,
        checkpoint_at=activity.global_sequence,
    )
    assert full.executions == tail.executions
    assert full.source_revision_vector == tail.source_revision_vector
    assert full.projection_hash == tail.projection_hash
    assert full.source_revision_vector == {
        ORGANIZATION_STREAM: store.get_stream_head(ORGANIZATION_STREAM),
        "gameplay:economy": store.get_stream_head("gameplay:economy"),
    }


def test_inf4aj_duplicate_changed_duplicate_private_stale_and_mismatched_sources_are_zero_write() -> None:
    store, activity, consumed = _prepared_execution_case()
    authority = OrganizationAuthority(store=store)
    request = _request(store, activity, consumed)
    first = authority.record_public_project_execution(**request)
    assert first.committed
    before = store.export_snapshot()

    replay = authority.record_public_project_execution(**request)
    changed = authority.record_public_project_execution(
        **_request(store, activity, consumed, correlation_id="corr:changed")
    )
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure and changed.failure.error_code.endswith("idempotency_key_reused")
    assert store.export_snapshot() == before

    private_activity = activity.model_copy(
        update={"visibility_policy": "authority_only"}, deep=True
    )
    store._events_by_id[activity.event_id] = private_activity
    denied_private = authority.record_public_project_execution(
        **_request(
            store,
            private_activity,
            consumed,
            idempotency_key="organization:public-project-execution:private",
        )
    )
    assert not denied_private.committed
    assert denied_private.failure
    assert denied_private.failure.error_code.endswith("activity_invalid")
    store._events_by_id[activity.event_id] = activity

    stale = authority.record_public_project_execution(
        **_request(
            store,
            activity,
            consumed,
            expected_economy_stream_revision=store.get_stream_head("gameplay:economy") - 1,
            idempotency_key="organization:public-project-execution:stale",
        )
    )
    assert not stale.committed
    assert stale.failure and stale.failure.error_code.endswith("revision_conflict")

    mismatched = activity.model_copy(
        update={"payload": {**activity.payload, "project_ref": "plot:other"}},
        deep=True,
    )
    store._events_by_id[activity.event_id] = mismatched
    conflict = authority.record_public_project_execution(
        **_request(
            store,
            mismatched,
            consumed,
            idempotency_key="organization:public-project-execution:mismatch",
        )
    )
    assert not conflict.committed
    assert conflict.failure and conflict.failure.error_code.endswith("binding_invalid")
    assert store.export_snapshot() == before


def test_inf4aj_catalog_pins_exact_existing_organization_owner_contract() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:organization-public-project-execution@1",
        contract_kind="contract_admission",
    )
    assert contract.owner_ref == "actor_gameplay.organization_domain"
    assert contract.stream_patterns == ("gameplay:organization:{organization_ref}",)
    assert contract.event_types == (
        "gameplay.organization.public_project_execution_recorded",
    )
    assert contract.projection_scope == "project"
    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref == "descriptor:organization-public-project-execution@1"
    )
    assert descriptor.capability_ref == "capability:organization-public-project-execution@1"
    assert descriptor.outcome_family_ref == (
        "outcome:organization-public-project-execution-recorded@1"
    )


def test_inf4aj_rejects_forged_consumed_budget_provenance_before_append() -> None:
    store, activity, consumed = _prepared_execution_case()
    authority = OrganizationAuthority(store=store)
    forged = consumed.model_copy(
        update={
            "payload": {
                **consumed.payload,
                "source_reservation_event_id": "event:forged-reservation",
            }
        },
        deep=True,
    )
    store._events_by_id[consumed.event_id] = forged
    before = store.export_snapshot()
    result = authority.record_public_project_execution(
        **_request(
            store,
            activity,
            forged,
            idempotency_key="organization:public-project-execution:forged-budget",
        )
    )
    assert not result.committed
    assert result.failure and result.failure.error_code.endswith("budget_consumed_invalid")
    assert store.export_snapshot() == before


def test_inf4aj_replay_rejects_forged_target_source_pin() -> None:
    store, activity, consumed = _prepared_execution_case()
    authority = OrganizationAuthority(store=store)
    result = authority.record_public_project_execution(
        **_request(store, activity, consumed)
    )
    assert result.committed
    execution = store.get_event(result.committed_event_ids[0])
    forged = execution.model_copy(
        update={
            "payload": {
                **execution.payload,
                "source_budget_consumed_event_id": "event:forged-budget",
            }
        },
        deep=True,
    )
    store._events_by_id[execution.event_id] = forged
    store._events = [
        forged if event.event_id == execution.event_id else event
        for event in store._events
    ]
    with pytest.raises(ValueError, match="public_project_execution_replay_provenance_invalid"):
        authority.public_project_execution_view_for(organization_ref=ORGANIZATION)
