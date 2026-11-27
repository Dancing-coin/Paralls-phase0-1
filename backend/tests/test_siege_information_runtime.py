from __future__ import annotations

import hashlib
import hmac

import pytest

from app.gameplay.event_schema_registry import (
    EventSchemaRegistry,
    EventSchemaRegistration,
    register_social_delivery_event_schemas,
    create_stormnight_event_schema_registry,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.information_event_schema import register_information_event_schemas
from app.gameplay.information_runtime import (
    InformationAuthority,
    SiegeReportPublicationReceipt,
)
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.p5.social_delivery import (
    SocialDeliveryAuthority, SocialDeliveryResult, SocialDeliveryWindow,
)
from app.models.siming_heavenly_graph import HeavenlyGraphScope, HeavenlyNodeQuery
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.fact_type import FACT_TYPE_REGISTRY


REPORT_AUTHORITY = "authority:information:report-publisher"
REPORT_SECRET = "information-report-fixture-key"
REPORT_EVENT = "gameplay.information.siege_report_published@1"
REPORT_FACT = "fact:information:siege:report"


def _store():
    source_stream_id = "gameplay:reports:campaign"
    registry = EventSchemaRegistry()
    register_social_delivery_event_schemas(registry)
    register_information_event_schemas(registry)
    registry.register(EventSchemaRegistration(
        "gameplay.social.knowledge_observed", 1, "sha256:test:knowledge:v1"
    ))
    registry.register(EventSchemaRegistration(
        "gameplay.social.visibility_revoked", 1, "sha256:test:visibility-revoked:v1"
    ))
    store = GameplayEventStore(event_schema_registry=registry)
    source = build_atomic_event_batch(
        command_id="report:source",
        principal_ref="authority:p5:social",
        stream_id=source_stream_id,
        expected_revision=0,
        event_specs=(("gameplay.social.knowledge_observed", {"fact_ref": "report:east-gate"}),),
        idempotency_key="report:source",
        causation_id="event:dispatch",
        correlation_id="correlation:campaign",
    )
    source = source.model_copy(update={
        "events": [source.events[0].model_copy(update={"visibility_policy": "public"})]
    }, deep=True)
    source_receipt = store.append_batch(source)
    assert source_receipt.committed
    delivered = SocialDeliveryAuthority(store=store).record_delivery(
        delivery_ref="delivery:east-gate:recipient",
        source_stream_id=source_stream_id,
        source_revision=1,
        source_event_id=source_receipt.committed_event_ids[0],
        recipient_ref="character:recipient",
        window=SocialDeliveryWindow(10, 20, 30),
        world_now=15,
        operational_now=12,
        command_id="delivery:east-gate:recipient",
        idempotency_key="delivery:east-gate:recipient",
        causation_id=source_receipt.committed_event_ids[0],
        correlation_id="correlation:east-gate",
    )
    assert delivered.committed
    event_id, = delivered.append_result.committed_event_ids
    return store, event_id


def _update(authority, store, delivery_event_id, **overrides):
    values = {
        "delivery_event_id": delivery_event_id,
        "recipient_ref": "character:recipient",
        "world_now": 15,
        "expected_revision": 0,
        "command_id": "knowledge:east-gate:recipient",
        "idempotency_key": "knowledge:east-gate:recipient",
        "causation_id": delivery_event_id,
        "correlation_id": "correlation:east-gate",
    }
    values.update(overrides)
    return authority.update_knowledge(**values)


def test_committed_delivery_updates_only_its_recipient_knowledge():
    store, delivery_id = _store()
    authority = InformationAuthority(store=store)
    result = _update(authority, store, delivery_id)

    assert result.committed
    event, = store.read_events(event_type="gameplay.information.knowledge_updated@1")
    assert event.visibility_policy == "actor:character:recipient"
    assert event.payload == {
        "recipient_ref": "character:recipient",
        "report_ref": "event:report:source:1",
        "delivery_event_id": delivery_id,
        "delivery_ref": "delivery:east-gate:recipient",
        "known_at_world_tick": 15,
        "source_stream_id": "gameplay:reports:campaign",
        "source_revision": 1,
    }
    assert event.event_id in result.append_result.committed_event_ids
    transaction = store.get_transaction(result.append_result.transaction_id)
    assert transaction.read_stream_revisions == {
        "gameplay:social:delivery:character:recipient:delivery:east-gate:recipient": 1,
        "gameplay:reports:campaign": 1,
    }
    assert "gameplay.information.knowledge_updated@1" in set(FACT_TYPE_REGISTRY.event_types())


def test_information_update_replay_returns_original_receipt():
    store, delivery_id = _store()
    authority = InformationAuthority(store=store)
    first = _update(authority, store, delivery_id)
    second = _update(authority, store, delivery_id)
    assert first.committed and second.committed
    assert second.append_result.idempotency_status == "duplicate_replayed"
    assert second.append_result.committed_event_ids == first.append_result.committed_event_ids
    assert len(store.read_events(event_type="gameplay.information.knowledge_updated@1")) == 1


def test_information_update_retry_rejects_incomplete_receipt_without_writing():
    store, delivery_id = _store()
    authority = InformationAuthority(store=store)
    first = _update(authority, store, delivery_id)
    assert first.committed
    event = store.get_event(first.append_result.committed_event_ids[0])
    transaction = store.get_transaction(event.transaction_id)
    key = (
        transaction.idempotency_record.principal_ref,
        transaction.idempotency_record.idempotency_key,
    )
    store._idempotency_results[key] = first.append_result.model_copy(
        update={"committed_event_ids": []}, deep=True
    )
    before = store.export_snapshot()

    retry = _update(authority, store, delivery_id)

    assert not retry.committed
    assert retry.error_code == "information_knowledge_replay_event_count_mismatch"
    assert store.export_snapshot() == before


def test_information_reaction_uses_committed_recipient_and_current_time():
    store, delivery_id = _store()
    authority = InformationAuthority(store=store)
    delivery = store.get_event(delivery_id)
    command = {
        "delivery": delivery,
        "command_id": "reaction:report-arrival",
        "idempotency_key": "reaction:report-arrival",
        "correlation_id": "correlation:east-gate",
    }
    expired = authority.update_from_delivery(world_now=20, **command)
    assert not expired.committed
    assert expired.error_code == "information_delivery_not_visible"
    assert not store.read_events(event_type="gameplay.information.knowledge_updated@1")

    first = authority.update_from_delivery(world_now=15, **command)
    retry = authority.update_from_delivery(world_now=20, **command)
    changed = authority.update_from_delivery(
        world_now=15, **{**command, "command_id": "reaction:other"}
    )
    assert first.committed
    assert retry.append_result.idempotency_status == "duplicate_replayed"
    assert retry.append_result.committed_event_ids == first.append_result.committed_event_ids
    assert not changed.committed
    assert changed.error_code == "information_idempotency_key_reused"
    event, = store.read_events(event_type="gameplay.information.knowledge_updated@1")
    assert event.visibility_policy == "actor:character:recipient"
    assert event.causation_id == delivery_id
    assert event.payload["known_at_world_tick"] == 15


def test_committed_information_event_reaches_registered_graph_projector():
    store, delivery_id = _store()
    result = _update(InformationAuthority(store=store), store, delivery_id)
    assert result.committed

    scope = HeavenlyGraphScope(
        world_id="world:siege", session_id="session:siege", story_branch_id="branch:main"
    )
    graph = InMemoryHeavenlyGraphAdapter()
    bus = InMemoryAuthorityEventBus()
    bus.subscribe(
        "gameplay.information.knowledge_updated@1",
        HeavenlyAuthorityEventProjector(graph, scope_resolver=lambda _event: scope).project,
    )
    dispatch = GameplayOutboxDispatcher(store=store, bus=bus).dispatch_pending()
    assert dispatch.failed_count == 0
    nodes = graph.query_nodes(HeavenlyNodeQuery(
        scope=scope, valid_at=100, node_types=["causal_event"]
    ))
    assert len(nodes) == 1
    assert nodes[0].attributes["event_type"] == "gameplay.information.knowledge_updated@1"
    assert nodes[0].attributes["domain"] == "information"


def test_information_update_cannot_claim_another_recipient_delivery():
    store, delivery_id = _store()
    before = store.export_snapshot()
    result = _update(
        InformationAuthority(store=store),
        store,
        delivery_id,
        recipient_ref="character:other",
    )
    assert not result.committed
    assert result.error_code == "information_delivery_recipient_mismatch"
    assert store.export_snapshot() == before


def test_information_update_rejects_delivery_after_source_revocation():
    store, delivery_id = _store()
    delivery = store.get_event(delivery_id)
    revoke = build_atomic_event_batch(
        command_id="report:revoke",
        principal_ref="authority:p5:social",
        stream_id=delivery.payload["source_stream_id"],
        expected_revision=1,
        event_specs=(("gameplay.social.visibility_revoked", {
            "recipient_ref": delivery.payload["recipient_ref"],
            "source_event_id": delivery.payload["source_event_id"],
        }),),
        idempotency_key="report:revoke",
        causation_id=delivery_id,
        correlation_id="correlation:east-gate",
    )
    assert store.append_batch(revoke).committed
    before = store.export_snapshot()
    result = _update(InformationAuthority(store=store), store, delivery_id)
    assert not result.committed
    assert result.error_code == "information_delivery_not_visible"
    assert store.export_snapshot() == before


def _report_source(store, *, stream_id="gameplay:facility:east-gate:integrity"):
    result = store.append_batch(build_atomic_event_batch(
        command_id="facility:report-source",
        principal_ref="authority:facility:gate",
        stream_id=stream_id,
        expected_revision=0,
        event_specs=(("gameplay.social.knowledge_observed", {
            "fact_type": "fact:facility:east-gate:integrity",
            "integrity": "72",
        }),),
        idempotency_key="facility:report-source",
        causation_id="event:facility-impact",
        correlation_id="correlation:east-gate",
    ))
    assert result.committed
    return store.get_event(result.committed_event_ids[0])


def _signed_report_receipt(source, **changes):
    values = {
        "authority_ref": REPORT_AUTHORITY,
        "receipt_id": "receipt:east-gate:defender",
        "report_ref": "report:east-gate:integrity",
        "recipient_ref": "character:defender-1",
        "summary": "The east gate integrity is 72.",
        "source_event_id": source.event_id,
        "source_stream_id": source.stream_id,
        "source_revision": source.stream_revision,
        "effective_from": 10,
        "effective_to": 20,
        "signature": "0" * 64,
    }
    values.update(changes)
    unsigned = SiegeReportPublicationReceipt(**values)
    signature = hmac.new(
        REPORT_SECRET.encode("utf-8"), unsigned.canonical_bytes(), hashlib.sha256
    ).hexdigest()
    return unsigned.model_copy(update={"signature": signature})


def _report_authority(store, secrets=None):
    return InformationAuthority(
        store=store,
        report_authority_secrets=secrets or {REPORT_AUTHORITY: REPORT_SECRET},
    )


def _information_store_with_revocations():
    registry = EventSchemaRegistry()
    register_social_delivery_event_schemas(registry)
    register_information_event_schemas(registry)
    registry.register(EventSchemaRegistration(
        "gameplay.social.knowledge_observed", 1, "sha256:test:knowledge:v1"
    ))
    registry.register(EventSchemaRegistration(
        "gameplay.social.visibility_revoked", 1, "sha256:test:visibility-revoked:v1"
    ))
    return GameplayEventStore(event_schema_registry=registry)


def test_information_owner_publishes_signed_report_and_replays_after_window():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    receipt = _signed_report_receipt(source)
    authority = _report_authority(store)

    first = authority.publish_siege_report(receipt=receipt, world_now=15)

    assert first.committed
    report, = store.read_events(event_type=REPORT_EVENT)
    assert report.event_time == 15
    assert report.payload == {
        "fact_type": REPORT_FACT,
        "report_ref": receipt.report_ref,
        "recipient_ref": receipt.recipient_ref,
        "summary": receipt.summary,
        "source_event_id": source.event_id,
        "source_stream_id": source.stream_id,
        "source_revision": source.stream_revision,
        "effective_from": 10,
        "effective_to": 20,
        "published_at_world_tick": 15,
    }
    assert report.visibility_policy == f"actor:{receipt.recipient_ref}"
    report_transaction = store.get_transaction(report.transaction_id)
    assert report_transaction.idempotency_record.principal_ref == "authority:information:report-publisher"

    second = authority.publish_siege_report(receipt=receipt, world_now=25)

    assert second.committed
    assert second.error_code == "duplicate_replayed"
    assert second.report_append_result.idempotency_status == "duplicate_replayed"
    assert second.report_append_result.committed_event_ids == first.report_append_result.committed_event_ids
    assert second.delivery_append_result.committed_event_ids == first.delivery_append_result.committed_event_ids
    assert len(store.read_events(event_type=REPORT_EVENT)) == 1
    assert len(store.read_events(event_type="gameplay.social.delivery_recorded@2")) == 1


def test_information_owner_rejects_invalid_signature_without_writes():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    receipt = _signed_report_receipt(source).model_copy(update={"signature": "0" * 64})
    before = store.export_snapshot()

    result = _report_authority(store).publish_siege_report(receipt=receipt, world_now=15)

    assert not result.committed
    assert result.error_code == "information_report_signature_invalid"
    assert store.export_snapshot() == before


def test_information_owner_rejects_unknown_report_authority_without_writes():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    receipt = _signed_report_receipt(source, authority_ref="authority:unknown")
    before = store.export_snapshot()

    result = _report_authority(store).publish_siege_report(receipt=receipt, world_now=15)

    assert not result.committed
    assert result.error_code == "information_report_signature_invalid"
    assert store.export_snapshot() == before


def test_information_owner_rejects_missing_and_stale_report_sources_without_writes():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    authority = _report_authority(store)
    missing = _signed_report_receipt(
        source,
        source_event_id="event:missing",
        source_stream_id="gameplay:facility:missing:integrity",
    )

    missing_result = authority.publish_siege_report(receipt=missing, world_now=15)
    assert not missing_result.committed
    assert missing_result.error_code == "information_report_source_invalid"
    assert len(store.read_events()) == 1

    advance = build_atomic_event_batch(
        command_id="facility:advance-report-source",
        principal_ref="authority:facility:gate",
        stream_id=source.stream_id,
        expected_revision=1,
        event_specs=(("gameplay.social.knowledge_observed", {"fact_type": "fact:facility:east-gate:integrity"}),),
        idempotency_key="facility:advance-report-source",
        causation_id=source.event_id,
        correlation_id="correlation:east-gate",
    )
    assert store.append_batch(advance).committed
    before = store.export_snapshot()

    stale = authority.publish_siege_report(
        receipt=_signed_report_receipt(source),
        world_now=15,
    )

    assert not stale.committed
    assert stale.error_code == "information_report_source_stale"
    assert store.export_snapshot() == before


def test_information_owner_rejects_changed_receipt_content_without_writes():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    authority = _report_authority(store)
    first = authority.publish_siege_report(
        receipt=_signed_report_receipt(source), world_now=15
    )
    assert first.committed
    before = store.export_snapshot()

    changed = authority.publish_siege_report(
        receipt=_signed_report_receipt(source, summary="Changed report."),
        world_now=15,
    )

    assert not changed.committed
    assert changed.error_code == "information_report_idempotency_key_reused"
    assert store.export_snapshot() == before


def test_information_report_retry_rejects_incomplete_receipt_without_writing():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    authority = _report_authority(store)
    first = authority.publish_siege_report(
        receipt=_signed_report_receipt(source), world_now=15
    )
    assert first.committed
    report = store.get_event(first.report_append_result.committed_event_ids[0])
    transaction = store.get_transaction(report.transaction_id)
    key = (
        transaction.idempotency_record.principal_ref,
        transaction.idempotency_record.idempotency_key,
    )
    store._idempotency_results[key] = first.report_append_result.model_copy(
        update={"committed_event_ids": []}, deep=True
    )
    before = store.export_snapshot()

    retry = authority.publish_siege_report(
        receipt=_signed_report_receipt(source), world_now=25
    )

    assert not retry.committed
    assert retry.error_code == "information_report_replay_event_count_mismatch"
    assert store.export_snapshot() == before


def test_information_report_retry_recovers_delivery_at_committed_tick(monkeypatch):
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    receipt = _signed_report_receipt(source)
    authority = _report_authority(store)
    with monkeypatch.context() as patch:
        patch.setattr(
            SocialDeliveryAuthority, "record_delivery",
            lambda *_args, **_kwargs: SocialDeliveryResult(False, "delivery_unavailable"),
        )
        first = authority.publish_siege_report(receipt=receipt, world_now=15)
    assert not first.committed
    assert first.report_append_result.committed
    assert not store.read_events(event_type="gameplay.social.delivery_recorded@2")

    recovered = _report_authority(store).publish_siege_report(receipt=receipt, world_now=25)

    assert recovered.committed
    assert recovered.report_append_result.committed_event_ids == first.report_append_result.committed_event_ids
    delivery, = store.read_events(event_type="gameplay.social.delivery_recorded@2")
    assert delivery.payload["known_at_world_tick"] == 15


def test_information_report_read_requires_report_and_delivery_known_by_as_of_tick():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    authority = _report_authority(store)
    published = authority.publish_siege_report(
        receipt=_signed_report_receipt(source), world_now=15,
    )
    assert published.committed

    assert authority.read_report_for_recipient(
        recipient_ref="character:defender-1",
        report_ref="report:east-gate:integrity",
        as_of_tick=14,
    ) is None
    view = authority.read_report_for_recipient(
        recipient_ref="character:defender-1",
        report_ref="report:east-gate:integrity",
        as_of_tick=15,
    )

    assert view is not None
    assert view.fact_type == REPORT_FACT
    assert view.report_ref == "report:east-gate:integrity"
    assert view.recipient_ref == "character:defender-1"
    assert view.summary == "The east gate integrity is 72."
    assert view.source_owner_ref == "Information"
    assert view.source_revision == 1
    assert view.event_time == 15
    assert view.known_time == 15


def test_information_report_read_is_recipient_private_and_respects_delivery_window():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source = _report_source(store)
    authority = _report_authority(store)
    published = authority.publish_siege_report(
        receipt=_signed_report_receipt(source), world_now=15,
    )
    assert published.committed

    assert authority.read_report_for_recipient(
        recipient_ref="character:other",
        report_ref="report:east-gate:integrity",
        as_of_tick=15,
    ) is None
    assert authority.read_report_for_recipient(
        recipient_ref="character:defender-1",
        report_ref="report:east-gate:integrity",
        as_of_tick=20,
    ) is None


def test_information_report_read_hides_a_revoked_report():
    store = _information_store_with_revocations()
    source = _report_source(store)
    authority = _report_authority(store)
    published = authority.publish_siege_report(
        receipt=_signed_report_receipt(source), world_now=15,
    )
    assert published.committed
    report, = store.read_stream(
        InformationAuthority.report_stream_id(
            recipient_ref="character:defender-1",
            report_ref="report:east-gate:integrity",
        ),
        event_type=REPORT_EVENT,
        limit=1,
    )
    revocation = build_atomic_event_batch(
        command_id="report:read-revoke",
        principal_ref="authority:p5:social",
        stream_id="gameplay:social:visibility-revocations",
        expected_revision=0,
        event_specs=(("gameplay.social.visibility_revoked", {
            "source_event_id": report.event_id,
            "recipient_ref": "character:defender-1",
        }),),
        idempotency_key="report:read-revoke",
        causation_id=report.event_id,
        correlation_id="correlation:report-revoked",
    )
    assert store.append_batch(revocation).committed

    assert authority.read_report_for_recipient(
        recipient_ref="character:defender-1",
        report_ref="report:east-gate:integrity",
        as_of_tick=15,
    ) is None


def test_information_report_read_rejects_invalid_query_without_store_mutation():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    authority = _report_authority(store)
    before = store.export_snapshot()

    with pytest.raises(ValueError, match="information_report_read_input_invalid"):
        authority.read_report_for_recipient(
            recipient_ref="character:defender-1",
            report_ref="not-a-report",
            as_of_tick=True,
        )

    with pytest.raises(ValueError, match="information_report_read_input_invalid"):
        authority.read_report_for_recipient(
            recipient_ref="character:" + "a" * 161,
            report_ref="report:east-gate",
            as_of_tick=15,
        )

    assert store.export_snapshot() == before
