from __future__ import annotations

from typing import Any, Callable, Mapping

from app.population_continuity.models import PopulationWorldPlan
from app.population_continuity.social_input import FrozenSocialPlanningInput
from app.population_continuity.source_inputs import HouseholdScheduleInput, OrganizationScheduleInput
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.siming_contracts import PopulationOwnerReceipt, PopulationReadSet


class ScheduleGatedSupplyOwnerExecutor:
    """Adapter for the existing Organization/Continuity merge authority."""
    EVENT_FAMILY = "gameplay.organization.commerce_commitment_accepted"
    OWNER_REF = "actor_gameplay.organization_domain"

    def __init__(self, *, merger: Any | None = None, plan: Any | None = None, pending_change_ref: str | None = None, social_input: Any | None = None, household_input: Any | None = None, organization_input: Any | None = None, context_builder: Callable[[BatchIntentCandidate, PopulationReadSet], Mapping[str, Any]] | None = None) -> None:
        self._merger = merger
        self._plan = plan
        self._pending_change_ref = pending_change_ref
        self._social_input = social_input
        self._household_input = household_input
        self._organization_input = organization_input
        self._context_builder = context_builder

    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
        if intent.intent_kind != "supply" or self._merger is None:
            return PopulationOwnerReceipt(receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True)
        context = self._context_builder(intent, read_set) if self._context_builder is not None else {}
        plan = context.get("plan", self._plan)
        pending_change_ref = context.get("pending_change_ref", self._pending_change_ref)
        social_input = context.get("social_input", self._social_input)
        household_input = context.get("household_input", self._household_input)
        organization_input = context.get("organization_input", self._organization_input)
        if plan is None or not pending_change_ref or social_input is None or household_input is None or organization_input is None:
            return PopulationOwnerReceipt(receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True)
        try:
            result = self._merger.merge_released_schedule_gated_supply(plan=plan, pending_change_ref=pending_change_ref, social_input=social_input, household_input=household_input, organization_input=organization_input)
            receipt_ref = str(getattr(result, "owner_receipt_ref", "") or f"receipt:{intent.intent_ref}")
            return PopulationOwnerReceipt(receipt_ref=receipt_ref, owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=bool(result.committed), revision_vector=dict(result.revision_vector), zero_write=not bool(result.committed))
        except Exception:
            return PopulationOwnerReceipt(receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True)

    @staticmethod
    def context_from_intent_payload(intent: BatchIntentCandidate, _: PopulationReadSet) -> Mapping[str, Any]:
        context = intent.payload.get("schedule_gated_supply_owner_context")
        if not isinstance(context, dict):
            return {}
        try:
            return {
                "plan": PopulationWorldPlan.model_validate(context["plan"]),
                "pending_change_ref": str(context["pending_change_ref"]),
                "social_input": FrozenSocialPlanningInput.model_validate(context["social_input"]),
                "household_input": HouseholdScheduleInput.model_validate(context["household_input"]),
                "organization_input": OrganizationScheduleInput.model_validate(context["organization_input"]),
            }
        except (KeyError, TypeError, ValueError):
            return {}


__all__ = ["ScheduleGatedSupplyOwnerExecutor"]
