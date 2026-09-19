import pytest

from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionPublisher, GameplayGodotProjectionRepository,
    GameplayMirrorDeliveryError, GameplayMirrorSubscriptionRegistry,
)
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.services.gameplay_mirror_session_access_service import (
    GameplayMirrorSessionAccessError,
    GameplayMirrorSessionAccessService,
    GameplayMirrorSubscriptionRequest,
)
from app.services.websocket_session_auth_service import WebSocketConnectionContext, WebSocketSessionBinding
from app.services.websocket_session_auth_service import WebSocketSessionAuthService, WebSocketSessionEnrollment


def _projection_source(actor_ref: str):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="resources", definition_version="v1", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref=actor_ref,
        enabled_group_ids=("resources",),
        group_payloads={"resources": {"value": 4}},
        source_revision_vector={actor_ref: 1},
        registry_revision="registry:v1",
        world_config_revision="world:v1",
        active_patch_set_revision="patch:v1",
    )
    return StateGroupViewProjector(
        [StateGroupConsumerViewPolicy(group_id="resources", godot_allowed_fields=("value",))]
    ).godot_view(state, allowed_group_ids=("resources",))


def _context(*actor_refs: str) -> WebSocketConnectionContext:
    return WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=10,
        binding=WebSocketSessionBinding(
            session_ref="ws_session:test",
            principal_ref="principal:test",
            allowed_actor_refs=actor_refs,
            lease_expires_at=100,
        ),
    )


def test_session_access_subscribes_and_reads_only_binding_granted_actor() -> None:
    context = _context("actor:a", "actor:b")
    service = GameplayMirrorSessionAccessService(
        registry=GameplayMirrorSubscriptionRegistry(projection_source=_projection_source),
        binding_resolver=lambda _: context.binding,
    )

    snapshot = service.subscribe(
        context=context,
        request=GameplayMirrorSubscriptionRequest(actor_ref="actor:b", requested_state_group_ids=("inventory",)),
    )

    assert snapshot["actor_ref"] == "actor:b"
    assert snapshot["groups"] == {"resources": snapshot["groups"]["resources"]}
    assert service.snapshot(context=context, actor_ref="actor:b") == snapshot
    assert service.unsubscribe(context=context, actor_ref="actor:b") is True
    with pytest.raises(GameplayMirrorSessionAccessError, match="mirror_subscription_required"):
        service.snapshot(context=context, actor_ref="actor:b")


def test_session_access_rejects_unbound_or_out_of_scope_actor() -> None:
    service = GameplayMirrorSessionAccessService(
        registry=GameplayMirrorSubscriptionRegistry(projection_source=_projection_source),
        binding_resolver=lambda _: _context("actor:a").binding,
    )

    with pytest.raises(GameplayMirrorSessionAccessError, match="websocket_session_required"):
        service.subscribe(
            context=WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=10),
            request=GameplayMirrorSubscriptionRequest(actor_ref="actor:a"),
        )
    with pytest.raises(GameplayMirrorSessionAccessError, match="mirror_scope_unauthorized"):
        service.subscribe(
            context=_context("actor:a"),
            request=GameplayMirrorSubscriptionRequest(actor_ref="actor:b"),
        )


def test_disconnect_discards_only_views_without_remaining_subscribers():
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    for actor in ("actor:a", "actor:b"):
        publisher.register_actor_source(actor_ref=actor, source=lambda actor=actor: _projection_source(actor))
    first = _context("actor:a", "actor:b")
    second = _context("actor:a")
    second.binding = second.binding.model_copy(update={"session_ref": "ws_session:other"})
    bindings = {ctx.binding.session_ref: ctx.binding for ctx in (first, second)}
    registry = GameplayMirrorSubscriptionRegistry(projection_source=repository.view_for)
    service = GameplayMirrorSessionAccessService(
        registry=registry, binding_resolver=bindings.get, projection_publisher=publisher,
    )
    for context, actor in ((first, "actor:a"), (first, "actor:b"), (second, "actor:a")):
        service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref=actor))

    service.drop_session(session_ref=first.binding.session_ref)
    assert registry.subscribed_actor_refs(session_ref=first.binding.session_ref) == ()
    assert repository.view_for("actor:a").actor_ref == "actor:a"
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_projection_unavailable"):
        repository.view_for("actor:b")
    service.drop_session(session_ref=second.binding.session_ref)
    service.drop_session(session_ref=second.binding.session_ref)
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_projection_unavailable"):
        repository.view_for("actor:a")
    assert all(publisher.has_actor_source(actor_ref=actor) for actor in ("actor:a", "actor:b"))


@pytest.mark.parametrize("failure", ["revoked", "expired", "epoch", "scope"])
def test_live_binding_is_checked_before_every_mirror_read(failure):
    auth = WebSocketSessionAuthService()
    credential = auth.create_trusted_local_launch_credential(
        principal_ref="p", allowed_actor_refs=("actor:a",), issued_at=10, expires_at=20,
    )
    binding = auth.bind_session(WebSocketSessionEnrollment(
        credential_kind="trusted_local_launch", credential=credential, protocol_version=1,
    ), remote_host="127.0.0.1", now=11).binding
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11, binding=binding)
    calls = []

    def source(actor):
        calls.append(actor)
        return _projection_source(actor)

    registry = GameplayMirrorSubscriptionRegistry(projection_source=source)
    service = GameplayMirrorSessionAccessService(registry=registry, binding_resolver=auth.resolve_binding)
    request = GameplayMirrorSubscriptionRequest(actor_ref="actor:a")
    service.subscribe(context=context, request=request)
    before = len(calls)
    if failure == "revoked":
        auth.revoke_session(binding.session_ref, reason_code="test", now=12)
    elif failure == "expired":
        context.observed_at = 21
    else:
        auth._bindings[binding.session_ref] = binding.model_copy(update=(
            {"connection_epoch": binding.connection_epoch + 1} if failure == "epoch" else {"allowed_actor_refs": ("actor:b",)}
        ))
    for operation in (
        lambda: service.subscribe(context=context, request=request),
        lambda: service.snapshot(context=context, actor_ref="actor:a"),
        lambda: service.unsubscribe(context=context, actor_ref="actor:a"),
    ):
        with pytest.raises(GameplayMirrorSessionAccessError):
            operation()
    assert len(calls) == before
    if failure == "scope":
        with pytest.raises(GameplayMirrorSessionAccessError, match="mirror_scope_unauthorized"):
            service.subscribe(context=context, request=GameplayMirrorSubscriptionRequest(actor_ref="actor:b"))
