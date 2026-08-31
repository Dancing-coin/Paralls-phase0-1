import pytest

from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionPublisher,
    GameplayGodotProjectionRepository,
    GameplayMirrorAfterCommitDelivery,
    GameplayMirrorConnectionError,
    GameplayMirrorConnectionRegistry,
    GameplayGodotMirrorSyncAdapter,
    GameplayMirrorOutboundQueue,
    GameplayMirrorDeliveryError,
    GameplayMirrorOutboxRefreshConsumer,
    GameplayMirrorSubscriptionRegistry,
)
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from test_gameplay_event_store_contract import _batch, _event, _outbox
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.ws_protocol import GameplayMirrorPredictionResolution


def _snapshot_projection(actor_ref: str, facade_revision: str) -> dict[str, object]:
    return {
        "actor_ref": actor_ref,
        "projection_kind": "gameplay_runtime_state.godot.v1",
        "facade_revision": facade_revision,
        "source_revision_vector": {"stream": 1},
        "groups": {},
    }


def _delivery_envelope(actor_ref: str, sequence: int) -> dict[str, object]:
    return {
        "message_type": "gameplay_mirror_delivery",
        "payload": {
            "actor_ref": actor_ref,
            "delivery_sequence": sequence,
        },
    }


def _godot_view(actor_ref: str, *, include_resources: bool = True, include_status: bool = False):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1))
    registry.register(StateGroupDefinition(group_id="core.status", definition_version="1", projection_schema_version=1))
    group_payloads = {}
    enabled_group_ids = []
    if include_resources:
        group_payloads["core.resources"] = {"current": 7, "private": "hidden"}
        enabled_group_ids.append("core.resources")
    if include_status:
        group_payloads["core.status"] = {"current": 2, "private": "hidden"}
        enabled_group_ids.append("core.status")
    state = CharacterGameRuntimeStateBuilder(registry).build(actor_ref=actor_ref, enabled_group_ids=enabled_group_ids, group_payloads=group_payloads, source_revision_vector={"stream": 1}, registry_revision="registry", world_config_revision="world", active_patch_set_revision="patch")
    return StateGroupViewProjector([
        StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("current",)),
        StateGroupConsumerViewPolicy(group_id="core.status", godot_allowed_fields=("current",)),
    ]).godot_view(state, allowed_group_ids=("core.resources", "core.status"))


def test_subscription_requires_backend_grant_and_only_delivers_filtered_actor_view() -> None:
    registry = GameplayMirrorSubscriptionRegistry(projection_source=_godot_view)
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_scope_unauthorized"):
        registry.subscribe(session_ref="session:a", actor_ref="actor:a")

    registry.grant_read_scope(session_ref="session:a", actor_ref="actor:a")
    subscription, snapshot = registry.subscribe(session_ref="session:a", actor_ref="actor:a")
    after_commit = registry.after_commit_snapshot(subscription)

    assert snapshot["actor_ref"] == "actor:a"
    assert snapshot["groups"]["core.resources"]["payload"] == {"current": 7}
    assert after_commit == snapshot


def test_after_commit_fanout_only_reaches_subscribed_authorized_affected_actor_scopes() -> None:
    registry = GameplayMirrorSubscriptionRegistry(projection_source=_godot_view)
    for session_ref, actor_ref in (("session:one", "actor:a"), ("session:two", "actor:a"), ("session:one", "actor:b")):
        registry.grant_read_scope(session_ref=session_ref, actor_ref=actor_ref)
        registry.subscribe(session_ref=session_ref, actor_ref=actor_ref)

    sent: list[tuple[str, dict[str, object]]] = []
    delivery = GameplayMirrorAfterCommitDelivery(registry=registry, deliver=lambda session_ref, payload: sent.append((session_ref, payload)))

    result = delivery.deliver_for_committed_actor_refs(affected_actor_refs=("actor:a",))

    assert result.delivered_session_refs == ("session:one", "session:two")
    assert result.failed_session_refs == ()
    assert [(session_ref, payload["actor_ref"]) for session_ref, payload in sent] == [
        ("session:one", "actor:a"),
        ("session:two", "actor:a"),
    ]


