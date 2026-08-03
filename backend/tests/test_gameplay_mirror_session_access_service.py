import pytest

from app.gameplay.godot_mirror_delivery import GameplayMirrorSubscriptionRegistry
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.services.gameplay_mirror_session_access_service import (
    GameplayMirrorSessionAccessError,
    GameplayMirrorSessionAccessService,
    GameplayMirrorSubscriptionRequest,
)
from app.services.websocket_session_auth_service import WebSocketConnectionContext, WebSocketSessionBinding


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
        ),
    )


def test_session_access_subscribes_and_reads_only_binding_granted_actor() -> None:
    service = GameplayMirrorSessionAccessService(
        registry=GameplayMirrorSubscriptionRegistry(projection_source=_projection_source),
    )
    context = _context("actor:a", "actor:b")

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
