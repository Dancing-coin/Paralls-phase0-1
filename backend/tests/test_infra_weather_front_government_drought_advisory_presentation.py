from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AtomicEventBatch, GameplayEvent, GameplayOutboxEntry, IdempotencyRecord
from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.gameplay.government_drought_advisory_presentation import (
    GovernmentDroughtAdvisoryPresentationError,
    GovernmentDroughtAdvisoryPresentationService,
)
from app.services.websocket_session_auth_service import WebSocketConnectionContext, WebSocketSessionBinding


JURISDICTION = "jurisdiction:advisory-presentation"
FOREIGN_JURISDICTION = "jurisdiction:advisory-foreign"
STREAM = f"gameplay:government:advisory:{JURISDICTION}"


def _snapshot(store: GameplayEventStore) -> dict[str, object]:
    exported = store.export_snapshot()
    return {key: exported[key] for key in ("events", "outbox", "idempotency")}


def _commit_advisory(store: GameplayEventStore, *, topic: str = "world.government.drought_advisory_projection", audience: str = "project") -> AtomicEventBatch:
    event = GameplayEvent(
        event_id="event:government:drought-advisory:presentation",
        event_type="gameplay.government.drought_advisory_issued",
        schema_version=1,
        stream_id=STREAM,
        stream_revision=0,
        global_sequence=0,
        transaction_id="tx:government:drought-advisory:presentation",
        command_id="command:government:drought-advisory:presentation",
        causation_id="cause:government:drought-advisory:presentation",
        correlation_id="corr:government:drought-advisory:presentation",
        visibility_policy="project",
        payload={
            "advisory_ref": "advisory:drought:presentation",
            "jurisdiction_ref": JURISDICTION,
            "weather_ref": "weather:drought",
            "ecology_stream_id": "gameplay:ecology:region:advisory-presentation",
            "ecology_event_revision": 3,
        },
    )
    batch = AtomicEventBatch(
        transaction_id=event.transaction_id,
        command_id=event.command_id,
        expected_stream_revisions={STREAM: 0},
        idempotency_record=IdempotencyRecord(
            principal_ref="authority:government",
            idempotency_key="government:drought-advisory:presentation",
            payload_digest="sha256:government-drought-advisory-presentation",
        ),
        events=[event],
        outbox_entries=[
            GameplayOutboxEntry(
                outbox_id="outbox:government:drought-advisory:presentation",
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                global_sequence=0,
                topic=topic,
                audience=audience,
                payload_projection={
                    "advisory_ref": "advisory:drought:presentation",
                    "jurisdiction_ref": JURISDICTION,
                    "event_type": event.event_type,
                },
            )
        ],
        result_digest="sha256:government-drought-advisory-presentation",
    )
    result = store.append_batch(batch)
    assert result.committed, result.failure
    return store.read_transactions()[-1]


def _context(*, jurisdictions: tuple[str, ...] = (JURISDICTION,)) -> WebSocketConnectionContext:
    return WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=1,
        connection_ref="connection:advisory-presentation",
        binding=WebSocketSessionBinding(
            session_ref="session:advisory-presentation",
            principal_ref="principal:advisory-presentation",
            allowed_actor_refs=("actor:unrelated",),
            allowed_government_drought_advisory_jurisdiction_refs=jurisdictions,
            connection_epoch=1,
            lease_expires_at=10,
        ),
    )


def test_project_granted_jurisdiction_receives_only_fixed_advisory_snapshot_and_delivery() -> None:
    store = GameplayEventStore()
    transaction = _commit_advisory(store)
    delivered: list[tuple[str, dict[str, object]]] = []
    service = GovernmentDroughtAdvisoryPresentationService(
        government=GovernmentAuthority(store=store),
        deliver=lambda session_ref, payload: delivered.append((session_ref, payload)),
    )

    snapshot = service.subscribe(context=_context(), jurisdiction_ref=JURISDICTION)
    service.after_transaction_dispatched(transaction)

    assert snapshot["projection_kind"] == "government_drought_advisory.project.v1"
    assert snapshot["jurisdiction_ref"] == JURISDICTION
    assert snapshot["advisory_refs"] == ["advisory:drought:presentation"]
    assert snapshot["source_revision_vector"] == {STREAM: 1, "gameplay:ecology:region:advisory-presentation": 3}
    assert snapshot["projection_hash"].startswith("sha256:")
    assert delivered == [("session:advisory-presentation", snapshot)]
    assert store.read_events()[0].event_type == "gameplay.government.drought_advisory_issued"


def test_foreign_scope_wrong_outbox_and_disconnected_session_are_zero_leak() -> None:
    store = GameplayEventStore()
    transaction = _commit_advisory(store)
    delivered: list[tuple[str, dict[str, object]]] = []
    service = GovernmentDroughtAdvisoryPresentationService(
        government=GovernmentAuthority(store=store),
        deliver=lambda session_ref, payload: delivered.append((session_ref, payload)),
    )
    before = _snapshot(store)

    with pytest.raises(GovernmentDroughtAdvisoryPresentationError, match="government_drought_advisory_scope_unauthorized"):
        service.subscribe(context=_context(), jurisdiction_ref=FOREIGN_JURISDICTION)
    service.subscribe(context=_context(), jurisdiction_ref=JURISDICTION)
    wrong_outbox = transaction.model_copy(
        update={
            "outbox_entries": [
                transaction.outbox_entries[0].model_copy(
                    update={"topic": "world.government.other_projection"}
                )
            ]
        },
        deep=True,
    )
    service.after_transaction_dispatched(wrong_outbox)
    spoofed_event = transaction.model_copy(
        update={
            "outbox_entries": [
                transaction.outbox_entries[0].model_copy(
                    update={"event_id": "event:government:not-an-advisory"}
                )
            ]
        },
        deep=True,
    )
    service.after_transaction_dispatched(spoofed_event)
    service.drop_session(session_ref="session:advisory-presentation")
    service.after_transaction_dispatched(transaction)

    assert delivered == []
    assert _snapshot(store) == before


def test_presentation_never_appends_retries_or_rewrites_authority_receipt() -> None:
    store = GameplayEventStore()
    transaction = _commit_advisory(store)
    service = GovernmentDroughtAdvisoryPresentationService(
        government=GovernmentAuthority(store=store),
        deliver=lambda _session_ref, _payload: (_ for _ in ()).throw(RuntimeError("transport down")),
    )
    service.subscribe(context=_context(), jurisdiction_ref=JURISDICTION)
    before = _snapshot(store)

    service.after_transaction_dispatched(transaction)

    assert _snapshot(store) == before
    assert service.subscribed_jurisdictions_for(session_ref="session:advisory-presentation") == ()
    assert not hasattr(service, "issue_drought_advisory")
    assert not hasattr(service, "append_batch")
