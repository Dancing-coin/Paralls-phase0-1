"""Backend-owned session scope and snapshot delivery preparation for Godot mirrors."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Callable

from app.gameplay.godot_mirror_projection import project_godot_runtime_state
from app.gameplay.models import AtomicEventBatch
from app.gameplay.state_group_views import CharacterGameRuntimeStateView


class GameplayMirrorDeliveryError(ValueError):
    """Raised before an unauthorized session can receive a Godot projection."""


class GameplayMirrorConnectionError(ValueError):
    """Raised when a committed presentation refresh has no usable local transport."""


class GameplayGodotProjectionRepository:
    """Backend-internal source of already policy-filtered actor mirror views."""

    def __init__(self) -> None:
        self._views: dict[str, CharacterGameRuntimeStateView] = {}

    def publish(self, view: CharacterGameRuntimeStateView) -> None:
        if view.consumer != "godot" or not view.actor_ref:
            raise GameplayMirrorDeliveryError("godot_projection_required")
        self._views[view.actor_ref] = view

    def remove(self, actor_ref: str) -> None:
        self._views.pop(actor_ref, None)

    def view_for(self, actor_ref: str) -> CharacterGameRuntimeStateView:
        view = self._views.get(actor_ref)
        if view is None:
            raise GameplayMirrorDeliveryError("mirror_projection_unavailable")
        return view


class GameplayMirrorConnectionRegistry:
    """Connection-local delivery callbacks keyed by opaque backend session references."""

    def __init__(self) -> None:
        self._connections: dict[str, tuple[str, Callable[[dict[str, object]], None]]] = {}

    def register(
        self,
        *,
        session_ref: str,
        connection_ref: str,
        deliver: Callable[[dict[str, object]], None],
    ) -> None:
        if not session_ref or not connection_ref:
            raise GameplayMirrorConnectionError("mirror_connection_invalid")
        self._connections[session_ref] = (connection_ref, deliver)

    def unregister(self, *, session_ref: str, connection_ref: str) -> bool:
        connection = self._connections.get(session_ref)
        if connection is None or connection[0] != connection_ref:
            return False
        del self._connections[session_ref]
        return True

    def deliver(self, session_ref: str, payload: dict[str, object]) -> None:
        connection = self._connections.get(session_ref)
        if connection is None:
            raise GameplayMirrorConnectionError("mirror_connection_unavailable")
        connection[1](payload)


@dataclass(frozen=True)
class GameplayGodotProjectionRefreshResult:
    published_actor_refs: tuple[str, ...]
    unavailable_actor_refs: tuple[str, ...]


class GameplayGodotProjectionPublisher:
    """Refreshes backend-owned filtered views before the mirror observer fans out."""

    def __init__(self, *, repository: GameplayGodotProjectionRepository) -> None:
        self._repository = repository
        self._sources: dict[str, Callable[[], CharacterGameRuntimeStateView]] = {}

    def register_actor_source(self, *, actor_ref: str, source: Callable[[], CharacterGameRuntimeStateView]) -> None:
        if not actor_ref:
            raise GameplayMirrorDeliveryError("mirror_projection_actor_required")
        self._sources[actor_ref] = source

    def unregister_actor_source(self, *, actor_ref: str) -> None:
        self._sources.pop(actor_ref, None)
        self._repository.remove(actor_ref)

    def has_actor_source(self, *, actor_ref: str) -> bool:
        return actor_ref in self._sources

    def refresh_actor(self, *, actor_ref: str) -> CharacterGameRuntimeStateView:
        """Refresh one explicit backend source for an authorized snapshot request."""

        source = self._sources.get(actor_ref)
        if source is None:
            self._repository.remove(actor_ref)
            raise GameplayMirrorDeliveryError("mirror_projection_unavailable")
        try:
            view = source()
            if view.actor_ref != actor_ref:
                raise GameplayMirrorDeliveryError("mirror_projection_actor_mismatch")
            self._repository.publish(view)
            return view
        except GameplayMirrorDeliveryError:
            self._repository.remove(actor_ref)
            raise
        except Exception as exc:
            self._repository.remove(actor_ref)
            raise GameplayMirrorDeliveryError("mirror_projection_unavailable") from exc

    def after_transaction_dispatched(self, transaction: AtomicEventBatch) -> GameplayGodotProjectionRefreshResult:
        actor_refs = tuple(
            dict.fromkeys(
                actor_ref
                for hint in transaction.projection_refresh_hints
                if hint.projection_id == "godot_mirror"
                for actor_ref in hint.actor_refs
                if actor_ref
            )
        )
        published: list[str] = []
        unavailable: list[str] = []
        for actor_ref in actor_refs:
            try:
                self.refresh_actor(actor_ref=actor_ref)
            except Exception:
                unavailable.append(actor_ref)
                continue
            published.append(actor_ref)
        return GameplayGodotProjectionRefreshResult(tuple(published), tuple(unavailable))


@dataclass(frozen=True)
class GameplayMirrorSubscription:
    session_ref: str
    actor_ref: str


@dataclass(frozen=True)
class GameplayMirrorDelivery:
    """A prepared presentation snapshot for one backend-authorized scope."""

    subscription: GameplayMirrorSubscription
    payload: dict[str, object]


@dataclass(frozen=True)
class GameplayMirrorDeliveryResult:
    delivered_session_refs: tuple[str, ...]
    failed_session_refs: tuple[str, ...]


class GameplayMirrorSubscriptionRegistry:
    """Stores backend-granted read scopes; it is not a client command endpoint."""

    def __init__(self, *, projection_source: Callable[[str], CharacterGameRuntimeStateView]) -> None:
        self._projection_source = projection_source
        self._grants: set[tuple[str, str]] = set()
        self._subscriptions: set[tuple[str, str]] = set()

    def grant_read_scope(self, *, session_ref: str, actor_ref: str) -> None:
        if not session_ref or not actor_ref:
            raise GameplayMirrorDeliveryError("mirror_scope_invalid")
        self._grants.add((session_ref, actor_ref))

    def subscribe(self, *, session_ref: str, actor_ref: str) -> tuple[GameplayMirrorSubscription, dict[str, object]]:
        scope = (session_ref, actor_ref)
        if scope not in self._grants:
            raise GameplayMirrorDeliveryError("mirror_scope_unauthorized")
        view = self._projection_source(actor_ref)
        if view.actor_ref != actor_ref:
            raise GameplayMirrorDeliveryError("mirror_projection_actor_mismatch")
        self._subscriptions.add(scope)
        return GameplayMirrorSubscription(session_ref=session_ref, actor_ref=actor_ref), project_godot_runtime_state(view)

    def unsubscribe(self, *, session_ref: str, actor_ref: str) -> bool:
        """Remove a read subscription without changing the underlying server grant."""

        scope = (session_ref, actor_ref)
        if scope not in self._grants:
            raise GameplayMirrorDeliveryError("mirror_scope_unauthorized")
        if scope not in self._subscriptions:
            return False
        self._subscriptions.remove(scope)
        return True

    def after_commit_snapshot(self, subscription: GameplayMirrorSubscription) -> dict[str, object] | None:
        scope = (subscription.session_ref, subscription.actor_ref)
        if scope not in self._subscriptions:
            return None
        view = self._projection_source(subscription.actor_ref)
        if view.actor_ref != subscription.actor_ref:
            raise GameplayMirrorDeliveryError("mirror_projection_actor_mismatch")
        return project_godot_runtime_state(view)

    def after_commit_snapshots(self, *, affected_actor_refs: Iterable[str]) -> list[GameplayMirrorDelivery]:
        """Prepare only subscribed, backend-granted actor snapshots after a known commit."""

        affected = {actor_ref for actor_ref in affected_actor_refs if actor_ref}
        deliveries: list[GameplayMirrorDelivery] = []
        for session_ref, actor_ref in sorted(self._subscriptions):
            if actor_ref not in affected:
                continue
            subscription = GameplayMirrorSubscription(session_ref=session_ref, actor_ref=actor_ref)
            payload = self.after_commit_snapshot(subscription)
            if payload is not None:
                deliveries.append(GameplayMirrorDelivery(subscription=subscription, payload=payload))
        return deliveries


class GameplayMirrorAfterCommitDelivery:
    """Transport-neutral fanout invoked only by a committed-outbox integration."""

    def __init__(
        self,
        *,
        registry: GameplayMirrorSubscriptionRegistry,
        deliver: Callable[[str, dict[str, object]], None],
    ) -> None:
        self._registry = registry
        self._deliver = deliver

    def deliver_for_committed_actor_refs(self, *, affected_actor_refs: Iterable[str]) -> GameplayMirrorDeliveryResult:
        delivered_session_refs: list[str] = []
        failed_session_refs: list[str] = []
        for delivery in self._registry.after_commit_snapshots(affected_actor_refs=affected_actor_refs):
            try:
                self._deliver(delivery.subscription.session_ref, delivery.payload)
            except Exception:
                # Delivery cannot reverse or retry the already committed authority batch.
                failed_session_refs.append(delivery.subscription.session_ref)
                continue
            delivered_session_refs.append(delivery.subscription.session_ref)
        return GameplayMirrorDeliveryResult(
            delivered_session_refs=tuple(delivered_session_refs),
            failed_session_refs=tuple(failed_session_refs),
        )


class GameplayMirrorOutboxRefreshConsumer:
    """Consumes only explicit Godot mirror refresh hints after full outbox delivery."""

    def __init__(self, *, delivery: GameplayMirrorAfterCommitDelivery) -> None:
        self._delivery = delivery
        self.results: list[GameplayMirrorDeliveryResult] = []

    def after_transaction_dispatched(self, transaction: AtomicEventBatch) -> None:
        actor_refs = tuple(
            actor_ref
            for hint in transaction.projection_refresh_hints
            if hint.projection_id == "godot_mirror"
            for actor_ref in hint.actor_refs
        )
        if not actor_refs:
            return
        self.results.append(self._delivery.deliver_for_committed_actor_refs(affected_actor_refs=actor_refs))
