"""Small Organization/Government owner for bakery permit and period references."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ecology_consumer_admission import EcologyConsumerAdmissionCheck
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AppendBatchResult, GameplayFailure, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.settlement_plan import SettlementPlan as EventStoreSettlementPlan
from app.gameplay.settlement_plan import build_atomic_event_batch, build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope


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


class OrganizationScheduleRecipientView(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owner_principal_ref: str
    organization_ref: str
    organization_memberships: tuple[dict[str, object], ...] = ()
    role_terms: tuple[dict[str, object], ...] = ()
    shift_offers: tuple[dict[str, object], ...] = ()
    work_orders: tuple[dict[str, object], ...] = ()
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    projection_hash: str = ""

    def validate_against(self, *, store: GameplayEventStore) -> bool:
        return all(store.get_stream_head(stream_id) == revision for stream_id, revision in self.source_revision_vector.items())


class OrganizationOperatingWindowView(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owner_principal_ref: str
    organization_ref: str
    window_ref: str
    status: str = "missing"
    due_recorded: bool = False
    opens_at_tick: int | None = None
    closes_at_tick: int | None = None
    visibility_scope: str = ""
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    projection_hash: str = ""

    def validate_against(self, *, store: GameplayEventStore) -> bool:
        return all(
            store.get_stream_head(stream_id) == revision
            for stream_id, revision in self.source_revision_vector.items()
        )


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


class GovernmentCommercialInspectionPolicy(StrictGameplayModel):
    """The sole Government-owned policy registration admitted by INF-2K."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: Literal["policy:commercial-inspection-window@1"]
    policy_revision: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    inspection_window_ticks: int = Field(gt=0, le=64)


