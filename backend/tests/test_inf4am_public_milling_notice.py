from __future__ import annotations

from app.gameplay.organization_government_runtime import GovernmentAuthority, OrganizationAuthority
from test_inf2al_public_milling_session import _economy_setup


JURISDICTION = "jurisdiction:mill-reinforcement:1"
NOTICE_STREAM = f"gameplay:government:public-notice:{JURISDICTION}"


def _activity(store):
    fulfilled = next(event for event in store.read_stream("gameplay:contracts") if event.event_type == "gameplay.contract.record_fulfilled")
    result = OrganizationAuthority(store=store).record_public_milling_activity(
        contract_fulfilled_event_id=fulfilled.event_id,
        expected_contract_revision=store.get_stream_head("gameplay:contracts"),
        expected_organization_revision=store.get_stream_head("gameplay:organization:organization:district-milling-cooperative"),
        command_id="inf4am:activity",
        idempotency_key=f"organization:public-milling-activity:{fulfilled.payload['contract_id']}:{store.get_stream_head('gameplay:contracts')}:0:v1",
        causation_id=fulfilled.event_id,
        correlation_id="corr:inf4am",
        submitted_at="2026-08-28T00:20:00Z",
    )
    assert result.committed
    return store.get_event(result.committed_event_ids[0])


def _request(store, activity, **updates: object) -> dict[str, object]:
    values = {
        "activity_event_id": activity.event_id,
        "expected_activity_revision": activity.stream_revision,
        "expected_government_revision": store.get_stream_head(NOTICE_STREAM),
        "command_id": "inf4am:notice",
        "idempotency_key": "pending",
        "causation_id": activity.event_id,
        "correlation_id": "corr:inf4am",
        "submitted_at": "2026-08-28T00:21:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = f"government:public-milling-notice:{activity.event_id}:{values['expected_activity_revision']}:{values['expected_government_revision']}:v1"
    return values


def test_inf4am_records_exact_milling_notice_and_replays() -> None:
    store, _economy, _fulfilled = _economy_setup()
    activity = _activity(store)
    authority = GovernmentAuthority(store=store)
    result = authority.record_public_milling_notice(**_request(store, activity))
    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.government.public_milling_notice_recorded"
    assert event.stream_id == NOTICE_STREAM
    assert event.payload["notice_kind"] == "public_milling_session_completed"
    full = authority.public_milling_notice_view_for(jurisdiction_ref=JURISDICTION)
    tail = authority.public_milling_notice_view_for(jurisdiction_ref=JURISDICTION, checkpoint_at=activity.global_sequence)
    assert full.notice_refs == tail.notice_refs


def test_inf4am_duplicate_changed_and_wrong_source_are_zero_write() -> None:
    store, _economy, _fulfilled = _economy_setup()
    activity = _activity(store)
    authority = GovernmentAuthority(store=store)
    request = _request(store, activity)
    first = authority.record_public_milling_notice(**request)
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.record_public_milling_notice(**request)
    changed = authority.record_public_milling_notice(**_request(store, activity, correlation_id="corr:changed"))
    missing = authority.record_public_milling_notice(**_request(store, activity, activity_event_id="event:missing"))
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed and not missing.committed
    assert store.export_snapshot() == before


def test_inf4am_replay_rejects_forged_notice_partition() -> None:
    store, _economy, _fulfilled = _economy_setup()
    activity = _activity(store)
    authority = GovernmentAuthority(store=store)
    result = authority.record_public_milling_notice(**_request(store, activity))
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    forged = event.model_copy(update={"payload": {**event.payload, "organization_ref": "organization:forged"}}, deep=True)
    store._events_by_id[event.event_id] = forged
    store._events = [forged if item.event_id == event.event_id else item for item in store._events]
    with __import__("pytest").raises(ValueError, match="public_milling_notice_replay_invalid"):
        authority.public_milling_notice_view_for(jurisdiction_ref=JURISDICTION)
