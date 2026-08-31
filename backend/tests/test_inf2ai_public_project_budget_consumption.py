from __future__ import annotations

import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.models import GameplayEvent
from test_inf2ah_public_project_budget_reservation import _prepared_reservation_case


ACTIVITY_STREAM = "gameplay:organization:organization:municipal-assessment-office"


def _prepared_consumption_case():
    store, economy, commitment, acquisition = _prepared_reservation_case()
    economy_head = store.get_stream_head("gameplay:economy")
    reservation = economy.reserve_public_project_budget(
        commitment_event_id=commitment.event_id,
        expected_commitment_revision=commitment.stream_revision,
        expected_economy_stream_revision=economy_head,
        expected_acquisition_revision=acquisition.stream_revision,
        expected_facility_stream_revision=store.get_stream_head(acquisition.stream_id),
        command_id="inf2ai:reservation",
        idempotency_key=(
            f"economy:public-project-budget-reservation:{commitment.event_id}:"
            f"{commitment.stream_revision}:{acquisition.event_id}:{acquisition.stream_revision}:"
            f"{economy_head}:account:inf2ah:0:v1"
        ),
        causation_id="cause:inf2ai",
        correlation_id="corr:inf2ai",
        submitted_at="2026-08-27T13:04:00Z",
    )
    assert reservation.committed
    reservation_event = store.get_event(reservation.committed_event_ids[0])
    activity_result = store.append_batch(
        {
            "transaction_id": "transaction:inf2ai:activity",
            "command_id": "inf2ai:activity",
            "expected_stream_revisions": {ACTIVITY_STREAM: store.get_stream_head(ACTIVITY_STREAM)},
            "read_stream_revisions": {},
            "pinned_revisions": {"activity_source": store.get_stream_head(ACTIVITY_STREAM)},
            "events": [
                GameplayEvent(
                    event_id="event:inf2ai:activity",
                    event_type="gameplay.organization.public_workshop_activity_recorded",
                    schema_version=1,
                    stream_id=ACTIVITY_STREAM,
                    stream_revision=0,
                    global_sequence=0,
                    transaction_id="transaction:inf2ai:activity",
                    command_id="inf2ai:activity",
                    causation_id="source:inf2ai:workshop",
                    correlation_id="corr:inf2ai",
                    visibility_policy="project",
                    payload={
                        "activity_ref": "activity:public-workshop-session:inf2ai",
                        "activity_kind": "public_workshop_session",
                        "status": "completed",
                        "organization_ref": "organization:municipal-assessment-office",
                        "service_ref": "service:industrial-facility-public-workshop-session@1",
                        "policy_revision": "policy:organization-public-workshop-activity@1",
                        "descriptor_ref": "descriptor:organization-public-workshop-activity@1",
                        "facility_ref": commitment.payload["facility_ref"],
                        "project_ref": commitment.payload["project_ref"],
                        "source_contract_fulfilled_event_id": "event:inf2ai:contract-fulfilled",
                        "contract_id": "contract:inf2ai:public-workshop",
                    },
                )
            ],
            "idempotency_record": {
                "principal_ref": "actor_gameplay.organization_domain",
                "idempotency_key": "inf2ai:activity",
                "payload_digest": "sha256:inf2ai:activity",
            },
            "outbox_entries": [],
            "result_digest": "sha256:inf2ai:activity",
            "projection_refresh_hints": [],
        }
    )
    assert activity_result.committed
    activity = store.get_event(activity_result.committed_event_ids[0])
    return store, economy, commitment, reservation_event, activity


