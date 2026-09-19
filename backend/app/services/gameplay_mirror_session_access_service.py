"""Connect backend session bindings to transport-neutral Godot mirror reads."""

from __future__ import annotations

from collections.abc import Callable
from pydantic import BaseModel, ConfigDict, Field

from app.gameplay.godot_mirror_delivery import GameplayGodotProjectionPublisher, GameplayMirrorSubscriptionRegistry
from app.services.websocket_session_auth_service import WebSocketConnectionContext, WebSocketSessionBinding


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
        binding_resolver: Callable[[str], WebSocketSessionBinding | None],
        projection_publisher: GameplayGodotProjectionPublisher | None = None,
    ) -> None:
        self._registry = registry
        self._binding_resolver = binding_resolver
        self._projection_publisher = projection_publisher

    def subscribe(
        self,
        *,
        context: WebSocketConnectionContext,
        request: GameplayMirrorSubscriptionRequest,
    ) -> dict[str, object]:
        binding = self._binding_for_actor(context, request.actor_ref)
        self._registry.ensure_can_subscribe(session_ref=binding.session_ref, actor_ref=request.actor_ref)
        self._refresh_configured_source(actor_ref=request.actor_ref)
        self._registry.grant_read_scope(session_ref=binding.session_ref, actor_ref=request.actor_ref)
        _subscription, snapshot = self._registry.subscribe(session_ref=binding.session_ref, actor_ref=request.actor_ref)
        return snapshot

    def unsubscribe(self, *, context: WebSocketConnectionContext, actor_ref: str) -> bool:
        binding = self._binding_for_actor(context, actor_ref)
        removed = self._registry.unsubscribe(session_ref=binding.session_ref, actor_ref=actor_ref)
        if removed and self._projection_publisher is not None and not self._registry.subscribed_session_refs(actor_ref=actor_ref):
            self._projection_publisher.discard_actor_view(actor_ref=actor_ref)
        return removed

    def snapshot(self, *, context: WebSocketConnectionContext, actor_ref: str) -> dict[str, object]:
        binding = self._binding_for_actor(context, actor_ref)
        if not self._registry.is_subscribed(session_ref=binding.session_ref, actor_ref=actor_ref):
            raise GameplayMirrorSessionAccessError("mirror_subscription_required")
        self._refresh_configured_source(actor_ref=actor_ref)
        snapshot = self._registry.after_commit_snapshot(
            subscription=self._subscription(binding.session_ref, actor_ref),
        )
        if snapshot is None:
            raise GameplayMirrorSessionAccessError("mirror_subscription_required")
        return snapshot

    def drop_session(self, *, session_ref: str) -> None:
        """断连释放失去最后订阅的视图，保留共享视图和来源配置。"""
        actors = self._registry.subscribed_actor_refs(session_ref=session_ref)
        self._registry.drop_session(session_ref=session_ref)
        if self._projection_publisher is not None:
            for actor_ref in actors:
                if not self._registry.subscribed_session_refs(actor_ref=actor_ref):
                    self._projection_publisher.discard_actor_view(actor_ref=actor_ref)

    @staticmethod
    def _subscription(session_ref: str, actor_ref: str):
        from app.gameplay.godot_mirror_delivery import GameplayMirrorSubscription

        return GameplayMirrorSubscription(session_ref=session_ref, actor_ref=actor_ref)

    def _binding_for_actor(self, context: WebSocketConnectionContext, actor_ref: str):
        binding = context.binding
        if binding is None:
            raise GameplayMirrorSessionAccessError("websocket_session_required")
        current = self._binding_resolver(binding.session_ref)
        # observed_at 必须由生产 owner 在处理该次请求时刷新；离线工具可显式使用模拟时间。
        if (current is None or current.binding_state != "bound_active" or binding.binding_state != "bound_active"
                or current.session_ref != binding.session_ref or current.connection_epoch != binding.connection_epoch
                or current.principal_ref != binding.principal_ref
                or min(current.lease_expires_at, binding.lease_expires_at) < context.observed_at):
            raise GameplayMirrorSessionAccessError("websocket_session_renewal_required")
        if actor_ref not in binding.allowed_actor_refs or actor_ref not in current.allowed_actor_refs:
            raise GameplayMirrorSessionAccessError("mirror_scope_unauthorized")
        return current

    def _refresh_configured_source(self, *, actor_ref: str) -> None:
        if self._projection_publisher is not None and self._projection_publisher.has_actor_source(actor_ref=actor_ref):
            self._projection_publisher.refresh_actor(actor_ref=actor_ref)
