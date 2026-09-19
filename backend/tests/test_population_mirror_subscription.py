import pytest

from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionPublisher, GameplayGodotProjectionRepository,
    GameplayMirrorDeliveryError, GameplayMirrorSubscriptionRegistry,
)
from app.services.gameplay_mirror_session_access_service import (
    GameplayMirrorSessionAccessError, GameplayMirrorSessionAccessService, GameplayMirrorSubscriptionRequest,
)
from test_gameplay_mirror_session_access_service import _context, _projection_source


def test_subscription_cap_rejects_before_build_and_rotation_evicts_unused_view():
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    registry = GameplayMirrorSubscriptionRegistry(projection_source=repository.view_for)
    bindings = {}
    service = GameplayMirrorSessionAccessService(registry=registry, projection_publisher=publisher, binding_resolver=bindings.get)
    calls = []
    actors = tuple(f"character:resident_{index}" for index in range(161))
    context = _context(*actors)
    bindings[context.binding.session_ref] = context.binding

    def source(actor):
        calls.append(actor)
        return _projection_source(actor)

    for actor in actors:
        publisher.register_actor_source(actor_ref=actor, source=lambda actor=actor: source(actor))
    with pytest.raises(GameplayMirrorSessionAccessError, match="mirror_subscription_required"):
        service.snapshot(context=context, actor_ref=actors[-1])
    assert not calls
    for actor in actors[:160]:
        service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref=actor))
    assert len(calls) == 160
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_subscription_limit"):
        service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref=actors[-1]))
    assert len(calls) == 160 and len(registry.subscribed_actor_refs()) == 160
    assert len(repository._views) == 160
    service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref=actors[0]))
    assert len(registry.subscribed_actor_refs()) == 160
    other = _context(actors[0])
    other.binding = other.binding.model_copy(update={"session_ref": "second"})
    bindings[other.binding.session_ref] = other.binding
    service.subscribe(context=other, request=GameplayMirrorSubscriptionRequest(actor_ref=actors[0]))
    assert service.unsubscribe(context=context, actor_ref=actors[0])
    assert repository.view_for(actors[0]).actor_ref == actors[0]
    assert service.unsubscribe(context=other, actor_ref=actors[0])
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_projection_unavailable"):
        repository.view_for(actors[0])
    service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref=actors[-1]))
    assert len(registry.subscribed_actor_refs()) == len(repository._views) == 160
    assert actors[0] not in registry.subscribed_actor_refs()


def test_direct_registry_subscribe_also_enforces_per_session_cap():
    registry = GameplayMirrorSubscriptionRegistry(projection_source=_projection_source)
    for index in range(161):
        actor = f"character:resident_{index}"
        registry.grant_read_scope(session_ref="s", actor_ref=actor)
        if index == 160:
            with pytest.raises(GameplayMirrorDeliveryError, match="mirror_subscription_limit"):
                registry.subscribe(session_ref="s", actor_ref=actor)
        else:
            registry.subscribe(session_ref="s", actor_ref=actor)
    registry.drop_session(session_ref="s")
    assert registry.subscribed_actor_refs() == ()


def test_live_mirror_reads_use_owner_and_refresh_lease_time(monkeypatch):
    from threading import get_ident
    from websocket_test_support import CompletingWebSocketApp
    from fastapi.testclient import TestClient
    from app import main

    now = [100]
    monkeypatch.setattr(main, "time", lambda: now[0])
    calls = []

    def source():
        calls.append(get_ident())
        return _projection_source("actor:visible")

    tracked_app = CompletingWebSocketApp(main.component_app)

    with TestClient(tracked_app, client=("127.0.0.1", 47111)) as client:
        owner = main.runtime_execution

        def configure():
            main.gameplay_godot_projection_publisher.register_actor_source(actor_ref="actor:visible", source=source)
            return main.websocket_session_auth_service.create_trusted_local_launch_credential(
                principal_ref="player", allowed_actor_refs=("actor:visible",), issued_at=100, expires_at=110,
            )

        credential = owner.submit(configure).result(timeout=5)
        with client.websocket_connect("/ws") as socket:
            socket.send_json({"message_type": "websocket_session_bind", "payload": {
                "credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1,
            }})
            assert socket.receive_json()["payload"]["accepted"]
            assert socket.receive_json()["message_type"] == "websocket_session_bound"
            socket.send_json({"message_type": "gameplay_mirror_subscribe", "payload": {"actor_ref": "actor:visible"}})
            assert socket.receive_json()["payload"]["accepted"]
            initial = socket.receive_json()
            assert initial["message_type"] == "gameplay_mirror_delivery"
            assert initial["payload"]["actor_ref"] == "actor:visible"
            assert initial["payload"]["delivery_sequence"] == 1
            assert calls == [owner.submit(get_ident).result(timeout=5)]
            now[0] = 111
            socket.send_json({"message_type": "gameplay_mirror_snapshot_request", "payload": {"actor_ref": "actor:visible"}})
            rejected = socket.receive_json()
            assert rejected["payload"]["accepted"] is False
            assert rejected["payload"]["error_code"] == "websocket_session_renewal_required"
            assert len(calls) == 1
            # 正常断开后等真实 endpoint 清理退出，再让 TestClient 取消自己的会话任务。
            tracked_app.close_and_wait(socket)