class GovernmentCommercialInspectionPolicyView(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_ref: str = Field(min_length=1)
    active_policy_refs: tuple[str, ...] = ()
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    projection_hash: str = Field(min_length=1)


class BranchScenarioReceipt(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(min_length=1)
    committed_event_ids: tuple[str, ...] = ()
    scenario_stream: str = Field(min_length=1)
    scenario_revision: int = Field(ge=1)
    source_government_revision: int = Field(ge=0)
    projection_hash: str = Field(min_length=1)
    privacy_scope: str = Field(min_length=1)
    idempotency_status: str = Field(min_length=1)


class GovernmentBranchPromotionReceipt(StrictGameplayModel):
    """Read-derived receipt for the sole admitted production branch consequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(min_length=1)
    committed_event_ids: tuple[str, ...] = ()
    production_stream: str = Field(min_length=1)
    production_revision: int = Field(ge=1)
    admission_event_id: str = Field(min_length=1)
    scenario_event_id: str = Field(min_length=1)
    projection_hash: str = Field(min_length=1)
    privacy_scope: Literal["project"]
    idempotency_status: str = Field(min_length=1)


class GovernmentBranchPromotionResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    error_code: str | None = None
    receipt: GovernmentBranchPromotionReceipt | None = None


class OrganizationBranchPromotionReceipt(StrictGameplayModel):
    """Read-derived receipt for the sole admitted production supply consequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(min_length=1)
    committed_event_ids: tuple[str, ...] = ()
    production_stream: str = Field(min_length=1)
    production_revision: int = Field(ge=1)
    admission_event_id: str = Field(min_length=1)
    scenario_event_id: str = Field(min_length=1)
    projection_hash: str = Field(min_length=1)
    privacy_scope: Literal["project"]
    idempotency_status: str = Field(min_length=1)


class OrganizationBranchPromotionResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    error_code: str | None = None
    receipt: OrganizationBranchPromotionReceipt | None = None


def _canonical_weather_front_organization_supply_admission_channel():
    """Create a sealed one-way source-evidence handoff for INF-3I."""

    @dataclass(frozen=True)
    class _Admission:
        edge_ref: str
        weather_event_id: str
        organization_ref: str
        commitment_ref: str

    def issue(
        *, edge_ref: str, weather_event_id: str, organization_ref: str, commitment_ref: str
    ) -> object:
        return _Admission(
            edge_ref=edge_ref,
            weather_event_id=weather_event_id,
            organization_ref=organization_ref,
            commitment_ref=commitment_ref,
        )

    def contains(admission: object) -> bool:
        return isinstance(admission, _Admission)

    return issue, contains


(
    _CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_ADMISSION_ISSUER,
    _CONTAINS_CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_ADMISSION,
) = _canonical_weather_front_organization_supply_admission_channel()


def _take_canonical_weather_front_organization_supply_admission_issuer() -> object:
    """One-time handoff to Ecology; callers cannot manufacture admissions."""

    issuer = _CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_ADMISSION_ISSUER
    del globals()["_CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_ADMISSION_ISSUER"]
    del globals()["_take_canonical_weather_front_organization_supply_admission_issuer"]
    return issuer


def _canonical_weather_front_organization_supply_fanout_admission_channel():
    """Create a sealed one-way source-evidence handoff for INF-3O."""

    @dataclass(frozen=True)
    class _Admission:
        edge_ref: str
        weather_event_id: str
        organization_refs: tuple[str, str]

    def issue(
        *, edge_ref: str, weather_event_id: str, organization_refs: tuple[str, str]
    ) -> object:
        return _Admission(
            edge_ref=edge_ref,
            weather_event_id=weather_event_id,
            organization_refs=organization_refs,
        )

    def contains(admission: object) -> bool:
        return isinstance(admission, _Admission)

    return issue, contains


(
    _CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_FANOUT_ADMISSION_ISSUER,
    _CONTAINS_CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_FANOUT_ADMISSION,
) = _canonical_weather_front_organization_supply_fanout_admission_channel()


def _take_canonical_weather_front_organization_supply_fanout_admission_issuer() -> object:
    """One-time handoff to Ecology; callers cannot manufacture fanout admissions."""

    issuer = _CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_FANOUT_ADMISSION_ISSUER
    del globals()["_CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_FANOUT_ADMISSION_ISSUER"]
    del globals()["_take_canonical_weather_front_organization_supply_fanout_admission_issuer"]
    return issuer


_BRANCH_INSPECTION_REMEDIATION_SEAL = object()


@dataclass(frozen=True, slots=True)
class BranchInspectionRemediationProposal:
    """Sealed provenance issued only after BranchPreview accepted evaluation."""

    branch_ref: str
    base_event_digest: str
    candidate_digest: str
    organization_ref: str
    inspection_ref: str
    jurisdiction_ref: str
    policy_revision: str
    policy_digest: str
    evidence_ref: str
    source_government_revision: int
    fragment_digest: str
    _seal: object = field(repr=False, compare=False)

    @classmethod
    def _issue(
        cls,
        *,
        branch_ref: str,
        base_event_digest: str,
        candidate_digest: str,
        organization_ref: str,
        inspection_ref: str,
        jurisdiction_ref: str,
        policy_revision: str,
        policy_digest: str,
        evidence_ref: str,
        source_government_revision: int,
        fragment_digest: str,
    ) -> "BranchInspectionRemediationProposal":
        proposal = cls(
            branch_ref=branch_ref,
            base_event_digest=base_event_digest,
            candidate_digest=candidate_digest,
            organization_ref=organization_ref,
            inspection_ref=inspection_ref,
            jurisdiction_ref=jurisdiction_ref,
            policy_revision=policy_revision,
            policy_digest=policy_digest,
            evidence_ref=evidence_ref,
            source_government_revision=source_government_revision,
            fragment_digest=fragment_digest,
            _seal=_BRANCH_INSPECTION_REMEDIATION_SEAL,
        )
        proposal.validate()
        return proposal

    def validate(self) -> None:
        if self._seal is not _BRANCH_INSPECTION_REMEDIATION_SEAL:
            raise ValueError("branch_scenario_provenance_invalid")
        if (
            not self.branch_ref.startswith("branch:")
            or not self.base_event_digest.startswith("sha256:")
            or not self.candidate_digest.startswith("sha256:")
            or not self.organization_ref
            or not self.inspection_ref
            or not self.jurisdiction_ref
            or not self.policy_revision
            or not self.policy_digest.startswith("sha256:")
            or not self.evidence_ref
            or not isinstance(self.source_government_revision, int)
            or isinstance(self.source_government_revision, bool)
            or self.source_government_revision < 0
            or not self.fragment_digest.startswith("sha256:")
        ):
            raise ValueError("branch_scenario_provenance_invalid")


class GovernmentAuthority:
    _PRINCIPAL = "actor_gameplay.government_domain"
    _BRANCH_STREAM_PREFIX = "gameplay:government_branch:"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def register_commercial_inspection_policy(
        self,
        *,
        policy: GovernmentCommercialInspectionPolicy,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
        privacy_scope: str,
    ) -> AppendBatchResult:
        if privacy_scope != "project":
            return self._rejected_append(command_id, "government_policy_privacy_denied")
        stream_id = f"gameplay:government:{policy.organization_ref}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None and existing.committed:
            if len(existing.committed_event_ids) != 1:
                return self._rejected_append(command_id, "idempotency_key_reused")
            event = self._store.get_event(existing.committed_event_ids[0])
            if (
                event.event_type != "gameplay.government.commercial_inspection_policy_registered"
                or event.payload != policy.model_dump(mode="json")
            ):
                return self._rejected_append(command_id, "idempotency_key_reused")
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        view = self.commercial_inspection_policy_view_for(organization_ref=policy.organization_ref, scope="project")
        if policy.policy_ref in view.active_policy_refs:
            return self._rejected_append(command_id, "government_policy_already_active")
        return self._append_commercial_inspection_policy_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            expected_revision=expected_revision,
            stream_id=stream_id,
            event_type="gameplay.government.commercial_inspection_policy_registered",
            payload=policy.model_dump(mode="json"),
        )

    def revoke_commercial_inspection_policy(
        self,
        *,
        organization_ref: str,
        policy_ref: str,
        policy_revision: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
        privacy_scope: str,
    ) -> AppendBatchResult:
        if privacy_scope != "project":
            return self._rejected_append(command_id, "government_policy_privacy_denied")
        stream_id = f"gameplay:government:{organization_ref}"
        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        if policy_ref not in self.commercial_inspection_policy_view_for(organization_ref=organization_ref, scope="project").active_policy_refs:
            return self._rejected_append(command_id, "government_policy_not_active")
        return self._append_commercial_inspection_policy_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            expected_revision=expected_revision,
            stream_id=stream_id,
            event_type="gameplay.government.commercial_inspection_policy_revoked",
            payload={"organization_ref": organization_ref, "policy_ref": policy_ref, "policy_revision": policy_revision},
        )

    def commercial_inspection_policy_view_for(
        self, *, organization_ref: str, scope: str, checkpoint_at: int | None = None
    ) -> GovernmentCommercialInspectionPolicyView:
        if scope != "project":
            raise ValueError("government_policy_view_scope_denied")
        stream_id = f"gameplay:government:{organization_ref}"
        events = self._store.read_stream(stream_id)
        if checkpoint_at is None:
            checkpoint_at = 0
        if checkpoint_at < 0 or checkpoint_at > len(events):
            raise ValueError("government_policy_checkpoint_out_of_range")
        active: dict[str, str] = {}
        revision = 0
        for event in events[:checkpoint_at]:
            active, revision = self._apply_commercial_inspection_policy_event(active, revision, event, organization_ref)
        for event in events[checkpoint_at:]:
            active, revision = self._apply_commercial_inspection_policy_event(active, revision, event, organization_ref)
        refs = tuple(sorted(active))
        digest_payload = {"organization_ref": organization_ref, "active_policy_refs": refs, "source_revision": revision}
        return GovernmentCommercialInspectionPolicyView(
            organization_ref=organization_ref,
            active_policy_refs=refs,
            source_revision_vector={stream_id: revision} if revision else {},
            projection_hash="sha256:" + hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _apply_commercial_inspection_policy_event(
        active: dict[str, str], revision: int, event, organization_ref: str
    ) -> tuple[dict[str, str], int]:
        payload = event.payload
        if event.event_type not in {
            "gameplay.government.commercial_inspection_policy_registered",
            "gameplay.government.commercial_inspection_policy_revoked",
        }:
            return active, revision
        if payload.get("organization_ref") != organization_ref or event.visibility_policy != "project":
            raise ValueError("government_policy_projection_invalid")
        policy_ref = payload.get("policy_ref")
        if not isinstance(policy_ref, str) or not policy_ref:
            raise ValueError("government_policy_projection_invalid")
        next_active = dict(active)
        if event.event_type.endswith("registered"):
            next_active[policy_ref] = str(payload.get("policy_revision", ""))
        else:
            next_active.pop(policy_ref, None)
        return next_active, max(revision, event.stream_revision)

    def _append_commercial_inspection_policy_event(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
        stream_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> AppendBatchResult:
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:government-inspection-policy@1",
                contract_kind="policy",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=(event_type,),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(command_id, str(exc))
        command = GameplayCommandEnvelope(
            command_id=command_id, command_type="gameplay.government.commercial_inspection_policy",
            command_version=1, principal_ref=self._PRINCIPAL, actor_ref=None, project_ref=None,
            transaction_id=f"transaction:{command_id}", idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision}, read_set_revisions={stream_id: expected_revision},
            causation_id=causation_id, correlation_id=correlation_id, source_ref="government-policy-registration",
            submitted_at="government-policy-registration", pinned_revisions={"government": expected_revision},
            payload={"stream_ref": stream_id, "event_type": event_type, "visibility_policy": "project", **payload},
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(
            outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id,
            global_sequence=0, topic="world.government.policy_projection", audience="project",
            payload_projection={"organization_ref": str(payload["organization_ref"]), "policy_ref": str(payload["policy_ref"]), "event_type": event_type},
        )]}, deep=True)
        return self._store.append_batch(batch)

    @staticmethod
    def _rejected_append(command_id: str, reason: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=reason, message=reason, failed_stage="government_policy_admission"),
        )

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
        capability_eligibility_digest: str | None = None,
        capability_consumer_plan_digest: str | None = None,
    ) -> OwnerAuthorizedFragment:
        if not evidence_ref:
            raise ValueError("inspection_evidence_required")
        if (capability_eligibility_digest is None) != (capability_consumer_plan_digest is None):
            raise ValueError("inspection_capability_provenance_incomplete")
        stream_id = f"gameplay:government:{organization_ref}"
        recorded_payload: dict[str, object] = {
            "inspection_ref": inspection_ref,
            "organization_ref": organization_ref,
            "jurisdiction_ref": jurisdiction_ref,
            "policy_revision": policy_revision,
            "policy_digest": policy_digest,
            "evidence_ref": evidence_ref,
            "passed": passed,
        }
        if capability_eligibility_digest is not None:
            recorded_payload["capability_eligibility_digest"] = capability_eligibility_digest
            recorded_payload["capability_consumer_plan_digest"] = capability_consumer_plan_digest or ""
        events: tuple[tuple[str, dict[str, object]], ...] = (
            (
                "gameplay.government.inspection_recorded",
                recorded_payload,
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

    @classmethod
    def branch_scenario_stream_id(cls, *, branch_ref: str, organization_ref: str) -> str:
        return f"{cls._BRANCH_STREAM_PREFIX}{branch_ref}:{organization_ref}"

    def _branch_inspection_admission_payload_for(
        self, *, admission_event_id: str, passed: bool
    ) -> dict[str, object]:
        try:
            event = self._store.get_event(admission_event_id)
        except KeyError as exc:
            raise ValueError("branch_scenario_admission_missing") from exc
        payload = event.payload
        expected_preview_stream = f"gameplay:branch_preview:{payload.get('branch_ref', '')}"
        if (
            event.event_type != "gameplay.branch_preview.inspection_admission_recorded"
            or event.stream_id != expected_preview_stream
            or event.visibility_policy != "creator_debug"
            or payload.get("passed") is not passed
        ):
            raise ValueError("branch_scenario_admission_invalid")
        expected_source = f"gameplay:government:{payload.get('organization_ref', '')}"
        source_revision = payload.get("source_government_revision")
        if (
            payload.get("source_stream") != expected_source
            or not isinstance(source_revision, int)
            or isinstance(source_revision, bool)
            or not all(
                isinstance(payload.get(key), str) and payload[key]
                for key in (
                    "branch_ref", "intent_ref", "base_event_digest", "candidate_digest",
                    "fragment_digest", "organization_ref", "inspection_ref", "jurisdiction_ref",
                    "policy_revision", "policy_digest", "evidence_ref",
                )
            )
            or not str(payload["branch_ref"]).startswith("branch:")
            or not str(payload["base_event_digest"]).startswith("sha256:")
            or not str(payload["candidate_digest"]).startswith("sha256:")
            or not str(payload["fragment_digest"]).startswith("sha256:")
            or not str(payload["policy_digest"]).startswith("sha256:")
        ):
            raise ValueError("branch_scenario_admission_invalid")
        return dict(payload)

    @staticmethod
    def _branch_promotion_rejected(error_code: str) -> GovernmentBranchPromotionResult:
        return GovernmentBranchPromotionResult(accepted=False, error_code=error_code)

    def _branch_promotion_receipt(
        self,
        *,
        result: AppendBatchResult,
        admission_event_id: str,
        scenario_event_id: str,
    ) -> GovernmentBranchPromotionReceipt:
        if not result.committed or len(result.committed_event_ids) != 1:
            raise ValueError("branch_promotion_receipt_unavailable")
        event = self._store.get_event(result.committed_event_ids[0])
        if (
            event.event_type != "gameplay.government.inspection_recorded"
            or event.visibility_policy != "project"
            or event.payload.get("branch_admission_event_id") != admission_event_id
            or event.payload.get("branch_scenario_event_id") != scenario_event_id
        ):
            raise ValueError("branch_promotion_receipt_invalid")
        projection = {
            "event_id": event.event_id,
            "organization_ref": event.payload.get("organization_ref"),
            "inspection_ref": event.payload.get("inspection_ref"),
            "branch_ref": event.payload.get("branch_ref"),
            "passed": event.payload.get("passed"),
        }
        return GovernmentBranchPromotionReceipt(
            transaction_id=result.transaction_id,
            committed_event_ids=tuple(result.committed_event_ids),
            production_stream=event.stream_id,
            production_revision=event.stream_revision,
            admission_event_id=admission_event_id,
            scenario_event_id=scenario_event_id,
            projection_hash="sha256:" + hashlib.sha256(
                json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            privacy_scope="project",
            idempotency_status=result.idempotency_status,
        )

    def promote_branch_inspection(
        self,
        *,
        admission_event_id: str,
        scenario_event_id: str,
        expected_production_revision: int,
        idempotency_key: str,
        privacy_scope: str,
    ) -> GovernmentBranchPromotionResult:
        """Promote one revalidated passed inspection; no other branch rows are admitted."""
        if privacy_scope != "project":
            return self._branch_promotion_rejected("branch_promotion_privacy_denied")
        try:
            admission = self._branch_inspection_admission_payload_for(
                admission_event_id=admission_event_id, passed=True
            )
            admission_event = self._store.get_event(admission_event_id)
            scenario_event = self._store.get_event(scenario_event_id)
            branch_ref = str(admission["branch_ref"])
            organization_ref = str(admission["organization_ref"])
            production_stream = f"gameplay:government:{organization_ref}"
            scenario_stream = self.branch_scenario_stream_id(
                branch_ref=branch_ref, organization_ref=organization_ref
            )
            source_revision = int(admission["source_government_revision"])
            required_matches = {
                "branch_ref": branch_ref,
                "candidate_digest": admission["candidate_digest"],
                "organization_ref": organization_ref,
                "inspection_ref": admission["inspection_ref"],
                "jurisdiction_ref": admission["jurisdiction_ref"],
                "policy_revision": admission["policy_revision"],
                "policy_digest": admission["policy_digest"],
                "evidence_ref": admission["evidence_ref"],
                "source_government_revision": source_revision,
                "admission_event_id": admission_event_id,
            }
            if (
                scenario_event.event_type != "gameplay.government.branch_inspection_recorded"
                or scenario_event.stream_id != scenario_stream
                or scenario_event.visibility_policy != "creator_debug"
                or scenario_event.payload.get("passed") is not True
                or any(scenario_event.payload.get(key) != value for key, value in required_matches.items())
            ):
                return self._branch_promotion_rejected("branch_promotion_scenario_invalid")
            existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
            if existing is not None:
                if not existing.committed or len(existing.committed_event_ids) != 1:
                    return self._branch_promotion_rejected("idempotency_key_reused")
                prior_event = self._store.get_event(existing.committed_event_ids[0])
                if (
                    expected_production_revision != source_revision
                    or prior_event.stream_id != production_stream
                    or prior_event.event_type != "gameplay.government.inspection_recorded"
                    or prior_event.payload.get("branch_admission_event_id") != admission_event_id
                    or prior_event.payload.get("branch_scenario_event_id") != scenario_event_id
                ):
                    return self._branch_promotion_rejected("idempotency_key_reused")
                replayed = existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
                return GovernmentBranchPromotionResult(
                    accepted=True,
                    receipt=self._branch_promotion_receipt(
                        result=replayed,
                        admission_event_id=admission_event_id,
                        scenario_event_id=scenario_event_id,
                    ),
                )
            if (
                self._store.get_stream_head(admission_event.stream_id) != admission_event.stream_revision
                or self._store.get_stream_head(scenario_stream) != scenario_event.stream_revision
                or self._store.get_stream_head(production_stream) != source_revision
                or expected_production_revision != source_revision
            ):
                return self._branch_promotion_rejected("branch_promotion_revision_conflict")
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:government-inspection-promotion@1",
                contract_kind="branch_promotion",
                owner_ref=self._PRINCIPAL,
                stream_ids=(production_stream,),
                event_types=("gameplay.government.inspection_recorded",),
                projection_scope="project",
            )
            fragment = self.build_commercial_inspection_fragment(
                inspection_ref=str(admission["inspection_ref"]),
                organization_ref=organization_ref,
                jurisdiction_ref=str(admission["jurisdiction_ref"]),
                policy_revision=str(admission["policy_revision"]),
                policy_digest=str(admission["policy_digest"]),
                evidence_ref=str(admission["evidence_ref"]),
                passed=True,
            )
            event_type, event_payload = fragment.event_specs[production_stream][0]
            promoted_payload = {
                **event_payload,
                "branch_ref": branch_ref,
                "branch_admission_event_id": admission_event_id,
                "branch_scenario_event_id": scenario_event_id,
                "branch_candidate_digest": admission["candidate_digest"],
            }
            read_revisions = {
                admission_event.stream_id: admission_event.stream_revision,
                scenario_stream: scenario_event.stream_revision,
                production_stream: source_revision,
            }
            command_id = f"branch-promotion:{branch_ref}:{admission['inspection_ref']}"
            command = GameplayCommandEnvelope(
                command_id=command_id,
                command_type="gameplay.government.promote_branch_inspection",
                command_version=1,
                principal_ref=self._PRINCIPAL,
                actor_ref=None,
                project_ref=None,
                transaction_id=f"transaction:{command_id}",
                idempotency_key=idempotency_key,
                expected_revisions={production_stream: source_revision},
                read_set_revisions=read_revisions,
                causation_id=str(admission["candidate_digest"]),
                correlation_id=f"branch-promotion:{branch_ref}:{admission['inspection_ref']}",
                source_ref="branch-preview-admission",
                submitted_at="branch-promotion",
                pinned_revisions={
                    "government": source_revision,
                    "branch_preview_admission": admission_event.stream_revision,
                    "branch_government_scenario": scenario_event.stream_revision,
                },
                payload={
                    "stream_ref": production_stream,
                    "event_type": event_type,
                    "visibility_policy": "project",
                    **promoted_payload,
                },
            )
            batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
            fragment = fragment.model_copy(
                update={
                    "fragment_id": f"{fragment.fragment_id}:branch-promotion:{branch_ref}",
                    "expected_revisions": {production_stream: source_revision},
                    "read_set_revisions": read_revisions,
                    "pinned_revisions": dict(command.pinned_revisions),
                    "event_specs": {production_stream: ((event_type, promoted_payload),)},
                    "event_visibility_policies": {production_stream: ("project",)},
                },
                deep=True,
            )
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "owner_fragments": [fragment],
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.government.inspection_projection",
                            audience="project",
                            payload_projection={
                                "organization_ref": organization_ref,
                                "inspection_ref": str(admission["inspection_ref"]),
                                "branch_ref": branch_ref,
                            },
                        )
                    ],
                },
                deep=True,
            )
            result = self._store.append_batch(batch)
            if not result.committed:
                return self._branch_promotion_rejected(
                    result.failure.error_code if result.failure is not None else "branch_promotion_append_rejected"
                )
            return GovernmentBranchPromotionResult(
                accepted=True,
                receipt=self._branch_promotion_receipt(
                    result=result,
                    admission_event_id=admission_event_id,
                    scenario_event_id=scenario_event_id,
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return self._branch_promotion_rejected(str(exc) or "branch_promotion_source_invalid")

    def promote_failed_branch_inspection(
        self,
        *,
        admission_event_id: str,
        scenario_event_id: str,
        expected_production_revision: int,
        idempotency_key: str,
        privacy_scope: str,
    ) -> GovernmentBranchPromotionResult:
        """Promote one revalidated failed inspection; no other branch rows are admitted."""
        if privacy_scope != "project":
            return self._branch_promotion_rejected("branch_promotion_privacy_denied")
        try:
            admission = self._branch_inspection_admission_payload_for(
                admission_event_id=admission_event_id, passed=False
            )
            admission_event = self._store.get_event(admission_event_id)
            scenario_event = self._store.get_event(scenario_event_id)
            branch_ref = str(admission["branch_ref"])
            organization_ref = str(admission["organization_ref"])
            production_stream = f"gameplay:government:{organization_ref}"
            scenario_stream = self.branch_scenario_stream_id(
                branch_ref=branch_ref, organization_ref=organization_ref
            )
            source_revision = int(admission["source_government_revision"])
            remediation_ref = f"branch-remediation:{branch_ref}:{admission['inspection_ref']}"
            required_matches = {
                "branch_ref": branch_ref,
                "candidate_digest": admission["candidate_digest"],
                "organization_ref": organization_ref,
                "inspection_ref": admission["inspection_ref"],
                "jurisdiction_ref": admission["jurisdiction_ref"],
                "policy_revision": admission["policy_revision"],
                "policy_digest": admission["policy_digest"],
                "evidence_ref": admission["evidence_ref"],
                "source_government_revision": source_revision,
                "admission_event_id": admission_event_id,
                "remediation_ref": remediation_ref,
                "remediation_action": "follow_up_required",
            }
            if (
                scenario_event.event_type
                != "gameplay.government.branch_inspection_remediation_recorded"
                or scenario_event.stream_id != scenario_stream
                or scenario_event.visibility_policy != "creator_debug"
                or scenario_event.payload.get("passed") is not False
                or any(
                    scenario_event.payload.get(key) != value
                    for key, value in required_matches.items()
                )
            ):
                return self._branch_promotion_rejected("branch_promotion_scenario_invalid")
            existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
            if existing is not None:
                if not existing.committed or len(existing.committed_event_ids) != 1:
                    return self._branch_promotion_rejected("idempotency_key_reused")
                prior_event = self._store.get_event(existing.committed_event_ids[0])
                if (
                    expected_production_revision != source_revision
                    or prior_event.stream_id != production_stream
                    or prior_event.event_type != "gameplay.government.inspection_recorded"
                    or prior_event.payload.get("branch_admission_event_id") != admission_event_id
                    or prior_event.payload.get("branch_scenario_event_id") != scenario_event_id
                    or prior_event.payload.get("passed") is not False
                ):
                    return self._branch_promotion_rejected("idempotency_key_reused")
                replayed = existing.model_copy(
                    update={"idempotency_status": "duplicate_replayed"}, deep=True
                )
                return GovernmentBranchPromotionResult(
                    accepted=True,
                    receipt=self._branch_promotion_receipt(
                        result=replayed,
                        admission_event_id=admission_event_id,
                        scenario_event_id=scenario_event_id,
                    ),
                )
            if (
                self._store.get_stream_head(admission_event.stream_id) != admission_event.stream_revision
                or self._store.get_stream_head(scenario_stream) != scenario_event.stream_revision
                or self._store.get_stream_head(production_stream) != source_revision
                or expected_production_revision != source_revision
            ):
                return self._branch_promotion_rejected("branch_promotion_revision_conflict")
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:government-failed-inspection-promotion@1",
                contract_kind="branch_promotion",
                owner_ref=self._PRINCIPAL,
                stream_ids=(production_stream,),
                event_types=("gameplay.government.inspection_recorded",),
                projection_scope="project",
            )
            fragment = self.build_commercial_inspection_fragment(
                inspection_ref=str(admission["inspection_ref"]),
                organization_ref=organization_ref,
                jurisdiction_ref=str(admission["jurisdiction_ref"]),
                policy_revision=str(admission["policy_revision"]),
                policy_digest=str(admission["policy_digest"]),
                evidence_ref=str(admission["evidence_ref"]),
                passed=False,
            )
            event_type, event_payload = fragment.event_specs[production_stream][0]
            promoted_payload = {
                **event_payload,
                "branch_ref": branch_ref,
                "branch_admission_event_id": admission_event_id,
                "branch_scenario_event_id": scenario_event_id,
                "branch_candidate_digest": admission["candidate_digest"],
            }
            read_revisions = {
                admission_event.stream_id: admission_event.stream_revision,
                scenario_stream: scenario_event.stream_revision,
                production_stream: source_revision,
            }
            command_id = f"branch-failed-promotion:{branch_ref}:{admission['inspection_ref']}"
            command = GameplayCommandEnvelope(
                command_id=command_id,
                command_type="gameplay.government.promote_failed_branch_inspection",
                command_version=1,
                principal_ref=self._PRINCIPAL,
                actor_ref=None,
                project_ref=None,
                transaction_id=f"transaction:{command_id}",
                idempotency_key=idempotency_key,
                expected_revisions={production_stream: source_revision},
                read_set_revisions=read_revisions,
                causation_id=str(admission["candidate_digest"]),
                correlation_id=f"branch-failed-promotion:{branch_ref}:{admission['inspection_ref']}",
                source_ref="branch-preview-admission",
                submitted_at="branch-promotion",
                pinned_revisions={
                    "government": source_revision,
                    "branch_preview_admission": admission_event.stream_revision,
                    "branch_government_scenario": scenario_event.stream_revision,
                },
                payload={
                    "stream_ref": production_stream,
                    "event_type": event_type,
                    "visibility_policy": "project",
                    **promoted_payload,
                },
            )
            batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
            fragment = fragment.model_copy(
                update={
                    "fragment_id": f"{fragment.fragment_id}:branch-failed-promotion:{branch_ref}",
                    "expected_revisions": {production_stream: source_revision},
                    "read_set_revisions": read_revisions,
                    "pinned_revisions": dict(command.pinned_revisions),
                    "event_specs": {production_stream: ((event_type, promoted_payload),)},
                    "event_visibility_policies": {production_stream: ("project",)},
                },
                deep=True,
            )
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "owner_fragments": [fragment],
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.government.inspection_projection",
                            audience="project",
                            payload_projection={
                                "organization_ref": organization_ref,
                                "inspection_ref": str(admission["inspection_ref"]),
                                "branch_ref": branch_ref,
                            },
                        )
                    ],
                },
                deep=True,
            )
            result = self._store.append_batch(batch)
            if not result.committed:
                return self._branch_promotion_rejected(
                    result.failure.error_code
                    if result.failure is not None
                    else "branch_promotion_append_rejected"
                )
            return GovernmentBranchPromotionResult(
                accepted=True,
                receipt=self._branch_promotion_receipt(
                    result=result,
                    admission_event_id=admission_event_id,
                    scenario_event_id=scenario_event_id,
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return self._branch_promotion_rejected(
                str(exc) or "branch_promotion_source_invalid"
            )

    def settle_branch_inspection(
        self,
        *,
        admission_event_id: str,
        expected_revision: int,
        idempotency_key: str,
        correlation_id: str,
        privacy_scope: str,
    ):
        """Append one passed inspection to Government's non-production branch stream."""
        admission = self._branch_inspection_admission_payload_for(
            admission_event_id=admission_event_id, passed=True
        )
        if privacy_scope != "creator_debug":
            raise ValueError("branch_scenario_privacy_denied")
        branch_ref = str(admission["branch_ref"])
        base_event_digest = str(admission["base_event_digest"])
        candidate_digest = str(admission["candidate_digest"])
        organization_ref = str(admission["organization_ref"])
        inspection_ref = str(admission["inspection_ref"])
        jurisdiction_ref = str(admission["jurisdiction_ref"])
        policy_revision = str(admission["policy_revision"])
        policy_digest = str(admission["policy_digest"])
        evidence_ref = str(admission["evidence_ref"])
        source_government_revision = int(admission["source_government_revision"])
        production_stream = f"gameplay:government:{organization_ref}"
        scenario_stream = self.branch_scenario_stream_id(branch_ref=branch_ref, organization_ref=organization_ref)
        command_id = f"branch-scenario:{branch_ref}:{inspection_ref}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.government.settle_branch_inspection",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={scenario_stream: expected_revision},
            read_set_revisions={production_stream: source_government_revision},
            causation_id=candidate_digest,
            correlation_id=correlation_id,
            source_ref="branch_preview",
            submitted_at="branch-scenario",
            pinned_revisions={"government_source": source_government_revision},
            payload={
                "stream_ref": scenario_stream,
                "event_type": "gameplay.government.branch_inspection_recorded",
                "visibility_policy": privacy_scope,
                "branch_ref": branch_ref,
                "base_event_digest": base_event_digest,
                "candidate_digest": candidate_digest,
                "organization_ref": organization_ref,
                "inspection_ref": inspection_ref,
                "jurisdiction_ref": jurisdiction_ref,
                "policy_revision": policy_revision,
                "policy_digest": policy_digest,
                "evidence_ref": evidence_ref,
                "passed": True,
                "source_government_revision": source_government_revision,
                "admission_event_id": admission_event_id,
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.government_branch.scenario_projection",
                        audience=privacy_scope,
                        payload_projection={"branch_ref": branch_ref, "organization_ref": organization_ref, "inspection_ref": inspection_ref},
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def settle_branch_inspection_remediation(
        self,
        *,
        admission_event_id: str,
        expected_revision: int,
        idempotency_key: str,
        correlation_id: str,
        privacy_scope: str,
    ):
        """Record one fixed failed-inspection remediation on Government's scenario stream."""
        admission = self._branch_inspection_admission_payload_for(
            admission_event_id=admission_event_id, passed=False
        )
        if privacy_scope != "creator_debug":
            raise ValueError("branch_scenario_privacy_denied")
        branch_ref = str(admission["branch_ref"])
        base_event_digest = str(admission["base_event_digest"])
        candidate_digest = str(admission["candidate_digest"])
        organization_ref = str(admission["organization_ref"])
        inspection_ref = str(admission["inspection_ref"])
        jurisdiction_ref = str(admission["jurisdiction_ref"])
        policy_revision = str(admission["policy_revision"])
        policy_digest = str(admission["policy_digest"])
        evidence_ref = str(admission["evidence_ref"])
        source_government_revision = int(admission["source_government_revision"])
        remediation_ref = f"branch-remediation:{branch_ref}:{inspection_ref}"
        production_stream = f"gameplay:government:{organization_ref}"
        scenario_stream = self.branch_scenario_stream_id(
            branch_ref=branch_ref, organization_ref=organization_ref
        )
        command_id = f"branch-remediation:{branch_ref}:{inspection_ref}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.government.settle_branch_inspection_remediation",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={scenario_stream: expected_revision},
            read_set_revisions={production_stream: source_government_revision},
            causation_id=candidate_digest,
            correlation_id=correlation_id,
            source_ref="branch_preview",
            submitted_at="branch-scenario",
            pinned_revisions={"government_source": source_government_revision},
            payload={
                "stream_ref": scenario_stream,
                "event_type": "gameplay.government.branch_inspection_remediation_recorded",
                "visibility_policy": privacy_scope,
                "branch_ref": branch_ref,
                "base_event_digest": base_event_digest,
                "candidate_digest": candidate_digest,
                "organization_ref": organization_ref,
                "inspection_ref": inspection_ref,
                "remediation_ref": remediation_ref,
                "remediation_action": "follow_up_required",
                "jurisdiction_ref": jurisdiction_ref,
                "policy_revision": policy_revision,
                "policy_digest": policy_digest,
                "evidence_ref": evidence_ref,
                "passed": False,
                "source_government_revision": source_government_revision,
                "admission_event_id": admission_event_id,
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.government_branch.scenario_projection",
                        audience=privacy_scope,
                        payload_projection={
                            "branch_ref": branch_ref,
                            "organization_ref": organization_ref,
                            "inspection_ref": inspection_ref,
                            "remediation_ref": remediation_ref,
                            "remediation_action": "follow_up_required",
                        },
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def branch_scenario_projection(
        self, *, branch_ref: str, organization_ref: str, checkpoint_at: int | None = None
    ) -> dict[str, object]:
        stream_id = self.branch_scenario_stream_id(branch_ref=branch_ref, organization_ref=organization_ref)
        events = self._store.read_stream(stream_id)
        if checkpoint_at is None:
            checkpoint_at = 0
        if checkpoint_at < 0 or checkpoint_at > len(events):
            raise ValueError("branch_scenario_checkpoint_out_of_range")

        def apply(
            state: tuple[tuple[str, ...], tuple[str, ...]], event
        ) -> tuple[tuple[str, ...], tuple[str, ...]]:
            event_payload = event.payload
            if event_payload.get("branch_ref") != branch_ref or event_payload.get("organization_ref") != organization_ref:
                raise ValueError("branch_scenario_projection_invalid")
            if event.event_type == "gameplay.government.branch_inspection_recorded":
                inspection_ref = event_payload.get("inspection_ref")
                if not isinstance(inspection_ref, str) or not inspection_ref or event_payload.get("passed") is not True:
                    raise ValueError("branch_scenario_projection_invalid")
                return (state[0] + (inspection_ref,), state[1])
            if event.event_type == "gameplay.government.branch_inspection_remediation_recorded":
                remediation_ref = event_payload.get("remediation_ref")
                if (
                    not isinstance(remediation_ref, str)
                    or not remediation_ref
                    or event_payload.get("passed") is not False
                    or event_payload.get("remediation_action") != "follow_up_required"
                ):
                    raise ValueError("branch_scenario_projection_invalid")
                return (state[0], state[1] + (remediation_ref,))
            raise ValueError("branch_scenario_projection_invalid")

        state: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())
        for event in events[:checkpoint_at]:
            state = apply(state, event)
        checkpoint = state
        for event in events[checkpoint_at:]:
            checkpoint = apply(checkpoint, event)
        projection = {
            "branch_ref": branch_ref,
            "organization_ref": organization_ref,
            "inspection_refs": checkpoint[0],
            "remediation_refs": checkpoint[1],
        }
        projection["projection_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return projection

    def branch_remediation_receipt_for(
        self, *, event_id: str, privacy_scope: str
    ) -> BranchScenarioReceipt:
        if privacy_scope != "creator_debug":
            raise ValueError("branch_remediation_receipt_privacy_denied")
        try:
            event = self._store.get_event(event_id)
        except KeyError as exc:
            raise ValueError("branch_remediation_receipt_event_invalid") from exc
        payload = event.payload
        if (
            event.event_type != "gameplay.government.branch_inspection_remediation_recorded"
            or not event.stream_id.startswith(self._BRANCH_STREAM_PREFIX)
            or payload.get("passed") is not False
        ):
            raise ValueError("branch_remediation_receipt_event_invalid")
        branch_ref = payload.get("branch_ref")
        organization_ref = payload.get("organization_ref")
        source_revision = payload.get("source_government_revision")
        if (
            not isinstance(branch_ref, str)
            or not isinstance(organization_ref, str)
            or isinstance(source_revision, bool)
            or not isinstance(source_revision, int)
        ):
            raise ValueError("branch_remediation_receipt_event_invalid")
        projection = self.branch_scenario_projection(
            branch_ref=branch_ref, organization_ref=organization_ref
        )
        return BranchScenarioReceipt(
            transaction_id=event.transaction_id,
            committed_event_ids=(event.event_id,),
            scenario_stream=event.stream_id,
            scenario_revision=event.stream_revision,
            source_government_revision=source_revision,
            projection_hash=str(projection["projection_hash"]),
            privacy_scope=privacy_scope,
            idempotency_status="new_commit",
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
            return existing.model_copy(
                update={"idempotency_status": "duplicate_replayed"}, deep=True
            )
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
    _BRANCH_STREAM_PREFIX = "gameplay:organization_branch:"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    @staticmethod
    def _weather_front_supply_rejected(command_id: str, reason: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=reason,
                message=reason,
                failed_stage="organization_weather_front_admission",
            ),
        )

    @staticmethod
    def _organization_window_rejected(
        command_id: str, reason: str
    ) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=reason,
                message=reason,
                failed_stage="organization_operating_window",
            ),
        )

    @classmethod
    def _operating_window_contract_error(
        cls, *, stream_id: str, event_type: str, visibility_scope: str
    ) -> str | None:
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:organization-operating-window@1",
                contract_kind="lifecycle",
                owner_ref=cls._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=(event_type,),
                projection_scope="mixed",
            )
        except GovernedAuthorityContractError as error:
            return str(error)
        return None

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
            return existing.model_copy(
                update={"idempotency_status": "duplicate_replayed"}, deep=True
            )
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

    def open_operating_window(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        window: object,
        visibility_scope: str,
    ) -> AppendBatchResult:
        if visibility_scope not in {"project", "authority_only"}:
            return self._organization_window_rejected(
                command_id, "organization_window_visibility_invalid"
            )
        window_ref = str(getattr(window, "window_ref", ""))
        organization_ref = str(getattr(window, "organization_ref", ""))
        opens_at_tick = getattr(window, "opens_at_tick", None)
        closes_at_tick = getattr(window, "closes_at_tick", None)
        policy_revision = str(getattr(window, "policy_revision", ""))
        source_revision = str(getattr(window, "source_revision", ""))
        status = str(getattr(window, "status", ""))
        if (
            not window_ref
            or not organization_ref.startswith("org:")
            or not isinstance(opens_at_tick, int)
            or not isinstance(closes_at_tick, int)
            or closes_at_tick < opens_at_tick
            or not policy_revision
            or not source_revision
            or status not in {"planned", "open"}
        ):
            return self._organization_window_rejected(
                command_id, "organization_operating_window_invalid"
            )
        stream_id = f"gameplay:organization:window:{window_ref}"
        contract_error = self._operating_window_contract_error(
            stream_id=stream_id,
            event_type="gameplay.organization.operating_window_opened",
            visibility_scope=visibility_scope,
        )
        if contract_error is not None:
            return self._organization_window_rejected(command_id, contract_error)
        current = self._operating_window_state(window_ref)
        if current["status"] != "missing" and int(current["stream_revision"]) == 0:
            return self._organization_window_rejected(
                command_id, "organization_operating_window_already_opened"
            )
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.organization.open_operating_window",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: 0},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=self._PRINCIPAL,
            submitted_at=f"tick:{opens_at_tick}",
            pinned_revisions={"organization_window_policy": 1},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.organization.operating_window_opened",
                "visibility_policy": visibility_scope,
                "window_ref": window_ref,
                "organization_ref": organization_ref,
                "opens_at_tick": opens_at_tick,
                "closes_at_tick": closes_at_tick,
                "policy_revision": policy_revision,
                "source_revision": source_revision,
                "status": "open",
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(
            command
        ).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.organization_window.scoped_projection",
                        audience=visibility_scope,
                        payload_projection={
                            "organization_ref": organization_ref,
                            "window_ref": window_ref,
                            "status": "open",
                        },
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def close_operating_window(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        organization_ref: str,
        window_ref: str,
        expected_stream_revision: int,
        visibility_scope: str,
    ) -> AppendBatchResult:
        if visibility_scope not in {"project", "authority_only"}:
            return self._organization_window_rejected(
                command_id, "organization_window_visibility_invalid"
            )
        if (
            not organization_ref.startswith("org:")
            or not window_ref
            or expected_stream_revision < 0
        ):
            return self._organization_window_rejected(
                command_id, "organization_operating_window_invalid"
            )
        current = self._operating_window_state(window_ref)
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if (
            existing is None
            and (
                not current["organization_ref"]
                or current["organization_ref"] != organization_ref
                or current["opens_at_tick"] is None
                or current["closes_at_tick"] is None
                or not current["policy_revision"]
                or not current["source_revision"]
            )
        ):
            return self._organization_window_rejected(
                command_id, "organization_operating_window_not_open"
            )
        if (
            existing is None
            and (
            current["status"] != "open"
            and expected_stream_revision == int(current["stream_revision"])
            )
        ):
            return self._organization_window_rejected(
                command_id, "organization_operating_window_not_open"
            )
        stream_id = f"gameplay:organization:window:{window_ref}"
        contract_error = self._operating_window_contract_error(
            stream_id=stream_id,
            event_type="gameplay.organization.operating_window_closed",
            visibility_scope=visibility_scope,
        )
        if contract_error is not None:
            return self._organization_window_rejected(command_id, contract_error)
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.organization.close_operating_window",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_stream_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=self._PRINCIPAL,
            submitted_at=f"tick:{current['closes_at_tick']}",
            pinned_revisions={"organization_window_policy": 1},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.organization.operating_window_closed",
                "visibility_policy": visibility_scope,
                "window_ref": window_ref,
                "organization_ref": organization_ref,
                "opens_at_tick": current["opens_at_tick"],
                "closes_at_tick": current["closes_at_tick"],
                "policy_revision": current["policy_revision"],
                "source_revision": current["source_revision"],
                "status": "closed",
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(
            command
        ).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.organization_window.scoped_projection",
                        audience=visibility_scope,
                        payload_projection={
                            "organization_ref": organization_ref,
                            "window_ref": window_ref,
                            "status": "closed",
                        },
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def record_operating_window_due(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        organization_ref: str,
        window_ref: str,
        expected_stream_revision: int,
        visibility_scope: str,
    ) -> AppendBatchResult:
        if visibility_scope not in {"project", "authority_only"}:
            return self._organization_window_rejected(
                command_id, "organization_window_visibility_invalid"
            )
        if (
            not organization_ref.startswith("org:")
            or not window_ref
            or expected_stream_revision < 0
        ):
            return self._organization_window_rejected(
                command_id, "organization_operating_window_invalid"
            )
        current = self._operating_window_state(window_ref)
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if (
            existing is None
            and (
                not current["organization_ref"]
                or current["organization_ref"] != organization_ref
            )
        ):
            return self._organization_window_rejected(
                command_id, "organization_operating_window_not_closed"
            )
        if existing is None and current["status"] != "closed":
            return self._organization_window_rejected(
                command_id, "organization_operating_window_not_closed"
            )
        if (
            existing is None
            and (
            current["due_recorded"]
            and expected_stream_revision == int(current["stream_revision"])
            )
        ):
            return self._organization_window_rejected(
                command_id, "organization_operating_window_due_already_recorded"
            )
        stream_id = f"gameplay:organization:window:{window_ref}"
        contract_error = self._operating_window_contract_error(
            stream_id=stream_id,
            event_type="gameplay.organization.operating_window_due_recorded",
            visibility_scope=visibility_scope,
        )
        if contract_error is not None:
            return self._organization_window_rejected(command_id, contract_error)
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.organization.record_operating_window_due",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_stream_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=self._PRINCIPAL,
            submitted_at=f"tick:{current['closes_at_tick']}",
            pinned_revisions={"organization_window_policy": 1},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.organization.operating_window_due_recorded",
                "visibility_policy": visibility_scope,
                "window_ref": window_ref,
                "organization_ref": organization_ref,
                "status": "closed",
                "due_state": "recorded",
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(
            command
        ).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.organization_window.scoped_projection",
                        audience=visibility_scope,
                        payload_projection={
                            "organization_ref": organization_ref,
                            "window_ref": window_ref,
                            "status": "closed",
                            "due_recorded": True,
                        },
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def record_schedule(
        self,
        *,
        command_id: str,
        organization_ref: str,
        recipient_ref: str,
        membership_ref: str,
        assignment_ref: str,
        role: str,
        shift_ref: str,
        operating_window_ref: str,
        work_order_ref: str,
        effective_from: str,
        effective_to: str | None,
        visibility_scope: str,
    ):
        if not organization_ref.startswith("org:") or not recipient_ref.startswith("character:"):
            raise ValueError("organization_schedule_reference_invalid")
        if any(not value for value in (membership_ref, assignment_ref, role, shift_ref, operating_window_ref, work_order_ref, effective_from)):
            raise ValueError("organization_schedule_invalid")
        if visibility_scope not in {"public", "organization:summary", f"actor:{recipient_ref}", "authority_only"}:
            raise ValueError("organization_schedule_visibility_invalid")
        stream_id = f"gameplay:organization:{organization_ref}"
        payload = {
            "organization_ref": organization_ref,
            "recipient_ref": recipient_ref,
            "membership_ref": membership_ref,
            "assignment_ref": assignment_ref,
            "role": role,
            "shift_ref": shift_ref,
            "operating_window_ref": operating_window_ref,
            "work_order_ref": work_order_ref,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "visibility_scope": visibility_scope,
        }
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.organization.record_schedule",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=recipient_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=f"idempotency:{command_id}",
            expected_revisions={stream_id: self._store.get_stream_head(stream_id)},
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{organization_ref}",
            source_ref=self._PRINCIPAL,
            submitted_at=effective_from,
            pinned_revisions={"organization:schedule": 1},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.organization.membership_recorded",
                "event_specs": [
                    {"event_type": "gameplay.organization.membership_recorded", "payload": payload},
                    {"event_type": "gameplay.organization.role_term_recorded", "payload": payload},
                    {"event_type": "gameplay.organization.shift_offer_recorded", "payload": payload},
                    {"event_type": "gameplay.organization.work_order_recorded", "payload": payload},
                ],
                "visibility_policy": visibility_scope,
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.organization_schedule.scoped_projection",
                        audience=visibility_scope,
                        payload_projection={"organization_ref": organization_ref, "recipient_ref": recipient_ref},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def schedule_view_for(
        self,
        *,
        organization_ref: str,
        recipient_ref: str,
        observed_at: str,
    ) -> OrganizationScheduleRecipientView:
        stream_id = f"gameplay:organization:{organization_ref}"
        rows: dict[str, list[dict[str, object]]] = {
            "membership": [],
            "role": [],
            "shift": [],
            "work_order": [],
        }
        event_row = {
            "gameplay.organization.membership_recorded": "membership",
            "gameplay.organization.role_term_recorded": "role",
            "gameplay.organization.shift_offer_recorded": "shift",
            "gameplay.organization.work_order_recorded": "work_order",
        }
        revision = 0
        for event in self._store.read_stream(stream_id):
            key = event_row.get(event.event_type)
            if key is None:
                continue
            payload = event.payload
            visibility = str(payload.get("visibility_scope", ""))
            try:
                observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                effective_from = datetime.fromisoformat(str(payload.get("effective_from", "")).replace("Z", "+00:00"))
                effective_to_raw = payload.get("effective_to")
                effective_to = datetime.fromisoformat(str(effective_to_raw).replace("Z", "+00:00")) if effective_to_raw else None
            except ValueError:
                continue
            if observed < effective_from or (effective_to is not None and observed >= effective_to):
                continue
            if not self._schedule_visible(visibility=visibility, recipient_ref=recipient_ref):
                continue
            if str(payload.get("recipient_ref")) != recipient_ref and visibility not in {"public", "organization:summary"}:
                continue
            row = dict(payload)
            if visibility == "organization:summary" and str(payload.get("recipient_ref")) != recipient_ref:
                row = {"organization_ref": organization_ref, "visibility_scope": visibility}
            rows[key].append(row)
            revision = max(revision, event.stream_revision)
        for values in rows.values():
            values.sort(key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), default=str))
        vector = {stream_id: revision} if revision else {}
        projection = {"organization_ref": organization_ref, "recipient_ref": recipient_ref, "observed_at": observed_at, "rows": rows, "source_revision_vector": vector}
        return OrganizationScheduleRecipientView(
            owner_principal_ref=self._PRINCIPAL,
            organization_ref=organization_ref,
            organization_memberships=tuple(rows["membership"]),
            role_terms=tuple(rows["role"]),
            shift_offers=tuple(rows["shift"]),
            work_orders=tuple(rows["work_order"]),
            source_revision_vector=vector,
            projection_hash="sha256:" + hashlib.sha256(json.dumps(projection, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest(),
        )

    def operating_window_view_for(
        self, *, window_ref: str, recipient_ref: str
    ) -> OrganizationOperatingWindowView:
        state = self._operating_window_state(window_ref)
        visibility_scope = str(state["visibility_scope"])
        stream_id = f"gameplay:organization:window:{window_ref}"
        visible = self._window_visible(
            visibility=visibility_scope, recipient_ref=recipient_ref
        )
        source_revision = (
            {stream_id: int(state["stream_revision"])}
            if visible and int(state["stream_revision"]) > 0
            else {}
        )
        projection = {
            "organization_ref": state["organization_ref"] if visible else "",
            "window_ref": window_ref,
            "status": state["status"] if visible else "missing",
            "due_recorded": bool(state["due_recorded"]) if visible else False,
            "opens_at_tick": state["opens_at_tick"] if visible else None,
            "closes_at_tick": state["closes_at_tick"] if visible else None,
            "visibility_scope": visibility_scope if visible else "",
            "source_revision_vector": source_revision,
        }
        return OrganizationOperatingWindowView(
            owner_principal_ref=self._PRINCIPAL,
            organization_ref=str(projection["organization_ref"]),
            window_ref=window_ref,
            status=str(projection["status"]),
            due_recorded=bool(projection["due_recorded"]),
            opens_at_tick=projection["opens_at_tick"],
            closes_at_tick=projection["closes_at_tick"],
            visibility_scope=str(projection["visibility_scope"]),
            source_revision_vector=source_revision,
            projection_hash="sha256:"
            + hashlib.sha256(
                json.dumps(
                    projection, sort_keys=True, separators=(",", ":"), default=str
                ).encode("utf-8")
            ).hexdigest(),
        )

    @staticmethod
    def _schedule_visible(*, visibility: str, recipient_ref: str) -> bool:
        return visibility in {"public", "organization:summary"} or visibility == f"actor:{recipient_ref}" or (visibility == "authority_only" and recipient_ref.startswith("authority:"))

    @staticmethod
    def _window_visible(*, visibility: str, recipient_ref: str) -> bool:
        return visibility == "project" or (
            visibility == "authority_only" and recipient_ref.startswith("authority:")
        )

    def _operating_window_state(self, window_ref: str) -> dict[str, object]:
        stream_id = f"gameplay:organization:window:{window_ref}"
        state: dict[str, object] = {
            "organization_ref": "",
            "status": "missing",
            "due_recorded": False,
            "opens_at_tick": None,
            "closes_at_tick": None,
            "policy_revision": "",
            "source_revision": "",
            "visibility_scope": "",
            "stream_revision": 0,
        }
        for event in self._store.read_stream(stream_id):
            payload = event.payload
            state["organization_ref"] = str(
                payload.get("organization_ref", state["organization_ref"])
            )
            state["visibility_scope"] = str(
                payload.get("visibility_policy", state["visibility_scope"])
            )
            state["stream_revision"] = event.stream_revision
            if event.event_type == "gameplay.organization.operating_window_opened":
                state["status"] = "open"
                state["due_recorded"] = False
                state["opens_at_tick"] = payload.get("opens_at_tick")
                state["closes_at_tick"] = payload.get("closes_at_tick")
                state["policy_revision"] = str(payload.get("policy_revision", ""))
                state["source_revision"] = str(payload.get("source_revision", ""))
            elif event.event_type == "gameplay.organization.operating_window_closed":
                state["status"] = "closed"
            elif event.event_type == "gameplay.organization.operating_window_due_recorded":
                state["due_recorded"] = True
        return state

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

    def commerce_commitment_projection(
        self, *, organization_ref: str, checkpoint_at: int | None = None
    ) -> dict[str, object]:
        """Replay the existing Organization commerce-commitment projection."""
        stream_id = f"gameplay:organization:{organization_ref}"
        events = self._store.read_stream(stream_id)
        checkpoint_at = 0 if checkpoint_at is None else checkpoint_at
        if checkpoint_at < 0 or checkpoint_at > len(events):
            raise ValueError("organization_commitment_checkpoint_out_of_range")

        def apply(commitments: tuple[str, ...], event) -> tuple[str, ...]:
            if event.event_type != "gameplay.organization.commerce_commitment_accepted":
                return commitments
            if event.payload.get("organization_ref") != organization_ref:
                raise ValueError("organization_commitment_projection_invalid")
            commitment_ref = event.payload.get("commitment_ref")
            if not isinstance(commitment_ref, str) or not commitment_ref:
                raise ValueError("organization_commitment_projection_invalid")
            return commitments + (commitment_ref,)

        state: tuple[str, ...] = ()
        for event in events[:checkpoint_at]:
            state = apply(state, event)
        for event in events[checkpoint_at:]:
            state = apply(state, event)
        projection = {"organization_ref": organization_ref, "commitment_refs": state, "source_revision": len(events)}
        projection["projection_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return projection

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
        capability_eligibility_digest: str | None = None,
        capability_consumer_plan_digest: str | None = None,
    ) -> OwnerAuthorizedFragment:
        """Validate organization-owned authorization/budget pins for P4B."""
        if not organization_ref or not commitment_ref or not counterparty_organization_ref:
            raise ValueError("commerce_organization_reference_invalid")
        if any(not ref.startswith("grant:") for ref in organization_grant_refs):
            raise ValueError("commerce_organization_grant_invalid")
        if any(not ref.startswith("reservation:") for ref in budget_reservation_refs):
            raise ValueError("commerce_budget_reservation_invalid")
        if capability_eligibility_digest is not None and not capability_eligibility_digest.startswith("sha256:"):
            raise ValueError("commerce_capability_eligibility_digest_invalid")
        if capability_consumer_plan_digest is not None and not capability_consumer_plan_digest.startswith("sha256:"):
            raise ValueError("commerce_capability_consumer_plan_digest_invalid")
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
                            "owner_principal_ref": self._PRINCIPAL,
                            **(
                                {"capability_eligibility_digest": capability_eligibility_digest}
                                if capability_eligibility_digest is not None
                                else {}
                            ),
                            **(
                                {"capability_consumer_plan_digest": capability_consumer_plan_digest}
                                if capability_consumer_plan_digest is not None
                                else {}
                            ),
                        },
                    ),
                )
            },
        )

    def settle_canonical_weather_front_supply(
        self,
        *,
        command: object,
        admission: object | None,
        expected_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str,
    ) -> AppendBatchResult:
        """Settle one fixed Ecology weather-front supply response on the Organization owner."""
        command_id = str(getattr(command, "command_id", "organization:weather-front:supply"))
        edge_ref = "ecology-weather:front-to-organization-supply:v1"
        if (
            admission is None
            or not _CONTAINS_CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_ADMISSION(admission)
            or getattr(admission, "edge_ref", None) != edge_ref
            or getattr(admission, "weather_event_id", None) != getattr(command, "weather_event_id", None)
            or getattr(admission, "organization_ref", None) != getattr(command, "organization_ref", None)
            or getattr(admission, "commitment_ref", None) != getattr(command, "commitment_ref", None)
        ):
            return self._weather_front_supply_rejected(command_id, "weather_front_organization_admission_required")
        if privacy_scope != "project" or getattr(command, "privacy_scope", None) != "project":
            return self._weather_front_supply_rejected(command_id, "weather_front_organization_privacy_denied")
        if (
            getattr(command, "edge_ref", None) != edge_ref
            or getattr(command, "source_authority_ref", None) != "authority:ecology"
            or not isinstance(getattr(command, "ecology_stream_id", None), str)
            or not isinstance(getattr(command, "weather_event_id", None), str)
        ):
            return self._weather_front_supply_rejected(command_id, "weather_front_organization_command_invalid")
        source_stream = str(command.ecology_stream_id)
        organization_ref = str(command.organization_ref)
        target_stream = f"gameplay:organization:{organization_ref}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            if not existing.committed or len(existing.committed_event_ids) != 1:
                return self._weather_front_supply_rejected(command_id, "idempotency_key_reused")
            prior = self._store.get_event(existing.committed_event_ids[0])
            if (
                prior.stream_id != target_stream
                or prior.event_type != "gameplay.organization.commerce_commitment_accepted"
                or prior.payload.get("weather_event_id") != command.weather_event_id
                or prior.payload.get("commitment_ref") != command.commitment_ref
                or prior.payload.get("source_organization_revision") != expected_revision
            ):
                return self._weather_front_supply_rejected(command_id, "idempotency_key_reused")
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        admission_check = EcologyConsumerAdmissionCheck.verify(
            store=self._store,
            contract_ref="inf:weather-front-organization-supply@1",
            target_owner_ref=self._PRINCIPAL,
            target_stream_ids=(target_stream,),
            target_event_types=("gameplay.organization.commerce_commitment_accepted",),
            projection_scope="project",
            source_event_id=command.weather_event_id,
            source_stream_id=source_stream,
            source_revision=int(command.ecology_stream_revision),
            target_expected_revisions={target_stream: expected_revision},
            idempotency_key=idempotency_key,
        )
        if not admission_check.accepted:
            error_code = admission_check.error_code
            if error_code == "ecology_consumer_source_missing":
                error_code = "weather_front_source_missing"
            elif error_code in {
                "ecology_consumer_source_pin_invalid",
                "ecology_consumer_target_revision_conflict",
            }:
                error_code = "weather_front_organization_source_revision_conflict"
            return self._weather_front_supply_rejected(
                command_id, error_code or "weather_front_organization_admission_invalid"
            )
        source_event = self._store.get_event(str(command.weather_event_id))
        if (
            int(command.ecology_stream_revision) != int(command.weather_event_revision)
            or str(source_event.payload.get("target_region_ref")) != str(command.target_region_ref)
        ):
            return self._weather_front_supply_rejected(command_id, "weather_front_organization_source_revision_conflict")
        try:
            fragment = self.build_commerce_commitment_fragment(
                organization_ref=organization_ref,
                commitment_ref=str(command.commitment_ref),
                counterparty_organization_ref=str(command.counterparty_organization_ref),
                organization_grant_refs=tuple(command.organization_grant_refs),
                budget_reservation_refs=tuple(command.budget_reservation_refs),
                policy_revision=str(command.policy_revision),
                expected_revision=expected_revision,
            )
        except (TypeError, ValueError) as exc:
            return self._weather_front_supply_rejected(command_id, str(exc) or "weather_front_organization_fragment_invalid")
        event_type, event_payload = fragment.event_specs[target_stream][0]
        promoted_payload = {
            **event_payload,
            "weather_event_id": command.weather_event_id,
            "source_ecology_stream": source_stream,
            "source_ecology_revision": int(command.ecology_stream_revision),
            "source_organization_revision": expected_revision,
            "source_region_ref": command.source_region_ref,
            "target_region_ref": command.target_region_ref,
            "weather_ref": command.weather_ref,
            "tick": int(command.tick),
            "edge_ref": edge_ref,
        }
        read_revisions = {source_stream: int(command.ecology_stream_revision), target_stream: expected_revision}
        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.organization.weather_front_supply",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={target_stream: expected_revision},
            read_set_revisions=read_revisions,
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref="ecology-weather-front",
            submitted_at="weather-front-organization-supply",
            pinned_revisions={"ecology_source": int(command.ecology_stream_revision), "organization": expected_revision},
            payload={"stream_ref": target_stream, "event_type": event_type, "visibility_policy": "project", **promoted_payload},
        )
        batch = EventStoreSettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
        owner_fragment = fragment.model_copy(
            update={
                "fragment_id": f"{fragment.fragment_id}:weather-front:{command.weather_event_id}",
                "expected_revisions": {target_stream: expected_revision},
                "read_set_revisions": read_revisions,
                "pinned_revisions": dict(envelope.pinned_revisions),
                "event_specs": {target_stream: ((event_type, promoted_payload),)},
                "event_visibility_policies": {target_stream: ("project",)},
            },
            deep=True,
        )
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "owner_fragments": [owner_fragment],
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.organization.commerce_commitment_projection",
                        audience="project",
                        payload_projection={
                            "organization_ref": organization_ref,
                            "commitment_ref": str(command.commitment_ref),
                            "event_type": event_type,
                        },
                    )
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def settle_canonical_weather_front_supply_fanout(
        self,
        *,
        command: object,
        admission: object | None,
        expected_revisions: Mapping[str, int],
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str,
    ) -> AppendBatchResult:
        """Settle one fixed two-target Ecology weather-front supply fanout."""

        command_id = str(
            getattr(command, "command_id", "organization:weather-front:supply-fanout")
        )
        edge_ref = "ecology-weather:front-to-organization-supply-fanout:v1"
        raw_targets = tuple(getattr(command, "target_specs", ()))
        organization_refs = tuple(
            str(getattr(target, "organization_ref", "")) for target in raw_targets
        )
        if (
            admission is None
            or not _CONTAINS_CANONICAL_WEATHER_FRONT_ORGANIZATION_SUPPLY_FANOUT_ADMISSION(
                admission
            )
            or getattr(admission, "edge_ref", None) != edge_ref
            or getattr(admission, "weather_event_id", None)
            != getattr(command, "weather_event_id", None)
            or getattr(admission, "organization_refs", None) != organization_refs
        ):
            return self._weather_front_supply_rejected(
                command_id, "weather_front_organization_fanout_admission_required"
            )
        if privacy_scope != "project" or getattr(command, "privacy_scope", None) != "project":
            return self._weather_front_supply_rejected(
                command_id, "weather_front_organization_fanout_privacy_denied"
            )
        if (
            getattr(command, "edge_ref", None) != edge_ref
            or getattr(command, "source_authority_ref", None) != "authority:ecology"
            or not isinstance(getattr(command, "ecology_stream_id", None), str)
            or not isinstance(getattr(command, "weather_event_id", None), str)
            or len(raw_targets) != 2
            or len(set(organization_refs)) != 2
            or tuple(organization_refs) != tuple(sorted(organization_refs))
        ):
            return self._weather_front_supply_rejected(
                command_id, "weather_front_organization_fanout_command_invalid"
            )
        try:
            source_event = self._store.get_event(str(command.weather_event_id))
        except KeyError:
            return self._weather_front_supply_rejected(
                command_id, "weather_front_source_missing"
            )
        source_stream = str(command.ecology_stream_id)
        target_streams = tuple(
            f"gameplay:organization:{organization_ref}"
            for organization_ref in organization_refs
        )
        if (
            set(expected_revisions) != set(target_streams)
            or any(
                isinstance(revision, bool)
                or not isinstance(revision, int)
                or revision < 0
                for revision in expected_revisions.values()
            )
        ):
            return self._weather_front_supply_rejected(
                command_id, "weather_front_organization_fanout_revision_conflict"
            )
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            if not existing.committed or len(existing.committed_event_ids) != 2:
                return self._weather_front_supply_rejected(command_id, "idempotency_key_reused")
            prior_events = [self._store.get_event(event_id) for event_id in existing.committed_event_ids]
            prior_refs = tuple(
                sorted(str(event.payload.get("organization_ref", "")) for event in prior_events)
            )
            prior_commitments = tuple(
                sorted(str(event.payload.get("commitment_ref", "")) for event in prior_events)
            )
            prior_revisions = {
                str(event.payload.get("organization_ref", "")): event.payload.get(
                    "source_organization_revision"
                )
                for event in prior_events
            }
            if (
                all(
                    event.event_type == "gameplay.organization.commerce_commitment_accepted"
                    and event.payload.get("weather_event_id") == command.weather_event_id
                    for event in prior_events
                )
                and prior_refs == organization_refs
                and prior_commitments
                == tuple(
                    sorted(
                        str(getattr(target, "commitment_ref", "")) for target in raw_targets
                    )
                )
                and prior_revisions
                == {
                    organization_ref: expected_revisions[
                        f"gameplay:organization:{organization_ref}"
                    ]
                    for organization_ref in organization_refs
                }
            ):
                return existing.model_copy(
                    update={"idempotency_status": "duplicate_replayed"}, deep=True
                )
            return self._weather_front_supply_rejected(command_id, "idempotency_key_reused")
        if (
            source_event.event_type != "gameplay.ecology.weather_front.propagated"
            or source_event.stream_id != source_stream
            or source_event.visibility_policy != "project"
            or source_event.stream_revision != int(command.weather_event_revision)
            or self._store.get_stream_head(source_stream) != int(command.ecology_stream_revision)
            or int(command.ecology_stream_revision) != int(command.weather_event_revision)
            or str(source_event.payload.get("target_region_ref")) != str(command.target_region_ref)
        ):
            return self._weather_front_supply_rejected(
                command_id, "weather_front_organization_fanout_source_revision_conflict"
            )
        if any(
            self._store.get_stream_head(stream_id) != expected_revisions[stream_id]
            for stream_id in target_streams
        ):
            return self._weather_front_supply_rejected(
                command_id, "weather_front_organization_fanout_revision_conflict"
            )
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-organization-supply-fanout@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=target_streams,
                event_types=(
                    "gameplay.organization.commerce_commitment_accepted",
                    "gameplay.organization.commerce_commitment_accepted",
                ),
                projection_scope="project",
            )
            owner_fragments: list[OwnerAuthorizedFragment] = []
            for target in raw_targets:
                organization_ref = str(target.organization_ref)
                target_stream = f"gameplay:organization:{organization_ref}"
                target_revision = expected_revisions[target_stream]
                fragment = self.build_commerce_commitment_fragment(
                    organization_ref=organization_ref,
                    commitment_ref=str(target.commitment_ref),
                    counterparty_organization_ref=str(target.counterparty_organization_ref),
                    organization_grant_refs=tuple(target.organization_grant_refs),
                    budget_reservation_refs=tuple(target.budget_reservation_refs),
                    policy_revision=str(target.policy_revision),
                    expected_revision=target_revision,
                )
                event_type, event_payload = fragment.event_specs[target_stream][0]
                promoted_payload = {
                    **event_payload,
                    "weather_event_id": command.weather_event_id,
                    "source_ecology_stream": source_stream,
                    "source_ecology_revision": int(command.ecology_stream_revision),
                    "source_organization_revision": target_revision,
                    "source_region_ref": command.source_region_ref,
                    "target_region_ref": command.target_region_ref,
                    "weather_ref": command.weather_ref,
                    "tick": int(command.tick),
                    "edge_ref": edge_ref,
                }
                owner_fragments.append(
                    fragment.model_copy(
                        update={
                            "fragment_id": f"{fragment.fragment_id}:weather-front-fanout:{command.weather_event_id}",
                            "expected_revisions": {target_stream: target_revision},
                            "read_set_revisions": {
                                source_stream: int(command.ecology_stream_revision),
                                target_stream: target_revision,
                            },
                            "pinned_revisions": {
                                "ecology_source": int(command.ecology_stream_revision),
                                "organization": target_revision,
                            },
                            "event_specs": {target_stream: ((event_type, promoted_payload),)},
                            "event_visibility_policies": {target_stream: ("project",)},
                        },
                        deep=True,
                    )
                )
        except (GovernedAuthorityContractError, TypeError, ValueError) as exc:
            return self._weather_front_supply_rejected(
                command_id,
                str(exc) or "weather_front_organization_fanout_fragment_invalid",
            )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=command_id,
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragments=tuple(owner_fragments),
        )
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.organization.commerce_commitment_projection",
                        audience="project",
                        payload_projection={
                            "organization_ref": str(event.payload["organization_ref"]),
                            "commitment_ref": str(event.payload["commitment_ref"]),
                            "event_type": event.event_type,
                        },
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def _branch_supply_admission_payload_for(
        self, *, admission_event_id: str
    ) -> dict[str, object]:
        try:
            event = self._store.get_event(admission_event_id)
        except KeyError as exc:
            raise ValueError("branch_promotion_admission_missing") from exc
        payload = event.payload
        branch_ref = payload.get("branch_ref")
        organization_ref = payload.get("organization_ref")
        source_revision = payload.get("source_organization_revision")
        expected_preview_stream = f"gameplay:branch_preview:{branch_ref}"
        source_stream = f"gameplay:organization:{organization_ref}"
        required = (
            "branch_ref",
            "intent_ref",
            "base_event_digest",
            "candidate_digest",
            "fragment_digest",
            "organization_ref",
            "counterparty_organization_ref",
            "commitment_ref",
            "policy_revision",
            "source_stream",
            "replay_contract_digest",
        )
        if (
            event.event_type != "gameplay.branch_preview.supply_admission_recorded"
            or event.stream_id != expected_preview_stream
            or event.visibility_policy != "creator_debug"
            or payload.get("source_stream") != source_stream
            or not isinstance(source_revision, int)
            or isinstance(source_revision, bool)
            or not all(isinstance(payload.get(key), str) and payload[key] for key in required)
            or not str(branch_ref).startswith("branch:")
            or not str(payload["base_event_digest"]).startswith("sha256:")
            or not str(payload["candidate_digest"]).startswith("sha256:")
            or not str(payload["fragment_digest"]).startswith("sha256:")
            or not str(payload["replay_contract_digest"]).startswith("sha256:")
        ):
            raise ValueError("branch_promotion_admission_invalid")
        replay_contract_value = payload.get("replay_contract")
        if not isinstance(replay_contract_value, Mapping):
            raise ValueError("branch_replay_contract_missing")
        from app.population_continuity.branch_replay_contract import FixedBaseBranchReplayContract

        try:
            replay_contract = FixedBaseBranchReplayContract.model_validate(dict(replay_contract_value))
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        stream_error = replay_contract.validate_branch_stream(
            stream_id=expected_preview_stream,
            branch_ref=str(branch_ref),
            privacy_scope="creator_debug",
        )
        if (
            stream_error is not None
            or replay_contract.contract_digest != payload["replay_contract_digest"]
            or replay_contract.base_event_digest != payload["base_event_digest"]
        ):
            raise ValueError("branch_replay_contract_mismatch")
        grant_refs = payload.get("organization_grant_refs")
        reservation_refs = payload.get("budget_reservation_refs")
        if (
            not isinstance(grant_refs, (list, tuple))
            or not isinstance(reservation_refs, (list, tuple))
            or any(not isinstance(ref, str) or not ref.startswith("grant:") for ref in grant_refs)
            or any(not isinstance(ref, str) or not ref.startswith("reservation:") for ref in reservation_refs)
        ):
            raise ValueError("branch_promotion_admission_invalid")
        return {
            **payload,
            "organization_grant_refs": tuple(grant_refs),
            "budget_reservation_refs": tuple(reservation_refs),
            "replay_contract": replay_contract,
        }

    @staticmethod
    def _organization_branch_promotion_rejected(
        error_code: str,
    ) -> OrganizationBranchPromotionResult:
        return OrganizationBranchPromotionResult(accepted=False, error_code=error_code)

    def _organization_branch_promotion_receipt(
        self,
        *,
        result: AppendBatchResult,
        admission_event_id: str,
        scenario_event_id: str,
    ) -> OrganizationBranchPromotionReceipt:
        if not result.committed or len(result.committed_event_ids) != 1:
            raise ValueError("branch_promotion_receipt_unavailable")
        event = self._store.get_event(result.committed_event_ids[0])
        if (
            event.event_type != "gameplay.organization.commerce_commitment_accepted"
            or event.visibility_policy != "project"
            or event.payload.get("branch_admission_event_id") != admission_event_id
            or event.payload.get("branch_scenario_event_id") != scenario_event_id
        ):
            raise ValueError("branch_promotion_receipt_invalid")
        projection = {
            "event_id": event.event_id,
            "organization_ref": event.payload.get("organization_ref"),
            "counterparty_organization_ref": event.payload.get("counterparty_organization_ref"),
            "commitment_ref": event.payload.get("commitment_ref"),
            "branch_ref": event.payload.get("branch_ref"),
        }
        return OrganizationBranchPromotionReceipt(
            transaction_id=result.transaction_id,
            committed_event_ids=tuple(result.committed_event_ids),
            production_stream=event.stream_id,
            production_revision=event.stream_revision,
            admission_event_id=admission_event_id,
            scenario_event_id=scenario_event_id,
            projection_hash="sha256:" + hashlib.sha256(
                json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            privacy_scope="project",
            idempotency_status=result.idempotency_status,
        )

    def promote_branch_supply(
        self,
        *,
        admission_event_id: str,
        scenario_event_id: str,
        expected_production_revision: int,
        idempotency_key: str,
        privacy_scope: str,
    ) -> OrganizationBranchPromotionResult:
        """Promote one revalidated supply commitment; no other branch rows are admitted."""
        if privacy_scope != "project":
            return self._organization_branch_promotion_rejected(
                "branch_promotion_privacy_denied"
            )
        try:
            admission = self._branch_supply_admission_payload_for(
                admission_event_id=admission_event_id
            )
            admission_event = self._store.get_event(admission_event_id)
            scenario_event = self._store.get_event(scenario_event_id)
            branch_ref = str(admission["branch_ref"])
            organization_ref = str(admission["organization_ref"])
            production_stream = f"gameplay:organization:{organization_ref}"
            scenario_stream = self.branch_scenario_stream_id(
                branch_ref=branch_ref, organization_ref=organization_ref
            )
            source_revision = int(admission["source_organization_revision"])
            required_matches = {
                "branch_ref": branch_ref,
                "base_event_digest": admission["base_event_digest"],
                "candidate_digest": admission["candidate_digest"],
                "fragment_digest": admission["fragment_digest"],
                "source_stream": production_stream,
                "admission_event_id": admission_event_id,
                "organization_ref": organization_ref,
                "counterparty_organization_ref": admission["counterparty_organization_ref"],
                "commitment_ref": admission["commitment_ref"],
                "policy_revision": admission["policy_revision"],
                "source_organization_revision": source_revision,
            }
            scenario_grants = scenario_event.payload.get("organization_grant_refs")
            scenario_reservations = scenario_event.payload.get("budget_reservation_refs")
            if (
                scenario_event.event_type
                != "gameplay.organization.branch_commerce_commitment_recorded"
                or scenario_event.stream_id != scenario_stream
                or scenario_event.visibility_policy != "creator_debug"
                or any(
                    scenario_event.payload.get(key) != value
                    for key, value in required_matches.items()
                )
                or tuple(scenario_grants or ()) != tuple(admission["organization_grant_refs"])
                or tuple(scenario_reservations or ())
                != tuple(admission["budget_reservation_refs"])
            ):
                return self._organization_branch_promotion_rejected(
                    "branch_promotion_scenario_invalid"
                )
            existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
            if existing is not None:
                if not existing.committed or len(existing.committed_event_ids) != 1:
                    return self._organization_branch_promotion_rejected(
                        "idempotency_key_reused"
                    )
                prior_event = self._store.get_event(existing.committed_event_ids[0])
                if (
                    expected_production_revision != source_revision
                    or prior_event.stream_id != production_stream
                    or prior_event.event_type
                    != "gameplay.organization.commerce_commitment_accepted"
                    or prior_event.payload.get("branch_admission_event_id")
                    != admission_event_id
                    or prior_event.payload.get("branch_scenario_event_id")
                    != scenario_event_id
                ):
                    return self._organization_branch_promotion_rejected(
                        "idempotency_key_reused"
                    )
                replayed = existing.model_copy(
                    update={"idempotency_status": "duplicate_replayed"}, deep=True
                )
                return OrganizationBranchPromotionResult(
                    accepted=True,
                    receipt=self._organization_branch_promotion_receipt(
                        result=replayed,
                        admission_event_id=admission_event_id,
                        scenario_event_id=scenario_event_id,
                    ),
                )
            if (
                self._store.get_stream_head(admission_event.stream_id)
                != admission_event.stream_revision
                or self._store.get_stream_head(scenario_stream)
                != scenario_event.stream_revision
                or self._store.get_stream_head(production_stream) != source_revision
                or expected_production_revision != source_revision
            ):
                return self._organization_branch_promotion_rejected(
                    "branch_promotion_revision_conflict"
                )
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:organization-supply-promotion@1",
                contract_kind="branch_promotion",
                owner_ref=self._PRINCIPAL,
                stream_ids=(production_stream,),
                event_types=("gameplay.organization.commerce_commitment_accepted",),
                projection_scope="project",
            )
            fragment = self.build_commerce_commitment_fragment(
                organization_ref=organization_ref,
                commitment_ref=str(admission["commitment_ref"]),
                counterparty_organization_ref=str(
                    admission["counterparty_organization_ref"]
                ),
                organization_grant_refs=tuple(admission["organization_grant_refs"]),
                budget_reservation_refs=tuple(admission["budget_reservation_refs"]),
                policy_revision=str(admission["policy_revision"]),
                expected_revision=source_revision,
            )
            event_type, event_payload = fragment.event_specs[production_stream][0]
            promoted_payload = {
                **event_payload,
                "source_stream": production_stream,
                "branch_ref": branch_ref,
                "branch_admission_event_id": admission_event_id,
                "branch_scenario_event_id": scenario_event_id,
                "branch_candidate_digest": admission["candidate_digest"],
                "branch_fragment_digest": admission["fragment_digest"],
                "branch_base_event_digest": admission["base_event_digest"],
                "source_organization_revision": source_revision,
            }
            read_revisions = {
                admission_event.stream_id: admission_event.stream_revision,
                scenario_stream: scenario_event.stream_revision,
                production_stream: source_revision,
            }
            command_id = f"branch-promotion:{branch_ref}:{admission['commitment_ref']}"
            command = GameplayCommandEnvelope(
                command_id=command_id,
                command_type="gameplay.organization.promote_branch_supply",
                command_version=1,
                principal_ref=self._PRINCIPAL,
                actor_ref=None,
                project_ref=None,
                transaction_id=f"transaction:{command_id}",
                idempotency_key=idempotency_key,
                expected_revisions={production_stream: source_revision},
                read_set_revisions=read_revisions,
                causation_id=str(admission["candidate_digest"]),
                correlation_id=f"branch-promotion:{branch_ref}:{admission['commitment_ref']}",
                source_ref="branch-preview-admission",
                submitted_at="branch-promotion",
                pinned_revisions={
                    "organization": source_revision,
                    "branch_preview_admission": admission_event.stream_revision,
                    "branch_organization_scenario": scenario_event.stream_revision,
                },
                payload={
                    "stream_ref": production_stream,
                    "event_type": event_type,
                    "visibility_policy": "project",
                    **promoted_payload,
                },
            )
            batch = EventStoreSettlementPlan.from_command_envelope(
                command
            ).to_atomic_event_batch()
            fragment = fragment.model_copy(
                update={
                    "fragment_id": f"{fragment.fragment_id}:branch-promotion:{branch_ref}",
                    "expected_revisions": {production_stream: source_revision},
                    "read_set_revisions": read_revisions,
                    "pinned_revisions": dict(command.pinned_revisions),
                    "event_specs": {production_stream: ((event_type, promoted_payload),)},
                    "event_visibility_policies": {production_stream: ("project",)},
                },
                deep=True,
            )
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "owner_fragments": [fragment],
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.organization.commerce_commitment_projection",
                            audience="project",
                            payload_projection={
                                "organization_ref": organization_ref,
                                "commitment_ref": str(admission["commitment_ref"]),
                                "branch_ref": branch_ref,
                            },
                        )
                    ],
                },
                deep=True,
            )
            result = self._store.append_batch(batch)
            if not result.committed:
                return self._organization_branch_promotion_rejected(
                    result.failure.error_code
                    if result.failure is not None
                    else "branch_promotion_append_rejected"
                )
            return OrganizationBranchPromotionResult(
                accepted=True,
                receipt=self._organization_branch_promotion_receipt(
                    result=result,
                    admission_event_id=admission_event_id,
                    scenario_event_id=scenario_event_id,
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return self._organization_branch_promotion_rejected(
                str(exc) or "branch_promotion_source_invalid"
            )

    @classmethod
    def branch_scenario_stream_id(cls, *, branch_ref: str, organization_ref: str) -> str:
        return f"{cls._BRANCH_STREAM_PREFIX}{branch_ref}:{organization_ref}"

    def settle_branch_commerce_commitment(
        self,
        *,
        branch_ref: str,
        base_event_digest: str,
        candidate_digest: str,
        source_stream: str | None = None,
        organization_ref: str,
        commitment_ref: str,
        counterparty_organization_ref: str,
        policy_revision: str,
        source_organization_revision: int,
        expected_revision: int,
        idempotency_key: str,
        correlation_id: str,
        privacy_scope: str,
        organization_grant_refs: tuple[str, ...] = (),
        budget_reservation_refs: tuple[str, ...] = (),
        fragment_digest: str | None = None,
        admission_event_id: str | None = None,
    ):
        """Append one non-production Organization-owned branch scenario record."""
        if (
            not branch_ref.startswith("branch:")
            or not base_event_digest.startswith("sha256:")
            or not candidate_digest.startswith("sha256:")
            or not organization_ref
            or not commitment_ref
            or not counterparty_organization_ref
            or not policy_revision
        ):
            raise ValueError("branch_scenario_input_invalid")
        if privacy_scope != "creator_debug":
            raise ValueError("branch_scenario_privacy_denied")
        production_stream = f"gameplay:organization:{organization_ref}"
        scenario_stream = self.branch_scenario_stream_id(branch_ref=branch_ref, organization_ref=organization_ref)
        command_id = f"branch-scenario:{branch_ref}:{commitment_ref}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.organization.settle_branch_commerce_commitment",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={scenario_stream: expected_revision},
            read_set_revisions={production_stream: source_organization_revision},
            causation_id=candidate_digest,
            correlation_id=correlation_id,
            source_ref="branch_preview",
            submitted_at="branch-scenario",
            pinned_revisions={"organization_source": source_organization_revision},
            payload={
                "stream_ref": scenario_stream,
                "event_type": "gameplay.organization.branch_commerce_commitment_recorded",
                "visibility_policy": privacy_scope,
                "branch_ref": branch_ref,
                "base_event_digest": base_event_digest,
                "candidate_digest": candidate_digest,
                "source_stream": source_stream or production_stream,
                **(
                    {"fragment_digest": fragment_digest}
                    if fragment_digest is not None
                    else {}
                ),
                **(
                    {"admission_event_id": admission_event_id}
                    if admission_event_id is not None
                    else {}
                ),
                "organization_ref": organization_ref,
                "commitment_ref": commitment_ref,
                "counterparty_organization_ref": counterparty_organization_ref,
                "policy_revision": policy_revision,
                "organization_grant_refs": organization_grant_refs,
                "budget_reservation_refs": budget_reservation_refs,
                "source_organization_revision": source_organization_revision,
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.organization_branch.scenario_projection",
                        audience=privacy_scope,
                        payload_projection={"branch_ref": branch_ref, "organization_ref": organization_ref, "commitment_ref": commitment_ref},
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def branch_scenario_projection(
        self, *, branch_ref: str, organization_ref: str, checkpoint_at: int | None = None
    ) -> dict[str, object]:
        stream_id = self.branch_scenario_stream_id(branch_ref=branch_ref, organization_ref=organization_ref)
        events = self._store.read_stream(stream_id)
        if checkpoint_at is None:
            checkpoint_at = 0
        if checkpoint_at < 0 or checkpoint_at > len(events):
            raise ValueError("branch_scenario_checkpoint_out_of_range")

        def apply(state: tuple[str, ...], event_payload: dict[str, object]) -> tuple[str, ...]:
            if event_payload.get("branch_ref") != branch_ref or event_payload.get("organization_ref") != organization_ref:
                raise ValueError("branch_scenario_projection_invalid")
            commitment_ref = event_payload.get("commitment_ref")
            if not isinstance(commitment_ref, str) or not commitment_ref:
                raise ValueError("branch_scenario_projection_invalid")
            return state + (commitment_ref,)

        state: tuple[str, ...] = ()
        for event in events[:checkpoint_at]:
            state = apply(state, event.payload)
        checkpoint = state
        for event in events[checkpoint_at:]:
            checkpoint = apply(checkpoint, event.payload)
        projection = {"branch_ref": branch_ref, "organization_ref": organization_ref, "commitment_refs": checkpoint}
        projection["projection_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return projection


__all__ = ["AttendanceEvidence", "BranchInspectionRemediationProposal", "BranchScenarioReceipt", "CommerceBudgetAuthorization", "GovernmentAuthority", "GovernmentBranchPromotionReceipt", "GovernmentBranchPromotionResult", "Inspection", "OperatingPlan", "Organization", "OrganizationAuthority", "OrganizationBranchPromotionReceipt", "OrganizationBranchPromotionResult", "OrganizationCommerceProjection", "OrganizationOperatingWindowView", "OrganizationScheduleRecipientView", "Permit", "RoleAssignment", "ShiftOffer", "TaxAssessment", "WorkOrder", "WorkerContributionRef"]
