from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main
from app.main import component_app as app, reset_runtime_state
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_handoff_authority_service import EmbodiedHandoffAuthorityService


def _service() -> tuple[EmbodiedHandoffAuthorityService, GameplayEventStore, InMemoryAuthorityEventBus]:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    service = EmbodiedHandoffAuthorityService(
        store=store,
        dispatcher=GameplayOutboxDispatcher(store=store, bus=bus),
        evidence_ledger=EmbodiedEvidenceLedger(),
    )
    service.seed_asset_possession(
        asset_ref="item:letter_01",
        custody_holder_ref="character:siming",
        owner_ref="character:siming",
    )
    return service, store, bus


def test_handoff_settles_session_custody_ownership_and_mirror_directive_in_one_gameplay_batch() -> None:
    service, store, bus = _service()
    service.start_handoff(
        session_id="session:handoff:letter:1",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        causation_id="cmd:handoff:letter:1:start",
        correlation_id="corr:handoff:letter:1",
    )

    result = service.settle_handoff(
        session_id="session:handoff:letter:1",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "character:maya": "digest:terminal:maya",
        },
        idempotency_key="handoff:letter:1:settle",
        payload_digest="digest:handoff:letter:1",
    )

    transaction = store.read_transactions()[-1]
    event_types = [event.event_type for event in transaction.events]
    projection = service.possession_projection("item:letter_01")

    assert result.accepted is True
    assert result.transaction_id == transaction.transaction_id
    assert event_types == [
        "embodied.interaction_session.participant_observed",
        "embodied.interaction_session.participant_observed",
        "inventory.custody_changed",
        "ownership.right_transferred",
        "embodied.handoff.settled",
        "embodied.interaction_session.committed",
    ]
    assert len({event.transaction_id for event in transaction.events}) == 1
    assert transaction.expected_stream_revisions == {
        "session:session:handoff:letter:1": 4,
        "inventory:possession:item:letter_01": 0,
        "ownership:right:item:letter_01": 0,
        "embodied:handoff:session:handoff:letter:1": 0,
    }
    assert projection == {
        "asset_ref": "item:letter_01",
        "custody_holder_ref": "character:maya",
        "owner_ref": "character:maya",
        "authority_transaction_id": transaction.transaction_id,
        "source": "backend_authority",
    }
    assert [event.event_type for event in bus.list_events()[-6:]] == event_types
    assert bus.list_events(event_type="embodied.handoff.settled")[-1].payload["attachment_directive"] == {
        "mode": "attach_for_presentation",
        "asset_ref": "item:letter_01",
        "attach_to_ref": "character:maya",
        "authority_only": True,
    }


def test_local_attachment_hint_never_changes_possession_or_ownership_projection() -> None:
    service, _store, _bus = _service()

    hinted = service.apply_local_attachment_hint(
        asset_ref="item:letter_01",
        attached_to_ref="character:maya",
        source_ref="godot:local_attachment_probe",
    )

    assert hinted == {
        "accepted": True,
        "authority_mutation": False,
        "reason": "presentation_hint_only",
    }
    assert service.possession_projection("item:letter_01") == {
        "asset_ref": "item:letter_01",
        "custody_holder_ref": "character:siming",
        "owner_ref": "character:siming",
        "authority_transaction_id": "",
        "source": "backend_authority",
    }


def test_handoff_duplicate_idempotency_replays_original_without_second_mutation() -> None:
    service, store, _bus = _service()
    service.start_handoff(
        session_id="session:handoff:letter:1",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        causation_id="cmd:handoff:letter:1:start",
        correlation_id="corr:handoff:letter:1",
    )

    first = service.settle_handoff(
        session_id="session:handoff:letter:1",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "character:maya": "digest:terminal:maya",
        },
        idempotency_key="handoff:letter:1:settle",
        payload_digest="digest:handoff:letter:1",
    )
    duplicate = service.settle_handoff(
        session_id="session:handoff:letter:1",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "character:maya": "digest:terminal:maya",
        },
        idempotency_key="handoff:letter:1:settle",
        payload_digest="digest:handoff:letter:1",
    )

    assert first.accepted is True
    assert duplicate.accepted is True
    assert duplicate.idempotent is True
    assert duplicate.transaction_id == first.transaction_id
    assert len(store.read_transactions()) == 4


def test_handoff_revision_conflict_rejects_without_partial_cross_domain_commit() -> None:
    service, store, _bus = _service()
    service.start_handoff(
        session_id="session:handoff:letter:1",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        causation_id="cmd:handoff:letter:1:start",
        correlation_id="corr:handoff:letter:1",
    )

    result = service.settle_handoff(
        session_id="session:handoff:letter:1",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "character:maya": "digest:terminal:maya",
        },
        idempotency_key="handoff:letter:1:settle",
        payload_digest="digest:handoff:letter:1",
        expected_stream_revisions={"inventory:possession:item:letter_01": 9},
    )

    assert result.accepted is False
    assert result.error_code == "revision_conflict"
    assert [event.event_type for event in store.read_events()] == [
        "embodied.interaction_session.proposed",
        "embodied.interaction_session.accepted",
        "embodied.interaction_session.authorized",
        "embodied.interaction_session.realizing",
    ]
    assert service.possession_projection("item:letter_01")["custody_holder_ref"] == "character:siming"


def test_websocket_handoff_probe_delivers_authority_only_mirror_directive_without_world_truth_claim() -> None:
    reset_runtime_state()
    started = main.embodied_handoff_authority_service.start_handoff(
        session_id="known-handoff-session",
        asset_ref="item:letter_01",
        from_actor_ref="character:siming",
        to_actor_ref="character:maya",
        causation_id="cmd:known-handoff:start",
        correlation_id="corr:known-handoff",
    )
    assert started.accepted
    before_sequence = main.gameplay_event_store.get_last_global_sequence()
    client = TestClient(app)
    responses = []
    with client.websocket_connect("/ws") as websocket:
        for session_id in ("known-handoff-session", "unknown-handoff-session"):
            websocket.send_json({
                "message_type": "embodied_handoff_probe",
                "payload": {
                    "session_id": session_id,
                    "asset_ref": "item:letter_01",
                    "from_actor_ref": "character:siming",
                    "to_actor_ref": "character:maya",
                },
            })
            responses.append(websocket.receive_json())

    expected = {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": "embodied_handoff_probe",
            "route": "embodied_handoff_authority",
            "error_code": "session_access_unavailable",
        },
    }
    assert responses == [expected, expected]
    assert main.gameplay_event_store.get_last_global_sequence() == before_sequence
    assert main.gameplay_event_store.read_stream("embodied:handoff:known-handoff-session") == []
    assert main.gameplay_event_store.read_stream("embodied:handoff:unknown-handoff-session") == []
    assert "known-handoff-session" not in str(responses)
    assert "unknown-handoff-session" not in str(responses)
