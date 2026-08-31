from __future__ import annotations

from app.gameplay.organization_government_runtime import OrganizationAuthority
from test_inf2al_public_milling_session import _economy_setup


PROVIDER = "organization:district-milling-cooperative"
STREAM = f"gameplay:organization:{PROVIDER}"


def _request(store, fulfilled, **updates: object) -> dict[str, object]:
    values = {
        "contract_fulfilled_event_id": fulfilled.committed_event_ids[-1],
        "expected_contract_revision": store.get_stream_head("gameplay:contracts"),
        "expected_organization_revision": store.get_stream_head(STREAM),
        "command_id": "inf4al:activity",
        "idempotency_key": "pending",
        "causation_id": fulfilled.committed_event_ids[-1],
        "correlation_id": "corr:inf4al:activity",
        "submitted_at": "2026-08-28T00:10:00Z",
    }
    values.update(updates)
    try:
        event = store.get_event(values["contract_fulfilled_event_id"])
        contract_id = event.payload["contract_id"]
    except KeyError:
        contract_id = "missing"
    values["idempotency_key"] = (
        f"organization:public-milling-activity:{contract_id}:"
        f"{values['expected_contract_revision']}:{values['expected_organization_revision']}:v1"
    )
    return values


def test_inf4al_records_exact_milling_activity_and_replays() -> None:
    store, _economy, fulfilled = _economy_setup()
    authority = OrganizationAuthority(store=store)
    result = authority.record_public_milling_activity(**_request(store, fulfilled))
    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.organization.public_milling_activity_recorded"
    assert event.visibility_policy == "project"
    assert event.payload["organization_ref"] == PROVIDER
    assert event.payload["activity_kind"] == "public_milling_session"
    view = authority.public_milling_activity_view_for(organization_ref=PROVIDER)
    tail = authority.public_milling_activity_view_for(
        organization_ref=PROVIDER, checkpoint_at=event.global_sequence - 1
    )
    assert len(view.activities) == 1
    assert view.activities == tail.activities
    assert view.source_revision_vector == tail.source_revision_vector


def test_inf4al_duplicate_changed_duplicate_and_wrong_source_are_zero_write() -> None:
    store, _economy, fulfilled = _economy_setup()
    authority = OrganizationAuthority(store=store)
    request = _request(store, fulfilled)
    first = authority.record_public_milling_activity(**request)
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.record_public_milling_activity(**request)
    changed = authority.record_public_milling_activity(
        **_request(store, fulfilled, correlation_id="corr:changed")
    )
    wrong = authority.record_public_milling_activity(
        **_request(store, fulfilled, contract_fulfilled_event_id="event:missing")
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert not wrong.committed
    assert store.export_snapshot() == before


def test_inf4al_caller_cannot_select_organization_revision_or_event_family() -> None:
    store, _economy, fulfilled = _economy_setup()
    authority = OrganizationAuthority(store=store)
    before = store.export_snapshot()
    denied = authority.record_public_milling_activity(
        **_request(store, fulfilled, expected_organization_revision=99)
    )
    assert not denied.committed
    assert denied.failure is not None
    assert store.export_snapshot() == before


def test_inf4al_replay_rejects_forged_activity_partition() -> None:
    store, _economy, fulfilled = _economy_setup()
    authority = OrganizationAuthority(store=store)
    result = authority.record_public_milling_activity(**_request(store, fulfilled))
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    forged = event.model_copy(update={"payload": {**event.payload, "package_revision": "package:forged:v1"}}, deep=True)
    store._events_by_id[event.event_id] = forged
    store._events = [forged if item.event_id == event.event_id else item for item in store._events]
    with __import__("pytest").raises(ValueError, match="public_milling_activity_replay_invalid"):
        authority.public_milling_activity_view_for(organization_ref=PROVIDER)
