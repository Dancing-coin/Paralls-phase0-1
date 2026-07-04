from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.models.siming_runtime_state import FairnessDimensionSnapshot


SituationState = Literal["open", "updated", "stale", "resolved"]
SituationSourceKind = Literal[
    "l1_projected_fact",
    "authority_event",
    "world_result",
    "environment_event",
    "evidence_event",
    "vla_global_advisory",
    "multi_actor_patch",
]


class SituationEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_id: str
    source_kind: SituationSourceKind
    summary: str = ""
    advisory: bool = False
    authoritative: bool = False
    freshness: Literal["fresh", "stale", "unknown"] = "fresh"


class SimingGlobalSituationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    context_id: str
    room_id: str
    scene_id: str
    zone_id: str
    lifecycle_state: SituationState = "open"
    multi_actor_patch_refs: list[str] = Field(default_factory=list)
    public_fact_refs: list[str] = Field(default_factory=list)
    authority_event_refs: list[str] = Field(default_factory=list)
    world_result_refs: list[str] = Field(default_factory=list)
    environment_event_refs: list[str] = Field(default_factory=list)
    evidence_chain: list[SituationEvidenceRef] = Field(default_factory=list)
    visibility_imbalance: float = Field(default=0.0, ge=0.0, le=1.0)
    fairness_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    intervention_candidate_evidence: list[str] = Field(default_factory=list)
    conflict_refs: list[str] = Field(default_factory=list)
    freshness: Literal["fresh", "stale", "contested", "resolved"] = "fresh"
    advisory_metadata: dict[str, Any] = Field(default_factory=dict)
    workbench_explanation: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_siming_context_boundary(self) -> "SimingGlobalSituationSnapshot":
        if not self.context_id.startswith("siming_mm:"):
            raise ValueError("Siming global situation context must use siming_mm namespace")
        for evidence in self.evidence_chain:
            if evidence.ref_id.startswith("character_mm:") or "character_private" in evidence.ref_id:
                raise ValueError("Siming global situation cannot read character private cache")
        return self


