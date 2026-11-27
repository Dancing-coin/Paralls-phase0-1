from __future__ import annotations

import hashlib
import hmac

import pytest

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import (
    DurableGameplayEventStore,
    GameplayEventStore,
    GameplayEventStoreSnapshotError,
)
from app.gameplay.information_runtime import (
    INFORMATION_KNOWLEDGE_EVENT_TYPE,
    INFORMATION_REPORT_EVENT,
    INFORMATION_REPORT_FACT_TYPE,
    INFORMATION_REPORT_PRINCIPAL,
    InformationAuthority,
    SiegeReportPublicationReceipt,
)
from app.gameplay.m6_5_siege_runtime import DEFAULT_MORALE_DEFINITIONS, build_m6_5_siege_runtime
from app.gameplay.models import ProjectionCheckpoint
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch


RECIPIENT = "character:checkpoint-defender"
REPORT_REF = "report:checkpoint-east-gate"
REPORT_SOURCE_PRINCIPAL = "authority:information:report-publisher"
REPORT_SECRET = "fixture-key"
PROJECTOR_ID = "test.information-checkpoint"
PROJECTOR_VERSION = "1"


def _append_source_event(store: GameplayEventStore) -> str:
    source_batch = build_atomic_event_batch(
        command_id="information-checkpoint:source",
        principal_ref="authority:facility:checkpoint-fixture",
        stream_id="gameplay:facility:gate:checkpoint-east-gate",
        expected_revision=0,
        event_specs=(("gameplay.pool.threshold_crossed", {
            "fact_type": "fact:facility:checkpoint-east-gate:integrity",
            "threshold_ref": "breach",
        }),),
        idempotency_key="information-checkpoint:source",
        causation_id="command:information-checkpoint:source",
        correlation_id="siege:checkpoint-east-gate",
    )
    committed = store.append_batch(source_batch)
    assert committed.committed
    return committed.committed_event_ids[0]


def _publish_report(store: GameplayEventStore):
    source_event_id = _append_source_event(store)
    source = store.get_event(source_event_id)
    receipt = SiegeReportPublicationReceipt(
        authority_ref=REPORT_SOURCE_PRINCIPAL,
        receipt_id="receipt:checkpoint-east-gate",
        report_ref=REPORT_REF,
        recipient_ref=RECIPIENT,
        summary="The east gate has been breached.",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        effective_from=10,
        effective_to=30,
        signature="0" * 64,
    )
    signature = hmac.new(
        REPORT_SECRET.encode("utf-8"), receipt.canonical_bytes(), hashlib.sha256
    ).hexdigest()
    receipt = receipt.model_copy(update={"signature": signature})
    authority = InformationAuthority(
        store=store,
        report_authority_secrets={REPORT_SOURCE_PRINCIPAL: REPORT_SECRET},
    )
    result = authority.publish_siege_report(receipt=receipt, world_now=15)
    assert result.committed
    assert result.delivery_append_result is not None
    return result


def _replay() -> GameplayProjectionReplay:
    return GameplayProjectionReplay(
        projector_id=PROJECTOR_ID,
        projector_version=PROJECTOR_VERSION,
    )


def _assert_report_delivery_checkpoint(checkpoint: ProjectionCheckpoint, store):
    report, = store.read_events(event_type=INFORMATION_REPORT_EVENT)
    delivery, = store.read_events(event_type="gameplay.social.delivery_recorded@2")
    assert report.event_id in checkpoint.applied_event_ids
    assert checkpoint.state[report.stream_id]["last_event_id"] == report.event_id
    assert checkpoint.state[delivery.stream_id]["last_event_id"] == delivery.event_id
    assert checkpoint.state[report.stream_id]["last_payload"]["recipient_ref"] == RECIPIENT
    assert report.visibility_policy == delivery.visibility_policy == f"actor:{RECIPIENT}"
    assert (
        store.get_transaction(report.transaction_id).idempotency_record.principal_ref
        == INFORMATION_REPORT_PRINCIPAL
    )
    assert (
        store.get_transaction(delivery.transaction_id).idempotency_record.principal_ref
        == "authority:p5:social-delivery"
    )


