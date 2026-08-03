"""Connect backend session bindings to transport-neutral Godot mirror reads."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.gameplay.godot_mirror_delivery import GameplayGodotProjectionPublisher, GameplayMirrorSubscriptionRegistry
from app.services.websocket_session_auth_service import WebSocketConnectionContext


class GameplayMirrorSubscriptionRequest(BaseModel):
    """Client selects one already-granted actor; requested groups are preferences only."""

    model_config = ConfigDict(extra="forbid")

    actor_ref: str = Field(min_length=1)
    requested_state_group_ids: tuple[str, ...] = ()


class GameplayMirrorActorRequest(BaseModel):
    """Actor selection for an existing subscription; it grants no additional scope."""

    model_config = ConfigDict(extra="forbid")

    actor_ref: str = Field(min_length=1)


class GameplayMirrorSessionAccessError(ValueError):
    """Raised when a connection cannot read the requested backend projection."""


class GameplayMirrorSessionAccessService:
    """Read-only scope adapter; it cannot issue bindings or change gameplay truth."""

    def __init__(
        self,
        *,
        registry: GameplayMirrorSubscriptionRegistry,
        projection_publisher: GameplayGodotProjectionPublisher | None = None,
    ) -> None:
        self._registry = registry
        self._projection_publisher = projection_publisher

    def subscribe(
        self,
        *,
        context: WebSocketConnectionContext,
        request: GameplayMirrorSubscriptionRequest,
    ) -> dict[str, object]:
        binding = self._binding_for_actor(context, request.actor_ref)
        self._refresh_configured_source(actor_ref=request.actor_ref)
        self._registry.grant_read_scope(session_ref=binding.session_ref, actor_ref=request.actor_ref)
        _subscription, snapshot = self._registry.subscribe(session_ref=binding.session_ref, actor_ref=request.actor_ref)
        return snapshot

    def unsubscribe(self, *, context: WebSocketConnectionContext, actor_ref: str) -> bool:
        binding = self._binding_for_actor(context, actor_ref)
        return self._registry.unsubscribe(session_ref=binding.session_ref, actor_ref=actor_ref)

    def snapshot(self, *, context: WebSocketConnectionContext, actor_ref: str) -> dict[str, object]:
        binding = self._binding_for_actor(context, actor_ref)
        self._refresh_configured_source(actor_ref=actor_ref)
        snapshot = self._registry.after_commit_snapshot(
            subscription=self._subscription(binding.session_ref, actor_ref),
        )
        if snapshot is None:
            raise GameplayMirrorSessionAccessError("mirror_subscription_required")
        return snapshot

    @staticmethod
    def _subscription(session_ref: str, actor_ref: str):
        from app.gameplay.godot_mirror_delivery import GameplayMirrorSubscription

        return GameplayMirrorSubscription(session_ref=session_ref, actor_ref=actor_ref)

    @staticmethod
    def _binding_for_actor(context: WebSocketConnectionContext, actor_ref: str):
        binding = context.binding
        if binding is None:
            raise GameplayMirrorSessionAccessError("websocket_session_required")
        if actor_ref not in binding.allowed_actor_refs:
            raise GameplayMirrorSessionAccessError("mirror_scope_unauthorized")
        return binding

    def _refresh_configured_source(self, *, actor_ref: str) -> None:
        if self._projection_publisher is not None and self._projection_publisher.has_actor_source(actor_ref=actor_ref):
            self._projection_publisher.refresh_actor(actor_ref=actor_ref)
