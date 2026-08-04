"""Backend-owned session scope and snapshot delivery preparation for Godot mirrors."""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from collections.abc import Iterable
from types import MappingProxyType
from typing import Callable

from app.gameplay.godot_mirror_projection import project_godot_runtime_state
from app.gameplay.models import AtomicEventBatch
from app.gameplay.runtime_state import CharacterGameRuntimeState, StateGroupProjectionEnvelope
from app.gameplay.state_group_sync import CharacterGameRuntimeDelta, CharacterGameRuntimeSnapshot, StateGroupSyncService
from app.gameplay.state_group_views import CharacterGameRuntimeStateView
from app.ws_protocol import GameplayMirrorDeliveryEnvelope, GameplayMirrorReceipt


class GameplayMirrorDeliveryError(ValueError):
    """Raised before an unauthorized session can receive a Godot projection."""


class GameplayMirrorConnectionError(ValueError):
    """Raised when a committed presentation refresh has no usable local transport."""


class GameplayMirrorOutboundQueue:
    """Bounded per-connection presentation queue with latest-only dirty actor recovery."""

    def __init__(self, *, projection_capacity: int, control_capacity: int, dirty_actor_limit: int) -> None:
        if min(projection_capacity, control_capacity, dirty_actor_limit) < 1:
            raise GameplayMirrorDeliveryError("mirror_delivery_limits_invalid")
        self._projection_capacity = projection_capacity
        self._control_capacity = control_capacity
        self._dirty_actor_limit = dirty_actor_limit
        self._projections: deque[dict[str, object]] = deque()
        self._controls: deque[dict[str, object]] = deque()
        self._dirty_by_actor: dict[str, dict[str, object]] = {}

    @property
    def dirty_actor_count(self) -> int:
        return len(self._dirty_by_actor)

    def enqueue_projection(self, payload: dict[str, object]) -> bool:
        if len(self._projections) < self._projection_capacity:
            self._projections.append(payload)
            return True
        actor_ref = _delivery_actor_ref(payload)
        if actor_ref not in self._dirty_by_actor and len(self._dirty_by_actor) >= self._dirty_actor_limit:
            raise GameplayMirrorConnectionError("mirror_backpressure")
        self._dirty_by_actor[actor_ref] = payload
        return False

    def pop_next(self) -> dict[str, object] | None:
        if self._controls:
            control = self._controls.popleft()
            actor_ref = str(control["payload"]["actor_ref"])
            recovered = self._dirty_by_actor.pop(actor_ref, None)
            if recovered is not None:
                self._projections.append(recovered)
            return control
        if not self._projections:
            return None
        projection = self._projections.popleft()
        if self._dirty_by_actor and not self._controls:
            actor_ref = next(iter(self._dirty_by_actor))
            self._controls.append(
                {
                    "message_type": "gameplay_mirror_resync_required",
                    "payload": {"actor_ref": actor_ref, "reason_code": "mirror_backpressure"},
                }
            )
        return projection

    def clear(self) -> None:
        self._projections.clear()
        self._controls.clear()
        self._dirty_by_actor.clear()