def test_information_checkpoint_tail_replay_matches_durable_full_replay(tmp_path):
    store_path = tmp_path / "information-events.sqlite"
    store = DurableGameplayEventStore(
        store_path,
        event_schema_registry=create_stormnight_event_schema_registry(),
    )
    try:
        publication = _publish_report(store)
        checkpoint = _replay().create_checkpoint(store.read_events())
        store.save_projection_checkpoint(checkpoint)
        _assert_report_delivery_checkpoint(checkpoint, store)

        delivery_transaction = store.get_transaction(
            publication.delivery_append_result.transaction_id
        )
        runtime = build_m6_5_siege_runtime(
            store=store,
            morale_definitions=DEFAULT_MORALE_DEFINITIONS,
            world_tick_provider=lambda: 16,
        )
        updates = runtime.after_transaction_dispatched(delivery_transaction)
        assert len(updates) == 1 and updates[0].committed

        tail = [
            event for event in store.read_events()
            if event.global_sequence > checkpoint.last_global_sequence
        ]
        assert [event.event_type for event in tail] == [INFORMATION_KNOWLEDGE_EVENT_TYPE]
        knowledge = tail[0]
        assert knowledge.event_time == 16
        assert knowledge.visibility_policy == f"actor:{RECIPIENT}"
        knowledge_transaction = store.get_transaction(knowledge.transaction_id)
        assert knowledge_transaction.idempotency_record.principal_ref == "authority:information"
        assert knowledge_transaction.read_stream_revisions == {
            store.get_event(knowledge.payload["delivery_event_id"]).stream_id: 1,
            knowledge.payload["source_stream_id"]: knowledge.payload["source_revision"],
        }

        store.close()
        reopened = DurableGameplayEventStore(
            store_path,
            event_schema_registry=create_stormnight_event_schema_registry(),
        )
        try:
            reopened_checkpoint = reopened.get_projection_checkpoint(checkpoint.checkpoint_id)
            assert reopened_checkpoint == checkpoint
            _assert_report_delivery_checkpoint(reopened_checkpoint, reopened)
            reopened_knowledge = reopened.read_events(
                event_type=INFORMATION_KNOWLEDGE_EVENT_TYPE
            )
            assert len(reopened_knowledge) == 1
            assert (
                reopened.get_transaction(reopened_knowledge[0].transaction_id)
                .idempotency_record.principal_ref == "authority:information"
            )
            assert reopened_knowledge[0].event_time == 16

            full = _replay().full_replay(reopened.read_events())
            tail_result = _replay().checkpoint_plus_tail_replay(
                reopened_checkpoint,
                [
                    event for event in reopened.read_events()
                    if event.global_sequence > reopened_checkpoint.last_global_sequence
                ],
            )
            assert full.succeeded and tail_result.succeeded
            assert tail_result.state == full.state
            assert tail_result.source_revision_vector == full.source_revision_vector
            assert tail_result.applied_event_ids == full.applied_event_ids
            assert tail_result.projection_hash == full.projection_hash
            assert tail_result.state[knowledge.stream_id]["last_event_id"] == knowledge.event_id
            assert tail_result.state[knowledge.stream_id]["last_payload"] == knowledge.payload

            missing_snapshot = reopened.export_snapshot()
            missing_snapshot["events"] = [
                row for row in missing_snapshot["events"]
                if row["event_type"] != INFORMATION_REPORT_EVENT
            ]
            with pytest.raises(GameplayEventStoreSnapshotError):
                GameplayEventStore.from_snapshot(
                    missing_snapshot,
                    event_schema_registry=create_stormnight_event_schema_registry(),
                )

            tampered_snapshot = reopened.export_snapshot()
            report_row = next(
                row for row in tampered_snapshot["events"]
                if row["event_type"] == INFORMATION_REPORT_EVENT
            )
            report_row["event_id"] = "event:tampered-report-reference"
            with pytest.raises(GameplayEventStoreSnapshotError):
                GameplayEventStore.from_snapshot(
                    tampered_snapshot,
                    event_schema_registry=create_stormnight_event_schema_registry(),
                )
        finally:
            reopened.close()
    finally:
        store.close()