def _request(store, commitment, reservation, activity, **updates: object) -> dict[str, object]:
    values = {
        "commitment_event_id": commitment.event_id,
        "expected_commitment_revision": commitment.stream_revision,
        "reservation_event_id": reservation.event_id,
        "expected_reservation_revision": reservation.stream_revision,
        "activity_event_id": activity.event_id,
        "expected_activity_revision": activity.stream_revision,
        "expected_economy_stream_revision": store.get_stream_head("gameplay:economy"),
        "expected_activity_stream_revision": store.get_stream_head(activity.stream_id),
        "command_id": "inf2ai:consume",
        "idempotency_key": "pending",
        "causation_id": activity.event_id,
        "correlation_id": "corr:inf2ai",
        "submitted_at": "2026-08-27T13:05:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"economy:public-project-budget-consumption:{commitment.event_id}:"
        f"{commitment.stream_revision}:{reservation.event_id}:{reservation.stream_revision}:"
        f"{activity.event_id}:{activity.stream_revision}:{values['expected_economy_stream_revision']}:"
        f"{activity.stream_id}:{values['expected_activity_stream_revision']}:v1"
    )
    return values


def test_inf2ai_consumes_one_reserved_public_project_budget_from_completed_activity() -> None:
    store, economy, commitment, reservation, activity = _prepared_consumption_case()
    result = economy.consume_public_project_budget(
        **_request(store, commitment, reservation, activity)
    )

    assert result.committed, result.failure
    assert len(result.committed_event_ids) == 1
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.economy.public_project_budget_consumed"
    assert event.visibility_policy == "authority_only"
    assert event.payload["amount_minor"] == 12
    assert event.payload["currency_ref"] == "currency:local"
    assert event.payload["status"] == "consumed"
    assert event.payload["terminal"] == "v1_terminal_no_compensation"
    assert event.payload["source_commitment_event_id"] == commitment.event_id
    assert event.payload["source_reservation_event_id"] == reservation.event_id
    assert event.payload["source_activity_event_id"] == activity.event_id
    receipt = economy.public_project_budget_consumption_receipt_for(
        result=result, scope="authority"
    )
    assert receipt.committed_event_ids == (event.event_id,)
    full = economy.public_project_budget_consumption_projection(scope="authority")
    tail = economy.public_project_budget_consumption_projection(
        scope="authority", checkpoint_at=reservation.global_sequence
    )
    assert full == tail


def test_inf2ai_exact_duplicate_replays_and_changed_or_semantic_duplicate_is_zero_write() -> None:
    store, economy, commitment, reservation, activity = _prepared_consumption_case()
    request = _request(store, commitment, reservation, activity)
    first = economy.consume_public_project_budget(**request)
    assert first.committed
    before = store.export_snapshot()

    replay = economy.consume_public_project_budget(
        **{**request, "command_id": "inf2ai:replay"}
    )
    changed = economy.consume_public_project_budget(
        **{**request, "correlation_id": "corr:changed"}
    )
    semantic_duplicate = economy.consume_public_project_budget(
        **{
            **_request(store, commitment, reservation, activity),
            "idempotency_key": "economy:public-project-budget-consumption:other",
        }
    )
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure and changed.failure.error_code.endswith("idempotency_key_reused")
    assert not semantic_duplicate.committed
    assert semantic_duplicate.failure and semantic_duplicate.failure.error_code.endswith("duplicate")
    assert store.export_snapshot() == before


