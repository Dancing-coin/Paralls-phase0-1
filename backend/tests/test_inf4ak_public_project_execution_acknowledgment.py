from __future__ import annotations

import pytest

from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from test_inf4aj_public_project_execution import _prepared_execution_case, _request as execution_request
from app.gameplay.organization_government_runtime import GovernmentPublicProjectExecutionAcknowledgmentIntentV1


def _prepared_case():
    store, activity, consumed = _prepared_execution_case()
    execution = __import__("app.gameplay.organization_government_runtime", fromlist=["OrganizationAuthority"]).OrganizationAuthority(store=store).record_public_project_execution(
        **execution_request(store, activity, consumed)
    )
    assert execution.committed
    return store, store.get_event(execution.committed_event_ids[0])


def _request(store, execution, **updates):
    values = {
        "execution_event_id": execution.event_id,
        "expected_execution_revision": execution.stream_revision,
        "expected_execution_stream_revision": store.get_stream_head(execution.stream_id),
        "expected_government_revision": 0,
        "command_id": "inf4ak:ack",
        "idempotency_key": "pending",
        "causation_id": execution.event_id,
        "correlation_id": "corr:inf4ak",
        "submitted_at": "2026-08-28T12:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"government:public-project-execution-ack:{execution.event_id}:"
        f"{execution.stream_revision}:{values['expected_execution_stream_revision']}:"
        f"{values['expected_government_revision']}:v1"
    )
    return GovernmentPublicProjectExecutionAcknowledgmentIntentV1.model_validate(values)


def test_inf4ak_acknowledges_exact_funded_execution() -> None:
    store, execution = _prepared_case()
    result = GovernmentAuthority(store=store).acknowledge_public_project_execution(_request(store, execution))
    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.government.public_project_execution_acknowledged"
    assert event.visibility_policy == "authority_only"
    assert event.payload["status"] == "acknowledged"
    assert event.payload["facility_ref"] == execution.payload["facility_ref"]
    assert event.payload["project_ref"] == execution.payload["project_ref"]


def test_inf4ak_duplicate_and_mismatch_are_zero_write() -> None:
    store, execution = _prepared_case()
    authority = GovernmentAuthority(store=store)
    request = _request(store, execution)
    first = authority.acknowledge_public_project_execution(request)
    assert first.committed
    before = store.export_snapshot()
    replay = authority.acknowledge_public_project_execution(request)
    changed = authority.acknowledge_public_project_execution(
        request.model_copy(update={"correlation_id": "corr:changed"})
    )
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert store.export_snapshot() == before


def test_inf4ak_private_or_stale_execution_is_zero_write() -> None:
    store, execution = _prepared_case()
    authority = GovernmentAuthority(store=store)
    private = execution.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[execution.event_id] = private
    before = store.export_snapshot()
    denied = authority.acknowledge_public_project_execution(_request(store, private))
    assert not denied.committed
    assert store.export_snapshot() == before
    store._events_by_id[execution.event_id] = execution
    stale = authority.acknowledge_public_project_execution(
        _request(store, execution, expected_execution_stream_revision=execution.stream_revision - 1)
    )
    assert not stale.committed
    assert store.export_snapshot() == before


def test_inf4ak_full_and_checkpoint_tail_replay_match() -> None:
    store, execution = _prepared_case()
    authority = GovernmentAuthority(store=store)
    result = authority.acknowledge_public_project_execution(_request(store, execution))
    assert result.committed
    full = authority.public_project_execution_acknowledgment_view_for(jurisdiction_ref="jurisdiction:inf2ag")
    tail = authority.public_project_execution_acknowledgment_view_for(
        jurisdiction_ref="jurisdiction:inf2ag", checkpoint_at=execution.global_sequence
    )
    assert full == tail


def test_inf4ak_catalog_is_only_the_exact_government_acknowledgment_operation() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:government-public-project-execution-acknowledgment@1",
        contract_kind="contract_admission",
    )
    assert contract.owner_ref == "actor_gameplay.government_domain"
    assert contract.projection_scope == "authority_only"
    assert contract.event_types == ("gameplay.government.public_project_execution_acknowledged",)


def test_inf4ak_replay_rejects_forged_execution_provenance() -> None:
    store, execution = _prepared_case()
    authority = GovernmentAuthority(store=store)
    result = authority.acknowledge_public_project_execution(_request(store, execution))
    assert result.committed
    store._events_by_id[execution.event_id] = execution.model_copy(
        update={"payload": {**execution.payload, "source_budget_consumed_event_id": "event:forged"}},
        deep=True,
    )
    with pytest.raises(ValueError, match="public_project_execution_acknowledgment_replay_provenance_invalid"):
        authority.public_project_execution_acknowledgment_view_for(
            jurisdiction_ref="jurisdiction:inf1ak"
        )
