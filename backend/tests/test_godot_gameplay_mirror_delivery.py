import pytest

from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionPublisher,
    GameplayGodotProjectionRepository,
    GameplayMirrorAfterCommitDelivery,
    GameplayMirrorConnectionError,
    GameplayMirrorConnectionRegistry,
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


def _godot_view(actor_ref: str):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(actor_ref=actor_ref, enabled_group_ids=("core.resources",), group_payloads={"core.resources": {"current": 7, "private": "hidden"}}, source_revision_vector={"stream": 1}, registry_revision="registry", world_config_revision="world", active_patch_set_revision="patch")
    return StateGroupViewProjector([StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("current",))]).godot_view(state, allowed_group_ids=("core.resources",))


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


def test_connection_registry_replaces_only_matching_connection_and_fails_closed() -> None:
    registry = GameplayMirrorConnectionRegistry()
    delivered: list[dict[str, object]] = []
    registry.register(
        session_ref="session:one",
        connection_ref="connection:one",
        deliver=delivered.append,
    )

    registry.deliver("session:one", {"actor_ref": "actor:a"})

    assert delivered == [{"actor_ref": "actor:a"}]
    assert registry.unregister(session_ref="session:one", connection_ref="connection:other") is False
    assert registry.unregister(session_ref="session:one", connection_ref="connection:one") is True
    with pytest.raises(GameplayMirrorConnectionError, match="mirror_connection_unavailable"):
        registry.deliver("session:one", {"actor_ref": "actor:a"})


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