def test_inf2ai_missing_private_stale_and_mismatched_sources_are_zero_write() -> None:
    store, economy, commitment, reservation, activity = _prepared_consumption_case()
    before = store.export_snapshot()
    missing = economy.consume_public_project_budget(
        **_request(
            store,
            commitment,
            reservation,
            activity,
            activity_event_id="event:missing",
            idempotency_key="economy:public-project-budget-consumption:missing",
        )
    )
    assert not missing.committed
    assert missing.failure and missing.failure.error_code == "economy_public_project_budget_consumption_activity_missing"
    assert store.export_snapshot() == before

    private = activity.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[activity.event_id] = private
    denied = economy.consume_public_project_budget(
        **_request(
            store,
            commitment,
            reservation,
            private,
            idempotency_key="economy:public-project-budget-consumption:private",
        )
    )
    assert not denied.committed
    assert denied.failure and denied.failure.error_code.endswith("source_invalid")
    assert store.export_snapshot() == before

    store._events_by_id[activity.event_id] = activity
    stale = economy.consume_public_project_budget(
        **_request(
            store,
            commitment,
            reservation,
            activity,
            expected_activity_stream_revision=store.get_stream_head(activity.stream_id) - 1,
            idempotency_key="economy:public-project-budget-consumption:stale",
        )
    )
    assert not stale.committed
    assert stale.failure and stale.failure.error_code.endswith("revision_conflict")
    assert store.export_snapshot() == before

    mismatched = activity.model_copy(
        update={"payload": {**activity.payload, "project_ref": "plot:other"}},
        deep=True,
    )
    store._events_by_id[activity.event_id] = mismatched
    conflict = economy.consume_public_project_budget(
        **_request(
            store,
            commitment,
            reservation,
            mismatched,
            idempotency_key="economy:public-project-budget-consumption:mismatch",
        )
    )
    assert not conflict.committed
    assert conflict.failure and conflict.failure.error_code.endswith("binding_invalid")
    assert store.export_snapshot() == before

    store._events_by_id[activity.event_id] = activity.model_copy(
        update={"payload": {**activity.payload, "organization_ref": "organization:other"}},
        deep=True,
    )
    provider_mismatch = economy.consume_public_project_budget(
        **_request(
            store,
            commitment,
            reservation,
            store._events_by_id[activity.event_id],
            expected_activity_stream_revision=1,
            idempotency_key="economy:public-project-budget-consumption:provider-mismatch",
        )
    )
    assert not provider_mismatch.committed
    assert provider_mismatch.failure and provider_mismatch.failure.error_code.endswith("source_invalid")
    assert store.export_snapshot() == before


def test_inf2ai_catalog_pins_exact_economy_owner_contract_and_descriptor() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:economy-public-project-budget-consumption@1",
        contract_kind="settlement",
    )
    assert contract.owner_ref == "actor_gameplay.economy_domain"
    assert contract.stream_patterns == ("gameplay:economy",)
    assert contract.event_types == (
        "gameplay.economy.public_project_budget_consumed",
    )
    assert contract.projection_scope == "authority_only"
    assert contract.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert (
        contract.replay_reader_ref
        == "EconomyAuthorityService.public_project_budget_consumption_projection"
    )
    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref
        == "descriptor:economy-public-project-budget-consumption@1"
    )
    assert descriptor.capability_ref == (
        "capability:economy-public-project-budget-consumption@1"
    )
    assert descriptor.outcome_family_ref == (
        "outcome:economy-public-project-budget-consumed@1"
    )


def test_inf2ai_projector_rejects_forged_activity_provenance() -> None:
    store, economy, commitment, reservation, activity = _prepared_consumption_case()
    result = economy.consume_public_project_budget(
        **_request(store, commitment, reservation, activity)
    )
    assert result.committed
    forged_activity = activity.model_copy(
        update={"payload": {**activity.payload, "service_ref": "service:forged"}},
        deep=True,
    )
    events = [
        forged_activity if event.event_id == activity.event_id else event
        for event in store.read_events()
    ]
    with pytest.raises(Exception, match="economy_public_project_budget_consumption_source_invalid"):
        economy._projector.rebuild(events)


def test_inf2ai_projector_rejects_forged_commitment_provenance() -> None:
    store, economy, commitment, reservation, activity = _prepared_consumption_case()
    result = economy.consume_public_project_budget(
        **_request(store, commitment, reservation, activity)
    )
    assert result.committed
    forged_commitment = commitment.model_copy(
        update={"payload": {**commitment.payload, "catalog_ref": "inf:forged"}},
        deep=True,
    )
    events = [
        forged_commitment if event.event_id == commitment.event_id else event
        for event in store.read_events()
    ]
    with pytest.raises(Exception, match="economy_public_project_budget_consumption_source_invalid"):
        economy._projector.rebuild(events)
