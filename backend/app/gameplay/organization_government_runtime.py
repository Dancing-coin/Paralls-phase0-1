"""Small Organization/Government owner for bakery permit and period references."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
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


class OperatingPlan(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    facility_ref: str = Field(min_length=1)
    recipe_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)


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


__all__ = ["GovernmentAuthority", "Inspection", "OperatingPlan", "Organization", "OrganizationAuthority", "Permit", "RoleAssignment", "TaxAssessment"]
