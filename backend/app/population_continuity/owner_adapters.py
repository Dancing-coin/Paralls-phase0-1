from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

from app.population_continuity.models import PopulationWorldPlan
from app.population_continuity.social_input import FrozenSocialPlanningInput
from app.population_continuity.source_inputs import HouseholdScheduleInput, OrganizationScheduleInput
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.siming_contracts import PopulationOwnerReceipt, PopulationReadSet
from app.gameplay.organization_government_runtime import OrganizationAuthority


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
        if plan is None or social_input is None or household_input is None or organization_input is None:
            return PopulationOwnerReceipt(receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True)
        try:
            request_context_digest = "sha256:" + hashlib.sha256(
                json.dumps(
                    {
                        "intent": intent.model_dump(mode="json"),
                        "read_set": read_set.model_dump(mode="json"),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode()
            ).hexdigest()
            if pending_change_ref:
                result = self._merger.merge_released_schedule_gated_supply(
                    plan=plan,
                    pending_change_ref=pending_change_ref,
                    social_input=social_input,
                    household_input=household_input,
                    organization_input=organization_input,
                    request_context_digest=request_context_digest,
                )
            else:
                result = self._merger.merge_schedule_gated_supply(
                    plan=plan,
                    social_input=social_input,
                    household_input=household_input,
                    organization_input=organization_input,
                    owner_request_digest=request_context_digest,
                )
            receipt_ref = str(getattr(result, "owner_receipt_ref", "") or f"receipt:{intent.intent_ref}")
            idempotency_status = str(getattr(result, "idempotency_status", "new_commit"))
            return PopulationOwnerReceipt(receipt_ref=receipt_ref, owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=bool(result.committed), revision_vector=dict(result.revision_vector), zero_write=not bool(result.committed) or idempotency_status == "duplicate_replayed", idempotency_status=idempotency_status)
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
                "pending_change_ref": str(context.get("pending_change_ref") or ""),
                "social_input": FrozenSocialPlanningInput.model_validate(context["social_input"]),
                "household_input": HouseholdScheduleInput.model_validate(context["household_input"]),
                "organization_input": OrganizationScheduleInput.model_validate(context["organization_input"]),
            }
        except (KeyError, TypeError, ValueError):
            return {}


class OrganizationOperatingWindowDueOwnerExecutor:
    """Adapter for the existing Organization operating-window Owner contract."""

    OWNER_REF = OrganizationAuthority._PRINCIPAL
    EVENT_FAMILY = "gameplay.organization.operating_window_due_recorded"
    CONTRACT_REF = "inf:organization-operating-window@1"
    OWNER_VISIBILITY_SCOPE = "project"

    def __init__(self, *, authority: OrganizationAuthority) -> None:
        self._authority = authority

    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
        if intent.intent_kind != "operating_window_due":
            return PopulationOwnerReceipt(
                receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF,
                event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True,
            )
        payload = intent.payload
        try:
            stream_ref = str(payload["stream_ref"])
            result = self._authority.record_operating_window_due(
                command_id=intent.intent_ref,
                idempotency_key=intent.idempotency_key,
                causation_id=intent.correlation_id,
                correlation_id=intent.correlation_id,
                organization_ref=str(payload["organization_ref"]),
                window_ref=str(payload["window_ref"]),
                expected_stream_revision=int(intent.expected_revisions.get(stream_ref, 0)),
                visibility_scope=self.OWNER_VISIBILITY_SCOPE,
            )
        except (KeyError, TypeError, ValueError):
            return PopulationOwnerReceipt(
                receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF,
                event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True,
            )
        committed = bool(result.committed)
        return PopulationOwnerReceipt(
            receipt_ref=(result.committed_event_ids[0] if result.committed_event_ids else f"receipt:{intent.intent_ref}"),
            owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY,
            committed=committed,
            revision_vector=dict(result.resulting_stream_revisions),
            zero_write=not committed or result.idempotency_status == "duplicate_replayed",
            idempotency_status=result.idempotency_status,
        )


class OrganizationProductionWorkContributionOwnerExecutor:
    """Narrow adapter for the committed Production -> Organization Owner contract."""

    OWNER_REF = "actor_gameplay.organization_domain"
    EVENT_FAMILY = "gameplay.organization.production_work_contribution_accepted"
    CAPABILITY_ID = "population:organization-production-work-contribution:v1"

    def __init__(self, *, authority: OrganizationAuthority) -> None:
        self._authority = authority

    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
        rejected = lambda: PopulationOwnerReceipt(
            receipt_ref=f"rejected:{intent.intent_ref}", owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY, committed=False, revision_vector={}, zero_write=True,
        )
        if intent.intent_kind != "organization_production_work_contribution" or intent.package_revision != self.CAPABILITY_ID or intent.privacy_scope not in {"organization:summary", "public"}:
            return rejected()
        payload = intent.payload
        try:
            projection = next((item for item in read_set.projections if item.ref == intent.source_ref), None)
            if projection is None or projection.scope != intent.privacy_scope or dict(projection.revision_vector) != dict(intent.expected_revisions):
                return rejected()
            organization_ref = str(payload["organization_ref"])
            source_event_id = str(payload["source_evidence_event_id"])
            source_revision = int(payload["source_evidence_revision"])
            organization_stream = f"gameplay:organization:{organization_ref}"
            organization_revision = int(payload["organization_stream_revision"])
            schedule_event_id = str(payload["schedule_event_id"])
            schedule_revision = int(payload["schedule_event_revision"])
            canonical_key = f"organization:production-work-contribution:{organization_ref}:{source_event_id}:{source_revision}:{schedule_event_id}:{schedule_revision}:v1"
            if "event_family" in payload or "stream_ref" in payload or payload.get("idempotency_key") != canonical_key:
                return rejected()
            if intent.expected_revisions.get(payload.get("source_stream_ref")) != source_revision or intent.expected_revisions.get(organization_stream) != organization_revision:
                return rejected()
            result = self._authority.accept_production_work_contribution(
                organization_ref=organization_ref,
                source_evidence_event_id=source_event_id,
                expected_source_stream_revision=source_revision,
                expected_organization_stream_revision=organization_revision,
                command_id=intent.intent_ref,
                idempotency_key=canonical_key,
                causation_id=intent.source_ref,
                correlation_id=intent.correlation_id,
            )
        except (KeyError, TypeError, ValueError):
            return rejected()
        committed = bool(result.committed)
        return PopulationOwnerReceipt(
            receipt_ref=(result.committed_event_ids[0] if result.committed_event_ids else f"receipt:{intent.intent_ref}"),
            owner_ref=self.OWNER_REF, event_family=self.EVENT_FAMILY, committed=committed,
            revision_vector=dict(result.resulting_stream_revisions),
            zero_write=not committed or result.idempotency_status == "duplicate_replayed",
            idempotency_status=result.idempotency_status,
        )


__all__ = ["ScheduleGatedSupplyOwnerExecutor", "OrganizationOperatingWindowDueOwnerExecutor", "OrganizationProductionWorkContributionOwnerExecutor"]
