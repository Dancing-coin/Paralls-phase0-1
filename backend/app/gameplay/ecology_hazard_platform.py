from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch


HazardKind = Literal["frost", "drought", "rain", "flood", "fire", "pollution", "disease"]
HazardLifecycleStage = Literal["proposed", "admitted", "active", "decay", "recover", "terminal"]


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class EcologyHazardPlatformError(ValueError):
    pass


class EcologyHazardIntent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hazard_ref: str = Field(min_length=1)
    hazard_kind: HazardKind
    region_ref: str = Field(min_length=1)
    severity_basis_points: int = Field(ge=0, le=10_000)
    created_tick: int = Field(ge=0)
    duration_ticks: int = Field(gt=0)
    policy_revision: str = Field(min_length=1)
    chain_budget: int = Field(ge=0)
    visibility_scope: Literal["project", "authority_only", "private_evidence"] = "project"
    causal_parent_refs: tuple[str, ...] = ()


class HazardRecoveryPolicy(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    hazard_kind: HazardKind
    required_stage: Literal["decay"] = "decay"
    recovery_action: str = Field(min_length=1)
    resulting_stage: Literal["recover"] = "recover"


class HazardRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hazard_ref: str = Field(min_length=1)
    hazard_kind: HazardKind
    region_ref: str = Field(min_length=1)
    lifecycle_stage: HazardLifecycleStage
    severity_basis_points: int = Field(ge=0, le=10_000)
    created_tick: int = Field(ge=0)
    duration_ticks: int = Field(gt=0)
    policy_revision: str = Field(min_length=1)
    recovery_policy_ref: str = Field(min_length=1)
    chain_budget: int = Field(ge=0)
    chain_depth: int = Field(ge=0)
    ancestor_region_refs: tuple[str, ...] = ()
    lineage_hazard_refs: tuple[str, ...] = ()
    visibility_scope: Literal["project", "authority_only", "private_evidence"] = "project"
    source_event_id: str = Field(min_length=1)
    source_stream_revision: int = Field(ge=0)
    parent_hazard_ref: str | None = None


class EcologyHazardProjection(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hazards: dict[str, dict[str, object]] = Field(default_factory=dict)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    projection_hash: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class EcologyHazardProposal:
    hazard_ref: str
    hazard_kind: HazardKind
    region_ref: str
    severity_basis_points: int
    created_tick: int
    duration_ticks: int
    policy_revision: str
    recovery_policy_ref: str
    chain_budget: int
    chain_depth: int
    ancestor_region_refs: tuple[str, ...]
    lineage_hazard_refs: tuple[str, ...]
    visibility_scope: Literal["project", "authority_only", "private_evidence"]
    expected_revision: int
    lifecycle_stage: Literal["proposed"] = "proposed"


@dataclass(frozen=True, slots=True)
class EcologyHazardProposalResult:
    accepted: bool
    proposal: EcologyHazardProposal | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class EcologyHazardPropagationProposal:
    hazard_ref: str
    propagated_hazard_ref: str
    hazard_kind: HazardKind
    source_region_ref: str
    target_region_ref: str
    severity_basis_points: int
    created_tick: int
    duration_ticks: int
    policy_revision: str
    recovery_policy_ref: str
    chain_budget: int
    chain_depth: int
    ancestor_region_refs: tuple[str, ...]
    lineage_hazard_refs: tuple[str, ...]
    visibility_scope: Literal["project", "authority_only", "private_evidence"]
    source_stream_revision: int
    target_stream_revision: int
    expected_revision: int
    lifecycle_stage: Literal["proposed"] = "proposed"


@dataclass(frozen=True, slots=True)
class EcologyHazardPropagationProposalResult:
    accepted: bool
    proposal: EcologyHazardPropagationProposal | None = None
    error_code: str | None = None


class EcologyHazardProjector:
    def rebuild(
        self,
        events: Sequence[object],
        *,
        checkpoint: EcologyHazardProjection | None = None,
    ) -> EcologyHazardProjection:
        hazards = dict(checkpoint.hazards) if checkpoint is not None else {}
        revisions = dict(checkpoint.source_revision_vector) if checkpoint is not None else {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if not isinstance(event.stream_id, str) or not event.stream_id.startswith(EcologyHazardPlatformAuthority._STREAM_PREFIX):
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), int(event.stream_revision))
            payload = event.payload
            if not isinstance(payload, dict):
                raise EcologyHazardPlatformError("ecology_hazard_replay_invalid")
            hazard_ref = payload.get("hazard_ref")
            if not isinstance(hazard_ref, str) or not hazard_ref:
                raise EcologyHazardPlatformError("ecology_hazard_replay_invalid")
            if event.event_type not in {
                "gameplay.ecology_hazard.hazard_admitted@1",
                "gameplay.ecology_hazard.hazard_activated@1",
                "gameplay.ecology_hazard.hazard_decayed@1",
                "gameplay.ecology_hazard.hazard_recovered@1",
                "gameplay.ecology_hazard.hazard_terminal@1",
                "gameplay.ecology_hazard.hazard_propagated@1",
            }:
                raise EcologyHazardPlatformError("ecology_hazard_replay_invalid")
            if event.event_type == "gameplay.ecology_hazard.hazard_propagated@1":
                hazard_record = self._record_from_payload(payload, stage="active")
            else:
                hazard_record = self._record_from_payload(
                    payload,
                    stage=str(payload.get("lifecycle_stage", "")),
                )
            hazard_record = hazard_record.model_copy(
                update={"source_stream_revision": int(event.stream_revision)}
            )
            hazards[hazard_ref] = hazard_record.model_dump(mode="json")
        projection = EcologyHazardProjection(
            hazards=dict(sorted(hazards.items())),
            source_revision_vector=dict(sorted(revisions.items())),
            projection_hash=_canonical_hash(
                {
                    "hazards": dict(sorted(hazards.items())),
                    "source_revision_vector": dict(sorted(revisions.items())),
                }
            ),
        )
        return projection

    @staticmethod
    def _record_from_payload(payload: Mapping[str, object], *, stage: str) -> HazardRecord:
        hazard = HazardRecord(
            hazard_ref=str(payload.get("hazard_ref", "")),
            hazard_kind=payload["hazard_kind"],
            region_ref=str(payload.get("region_ref", "")),
            lifecycle_stage=stage,  # type: ignore[arg-type]
            severity_basis_points=int(payload.get("severity_basis_points", 0)),
            created_tick=int(payload.get("created_tick", 0)),
            duration_ticks=int(payload.get("duration_ticks", 1)),
            policy_revision=str(payload.get("policy_revision", "")),
            recovery_policy_ref=str(payload.get("recovery_policy_ref", "")),
            chain_budget=int(payload.get("chain_budget", 0)),
            chain_depth=int(payload.get("chain_depth", 0)),
            ancestor_region_refs=tuple(str(value) for value in payload.get("ancestor_region_refs", ())),
            lineage_hazard_refs=tuple(str(value) for value in payload.get("lineage_hazard_refs", ())),
            visibility_scope=payload.get("visibility_scope", "project"),  # type: ignore[arg-type]
            source_event_id=str(payload.get("source_event_id", "")),
            source_stream_revision=int(payload.get("source_stream_revision", 0)),
            parent_hazard_ref=payload.get("parent_hazard_ref") if isinstance(payload.get("parent_hazard_ref"), str) else None,
        )
        hazard.model_dump(mode="json")
        return hazard


class EcologyHazardPlatformAuthority:
    _PRINCIPAL = "authority:ecology_hazard"
    _STREAM_PREFIX = "gameplay:ecology_hazard:"
    _HAZARD_EVENT_PREFIX = "gameplay.ecology_hazard."
    _RECOVERY_POLICY_BY_KIND: dict[HazardKind, HazardRecoveryPolicy] = {
        "frost": HazardRecoveryPolicy(policy_ref="policy:ecology-hazard-recovery:frost@1", policy_revision="1", hazard_kind="frost", recovery_action="thaw"),
        "drought": HazardRecoveryPolicy(policy_ref="policy:ecology-hazard-recovery:drought@1", policy_revision="1", hazard_kind="drought", recovery_action="rehydrate"),
        "rain": HazardRecoveryPolicy(policy_ref="policy:ecology-hazard-recovery:rain@1", policy_revision="1", hazard_kind="rain", recovery_action="drain"),
        "flood": HazardRecoveryPolicy(policy_ref="policy:ecology-hazard-recovery:flood@1", policy_revision="1", hazard_kind="flood", recovery_action="recede"),
        "fire": HazardRecoveryPolicy(policy_ref="policy:ecology-hazard-recovery:fire@1", policy_revision="1", hazard_kind="fire", recovery_action="extinguish"),
        "pollution": HazardRecoveryPolicy(policy_ref="policy:ecology-hazard-recovery:pollution@1", policy_revision="1", hazard_kind="pollution", recovery_action="remediate"),
        "disease": HazardRecoveryPolicy(policy_ref="policy:ecology-hazard-recovery:disease@1", policy_revision="1", hazard_kind="disease", recovery_action="treat"),
    }

    def __init__(self, *, store: GameplayEventStore, topology: Mapping[str, Sequence[str]]) -> None:
        self.store = store
        self._topology = {
            region_ref: tuple(dict.fromkeys(neighbor_refs))
            for region_ref, neighbor_refs in sorted(topology.items())
        }
        self._projector = EcologyHazardProjector()

    @property
    def principal_ref(self) -> str:
        return self._PRINCIPAL

    @classmethod
    def hazard_stream_id(cls, *, region_ref: str) -> str:
        return f"{cls._STREAM_PREFIX}{region_ref}"

    def recovery_policies(self) -> Mapping[str, HazardRecoveryPolicy]:
        return MappingProxyType(dict(self._RECOVERY_POLICY_BY_KIND))

    def recovery_policy_for(self, hazard_kind: HazardKind) -> HazardRecoveryPolicy:
        return self._RECOVERY_POLICY_BY_KIND[hazard_kind]

    def propose_hazard(self, *, intent: EcologyHazardIntent) -> EcologyHazardProposalResult:
        if intent.visibility_scope != "project":
            return EcologyHazardProposalResult(accepted=False, error_code="ecology_hazard_private_scope_denied")
        if intent.region_ref not in self._topology:
            return EcologyHazardProposalResult(accepted=False, error_code="ecology_hazard_missing")
        stream_id = self.hazard_stream_id(region_ref=intent.region_ref)
        return EcologyHazardProposalResult(
            accepted=True,
            proposal=EcologyHazardProposal(
                hazard_ref=intent.hazard_ref,
                hazard_kind=intent.hazard_kind,
                region_ref=intent.region_ref,
                severity_basis_points=intent.severity_basis_points,
                created_tick=intent.created_tick,
                duration_ticks=intent.duration_ticks,
                policy_revision=intent.policy_revision,
                recovery_policy_ref=self.recovery_policy_for(intent.hazard_kind).policy_ref,
                chain_budget=intent.chain_budget,
                chain_depth=0,
                ancestor_region_refs=(),
                lineage_hazard_refs=tuple(intent.causal_parent_refs),
                visibility_scope=intent.visibility_scope,
                expected_revision=self.store.get_stream_head(stream_id),
            ),
        )

    def admit_hazard(
        self,
        *,
        proposal: EcologyHazardProposal,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if type(proposal) is not EcologyHazardProposal:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_proposal_invalid", "proposal_validation")
        stream_id = self.hazard_stream_id(region_ref=proposal.region_ref)
        if self.store.get_stream_head(stream_id) != proposal.expected_revision:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_stale_proposal", "revision_check", stream_id=stream_id)
        return self._append_hazard_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            stream_id=stream_id,
            expected_revision=proposal.expected_revision,
            event_type="gameplay.ecology_hazard.hazard_admitted@1",
            payload=self._proposal_payload(proposal, stage="admitted"),
        )

    def activate_hazard(
        self,
        *,
        hazard_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        hazard = self._hazard_or_failure(hazard_ref)
        if hazard is None:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_missing", "projection_read")
        if hazard.lifecycle_stage != "admitted":
            return self._rejected(command_id, idempotency_key, "ecology_hazard_stage_invalid", "projection_read", stream_id=self.hazard_stream_id(region_ref=hazard.region_ref))
        return self._append_hazard_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            stream_id=self.hazard_stream_id(region_ref=hazard.region_ref),
            expected_revision=hazard.source_stream_revision,
            event_type="gameplay.ecology_hazard.hazard_activated@1",
            payload=hazard.model_copy(update={"lifecycle_stage": "active"}).model_dump(mode="json"),
        )

    def decay_hazard(
        self,
        *,
        hazard_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        hazard = self._hazard_or_failure(hazard_ref)
        if hazard is None:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_missing", "projection_read")
        if hazard.lifecycle_stage != "active":
            return self._rejected(command_id, idempotency_key, "ecology_hazard_stage_invalid", "projection_read", stream_id=self.hazard_stream_id(region_ref=hazard.region_ref))
        return self._append_hazard_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            stream_id=self.hazard_stream_id(region_ref=hazard.region_ref),
            expected_revision=hazard.source_stream_revision,
            event_type="gameplay.ecology_hazard.hazard_decayed@1",
            payload=hazard.model_copy(update={"lifecycle_stage": "decay"}).model_dump(mode="json"),
        )

    def recover_hazard(
        self,
        *,
        hazard_ref: str,
        recovery_policy_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        hazard = self._hazard_or_failure(hazard_ref)
        if hazard is None:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_missing", "projection_read")
        policy = self.recovery_policy_for(hazard.hazard_kind)
        if hazard.lifecycle_stage != policy.required_stage or recovery_policy_ref != policy.policy_ref:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_recovery_policy_mismatch", "projection_read", stream_id=self.hazard_stream_id(region_ref=hazard.region_ref))
        return self._append_hazard_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            stream_id=self.hazard_stream_id(region_ref=hazard.region_ref),
            expected_revision=hazard.source_stream_revision,
            event_type="gameplay.ecology_hazard.hazard_recovered@1",
            payload=hazard.model_copy(update={"lifecycle_stage": "recover", "recovery_policy_ref": policy.policy_ref}).model_dump(mode="json"),
        )

    def terminate_hazard(
        self,
        *,
        hazard_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        hazard = self._hazard_or_failure(hazard_ref)
        if hazard is None:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_missing", "projection_read")
        if hazard.lifecycle_stage != "recover":
            return self._rejected(command_id, idempotency_key, "ecology_hazard_stage_invalid", "projection_read", stream_id=self.hazard_stream_id(region_ref=hazard.region_ref))
        return self._append_hazard_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            stream_id=self.hazard_stream_id(region_ref=hazard.region_ref),
            expected_revision=hazard.source_stream_revision,
            event_type="gameplay.ecology_hazard.hazard_terminal@1",
            payload=hazard.model_copy(update={"lifecycle_stage": "terminal"}).model_dump(mode="json"),
        )

    def propose_neighbor_propagation(
        self,
        *,
        hazard_ref: str,
        propagated_hazard_ref: str,
        target_region_ref: str,
    ) -> EcologyHazardPropagationProposalResult:
        hazard = self._hazard_or_failure(hazard_ref)
        if hazard is None:
            return EcologyHazardPropagationProposalResult(accepted=False, error_code="ecology_hazard_missing")
        if hazard.lifecycle_stage not in {"active", "decay"}:
            return EcologyHazardPropagationProposalResult(accepted=False, error_code="ecology_hazard_stage_invalid")
        if target_region_ref not in self._topology:
            return EcologyHazardPropagationProposalResult(accepted=False, error_code="ecology_hazard_missing")
        if target_region_ref not in self._topology.get(hazard.region_ref, ()):
            return EcologyHazardPropagationProposalResult(accepted=False, error_code="ecology_hazard_cycle_denied")
        if target_region_ref in hazard.ancestor_region_refs or target_region_ref == hazard.region_ref:
            return EcologyHazardPropagationProposalResult(accepted=False, error_code="ecology_hazard_cycle_denied")
        if hazard.chain_depth + 1 > hazard.chain_budget:
            return EcologyHazardPropagationProposalResult(accepted=False, error_code="ecology_hazard_budget_exhausted")
        source_stream_id = self.hazard_stream_id(region_ref=hazard.region_ref)
        target_stream_id = self.hazard_stream_id(region_ref=target_region_ref)
        return EcologyHazardPropagationProposalResult(
            accepted=True,
            proposal=EcologyHazardPropagationProposal(
                hazard_ref=hazard_ref,
                propagated_hazard_ref=propagated_hazard_ref,
                hazard_kind=hazard.hazard_kind,
                source_region_ref=hazard.region_ref,
                target_region_ref=target_region_ref,
                severity_basis_points=hazard.severity_basis_points,
                created_tick=hazard.created_tick,
                duration_ticks=hazard.duration_ticks,
                policy_revision=hazard.policy_revision,
                recovery_policy_ref=hazard.recovery_policy_ref,
                chain_budget=hazard.chain_budget,
                chain_depth=hazard.chain_depth + 1,
                ancestor_region_refs=tuple((*hazard.ancestor_region_refs, hazard.region_ref)),
                lineage_hazard_refs=tuple((*hazard.lineage_hazard_refs, hazard_ref)),
                visibility_scope=hazard.visibility_scope,
                source_stream_revision=hazard.source_stream_revision,
                target_stream_revision=self.store.get_stream_head(target_stream_id),
                expected_revision=self.store.get_stream_head(target_stream_id),
            ),
        )

    def admit_neighbor_propagation(
        self,
        *,
        proposal: EcologyHazardPropagationProposal,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if type(proposal) is not EcologyHazardPropagationProposal:
            return self._rejected(command_id, idempotency_key, "ecology_hazard_proposal_invalid", "proposal_validation")
        source_stream_id = self.hazard_stream_id(region_ref=proposal.source_region_ref)
        target_stream_id = self.hazard_stream_id(region_ref=proposal.target_region_ref)
        if (
            self.store.get_stream_head(source_stream_id) != proposal.source_stream_revision
            or self.store.get_stream_head(target_stream_id) != proposal.target_stream_revision
        ):
            return self._rejected(command_id, idempotency_key, "ecology_hazard_stale_proposal", "revision_check", stream_id=target_stream_id)
        payload = {
            "hazard_ref": proposal.propagated_hazard_ref,
            "hazard_kind": proposal.hazard_kind,
            "region_ref": proposal.target_region_ref,
            "lifecycle_stage": "active",
            "severity_basis_points": proposal.severity_basis_points,
            "created_tick": proposal.created_tick,
            "duration_ticks": proposal.duration_ticks,
            "policy_revision": proposal.policy_revision,
            "recovery_policy_ref": proposal.recovery_policy_ref,
            "chain_budget": proposal.chain_budget,
            "chain_depth": proposal.chain_depth,
            "ancestor_region_refs": proposal.ancestor_region_refs,
            "lineage_hazard_refs": proposal.lineage_hazard_refs,
            "visibility_scope": proposal.visibility_scope,
            "source_event_id": f"event:{command_id}",
            "source_stream_revision": proposal.target_stream_revision + 1,
            "parent_hazard_ref": proposal.hazard_ref,
        }
        return self._append_hazard_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            stream_id=target_stream_id,
            expected_revision=proposal.target_stream_revision,
            event_type="gameplay.ecology_hazard.hazard_propagated@1",
            payload=payload,
            read_stream_revisions={
                source_stream_id: proposal.source_stream_revision,
                target_stream_id: proposal.target_stream_revision,
            },
        )

    def project(self, *, scope: Literal["public", "authority"] = "public") -> EcologyHazardProjection:
        if scope not in {"public", "authority"}:
            raise EcologyHazardPlatformError("ecology_hazard_scope_invalid")
        return self._projector.rebuild(self.store.read_events())

    def replay(self, *, checkpoint_at: int | None = None) -> EcologyHazardProjection:
        events = self.store.read_events()
        if checkpoint_at is None:
            return self._projector.rebuild(events)
        checkpoint = self._projector.rebuild(events[:checkpoint_at])
        return self._projector.rebuild(events[checkpoint_at:], checkpoint=checkpoint)

    def _hazard_or_failure(self, hazard_ref: str) -> HazardRecord | None:
        projection = self._projector.rebuild(self.store.read_events())
        hazard = projection.hazards.get(hazard_ref)
        if not isinstance(hazard, dict):
            return None
        return HazardRecord.model_validate(hazard)

    def _proposal_payload(self, proposal: EcologyHazardProposal, *, stage: HazardLifecycleStage) -> dict[str, object]:
        payload = {
            "hazard_ref": proposal.hazard_ref,
            "hazard_kind": proposal.hazard_kind,
            "region_ref": proposal.region_ref,
            "lifecycle_stage": stage,
            "severity_basis_points": proposal.severity_basis_points,
            "created_tick": proposal.created_tick,
            "duration_ticks": proposal.duration_ticks,
            "policy_revision": proposal.policy_revision,
            "recovery_policy_ref": proposal.recovery_policy_ref,
            "chain_budget": proposal.chain_budget,
            "chain_depth": proposal.chain_depth,
            "ancestor_region_refs": proposal.ancestor_region_refs,
            "lineage_hazard_refs": proposal.lineage_hazard_refs,
            "visibility_scope": proposal.visibility_scope,
            "source_event_id": f"event:{proposal.hazard_ref}",
            "source_stream_revision": proposal.expected_revision + 1,
            "parent_hazard_ref": None,
        }
        return payload

    def _append_hazard_event(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        stream_id: str,
        expected_revision: int,
        event_type: str,
        payload: Mapping[str, object],
        read_stream_revisions: Mapping[str, int] | None = None,
    ) -> AppendBatchResult:
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_specs=((event_type, dict(payload)),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            read_stream_revisions=read_stream_revisions,
        )
        hazard_event_payload = dict(payload)
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:ecology-hazard:{command_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="ecology-hazard-platform:owner-local-append@1",
            expected_revisions={stream_id: expected_revision},
            read_set_revisions=dict(read_stream_revisions or {}),
            event_specs={stream_id: ((event_type, hazard_event_payload),)},
            event_visibility_policies={stream_id: ("project",)},
            pinned_revisions={},
        )
        batch = batch.model_copy(update={"owner_fragments": [fragment]}, deep=True)
        return self.store.append_batch(batch)

    @classmethod
    def _rejected(
        cls,
        command_id: str,
        idempotency_key: str,
        error_code: str,
        failed_stage: str,
        *,
        stream_id: str | None = None,
    ) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure={
                "error_code": error_code,
                "message": error_code,
                "failed_stage": failed_stage,
                "retriable": False,
                "stream_id": stream_id,
            },
        )


__all__ = [
    "EcologyHazardIntent",
    "EcologyHazardPlatformAuthority",
    "EcologyHazardPlatformError",
    "EcologyHazardProjection",
    "EcologyHazardPropagationProposal",
    "EcologyHazardPropagationProposalResult",
    "EcologyHazardProposal",
    "EcologyHazardProposalResult",
    "EcologyHazardProjector",
    "HazardKind",
    "HazardLifecycleStage",
    "HazardRecoveryPolicy",
    "HazardRecord",
]