def test_prediction_resolution_targets_only_authorized_subscribed_actor_scopes() -> None:
    registry = GameplayMirrorSubscriptionRegistry(projection_source=_godot_view)
    for session_ref, actor_ref in (("session:one", "actor:a"), ("session:two", "actor:a"), ("session:one", "actor:b")):
        registry.grant_read_scope(session_ref=session_ref, actor_ref=actor_ref)
        registry.subscribe(session_ref=session_ref, actor_ref=actor_ref)

    assert registry.subscribed_session_refs(actor_ref="actor:a") == ("session:one", "session:two")
    assert registry.subscribed_session_refs(actor_ref="actor:b") == ("session:one",)


def test_after_commit_transport_failure_does_not_prevent_other_authorized_deliveries() -> None:
    registry = GameplayMirrorSubscriptionRegistry(projection_source=_godot_view)
    for session_ref in ("session:one", "session:two"):
        registry.grant_read_scope(session_ref=session_ref, actor_ref="actor:a")
        registry.subscribe(session_ref=session_ref, actor_ref="actor:a")

    delivered: list[str] = []

    def _deliver(session_ref: str, _payload: dict[str, object]) -> None:
        if session_ref == "session:one":
            raise ConnectionError("closed")
        delivered.append(session_ref)

    result = GameplayMirrorAfterCommitDelivery(registry=registry, deliver=_deliver).deliver_for_committed_actor_refs(affected_actor_refs=("actor:a",))

    assert result.delivered_session_refs == ("session:two",)
    assert result.failed_session_refs == ("session:one",)
    assert delivered == ["session:two"]


def test_unrecoverable_after_commit_failure_drops_scope_and_requests_transport_revocation() -> None:
    registry = GameplayMirrorSubscriptionRegistry(projection_source=_godot_view)
    registry.grant_read_scope(session_ref="session:failed", actor_ref="actor:a")
    registry.subscribe(session_ref="session:failed", actor_ref="actor:a")
    revoked: list[str] = []

    delivery = GameplayMirrorAfterCommitDelivery(
        registry=registry,
        deliver=lambda _session_ref, _payload: (_ for _ in ()).throw(ConnectionError("closed")),
        on_delivery_failure=revoked.append,
    )
    result = delivery.deliver_for_committed_actor_refs(affected_actor_refs=("actor:a",))

    assert result.delivered_session_refs == ()
    assert result.failed_session_refs == ("session:failed",)
    assert revoked == ["session:failed"]
    assert registry.subscribed_session_refs(actor_ref="actor:a") == ()


def test_connection_registry_replaces_only_matching_connection_and_fails_closed() -> None:
    registry = GameplayMirrorConnectionRegistry()
    delivered: list[dict[str, object]] = []
    registry.register(
        session_ref="session:one",
        connection_ref="connection:one",
        deliver=delivered.append,
    )

    registry.deliver("session:one", _snapshot_projection("actor:a", "facade:one"))

    assert delivered[0]["payload"]["payload"]["actor_ref"] == "actor:a"
    assert registry.unregister(session_ref="session:one", connection_ref="connection:other") is False
    assert registry.unregister(session_ref="session:one", connection_ref="connection:one") is True
    with pytest.raises(GameplayMirrorConnectionError, match="mirror_connection_unavailable"):
        registry.deliver("session:one", _snapshot_projection("actor:a", "facade:two"))


def test_connection_registry_assigns_monotonic_delivery_sequences_per_epoch() -> None:
    registry = GameplayMirrorConnectionRegistry()
    delivered: list[dict[str, object]] = []
    registry.register(
        session_ref="session:one",
        connection_ref="connection:one",
        connection_epoch=4,
        deliver=delivered.append,
    )

    registry.deliver("session:one", _snapshot_projection("actor:a", "facade:1"))
    registry.deliver("session:one", _snapshot_projection("actor:a", "facade:2"))

    assert [message["message_type"] for message in delivered] == ["gameplay_mirror_delivery", "gameplay_mirror_delivery"]
    assert [message["payload"]["delivery_sequence"] for message in delivered] == [1, 2]
    assert {message["payload"]["connection_epoch"] for message in delivered} == {4}


