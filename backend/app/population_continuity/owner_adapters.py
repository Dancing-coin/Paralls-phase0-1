from __future__ import annotations

from typing import Any

from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.siming_contracts import PopulationOwnerReceipt, PopulationReadSet


class ScheduleGatedSupplyOwnerExecutor:
    """Adapter for the existing Organization/Continuity merge authority."""
    EVENT_FAMILY = "gameplay.organization.commerce_commitment_accepted"
    OWNER_REF = "actor_gameplay.organization_domain"

    def __init__(self, *, merger: Any | None = None, plan: Any | None = None, pending_change_ref: str | None = None, social_input: Any | None = None, household_input: Any | None = None, organization_input: Any | None = None) -> None:
        self._merger = merger
        self._plan = plan
        self._pending_change_ref = pending_change_ref
        self._social_input = social_input
        self._household_input = household_input
        self._organization_input = organization_input

    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
        if intent.intent_kind != "supply" or self._merger is None or self._plan is None or not self._pending_change_ref:
            return PopulationOwnerReceipt(receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True)
        try:
            result = self._merger.merge_released_schedule_gated_supply(plan=self._plan, pending_change_ref=self._pending_change_ref, social_input=self._social_input, household_input=self._household_input, organization_input=self._organization_input)
            return PopulationOwnerReceipt(receipt_ref=f"receipt:{intent.intent_ref}", owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=bool(result.committed), revision_vector=dict(result.revision_vector), zero_write=not bool(result.committed))
        except Exception:
            return PopulationOwnerReceipt(receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True)


__all__ = ["ScheduleGatedSupplyOwnerExecutor"]
