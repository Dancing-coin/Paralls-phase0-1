from __future__ import annotations

from typing import Any

from app.gameplay.closed_generic_gameplay_families import ProductionOutputCustodyIntent
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.siming_contracts import PopulationOwnerReceipt, PopulationReadSet


class InventoryOutputCustodyOwnerExecutor:
    """Route one population candidate through Inventory's existing custody Owner."""

    OWNER_REF = "actor_gameplay.inventory_domain"
    EVENT_FAMILY = "gameplay.inventory.production_output_received@1"
    CAPABILITY_ID = "population:inventory-output-custody:v1"
    CONTRACT_REF = "inf:inventory-production-output-custody@1"
    _FORBIDDEN_OVERRIDES = frozenset(
        {"holder_ref", "container_id", "quantity", "item_ref", "stream_ref", "event_family", "owner_ref"}
    )

    def __init__(self, *, authority: Any) -> None:
        self._authority = authority

    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
        rejected = lambda: PopulationOwnerReceipt(
            receipt_ref=f"rejected:{intent.intent_ref}",
            owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY,
            committed=False,
            revision_vector={},
            zero_write=True,
        )
        if (
            intent.intent_kind != "inventory_output_custody"
            or intent.package_revision != self.CAPABILITY_ID
            or intent.privacy_scope not in {"organization:summary", "public"}
        ):
            return rejected()
        projection = next((item for item in read_set.projections if item.ref == intent.source_ref), None)
        if projection is None or projection.scope != intent.privacy_scope or dict(projection.revision_vector) != dict(intent.expected_revisions):
            return rejected()
        payload = projection.payload
        if self._FORBIDDEN_OVERRIDES.intersection(payload) or any(
            key in intent.payload for key in self._FORBIDDEN_OVERRIDES
        ):
            return rejected()
        try:
            certification_event_id = str(payload["source_certification_event_id"])
            certification_revision = int(payload["source_certification_revision"])
            source_stream_ref = str(payload["source_stream_ref"])
            if not certification_event_id or certification_revision < 1 or not source_stream_ref:
                return rejected()
            if intent.expected_revisions.get(source_stream_ref) != certification_revision:
                return rejected()
            inventory_revision = self._inventory_revision(certification_event_id, payload)
            typed_intent = ProductionOutputCustodyIntent(
                certification_event_id=certification_event_id,
                expected_certification_revision=certification_revision,
                expected_inventory_stream_revision=inventory_revision,
                command_id=intent.intent_ref,
                correlation_id=intent.correlation_id,
                submitted_at=str(payload.get("submitted_at") or f"population:{read_set.cadence.cadence_id}"),
            )
            result = self._authority.settle_production_output_custody(intent=typed_intent)
        except (KeyError, TypeError, ValueError, AttributeError):
            return rejected()
        committed = bool(getattr(result, "committed", False))
        status = str(getattr(result, "idempotency_status", "rejected"))
        revisions = dict(getattr(result, "resulting_stream_revisions", {}) or {})
        event_ids = tuple(str(item) for item in (getattr(result, "committed_event_ids", ()) or ()))
        return PopulationOwnerReceipt(
            receipt_ref=event_ids[0] if event_ids else f"receipt:{intent.intent_ref}",
            owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY,
            committed=committed,
            revision_vector=revisions,
            zero_write=not committed or status == "duplicate_replayed",
            idempotency_status=status,
        )

    def _inventory_revision(self, certification_event_id: str, payload: dict[str, object]) -> int:
        """Read the current Owner stream; only test doubles use the projection pin."""
        store = getattr(self._authority, "_store", None)
        if store is None:
            value = payload.get("expected_inventory_stream_revision", 0)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
        try:
            certification = store.get_event(certification_event_id)
            source_stream = certification.stream_id
            facility_ref = certification.payload.get("facility_ref")
            acquisitions = [
                event
                for event in store.read_stream(source_stream)
                if event.event_type == "gameplay.construction_production.facility_acquired"
                and event.payload.get("facility_ref") == facility_ref
            ]
            holder_ref = acquisitions[0].payload.get("owner_ref") if len(acquisitions) == 1 else None
            if isinstance(holder_ref, str) and holder_ref:
                return int(store.get_stream_head(f"gameplay:inventory:{holder_ref}"))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        return 0


__all__ = ["InventoryOutputCustodyOwnerExecutor"]
