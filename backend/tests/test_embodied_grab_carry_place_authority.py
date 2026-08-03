from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main
from app.main import app, reset_runtime_state
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_carry_place_authority_service import EmbodiedCarryPlaceAuthorityService
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger


def _service() -> tuple[EmbodiedCarryPlaceAuthorityService, GameplayEventStore, InMemoryAuthorityEventBus]:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    service = EmbodiedCarryPlaceAuthorityService(
        store=store,
        dispatcher=GameplayOutboxDispatcher(store=store, bus=bus),
        evidence_ledger=EmbodiedEvidenceLedger(),
    )
    service.seed_asset_possession(
        asset_ref="item:crate_01",
        custody_holder_ref="world:anchor:table_01",
        owner_ref="character:siming",
    )
    service.seed_drop_target(
        target_ref="world:anchor:floor_slot_01",
        occupied_by_ref="",
        scene_revision=11,
    )
    service.seed_drop_target(
        target_ref="world:anchor:occupied_slot_01",
        occupied_by_ref="item:barrel_01",
        scene_revision=11,
    )
    return service, store, bus


def test_grab_carry_place_settles_custody_occupancy_and_mirror_directive_in_one_gameplay_batch() -> None:
    service, store, bus = _service()
    service.start_carry_place(
        session_id="session:carry-place:crate:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:floor_slot_01",
        causation_id="cmd:carry-place:crate:1:start",
        correlation_id="corr:carry-place:crate:1",
    )

    result = service.settle_carry_place(
        session_id="session:carry-place:crate:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:floor_slot_01",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "world:anchor:floor_slot_01": "digest:terminal:floor_slot",
        },
        idempotency_key="carry-place:crate:1:settle",
        payload_digest="digest:carry-place:crate:1",
    )

    transaction = store.read_transactions()[-1]
    event_types = [event.event_type for event in transaction.events]
    projection = service.possession_projection("item:crate_01")
    occupancy = service.drop_target_projection("world:anchor:floor_slot_01")

    assert result.accepted is True
    assert result.transaction_id == transaction.transaction_id
    assert event_types == [
        "embodied.interaction_session.participant_observed",
        "embodied.interaction_session.participant_observed",
        "inventory.custody_changed",
        "embodied.carry.started",
        "scene.occupancy.changed",
        "embodied.place.settled",
        "embodied.interaction_session.committed",
    ]
    assert len({event.transaction_id for event in transaction.events}) == 1
    assert projection == {
        "asset_ref": "item:crate_01",
        "custody_holder_ref": "world:anchor:floor_slot_01",
        "owner_ref": "character:siming",
        "authority_transaction_id": transaction.transaction_id,
        "source": "backend_authority",
    }
    assert occupancy == {
        "target_ref": "world:anchor:floor_slot_01",
        "occupied_by_ref": "item:crate_01",
        "scene_revision": 12,
        "authority_transaction_id": transaction.transaction_id,
        "source": "backend_authority",
    }
    assert [event.event_type for event in bus.list_events()[-7:]] == event_types
    assert bus.list_events(event_type="embodied.place.settled")[-1].payload["placement_directive"] == {
        "mode": "place_for_presentation",
        "asset_ref": "item:crate_01",
        "place_at_ref": "world:anchor:floor_slot_01",
        "authority_only": True,
    }


def test_local_grab_carry_place_hint_never_changes_custody_or_occupancy_projection() -> None:
    service, _store, _bus = _service()

    hinted = service.apply_local_carry_hint(
        asset_ref="item:crate_01",
        carried_by_ref="character:siming",
        intended_drop_target_ref="world:anchor:floor_slot_01",
        source_ref="godot:local_carry_probe",
    )

    assert hinted == {
        "accepted": True,
        "authority_mutation": False,
        "reason": "presentation_hint_only",
    }
    assert service.possession_projection("item:crate_01")["custody_holder_ref"] == "world:anchor:table_01"
    assert service.drop_target_projection("world:anchor:floor_slot_01")["occupied_by_ref"] == ""


def test_carry_place_rejects_occupied_drop_target_before_any_cross_domain_commit() -> None:
    service, store, _bus = _service()
    started = service.start_carry_place(
        session_id="session:carry-place:occupied:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:occupied_slot_01",
        causation_id="cmd:carry-place:occupied:1:start",
        correlation_id="corr:carry-place:occupied:1",
    )

    assert started.accepted is False
    assert started.error_code == "drop_target_occupied"
    assert store.read_events() == []


def test_carry_place_rejects_invalid_source_custody_without_partial_commit() -> None:
    service, store, _bus = _service()
    started = service.start_carry_place(
        session_id="session:carry-place:bad-source:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="character:maya",
        drop_target_ref="world:anchor:floor_slot_01",
        causation_id="cmd:carry-place:bad-source:1:start",
        correlation_id="corr:carry-place:bad-source:1",
    )

    assert started.accepted is False
    assert started.error_code == "source_custody_mismatch"
    assert store.read_events() == []


