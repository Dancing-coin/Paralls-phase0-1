from __future__ import annotations

import hashlib
import json

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, ProductionCompletedEvidenceView
from app.gameplay.models import StrictGameplayModel
from app.gameplay.organization_government_runtime import OrganizationScheduleRecipientView
from app.gameplay.p5.social_knowledge import HouseholdRecipientView


class FrozenSourceInput(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    recipient_ref: str = Field(min_length=1)
    observed_at: str = Field(min_length=1)
    owner_principal_ref: str = Field(min_length=1)
    projection_digest: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)

    @property
    def input_digest(self) -> str:
        payload = {
            "recipient_ref": self.recipient_ref,
            "observed_at": self.observed_at,
            "owner_principal_ref": self.owner_principal_ref,
            "projection_digest": self.projection_digest,
            "source_revision_vector": dict(sorted(self.source_revision_vector.items())),
        }
        return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def validate_against(self, *, store: GameplayEventStore) -> "SourceInputValidation":
        if self.owner_principal_ref not in self.admitted_owner_principals:
            return SourceInputValidation(accepted=False, error_code="source_provenance_denied")
        if self.projection_digest != self.canonical_projection_digest:
            return SourceInputValidation(accepted=False, error_code="source_projection_digest_mismatch")
        for stream_id, expected_revision in self.source_revision_vector.items():
            if store.get_stream_head(stream_id) != expected_revision:
                return SourceInputValidation(accepted=False, error_code="source_revision_stale")
        return SourceInputValidation(accepted=True)

    @property
    def admitted_owner_principals(self) -> tuple[str, ...]:
        return ()

    @property
    def canonical_projection_digest(self) -> str:
        return self.projection_digest


class HouseholdScheduleInput(FrozenSourceInput):
    household_memberships: tuple[dict[str, object], ...] = ()

    @classmethod
    def freeze(cls, *, recipient_ref: str, observed_at: str, view: HouseholdRecipientView) -> "HouseholdScheduleInput":
        return cls(
            recipient_ref=recipient_ref,
            observed_at=observed_at,
            owner_principal_ref=view.owner_principal_ref,
            projection_digest=view.projection_hash,
            source_revision_vector=dict(view.source_revision_vector),
            household_memberships=view.household_memberships,
        )

    @property
    def admitted_owner_principals(self) -> tuple[str, ...]:
        return ("authority:p5:social",)

    @property
    def canonical_projection_digest(self) -> str:
        payload = {"household_memberships": self.household_memberships, "source_revision_vector": dict(sorted(self.source_revision_vector.items()))}
        return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class OrganizationScheduleInput(FrozenSourceInput):
    organization_ref: str = Field(min_length=1)
    organization_memberships: tuple[dict[str, object], ...] = ()
    role_terms: tuple[dict[str, object], ...] = ()
    shift_offers: tuple[dict[str, object], ...] = ()
    work_orders: tuple[dict[str, object], ...] = ()

    @classmethod
    def freeze(cls, *, recipient_ref: str, observed_at: str, view: OrganizationScheduleRecipientView) -> "OrganizationScheduleInput":
        return cls(
            recipient_ref=recipient_ref,
            observed_at=observed_at,
            owner_principal_ref=view.owner_principal_ref,
            organization_ref=view.organization_ref,
            projection_digest=view.projection_hash,
            source_revision_vector=dict(view.source_revision_vector),
            organization_memberships=view.organization_memberships,
            role_terms=view.role_terms,
            shift_offers=view.shift_offers,
            work_orders=view.work_orders,
        )

    @property
    def admitted_owner_principals(self) -> tuple[str, ...]:
        return ("actor_gameplay.organization_domain",)

    @property
    def canonical_projection_digest(self) -> str:
        payload = {
            "organization_ref": self.organization_ref,
            "recipient_ref": self.recipient_ref,
            "observed_at": self.observed_at,
            "rows": {
                "membership": self.organization_memberships,
                "role": self.role_terms,
                "shift": self.shift_offers,
                "work_order": self.work_orders,
            },
            "source_revision_vector": dict(sorted(self.source_revision_vector.items())),
        }
        return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class ProductionCompletedEvidenceInput(FrozenSourceInput):
    """Worker-scoped Production evidence frozen before the lone wage consumer."""

    evidence_refs: tuple[str, ...] = Field(min_length=1)
    evidence_rows: tuple[dict[str, object], ...] = Field(min_length=1)
    source_event_refs: tuple[str, ...] = Field(min_length=1)

    @classmethod
    def freeze(
        cls,
        *,
        recipient_ref: str,
        observed_at: str,
        view: ProductionCompletedEvidenceView,
    ) -> "ProductionCompletedEvidenceInput":
        if view.recipient_ref != recipient_ref:
            raise ValueError("production_evidence_recipient_scope_denied")
        return cls(
            recipient_ref=recipient_ref,
            observed_at=observed_at,
            owner_principal_ref=view.owner_principal_ref,
            projection_digest=view.projection_hash,
            source_revision_vector=dict(view.source_revision_vector),
            evidence_refs=view.evidence_refs,
            evidence_rows=view.evidence_rows,
            source_event_refs=view.source_event_refs,
        )

    @property
    def admitted_owner_principals(self) -> tuple[str, ...]:
        return ("actor_gameplay.construction_production_domain",)

    @property
    def canonical_projection_digest(self) -> str:
        payload = {
            "recipient_ref": self.recipient_ref,
            "evidence_rows": self.evidence_rows,
            "source_event_refs": self.source_event_refs,
            "source_revision_vector": dict(sorted(self.source_revision_vector.items())),
        }
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    def validate_against(self, *, store: GameplayEventStore) -> "SourceInputValidation":
        basic = super().validate_against(store=store)
        if not basic.accepted:
            return basic
        if not self.recipient_ref.startswith("character:"):
            return SourceInputValidation(accepted=False, error_code="production_evidence_recipient_scope_denied")
        view = ConstructionProductionAuthority(store=store).completed_evidence_view_for(
            recipient_ref=self.recipient_ref
        )
        if view.projection_hash != self.projection_digest:
            return SourceInputValidation(accepted=False, error_code="production_evidence_projection_digest_mismatch")
        if view.evidence_refs != self.evidence_refs or view.source_event_refs != self.source_event_refs:
            return SourceInputValidation(accepted=False, error_code="production_evidence_source_mismatch")
        return SourceInputValidation(accepted=True)


class SourceInputValidation(StrictGameplayModel):
    accepted: bool
    error_code: str | None = None


__all__ = ["FrozenSourceInput", "HouseholdScheduleInput", "OrganizationScheduleInput", "ProductionCompletedEvidenceInput", "SourceInputValidation"]