def test_connection_registry_orders_prediction_resolutions_after_authority_delivery() -> None:
    registry = GameplayMirrorConnectionRegistry()
    delivered: list[dict[str, object]] = []
    registry.register(
        session_ref="session:one",
        connection_ref="connection:one",
        connection_epoch=4,
        deliver=delivered.append,
    )

    registry.deliver("session:one", _snapshot_projection("actor:a", "facade:1"))
    registry.deliver_prediction_resolutions(
        session_ref="session:one",
        actor_ref="actor:a",
        facade_revision="facade:1",
        resolutions=(
            GameplayMirrorPredictionResolution(
                prediction_id="prediction:stamina:one",
                command_id="command:stamina:one",
                resolution="confirmed",
                transaction_id="tx:stamina:one",
            ),
        ),
    )

    assert [message["payload"]["delivery_kind"] for message in delivered] == ["snapshot", "prediction"]
    assert [message["payload"]["delivery_sequence"] for message in delivered] == [1, 2]
    assert delivered[1]["payload"]["prediction_resolutions"] == [
        {
            "prediction_id": "prediction:stamina:one",
            "command_id": "command:stamina:one",
            "resolution": "confirmed",
            "transaction_id": "tx:stamina:one",
            "error_code": "",
        }
    ]


def test_outbound_queue_coalesces_only_its_own_dirty_actor_without_authority_mutation() -> None:
    queue = GameplayMirrorOutboundQueue(projection_capacity=1, control_capacity=1, dirty_actor_limit=1)
    store = GameplayEventStore()
    authority_snapshot = store.export_snapshot()

    queue.enqueue_projection(_delivery_envelope("actor:a", 1))
    assert queue.enqueue_projection(_delivery_envelope("actor:a", 2)) is False
    assert queue.dirty_actor_count == 1
    assert queue.pop_next()["payload"]["delivery_sequence"] == 1
    assert queue.pop_next()["message_type"] == "gameplay_mirror_resync_required"
    assert queue.pop_next()["payload"]["delivery_sequence"] == 2
    assert store.export_snapshot() == authority_snapshot


def test_saturated_queue_does_not_block_a_separate_connection_queue() -> None:
    saturated = GameplayMirrorOutboundQueue(projection_capacity=1, control_capacity=1, dirty_actor_limit=1)
    healthy = GameplayMirrorOutboundQueue(projection_capacity=1, control_capacity=1, dirty_actor_limit=1)

    saturated.enqueue_projection(_delivery_envelope("actor:a", 1))
    saturated.enqueue_projection(_delivery_envelope("actor:a", 2))
    assert healthy.enqueue_projection(_delivery_envelope("actor:b", 1)) is True

    assert healthy.pop_next()["payload"]["actor_ref"] == "actor:b"
    assert saturated.dirty_actor_count == 1


def test_projection_publisher_refreshes_explicit_transaction_actors_and_removes_stale_views() -> None:
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    publisher.register_actor_source(actor_ref="actor:a", source=lambda: _godot_view("actor:a"))
    repository.publish(_godot_view("actor:missing"))
    store = GameplayEventStore()
    batch = _batch(
        events=[_event("evt:publisher", stream_id="actor:a")],
        outbox_entries=[_outbox("evt:publisher")],
        expected={"actor:a": 0},
    )
    batch["projection_refresh_hints"] = [
        {
            "projection_id": "godot_mirror",
            "stream_id": "actor:a",
            "reason": "projection_refresh",
            "actor_refs": ["actor:a", "actor:missing"],
        }
    ]
    assert store.append_batch(batch).committed

    result = publisher.after_transaction_dispatched(store.read_transactions()[0])

    assert result.published_actor_refs == ("actor:a",)
    assert result.unavailable_actor_refs == ("actor:missing",)
    assert repository.view_for("actor:a").actor_ref == "actor:a"
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_projection_unavailable"):
        repository.view_for("actor:missing")


