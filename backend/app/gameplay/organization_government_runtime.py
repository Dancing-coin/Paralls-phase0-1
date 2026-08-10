"""Small Organization/Government owner for bakery permit and period references."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch


class Organization(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    organization_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    owner_character_ref: str = Field(pattern=r"^character:")
    revision: int = Field(default=0, ge=0)


class RoleAssignment(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    organization_ref: str = Field(min_length=1)
    character_ref: str = Field(pattern=r"^character:")
    role: str = Field(min_length=1)
    assignment_ref: str | None = None
    permitted_role_ref: str | None = None
    authorization_revision: int = Field(default=0, ge=0)
    status: str = "active"


class ShiftOffer(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    shift_ref: str = Field(min_length=1)
    assignment_ref: str = Field(min_length=1)
    work_kind: str = Field(min_length=1)
    operating_window_ref: str = Field(min_length=1)
    status: str = "offered"


class WorkOrder(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    work_order_ref: str = Field(min_length=1)
    shift_ref: str = Field(min_length=1)
    evidence_kind: str = Field(min_length=1)
    status: str = "issued"
    target_refs: tuple[str, ...] = ()


class AttendanceEvidence(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_ref: str = Field(min_length=1)
    actor_ref: str = Field(pattern=r"^character:")
    assignment_ref: str = Field(min_length=1)
    work_order_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    issuer_principal_ref: str = Field(min_length=1)
    evidence_kind: str = Field(min_length=1)
    observed_at: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    verification_state: str = Field(min_length=1)
    source_digest: str = Field(min_length=1)


class WorkerContributionRef(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    actor_ref: str = Field(pattern=r"^character:")
    assignment_ref: str = Field(min_length=1)
    work_order_ref: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    contribution_digest: str = Field(min_length=1)


class OperatingPlan(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    facility_ref: str = Field(min_length=1)
    recipe_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)


@dataclass(frozen=True)
class CommerceBudgetAuthorization:
    grant_ref: str
    budget_reservation_ref: str
    amount_minor: int
    policy_revision: str
    source_event_id: str


@dataclass(frozen=True)
class OrganizationCommerceProjection:
    organization_ref: str
    authorizations: Mapping[str, CommerceBudgetAuthorization]
    budget_reservations: Mapping[str, CommerceBudgetAuthorization]
    source_revision: int


class Permit(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    permit_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    expires_tick: int = Field(ge=0)
    status: str = "active"


class Inspection(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    inspection_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    tick: int = Field(ge=0)
    passed: bool
    policy_revision: str = Field(min_length=1)


class TaxAssessment(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    assessment_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    amount: float = Field(ge=0)


class GovernmentAuthority:
    _PRINCIPAL = "actor_gameplay.government_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    @staticmethod
    def require_permit(permit: Permit, *, tick: int, policy_revision: str) -> None:
        if permit.status != "active" or tick > permit.expires_tick:
            raise ValueError("permit_expired")
        if permit.policy_revision != policy_revision:
            raise ValueError("policy_revision_unavailable")

    @staticmethod
    def assess_tax(period_ref: str, organization_ref: str, *, revenue: float, rate: float, policy_revision: str) -> TaxAssessment:
        return TaxAssessment(
            assessment_ref=f"tax:{period_ref}", organization_ref=organization_ref, period_ref=period_ref,
            policy_revision=policy_revision, amount=max(0.0, revenue * rate)
        )

    @staticmethod
    def inspection_obligation(inspection: Inspection) -> str | None:
        return None if inspection.passed else f"obligation:remediation:{inspection.inspection_ref}"

    def settle_permit_activation(
        self,
        permit: Permit,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        return self._settle(
            stream_id=f"gameplay:government:{permit.organization_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_specs=[("gameplay.government.permit_activated", permit.model_dump(mode="json"))],
        )

    def build_commercial_permit_fragment(
        self,
        *,
        application_ref: str,
        organization_ref: str,
        permit_class: str,
        policy_revision: str,
        policy_digest: str,
        evidence_refs: tuple[str, ...],
        approved: bool,
    ) -> OwnerAuthorizedFragment:
        """Return Government's permit decision; a caller may only compose it."""
        if approved and not evidence_refs:
            raise ValueError("permit_evidence_required")
        stream_id = f"gameplay:government:{organization_ref}"
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:government:permit:{application_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="government:commercial-permit",
            expected_revisions={stream_id: self._store.get_stream_head(stream_id)},
            pinned_revisions={},
            event_specs={
                stream_id: (
                    (
                        "gameplay.government.permit_approved" if approved else "gameplay.government.permit_denied",
                        {
                            "application_ref": application_ref,
                            "organization_ref": organization_ref,
                            "permit_class": permit_class,
                            "policy_revision": policy_revision,
                            "policy_digest": policy_digest,
                            "evidence_refs": evidence_refs,
                        },
                    ),
                )
            },
        )

    def build_commercial_inspection_fragment(
        self,
        *,
        inspection_ref: str,
        organization_ref: str,
        jurisdiction_ref: str,
        policy_revision: str,
        policy_digest: str,
        evidence_ref: str,
        passed: bool,
    ) -> OwnerAuthorizedFragment:
        if not evidence_ref:
            raise ValueError("inspection_evidence_required")
        stream_id = f"gameplay:government:{organization_ref}"
        events: tuple[tuple[str, dict[str, object]], ...] = (
            (
                "gameplay.government.inspection_recorded",
                {
                    "inspection_ref": inspection_ref,
                    "organization_ref": organization_ref,
                    "jurisdiction_ref": jurisdiction_ref,
                    "policy_revision": policy_revision,
                    "policy_digest": policy_digest,
                    "evidence_ref": evidence_ref,
                    "passed": passed,
                },
            ),
        )
        if not passed:
            events += (
                (
                    "gameplay.government.inspection_obligation_created",
                    {
                        "inspection_ref": inspection_ref,
                        "obligation_ref": f"obligation:remediation:{inspection_ref}",
                    },
                ),
            )
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:government:inspection:{inspection_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="government:commercial-inspection",
            expected_revisions={stream_id: self._store.get_stream_head(stream_id)},
            pinned_revisions={},
            event_specs={stream_id: events},
        )

    def settle_inspection(
        self,
        inspection: Inspection,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        event_specs: list[tuple[str, dict[str, object]]] = [
            ("gameplay.government.inspection_recorded", inspection.model_dump(mode="json"))
        ]
        obligation_ref = self.inspection_obligation(inspection)
        if obligation_ref is not None:
            event_specs.append(
                (
                    "gameplay.government.inspection_obligation_created",
                    {"inspection_ref": inspection.inspection_ref, "obligation_ref": obligation_ref},
                )
            )
        return self._settle(
            stream_id=f"gameplay:government:{inspection.organization_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_specs=event_specs,
        )

    def settle_tax(
        self,
        assessment: TaxAssessment,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        return self._settle(
            stream_id=f"gameplay:government:{assessment.organization_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_specs=[("gameplay.government.tax_assessed", assessment.model_dump(mode="json"))],
        )

    def settle_permit_verification(
        self,
        *,
        permit: Permit,
        organization_ref: str,
        tick: int,
        policy_revision: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        self.require_permit(permit, tick=tick, policy_revision=policy_revision)
        return self._settle(
            stream_id=f"gameplay:government:{organization_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_specs=[
                (
                    "gameplay.government.permit_verified",
                    {
                        "permit_ref": permit.permit_ref,
                        "organization_ref": organization_ref,
                        "tick": tick,
                        "policy_revision": policy_revision,
                    },
                )
            ],
        )

    def settle_tax_assessment(
        self,
        *,
        organization_ref: str,
        period_ref: str,
        revenue: float,
        rate: float,
        policy_revision: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        assessment = self.assess_tax(
            period_ref,
            organization_ref,
            revenue=revenue,
            rate=rate,
            policy_revision=policy_revision,
        )
        return self.settle_tax(
            assessment,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def _settle(
        self,
        *,
        stream_id: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        event_specs: list[tuple[str, dict[str, object]]],
    ):
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=event_specs,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"government": self._store.get_stream_head(stream_id)},
        )
        return self._store.append_batch(batch)

    @staticmethod
    def assess_tax_and_settle(
        *,
        store: GameplayEventStore,
        organization_ref: str,
        period_ref: str,
        revenue: float,
        rate: float,
        policy_revision: str,
    ):
        assessment = GovernmentAuthority.assess_tax(
            period_ref,
            organization_ref,
            revenue=revenue,
            rate=rate,
            policy_revision=policy_revision,
        )
        command_id = f"tax-assessment:{assessment.assessment_ref}"
        return GovernmentAuthority(store=store).settle_tax(
            assessment,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{organization_ref}:{period_ref}",
        )

    @staticmethod
    def require_permit_and_settle(
        *,
        store: GameplayEventStore,
        permit: Permit,
        organization_ref: str,
        tick: int,
        policy_revision: str,
    ):
        command_id = f"permit-verified:{permit.permit_ref}:{tick}"
        return GovernmentAuthority(store=store).settle_permit_verification(
            permit=permit,
            organization_ref=organization_ref,
            tick=tick,
            policy_revision=policy_revision,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{organization_ref}:{tick}",
        )


class OrganizationAuthority:
    _PRINCIPAL = "actor_gameplay.organization_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    @staticmethod
    def assign_role(role: RoleAssignment, *, existing_character_refs: set[str]) -> RoleAssignment:
        if role.character_ref not in existing_character_refs:
            raise ValueError("character_record_required")
        return role

    @staticmethod
    def completed_evidence(evidence: AttendanceEvidence) -> AttendanceEvidence:
        if evidence.outcome != "completed" or evidence.verification_state != "verified":
            raise ValueError("work_evidence_invalid")
        expected_issuer = {
            "production-completed": "actor_gameplay.production_domain",
            "procurement-completed": "actor_gameplay.economy_domain",
            "service-completed": "actor_gameplay.organization_domain",
        }.get(evidence.evidence_kind)
        if expected_issuer is None or evidence.issuer_principal_ref != expected_issuer:
            raise ValueError("work_evidence_issuer_unauthorized")
        if not evidence.source_digest.startswith("sha256:"):
            raise ValueError("work_evidence_digest_invalid")
        return evidence

    def settle_role_assignment(
        self,
        role: RoleAssignment,
        *,
        existing_character_refs: set[str],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        assigned = self.assign_role(role, existing_character_refs=existing_character_refs)
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        stream_id = f"gameplay:organization:{assigned.organization_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[("gameplay.organization.role_assigned", assigned.model_dump(mode="json"))],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"organization": self._store.get_stream_head(stream_id)},
        )
        return self._store.append_batch(batch)

    def grant_commerce_budget(
        self,
        *,
        command_id: str,
        organization_ref: str,
        grant_ref: str,
        budget_reservation_ref: str,
        amount_minor: int,
        policy_revision: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        """Persist the organization's bounded procurement authorization.

        This is an Organization fact, deliberately distinct from Economy's
        account reservation.  Commerce later only references and validates it.
        """
        projection = self._commerce_projection(organization_ref)
        if (
            not grant_ref.startswith("grant:")
            or not budget_reservation_ref.startswith("reservation:")
            or amount_minor <= 0
            or not policy_revision
            or grant_ref in projection.authorizations
            or budget_reservation_ref in projection.budget_reservations
        ):
            raise ValueError("commerce_organization_authorization_invalid")
        stream_id = f"gameplay:organization:{organization_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=projection.source_revision,
            event_specs=[
                (
                    "gameplay.organization.commerce_budget_authorized",
                    {
                        "organization_ref": organization_ref,
                        "grant_ref": grant_ref,
                        "budget_reservation_ref": budget_reservation_ref,
                        "amount_minor": amount_minor,
                        "policy_revision": policy_revision,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={f"organization:{organization_ref}": projection.source_revision},
        )
        return self._store.append_batch(batch)

    def _commerce_projection(self, organization_ref: str) -> OrganizationCommerceProjection:
        stream_id = f"gameplay:organization:{organization_ref}"
        authorizations: dict[str, CommerceBudgetAuthorization] = {}
        budget_reservations: dict[str, CommerceBudgetAuthorization] = {}
        revision = 0
        for event in sorted(self._store.read_events(), key=lambda item: (item.global_sequence, item.event_id)):
            if event.stream_id != stream_id:
                continue
            revision = max(revision, event.stream_revision)
            if event.event_type != "gameplay.organization.commerce_budget_authorized":
                continue
            payload = event.payload
            grant_ref = payload.get("grant_ref")
            budget_reservation_ref = payload.get("budget_reservation_ref")
            amount_minor = payload.get("amount_minor")
            policy_revision = payload.get("policy_revision")
            if (
                not isinstance(grant_ref, str)
                or not grant_ref.startswith("grant:")
                or not isinstance(budget_reservation_ref, str)
                or not budget_reservation_ref.startswith("reservation:")
                or isinstance(amount_minor, bool)
                or not isinstance(amount_minor, int)
                or amount_minor <= 0
                or not isinstance(policy_revision, str)
                or not policy_revision
                or grant_ref in authorizations
                or budget_reservation_ref in budget_reservations
            ):
                raise ValueError("commerce_organization_authorization_invalid")
            authorization = CommerceBudgetAuthorization(
                grant_ref,
                budget_reservation_ref,
                amount_minor,
                policy_revision,
                event.event_id,
            )
            authorizations[grant_ref] = authorization
            budget_reservations[budget_reservation_ref] = authorization
        return OrganizationCommerceProjection(
            organization_ref,
            MappingProxyType(dict(sorted(authorizations.items()))),
            MappingProxyType(dict(sorted(budget_reservations.items()))),
            revision,
        )

    def build_commerce_commitment_fragment(
        self,
        *,
        organization_ref: str,
        commitment_ref: str,
        counterparty_organization_ref: str,
        organization_grant_refs: tuple[str, ...],
        budget_reservation_refs: tuple[str, ...],
        policy_revision: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        """Validate organization-owned authorization/budget pins for P4B."""
        if not organization_ref or not commitment_ref or not counterparty_organization_ref:
            raise ValueError("commerce_organization_reference_invalid")
        if any(not ref.startswith("grant:") for ref in organization_grant_refs):
            raise ValueError("commerce_organization_grant_invalid")
        if any(not ref.startswith("reservation:") for ref in budget_reservation_refs):
            raise ValueError("commerce_budget_reservation_invalid")
        stream_id = f"gameplay:organization:{organization_ref}"
        if self._store.get_stream_head(stream_id) != expected_revision:
            raise ValueError("revision_conflict")
        projection = self._commerce_projection(organization_ref)
        if organization_grant_refs or budget_reservation_refs:
            if not organization_grant_refs or not budget_reservation_refs:
                raise ValueError("commerce_organization_authorization_incomplete")
            authorizations = [projection.authorizations.get(ref) for ref in organization_grant_refs]
            if any(authorization is None for authorization in authorizations):
                raise ValueError("commerce_organization_grant_missing")
            budgets = [projection.budget_reservations.get(ref) for ref in budget_reservation_refs]
            if any(authorization is None for authorization in budgets):
                raise ValueError("commerce_budget_reservation_missing")
            if any(authorization is None or authorization.policy_revision != policy_revision for authorization in authorizations + budgets):
                raise ValueError("commerce_organization_policy_stale")
            if {authorization.budget_reservation_ref for authorization in authorizations if authorization is not None} != set(budget_reservation_refs):
                raise ValueError("commerce_organization_budget_grant_mismatch")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:organization:commerce:{organization_ref}:{commitment_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="organization:commerce-commitment",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={f"organization:{organization_ref}": expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.organization.commerce_commitment_accepted",
                        {
                            "commitment_ref": commitment_ref,
                            "organization_ref": organization_ref,
                            "counterparty_organization_ref": counterparty_organization_ref,
                            "organization_grant_refs": organization_grant_refs,
                            "budget_reservation_refs": budget_reservation_refs,
                            "policy_revision": policy_revision,
                        },
                    ),
                )
            },
        )


__all__ = ["AttendanceEvidence", "CommerceBudgetAuthorization", "GovernmentAuthority", "Inspection", "OperatingPlan", "Organization", "OrganizationAuthority", "OrganizationCommerceProjection", "Permit", "RoleAssignment", "ShiftOffer", "TaxAssessment", "WorkOrder", "WorkerContributionRef"]