def test_carry_place_duplicate_idempotency_replays_original_without_second_mutation() -> None:
    service, store, _bus = _service()
    service.start_carry_place(
        session_id="session:carry-place:crate:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:floor_slot_01",
        causation_id="cmd:carry-place:crate:1:start",
        correlation_id="corr:carry-place:crate:1",
    )

    first = service.settle_carry_place(
        session_id="session:carry-place:crate:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:floor_slot_01",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "world:anchor:floor_slot_01": "digest:terminal:floor_slot",
        },
        idempotency_key="carry-place:crate:1:settle",
        payload_digest="digest:carry-place:crate:1",
    )
    duplicate = service.settle_carry_place(
        session_id="session:carry-place:crate:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:floor_slot_01",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "world:anchor:floor_slot_01": "digest:terminal:floor_slot",
        },
        idempotency_key="carry-place:crate:1:settle",
        payload_digest="digest:carry-place:crate:1",
    )

    assert first.accepted is True
    assert duplicate.accepted is True
    assert duplicate.idempotent is True
    assert duplicate.transaction_id == first.transaction_id
    assert len(store.read_transactions()) == 4


def test_carry_place_revision_conflict_rejects_without_partial_cross_domain_commit() -> None:
    service, store, _bus = _service()
    service.start_carry_place(
        session_id="session:carry-place:crate:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:floor_slot_01",
        causation_id="cmd:carry-place:crate:1:start",
        correlation_id="corr:carry-place:crate:1",
    )

    result = service.settle_carry_place(
        session_id="session:carry-place:crate:1",
        asset_ref="item:crate_01",
        actor_ref="character:siming",
        source_holder_ref="world:anchor:table_01",
        drop_target_ref="world:anchor:floor_slot_01",
        participant_observations={
            "character:siming": "digest:terminal:siming",
            "world:anchor:floor_slot_01": "digest:terminal:floor_slot",
        },
        idempotency_key="carry-place:crate:1:settle",
        payload_digest="digest:carry-place:crate:1",
        expected_stream_revisions={"scene:occupancy:world:anchor:floor_slot_01": 9},
    )

    assert result.accepted is False
    assert result.error_code == "revision_conflict"
    assert [event.event_type for event in store.read_events()] == [
        "embodied.interaction_session.proposed",
        "embodied.interaction_session.accepted",
        "embodied.interaction_session.authorized",
        "embodied.interaction_session.realizing",
    ]
    assert service.possession_projection("item:crate_01")["custody_holder_ref"] == "world:anchor:table_01"
    assert service.drop_target_projection("world:anchor:floor_slot_01")["occupied_by_ref"] == ""


def test_websocket_carry_place_probe_delivers_authority_only_projection_without_unsafe_fields() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "embodied_grab_carry_place_probe",
                "payload": {
                    "session_id": "session:carry-place:websocket:1",
                    "asset_ref": "item:crate_01",
                    "actor_ref": "character:siming",
                    "source_holder_ref": "world:anchor:table_01",
                    "drop_target_ref": "world:anchor:floor_slot_01",
                },
            }
        )

        received = [websocket.receive_json() for _ in range(2)]

    ack = received[0]
    carry_place_event = received[1]
    payload = carry_place_event["payload"]
    place_store_events = main.gameplay_event_store.read_stream("embodied:place:session:carry-place:websocket:1")

    assert ack == {
        "message_type": "ack",
        "payload": {
            "accepted": True,
            "source_type": "embodied_grab_carry_place_probe",
            "route": "embodied_carry_place_authority",
        },
    }
    assert carry_place_event["message_type"] == "embodied_carry_place_event"
    assert payload["event_type"] == "embodied.place.settled"
    assert payload["asset_ref"] == "item:crate_01"
    assert payload["actor_ref"] == "character:siming"
    assert payload["custody_holder_ref"] == "world:anchor:floor_slot_01"
    assert payload["drop_target_ref"] == "world:anchor:floor_slot_01"
    assert payload["transaction_id"].startswith("tx:session:carry-place:websocket:1:carry-place:")
    assert payload["global_sequence"] > 0
    assert payload["placement_directive"] == {
        "mode": "place_for_presentation",
        "asset_ref": "item:crate_01",
        "place_at_ref": "world:anchor:floor_slot_01",
        "authority_only": True,
    }
    assert [event.event_type for event in place_store_events] == ["embodied.place.settled"]
    assert "world_truth_claim" not in str(payload)
    assert "character_actor_status" not in str(payload)
    assert "participant_private_terms" not in str(payload)