class GameplayGodotMirrorSyncAdapter:
    """Adapts already-filtered Godot views to the existing exact-base sync contract."""

    schema_capabilities = ("gameplay_runtime_state.godot.v1",)

    def __init__(self, *, sync_service: StateGroupSyncService | None = None) -> None:
        self._sync = sync_service or StateGroupSyncService()

    def snapshot(self, view: CharacterGameRuntimeStateView) -> CharacterGameRuntimeSnapshot:
        return self._sync.snapshot(
            self._filtered_runtime_state(view),
            schema_capabilities=self.schema_capabilities,
        )

    def delta(
        self,
        base: CharacterGameRuntimeSnapshot,
        target: CharacterGameRuntimeSnapshot,
        *,
        confirmed_prediction_ids: tuple[str, ...] = (),
        rejected_predictions: tuple[str, ...] = (),
    ) -> CharacterGameRuntimeDelta:
        return self._sync.delta(
            base,
            target,
            confirmed_prediction_ids=confirmed_prediction_ids,
            rejected_predictions=rejected_predictions,
        )

    def apply_delta(
        self,
        base: CharacterGameRuntimeSnapshot,
        delta: CharacterGameRuntimeDelta,
    ) -> CharacterGameRuntimeSnapshot:
        return self._sync.apply_delta(
            base,
            delta,
            supported_schema_capabilities=self.schema_capabilities,
        )

    @staticmethod
    def snapshot_payload(snapshot: CharacterGameRuntimeSnapshot) -> dict[str, object]:
        """The complete disposable payload is rebuilt from the filtered sync snapshot."""

        return {
            "message_type": "gameplay_runtime_state_projection",
            "projection_kind": "gameplay_runtime_state.godot.v1",
            "actor_ref": snapshot.actor_ref,
            "facade_revision": snapshot.facade_revision,
            "source_revision_vector": dict(snapshot.source_revision_vector),
            "schema_capabilities": list(snapshot.schema_capabilities),
            "enabled_state_groups": list(snapshot.enabled_state_groups),
            "snapshot_checksum": snapshot.snapshot_checksum,
            "groups": {
                group_id: {
                    "projection_revision": envelope.projection_revision,
                    "payload": _json_ready(envelope.payload),
                }
                for group_id, envelope in snapshot.groups.items()
            },
        }

    @staticmethod
    def delta_payload(
        base: CharacterGameRuntimeSnapshot,
        delta: CharacterGameRuntimeDelta,
    ) -> dict[str, object]:
        """Serialize a filtered exact-base delta without consulting a client cache."""

        return {
            "message_type": "gameplay_runtime_state_projection",
            "projection_kind": "gameplay_runtime_state.godot.v1",
            "actor_ref": delta.actor_ref,
            "facade_revision": delta.target_facade_revision,
            "base_facade_revision": delta.base_facade_revision,
            "base_snapshot_checksum": base.snapshot_checksum,
            "target_snapshot_checksum": delta.target_snapshot_checksum,
            "source_revision_vector": dict(delta.target_source_revision_vector),
            "schema_capabilities": list(delta.target_schema_capabilities),
            "enabled_state_groups": list(delta.target_enabled_state_groups),
            "removed_group_ids": list(delta.removed_group_ids),
            "confirmed_prediction_ids": list(delta.confirmed_prediction_ids),
            "rejected_predictions": list(delta.rejected_predictions),
            "groups": {
                group_id: {
                    "projection_revision": envelope.projection_revision,
                    "payload": _json_ready(envelope.payload),
                }
                for group_id, envelope in delta.changed_group_envelopes.items()
            },
        }

    @staticmethod
    def _filtered_runtime_state(view: CharacterGameRuntimeStateView) -> CharacterGameRuntimeState:
        if view.consumer != "godot":
            raise GameplayMirrorDeliveryError("godot_view_required")
        groups = {
            group_id: StateGroupProjectionEnvelope(
                group_id=envelope.group_id,
                definition_version=envelope.definition_version,
                projection_schema_version=envelope.projection_schema_version,
                projection_revision=envelope.projection_revision,
                source_revision_vector=envelope.source_revision_vector,
                payload=envelope.payload,
            )
            for group_id, envelope in view.groups.items()
        }
        return CharacterGameRuntimeState(
            actor_ref=view.actor_ref,
            facade_schema_version=1,
            facade_revision=view.source_facade_revision,
            source_revision_vector=view.source_revision_vector,
            registry_revision="filtered_godot_view",
            world_config_revision="filtered_godot_view",
            active_patch_set_revision="filtered_godot_view",
            enabled_state_groups=tuple(groups),
            groups=MappingProxyType(groups),
            snapshot_checksum="",
        )


