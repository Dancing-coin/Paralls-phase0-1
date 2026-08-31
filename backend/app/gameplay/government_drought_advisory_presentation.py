"""Fixed project/jurisdiction presentation of committed Government drought advisories."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from app.gameplay.models import AtomicEventBatch
from app.gameplay.organization_government_runtime import GovernmentAuthority, GovernmentDroughtAdvisoryView
from app.services.websocket_session_auth_service import WebSocketConnectionContext


_TOPIC = "world.government.drought_advisory_projection"
_EVENT_TYPE = "gameplay.government.drought_advisory_issued"
_PROJECTION_KIND = "government_drought_advisory.project.v1"


class GovernmentDroughtAdvisoryPresentationError(ValueError):
    """Raised before a fixed advisory projection can be exposed to a session."""


class GovernmentDroughtAdvisoryPresentationView(BaseModel):
    """Transport-safe, read-only subset of the committed Government projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    projection_kind: str = Field(default=_PROJECTION_KIND, frozen=True)
    jurisdiction_ref: str = Field(min_length=1)
    advisory_refs: tuple[str, ...]
    source_revision_vector: dict[str, int]
    projection_hash: str = Field(min_length=1)


class GovernmentDroughtAdvisorySubscriptionRequest(BaseModel):
    """Client selection only; jurisdiction authorization remains in the binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jurisdiction_ref: str = Field(min_length=1)


class GovernmentDroughtAdvisoryPresentationService:
    """Fixed read scope and delivery hook; it cannot alter Government truth."""

    def __init__(
        self,
        *,
        government: GovernmentAuthority,
        deliver: Callable[[str, dict[str, object]], None],
    ) -> None:
        self._government = government
        self._deliver = deliver
        self._subscriptions: set[tuple[str, str]] = set()

    def subscribe(
        self, *, context: WebSocketConnectionContext, jurisdiction_ref: str
    ) -> dict[str, object]:
        binding = self._binding_for_jurisdiction(context=context, jurisdiction_ref=jurisdiction_ref)
        snapshot = self._snapshot(jurisdiction_ref=jurisdiction_ref)
        self._subscriptions.add((binding.session_ref, jurisdiction_ref))
        return snapshot

    def snapshot(
        self, *, context: WebSocketConnectionContext, jurisdiction_ref: str
    ) -> dict[str, object]:
        binding = self._binding_for_jurisdiction(context=context, jurisdiction_ref=jurisdiction_ref)
        if (binding.session_ref, jurisdiction_ref) not in self._subscriptions:
            raise GovernmentDroughtAdvisoryPresentationError("government_drought_advisory_subscription_required")
        return self._snapshot(jurisdiction_ref=jurisdiction_ref)

    def drop_session(self, *, session_ref: str) -> None:
        self._subscriptions = {
            scope for scope in self._subscriptions if scope[0] != session_ref
        }

    def subscribed_jurisdictions_for(self, *, session_ref: str) -> tuple[str, ...]:
        return tuple(sorted(jurisdiction_ref for subscribed_session_ref, jurisdiction_ref in self._subscriptions if subscribed_session_ref == session_ref))

    def after_transaction_dispatched(self, transaction: AtomicEventBatch) -> None:
        jurisdictions: set[str] = set()
        for entry in transaction.outbox_entries:
            jurisdiction_ref = entry.payload_projection.get("jurisdiction_ref")
            if (
                entry.topic != _TOPIC
                or entry.audience != "project"
                or entry.payload_projection.get("event_type") != _EVENT_TYPE
                or not isinstance(jurisdiction_ref, str)
                or not jurisdiction_ref
                or not self._government.is_project_visible_drought_advisory_event(
                    event_id=entry.event_id,
                    jurisdiction_ref=jurisdiction_ref,
                )
            ):
                continue
            jurisdictions.add(jurisdiction_ref)
        for jurisdiction_ref in sorted(jurisdictions):
            try:
                snapshot = self._snapshot(jurisdiction_ref=jurisdiction_ref)
            except GovernmentDroughtAdvisoryPresentationError:
                continue
            for session_ref, subscribed_jurisdiction_ref in tuple(sorted(self._subscriptions)):
                if subscribed_jurisdiction_ref != jurisdiction_ref:
                    continue
                try:
                    self._deliver(session_ref, snapshot)
                except Exception:
                    # Delivery failures cannot alter an already committed advisory.
                    self.drop_session(session_ref=session_ref)

    @staticmethod
    def _binding_for_jurisdiction(
        *, context: WebSocketConnectionContext, jurisdiction_ref: str
    ):
        binding = context.binding
        if binding is None:
            raise GovernmentDroughtAdvisoryPresentationError("websocket_session_required")
        if not jurisdiction_ref or jurisdiction_ref not in binding.allowed_government_drought_advisory_jurisdiction_refs:
            raise GovernmentDroughtAdvisoryPresentationError("government_drought_advisory_scope_unauthorized")
        return binding

    def _snapshot(self, *, jurisdiction_ref: str) -> dict[str, object]:
        try:
            view = self._government.drought_advisory_view_for(jurisdiction_ref=jurisdiction_ref)
        except Exception as exc:
            raise GovernmentDroughtAdvisoryPresentationError("government_drought_advisory_projection_unavailable") from exc
        self._validate_view(view=view, jurisdiction_ref=jurisdiction_ref)
        return GovernmentDroughtAdvisoryPresentationView(
            jurisdiction_ref=view.jurisdiction_ref,
            advisory_refs=view.advisory_refs,
            source_revision_vector=view.source_revision_vector,
            projection_hash=view.projection_hash,
        ).model_dump(mode="json")

    @staticmethod
    def _validate_view(*, view: GovernmentDroughtAdvisoryView, jurisdiction_ref: str) -> None:
        if view.jurisdiction_ref != jurisdiction_ref or not view.advisory_refs:
            raise GovernmentDroughtAdvisoryPresentationError("government_drought_advisory_projection_unavailable")
        if any(not key or not isinstance(revision, int) or isinstance(revision, bool) or revision < 1 for key, revision in view.source_revision_vector.items()):
            raise GovernmentDroughtAdvisoryPresentationError("government_drought_advisory_projection_invalid")


__all__ = [
    "GovernmentDroughtAdvisoryPresentationError",
    "GovernmentDroughtAdvisoryPresentationService",
    "GovernmentDroughtAdvisorySubscriptionRequest",
    "GovernmentDroughtAdvisoryPresentationView",
]