def test_outbox_refresh_waits_for_every_entry_of_the_committed_transaction() -> None:
    registry = GameplayMirrorSubscriptionRegistry(projection_source=_godot_view)
    registry.grant_read_scope(session_ref="session:one", actor_ref="actor:a")
    registry.subscribe(session_ref="session:one", actor_ref="actor:a")
    sent: list[tuple[str, dict[str, object]]] = []
    consumer = GameplayMirrorOutboxRefreshConsumer(
        delivery=GameplayMirrorAfterCommitDelivery(
            registry=registry,
            deliver=lambda session_ref, payload: sent.append((session_ref, payload)),
        )
    )
    store = GameplayEventStore()
    dispatcher = GameplayOutboxDispatcher(
        store=store,
        bus=InMemoryAuthorityEventBus(),
        after_transaction_dispatched=consumer.after_transaction_dispatched,
    )
    batch = _batch(
        events=[
            _event("evt:mirror:one", stream_id="actor:a"),
            _event("evt:mirror:two", stream_id="actor:a"),
        ],
        outbox_entries=[_outbox("evt:mirror:one"), _outbox("evt:mirror:two")],
        expected={"actor:a": 0},
    )
    batch["projection_refresh_hints"] = [
        {
            "projection_id": "godot_mirror",
            "stream_id": "actor:a",
            "reason": "resources_changed",
            "actor_refs": ["actor:a"],
        }
    ]
    assert store.append_batch(batch).committed

    assert dispatcher.dispatch_pending(limit=1).published_count == 1
    assert sent == []
    assert consumer.results == []

    assert dispatcher.dispatch_pending().published_count == 1
    assert [(session_ref, payload["actor_ref"]) for session_ref, payload in sent] == [("session:one", "actor:a")]
    assert consumer.results[0].delivered_session_refs == ("session:one",)


def test_filtered_view_sync_adapter_uses_exact_base_checksum_and_removes_omitted_groups() -> None:
    adapter = GameplayGodotMirrorSyncAdapter()
    base = adapter.snapshot(_godot_view("actor:a"))
    target_view = _godot_view("actor:a", include_resources=False, include_status=True)
    target = adapter.snapshot(target_view)

    delta = adapter.delta(
        base,
        target,
        confirmed_prediction_ids=("prediction:stamina:one",),
        rejected_predictions=("prediction:stamina:two",),
    )
    rebuilt = adapter.apply_delta(base, delta)
    snapshot_payload = adapter.snapshot_payload(target)
    delta_payload = adapter.delta_payload(base, delta)

    assert delta.removed_group_ids == ("core.resources",)
    assert rebuilt.snapshot_checksum == target.snapshot_checksum
    assert set(rebuilt.groups) == {"core.status"}
    assert snapshot_payload["groups"]["core.status"]["payload"] == {"current": 2}
    assert "private" not in str(snapshot_payload)
    assert delta_payload["base_snapshot_checksum"] == base.snapshot_checksum
    assert delta_payload["target_snapshot_checksum"] == target.snapshot_checksum
    assert delta_payload["removed_group_ids"] == ["core.resources"]
    assert delta_payload["confirmed_prediction_ids"] == ["prediction:stamina:one"]
    assert delta_payload["rejected_predictions"] == ["prediction:stamina:two"]


def test_connection_registry_delivers_fixed_government_advisory_without_an_actor_facade() -> None:
    registry = GameplayMirrorConnectionRegistry()
    sent: list[dict[str, object]] = []
    registry.register(
        session_ref="session:government-advisory",
        connection_ref="connection:government-advisory",
        connection_epoch=4,
        deliver=sent.append,
    )

    registry.deliver_government_drought_advisory(
        "session:government-advisory",
        {
            "projection_kind": "government_drought_advisory.project.v1",
            "jurisdiction_ref": "jurisdiction:government-advisory",
            "advisory_refs": ["advisory:drought:one"],
            "source_revision_vector": {"gameplay:government:advisory:government-advisory": 1},
            "projection_hash": "sha256:advisory",
        },
    )

    assert sent == [
        {
            "message_type": "government_drought_advisory_delivery",
            "payload": {
                "connection_epoch": 4,
                "delivery_sequence": 1,
                "projection_kind": "government_drought_advisory.project.v1",
                "jurisdiction_ref": "jurisdiction:government-advisory",
                "advisory_refs": ["advisory:drought:one"],
                "source_revision_vector": {"gameplay:government:advisory:government-advisory": 1},
                "projection_hash": "sha256:advisory",
            },
        }
    ]
    assert "actor_ref" not in str(sent)