class GameplayMirrorReceiptLedger:
    """A bounded connection-local record of sent presentation sequences."""

    def __init__(self, *, connection_epoch: int, receipt_window: int) -> None:
        if connection_epoch < 1 or receipt_window < 1:
            raise GameplayMirrorDeliveryError("mirror_receipt_ledger_invalid")
        self._connection_epoch = connection_epoch
        self._sent_sequences: deque[int] = deque(maxlen=receipt_window)
        self._last_sent_sequence = 0

    def record_sent(self, delivery_sequence: int) -> None:
        if delivery_sequence < 1 or delivery_sequence <= self._last_sent_sequence:
            raise GameplayMirrorDeliveryError("mirror_sequence_invalid")
        self._sent_sequences.append(delivery_sequence)
        self._last_sent_sequence = delivery_sequence

    def acknowledge(self, receipt) -> bool:
        if receipt.connection_epoch != self._connection_epoch:
            raise GameplayMirrorDeliveryError("mirror_receipt_stale_epoch")
        if receipt.delivery_sequence > self._last_sent_sequence:
            raise GameplayMirrorDeliveryError("mirror_receipt_unknown")
        if not self._sent_sequences or receipt.delivery_sequence < self._sent_sequences[0]:
            raise GameplayMirrorDeliveryError("mirror_receipt_out_of_window")
        if receipt.delivery_sequence not in self._sent_sequences:
            raise GameplayMirrorDeliveryError("mirror_receipt_unknown")
        return True


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
        self._connections: dict[str, _GameplayMirrorConnection] = {}

    def register(
        self,
        *,
        session_ref: str,
        connection_ref: str,
        connection_epoch: int = 1,
        deliver: Callable[[dict[str, object]], None],
    ) -> None:
        if not session_ref or not connection_ref:
            raise GameplayMirrorConnectionError("mirror_connection_invalid")
        self._connections[session_ref] = _GameplayMirrorConnection(
            connection_ref=connection_ref,
            connection_epoch=connection_epoch,
            deliver=deliver,
            receipt_ledger=GameplayMirrorReceiptLedger(connection_epoch=connection_epoch, receipt_window=32),
        )

    def unregister(self, *, session_ref: str, connection_ref: str) -> bool:
        connection = self._connections.get(session_ref)
        if connection is None or connection.connection_ref != connection_ref:
            return False
        del self._connections[session_ref]
        return True

    def connection_ref_for(self, *, session_ref: str) -> str | None:
        connection = self._connections.get(session_ref)
        return None if connection is None else connection.connection_ref

    def deliver(self, session_ref: str, payload: dict[str, object]) -> None:
        connection = self._connections.get(session_ref)
        if connection is None:
            raise GameplayMirrorConnectionError("mirror_connection_unavailable")
        sequence = connection.next_delivery_sequence
        envelope = GameplayMirrorDeliveryEnvelope(
            delivery_kind="snapshot",
            connection_epoch=connection.connection_epoch,
            delivery_sequence=sequence,
            actor_ref=str(payload.get("actor_ref", "")),
            projection_schema=str(payload.get("projection_kind", "")),
            facade_revision=str(payload.get("facade_revision", "")),
            source_revision_vector=dict(payload.get("source_revision_vector", {})),
            payload=payload,
        )
        connection.receipt_ledger.record_sent(sequence)
        connection.next_delivery_sequence += 1
        connection.deliver({"message_type": "gameplay_mirror_delivery", "payload": envelope.model_dump(mode="json")})

    def acknowledge(self, *, session_ref: str, receipt: GameplayMirrorReceipt) -> bool:
        connection = self._connections.get(session_ref)
        if connection is None:
            raise GameplayMirrorConnectionError("mirror_connection_unavailable")
        return connection.receipt_ledger.acknowledge(receipt)

    def deliver_prediction_resolutions(
        self,
        *,
        session_ref: str,
        actor_ref: str,
        facade_revision: str,
        resolutions: tuple,
    ) -> None:
        """Deliver only server-authored resolution metadata after a settled outcome."""

        connection = self._connections.get(session_ref)
        if connection is None:
            raise GameplayMirrorConnectionError("mirror_connection_unavailable")
        if not actor_ref or not facade_revision or not resolutions:
            raise GameplayMirrorConnectionError("mirror_prediction_resolution_invalid")
        sequence = connection.next_delivery_sequence
        envelope = GameplayMirrorDeliveryEnvelope(
            delivery_kind="prediction",
            connection_epoch=connection.connection_epoch,
            delivery_sequence=sequence,
            actor_ref=actor_ref,
            projection_schema="gameplay_runtime_state.godot.v1",
            facade_revision=facade_revision,
            payload={},
            prediction_resolutions=tuple(resolutions),
        )
        connection.receipt_ledger.record_sent(sequence)
        connection.next_delivery_sequence += 1
        connection.deliver({"message_type": "gameplay_mirror_delivery", "payload": envelope.model_dump(mode="json")})


