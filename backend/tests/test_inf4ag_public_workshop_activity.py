from __future__ import annotations

from app.gameplay.organization_government_runtime import OrganizationAuthority
from test_inf2ag_public_workshop_service_exchange import _setup


TARGET_ORGANIZATION = "organization:municipal-assessment-office"
TARGET_STREAM = f"gameplay:organization:{TARGET_ORGANIZATION}"


def _fulfilled(store):
    return next(
        event
        for event in store.read_stream("gameplay:contracts")
        if event.event_type == "gameplay.contract.record_fulfilled"
    )


def _request(store, fulfilled_event, **updates: object) -> dict[str, object]:
    values = {
        "contract_fulfilled_event_id": fulfilled_event.event_id,
        "expected_contract_revision": store.get_stream_head("gameplay:contracts"),
        "expected_organization_revision": store.get_stream_head(TARGET_STREAM),
        "command_id": "inf4ag:activity",
        "idempotency_key": "pending",
        "causation_id": fulfilled_event.event_id,
        "correlation_id": "corr:inf4ag:activity",
        "submitted_at": "2026-08-27T15:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"organization:public-workshop-activity:{fulfilled_event.payload['contract_id']}:"
        f"{values['expected_contract_revision']}:{values['expected_organization_revision']}:v1"
    )
    return values


def test_inf4ag_records_exact_fulfilled_public_workshop_activity() -> None:
    store, _economy = _setup()
    fulfilled = _fulfilled(store)
    result = OrganizationAuthority(store=store).record_public_workshop_activity(
        **_request(store, fulfilled)
    )
    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.organization.public_workshop_activity_recorded"
    assert event.visibility_policy == "project"
    assert event.payload["organization_ref"] == TARGET_ORGANIZATION
    assert event.payload["status"] == "completed"
    assert event.payload["facility_ref"] == "facility:inf2ag"
    assert event.payload["project_ref"] == "plot:inf2ag"
    view = OrganizationAuthority(store=store).public_workshop_activity_view_for(
        organization_ref=TARGET_ORGANIZATION
    )
    assert len(view.activities) == 1
    assert view.activities[0]["activity_ref"].startswith("activity:public-workshop-session:")


def test_inf4ag_activity_duplicate_changed_duplicate_and_private_source_are_zero_write() -> None:
    store, _economy = _setup()
    authority = OrganizationAuthority(store=store)
    fulfilled = _fulfilled(store)
    request = _request(store, fulfilled)
    first = authority.record_public_workshop_activity(**request)
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.record_public_workshop_activity(**request)
    changed = authority.record_public_workshop_activity(
        **_request(store, fulfilled, correlation_id="corr:changed")
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert store.export_snapshot() == before

    private = store.get_event(fulfilled.event_id).model_copy(
        update={"visibility_policy": "project"}, deep=True
    )
    store._events_by_id[fulfilled.event_id] = private
    target_before = store.read_stream(TARGET_STREAM)
    outbox_before = store.list_outbox()
    denied = authority.record_public_workshop_activity(
        **_request(store, fulfilled, idempotency_key="organization:public-workshop-activity:private:3:1:v1")
    )
    assert not denied.committed
    assert denied.failure is not None
    assert denied.failure.error_code == "public_workshop_activity_source_invalid"
    assert store.read_stream(TARGET_STREAM) == target_before
    assert store.list_outbox() == outbox_before


def test_inf4ag_activity_full_and_checkpoint_tail_replay_match() -> None:
    store, _economy = _setup()
    authority = OrganizationAuthority(store=store)
    fulfilled = _fulfilled(store)
    result = authority.record_public_workshop_activity(**_request(store, fulfilled))
    assert result.committed
    full = authority.public_workshop_activity_view_for(organization_ref=TARGET_ORGANIZATION)
    tail = authority.public_workshop_activity_view_for(
        organization_ref=TARGET_ORGANIZATION,
        checkpoint_at=fulfilled.global_sequence,
    )
    assert full.activities == tail.activities
    assert full.source_revision_vector == tail.source_revision_vector