class SimingGlobalSituationLayer:
    def __init__(self) -> None:
        self.snapshots: dict[str, SimingGlobalSituationSnapshot] = {}
        self.trace: list[dict[str, object]] = []

    def assemble_snapshot(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        context_id: str,
        l1_projected_facts: list[str] | None = None,
        authority_events: list[dict[str, object]] | None = None,
        world_results: list[dict[str, object]] | None = None,
        environment_events: list[dict[str, object]] | None = None,
        evidence_events: list[dict[str, object]] | None = None,
        vla_global_findings: list[dict[str, object]] | None = None,
        multi_actor_patch: dict[str, object] | None = None,
        producer_ts: int = 0,
    ) -> SimingGlobalSituationSnapshot:
        self._reject_private_inputs(context_id, multi_actor_patch or {}, vla_global_findings or [])
        l1_projected_facts = l1_projected_facts or []
        authority_events = authority_events or []
        world_results = world_results or []
        environment_events = environment_events or []
        evidence_events = evidence_events or []
        vla_global_findings = vla_global_findings or []
        multi_actor_patch = multi_actor_patch or {}

        evidence_chain: list[SituationEvidenceRef] = []
        evidence_chain.extend(
            SituationEvidenceRef(ref_id=ref, source_kind="l1_projected_fact", authoritative=True)
            for ref in l1_projected_facts
        )
        evidence_chain.extend(self._event_evidence(authority_events, "authority_event", authoritative=True))
        evidence_chain.extend(self._event_evidence(world_results, "world_result", authoritative=True))
        evidence_chain.extend(self._event_evidence(environment_events, "environment_event", authoritative=True))
        evidence_chain.extend(self._event_evidence(evidence_events, "evidence_event", authoritative=True))
        evidence_chain.extend(self._event_evidence(vla_global_findings, "vla_global_advisory", advisory=True))

        actor_visibility = multi_actor_patch.get("actor_visibility", {})
        visibility_values = [float(value) for value in actor_visibility.values()] if isinstance(actor_visibility, dict) else []
        imbalance = (max(visibility_values) - min(visibility_values)) if len(visibility_values) >= 2 else 0.0
        advisory_pressure = sum(float(finding.get("pressure", 0.0) or 0.0) for finding in vla_global_findings) * 0.1
        authority_pressure = 0.25 if world_results or authority_events else 0.0
        conflict_refs = self._conflict_refs(l1_projected_facts, world_results, vla_global_findings)
        fairness_pressure = min(1.0, max(imbalance, authority_pressure) + advisory_pressure)
        snapshot_id = f"siming_situation:{room_id}:{scene_id}:{producer_ts}"
        snapshot = SimingGlobalSituationSnapshot(
            snapshot_id=snapshot_id,
            context_id=context_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            lifecycle_state="open" if snapshot_id not in self.snapshots else "updated",
            multi_actor_patch_refs=[str(ref) for ref in multi_actor_patch.get("patch_refs", [])] if isinstance(multi_actor_patch.get("patch_refs", []), list) else [],
            public_fact_refs=list(l1_projected_facts),
            authority_event_refs=[self._ref_for_event(event) for event in authority_events],
            world_result_refs=[self._ref_for_event(result) for result in world_results],
            environment_event_refs=[self._ref_for_event(event) for event in environment_events],
            evidence_chain=evidence_chain,
            visibility_imbalance=min(1.0, max(0.0, imbalance)),
            fairness_pressure=fairness_pressure,
            intervention_candidate_evidence=[evidence.ref_id for evidence in evidence_chain if evidence.authoritative or evidence.advisory],
            conflict_refs=conflict_refs,
            freshness="contested" if conflict_refs else "fresh",
            advisory_metadata={
                "advisory_count": len(vla_global_findings),
                "advisory_only": True,
                "cannot_override_world_truth": True,
            },
            workbench_explanation={
                "source_refs": [evidence.ref_id for evidence in evidence_chain],
                "conflict_refs": conflict_refs,
                "freshness": "contested" if conflict_refs else "fresh",
                "context_id": context_id,
            },
        )
        self.snapshots[snapshot.snapshot_id] = snapshot
        self.trace.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "context_id": snapshot.context_id,
                "fairness_pressure": snapshot.fairness_pressure,
                "visibility_imbalance": snapshot.visibility_imbalance,
                "evidence_count": len(snapshot.evidence_chain),
                "conflict_refs": list(snapshot.conflict_refs),
            }
        )
        return snapshot

    def mark_stale(self, snapshot_id: str) -> SimingGlobalSituationSnapshot:
        snapshot = self.snapshots[snapshot_id].model_copy(update={"lifecycle_state": "stale", "freshness": "stale"})
        self.snapshots[snapshot_id] = snapshot
        return snapshot

    def resolve(self, snapshot_id: str, *, result_ref: str) -> SimingGlobalSituationSnapshot:
        snapshot = self.snapshots[snapshot_id].model_copy(
            update={
                "lifecycle_state": "resolved",
                "freshness": "resolved",
                "conflict_refs": [],
                "workbench_explanation": {
                    **self.snapshots[snapshot_id].workbench_explanation,
                    "resolved_by": result_ref,
                    "freshness": "resolved",
                },
            }
        )
        self.snapshots[snapshot_id] = snapshot
        return snapshot

    def to_fairness_snapshot(self, snapshot: SimingGlobalSituationSnapshot) -> FairnessStateSnapshot:
        return FairnessStateSnapshot(
            snapshot_id=f"fairness:{snapshot.snapshot_id}",
            room_id=snapshot.room_id,
            scene_id=snapshot.scene_id,
            zone_id=snapshot.zone_id,
            causation_id=snapshot.snapshot_id,
            correlation_id=snapshot.snapshot_id,
            known_fact_ids=list(snapshot.public_fact_refs),
            eligible_actor_ids=[],
            blocked_actor_ids=[],
            dimensions={
                "visibility_imbalance": FairnessDimensionSnapshot(
                    dimension_id="visibility_imbalance",
                    status="fresh",
                    score=snapshot.visibility_imbalance,
                    reason="Siming global situation visibility imbalance",
                    mapped_to_policy=True,
                ),
                "situation_pressure": FairnessDimensionSnapshot(
                    dimension_id="situation_pressure",
                    status="fresh",
                    score=snapshot.fairness_pressure,
                    reason="Siming global situation pressure",
                    mapped_to_policy=True,
                ),
            },
        )

    def to_intervention_candidate(self, snapshot: SimingGlobalSituationSnapshot) -> InterventionCandidate:
        target_environment_id = snapshot.environment_event_refs[0] if snapshot.environment_event_refs else None
        return InterventionCandidate(
            candidate_id=f"candidate:{snapshot.snapshot_id}",
            room_id=snapshot.room_id,
            scene_id=snapshot.scene_id,
            zone_id=snapshot.zone_id,
            causation_id=snapshot.snapshot_id,
            correlation_id=snapshot.snapshot_id,
            proposed_band="fact_reveal",
            target_environment_id=target_environment_id,
            established_fact_ids=list(snapshot.intervention_candidate_evidence),
            explanation=f"situation pressure={snapshot.fairness_pressure:.2f}; visibility imbalance={snapshot.visibility_imbalance:.2f}",
            confidence=min(1.0, max(0.1, snapshot.fairness_pressure)),
            reason_tags=["siming_global_situation", "situation_evidence_refs"],
            source="rule",
        )

    def _event_evidence(
        self,
        events: list[dict[str, object]],
        source_kind: SituationSourceKind,
        *,
        advisory: bool = False,
        authoritative: bool = False,
    ) -> list[SituationEvidenceRef]:
        return [
            SituationEvidenceRef(
                ref_id=self._ref_for_event(event),
                source_kind=source_kind,
                summary=str(event.get("summary", "") or event.get("result_type", "") or event.get("event_type", "")),
                advisory=advisory,
                authoritative=authoritative,
            )
            for event in events
        ]

    def _ref_for_event(self, event: dict[str, object]) -> str:
        for key in ("event_id", "result_id", "ref_id", "id", "causation_id"):
            value = str(event.get(key, "") or "")
            if value:
                return value
        return "event:unref"

    def _conflict_refs(
        self,
        l1_projected_facts: list[str],
        world_results: list[dict[str, object]],
        vla_global_findings: list[dict[str, object]],
    ) -> list[str]:
        authoritative_refs = set(l1_projected_facts)
        authoritative_refs.update(self._ref_for_event(result) for result in world_results)
        conflicts: list[str] = []
        for finding in vla_global_findings:
            conflicts_with = str(finding.get("conflicts_with", "") or "")
            if conflicts_with and conflicts_with in authoritative_refs:
                conflicts.append(f"vla_advisory_conflict:{self._ref_for_event(finding)}:{conflicts_with}")
        return conflicts

    def _reject_private_inputs(
        self,
        context_id: str,
        multi_actor_patch: dict[str, object],
        vla_global_findings: list[dict[str, object]],
    ) -> None:
        if not context_id.startswith("siming_mm:"):
            raise ValueError("Siming global situation context must use siming_mm namespace")
        serialized = f"{multi_actor_patch} {vla_global_findings}"
        if "character_mm:" in serialized or "character_private" in serialized:
            raise ValueError("Siming global situation cannot read character private cache")