@dataclass
class _GameplayMirrorConnection:
    connection_ref: str
    connection_epoch: int
    deliver: Callable[[dict[str, object]], None]
    receipt_ledger: GameplayMirrorReceiptLedger
    next_delivery_sequence: int = 1


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

    def __init__(
        self,
        *,
        projection_source: Callable[[str], CharacterGameRuntimeStateView],
        sync_adapter: GameplayGodotMirrorSyncAdapter | None = None,
    ) -> None:
        self._projection_source = projection_source
        self._sync_adapter = sync_adapter or GameplayGodotMirrorSyncAdapter()
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
        return GameplayMirrorSubscription(session_ref=session_ref, actor_ref=actor_ref), self._snapshot_payload(view)

    def unsubscribe(self, *, session_ref: str, actor_ref: str) -> bool:
        """Remove a read subscription without changing the underlying server grant."""

        scope = (session_ref, actor_ref)
        if scope not in self._grants:
            raise GameplayMirrorDeliveryError("mirror_scope_unauthorized")
        if scope not in self._subscriptions:
            return False
        self._subscriptions.remove(scope)
        return True

    def subscribed_session_refs(self, *, actor_ref: str) -> tuple[str, ...]:
        """Return only already-authorized, active subscribers for a server-selected actor."""

        if not actor_ref:
            return ()
        return tuple(sorted(session_ref for session_ref, subscribed_actor_ref in self._subscriptions if subscribed_actor_ref == actor_ref))

    def drop_session(self, *, session_ref: str) -> None:
        """Drop only connection-scoped mirror grants and subscriptions for one binding."""

        self._grants = {scope for scope in self._grants if scope[0] != session_ref}
        self._subscriptions = {scope for scope in self._subscriptions if scope[0] != session_ref}

    def after_commit_snapshot(self, subscription: GameplayMirrorSubscription) -> dict[str, object] | None:
        scope = (subscription.session_ref, subscription.actor_ref)
        if scope not in self._subscriptions:
            return None
        view = self._projection_source(subscription.actor_ref)
        if view.actor_ref != subscription.actor_ref:
            raise GameplayMirrorDeliveryError("mirror_projection_actor_mismatch")
        return self._snapshot_payload(view)

    def _snapshot_payload(self, view: CharacterGameRuntimeStateView) -> dict[str, object]:
        return self._sync_adapter.snapshot_payload(self._sync_adapter.snapshot(view))

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
        on_delivery_failure: Callable[[str], None] | None = None,
    ) -> None:
        self._registry = registry
        self._deliver = deliver
        self._on_delivery_failure = on_delivery_failure

    def deliver_for_committed_actor_refs(self, *, affected_actor_refs: Iterable[str]) -> GameplayMirrorDeliveryResult:
        delivered_session_refs: list[str] = []
        failed_session_refs: list[str] = []
        for delivery in self._registry.after_commit_snapshots(affected_actor_refs=affected_actor_refs):
            try:
                self._deliver(delivery.subscription.session_ref, delivery.payload)
            except Exception:
                # Delivery cannot reverse or retry the already committed authority batch.
                failed_session_refs.append(delivery.subscription.session_ref)
                if self._on_delivery_failure is not None:
                    try:
                        self._on_delivery_failure(delivery.subscription.session_ref)
                    except Exception:
                        pass
                # A failed transport must not retain read scope while awaiting a
                # fresh, backend-issued enrollment.
                self._registry.drop_session(session_ref=delivery.subscription.session_ref)
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


def _json_ready(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if hasattr(value, "items"):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def _delivery_actor_ref(payload: dict[str, object]) -> str:
    outer = payload.get("payload")
    if isinstance(outer, dict):
        actor_ref = str(outer.get("actor_ref", ""))
        if actor_ref:
            return actor_ref
    raise GameplayMirrorConnectionError("mirror_delivery_actor_required")
