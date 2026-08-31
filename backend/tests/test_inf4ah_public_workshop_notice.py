from __future__ import annotations

from app.gameplay.organization_government_runtime import GovernmentAuthority
from test_inf4ag_public_workshop_activity import _request as activity_request, _fulfilled
from test_inf2ag_public_workshop_service_exchange import _setup


JURISDICTION = "jurisdiction:inf2ag"
NOTICE_STREAM = f"gameplay:government:public-notice:{JURISDICTION}"


def _activity(store):
    from app.gameplay.organization_government_runtime import OrganizationAuthority

    fulfilled = _fulfilled(store)
    result = OrganizationAuthority(store=store).record_public_workshop_activity(
        **activity_request(store, fulfilled)
    )
    assert result.committed
    return store.get_event(result.committed_event_ids[0])


def _request(store, activity_event, **updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "activity_event_id": activity_event.event_id,
        "expected_activity_revision": activity_event.stream_revision,
        "expected_government_revision": store.get_stream_head(NOTICE_STREAM),
        "command_id": "inf4ah:notice",
        "idempotency_key": "pending",
        "causation_id": activity_event.event_id,
        "correlation_id": "corr:inf4ah:notice",
        "submitted_at": "2026-08-27T16:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"government:public-workshop-notice:{activity_event.event_id}:"
        f"{values['expected_activity_revision']}:{values['expected_government_revision']}:v1"
    )
    return values


def test_inf4ah_records_project_public_workshop_notice_from_exact_activity() -> None:
    store, _economy = _setup()
    activity = _activity(store)
    result = GovernmentAuthority(store=store).record_public_workshop_notice(
        **_request(store, activity)
    )
    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.government.public_workshop_notice_recorded"
    assert event.stream_id == NOTICE_STREAM
    assert event.visibility_policy == "project"
    assert event.payload["notice_kind"] == "public_workshop_session_completed"
    assert event.payload["facility_ref"] == "facility:inf2ag"
    assert event.payload["project_ref"] == "plot:inf2ag"
    assert "contract_id" not in event.payload
    assert "account_id" not in event.payload
    view = GovernmentAuthority(store=store).public_workshop_notice_view_for(
        jurisdiction_ref=JURISDICTION
    )
    assert view.notice_refs == (event.payload["notice_ref"],)


def test_inf4ah_notice_duplicate_changed_duplicate_private_and_wrong_source_are_zero_write() -> None:
    store, _economy = _setup()
    activity = _activity(store)
    authority = GovernmentAuthority(store=store)
    request = _request(store, activity)
    first = authority.record_public_workshop_notice(**request)
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.record_public_workshop_notice(**request)
    changed = authority.record_public_workshop_notice(
        **_request(store, activity, correlation_id="corr:changed")
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert store.export_snapshot() == before

    forged_activity = store.get_event(activity.event_id).model_copy(
        update={
            "payload": {
                **activity.payload,
                "source_contract_fulfilled_revision": activity.payload["source_contract_fulfilled_revision"] + 1,
            }
        },
        deep=True,
    )
    store._events_by_id[activity.event_id] = forged_activity
    forged = authority.record_public_workshop_notice(
        **_request(store, forged_activity, idempotency_key="government:public-workshop-notice:forged:1:0:v1")
    )
    assert not forged.committed
    assert forged.failure is not None
    assert forged.failure.error_code == "public_workshop_notice_source_invalid"
    store._events_by_id[activity.event_id] = activity

    private = store.get_event(activity.event_id).model_copy(
        update={"visibility_policy": "authority_only"}, deep=True
    )
    store._events_by_id[activity.event_id] = private
    denied = authority.record_public_workshop_notice(
        **_request(store, activity, idempotency_key="government:public-workshop-notice:private:1:0:v1")
    )
    assert not denied.committed
    assert denied.failure is not None
    assert denied.failure.error_code == "public_workshop_notice_source_private"
    assert store.export_snapshot() == before


def test_inf4ah_notice_full_and_checkpoint_tail_replay_match() -> None:
    store, _economy = _setup()
    activity = _activity(store)
    authority = GovernmentAuthority(store=store)
    result = authority.record_public_workshop_notice(**_request(store, activity))
    assert result.committed
    full = authority.public_workshop_notice_view_for(jurisdiction_ref=JURISDICTION)
    tail = authority.public_workshop_notice_view_for(
        jurisdiction_ref=JURISDICTION,
        checkpoint_at=activity.global_sequence,
    )
    assert full.notice_refs == tail.notice_refs
    assert full.source_revision_vector == tail.source_revision_vector
