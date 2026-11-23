from __future__ import annotations

import pytest

from app.gameplay.event_schema_registry import (
    EventSchemaRegistry,
    EventSchemaRegistration,
    register_social_delivery_event_schemas,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.information_event_schema import register_information_event_schemas
from app.gameplay.information_runtime import InformationAuthority
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority, SocialDeliveryWindow
from app.models.siming_heavenly_graph import HeavenlyGraphScope, HeavenlyNodeQuery
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.fact_type import FACT_TYPE_REGISTRY


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

\n