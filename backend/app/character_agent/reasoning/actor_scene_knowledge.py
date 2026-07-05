from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.object_anchor import append_unique_lineage, derive_world_anchor_id
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle


KnowledgeType = Literal["space", "obstacle", "occlusion", "path", "environment", "affordance", "target", "failure"]
KnowledgeSourceKind = Literal[
    "canonical_percept_bundle",
    "l1_projected_fact",
    "vla_advisory",
    "interaction_failure",
    "world_failure",
    "embodied_failure",
    "active_perception",
]
FreshnessState = Literal["fresh", "stale", "expired", "contested"]
RevisionOperation = Literal["add", "hit", "revise", "conflict", "stale", "expire", "resolve"]


class ActorSceneKnowledgeFreshness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: FreshnessState = "fresh"
    observed_at: int = 0
    last_confirmed_at: int = 0
    expires_at: int | None = None

    def state_at(self, now: int) -> FreshnessState:
        if self.expires_at is not None and now >= self.expires_at:
            return "expired"
        return self.state


class ActorSceneKnowledgeConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    world_anchor_id: str = ""
    subject_ref: str
    target_ref: str = ""
    reason: str
    source_refs: list[str] = Field(default_factory=list)
    source_ref_lineage: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolved_by_ref: str = ""


class ActorSceneKnowledgeRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    operation: RevisionOperation
    producer_ts: int
    summary: str
    source_refs: list[str] = Field(default_factory=list)
    previous_confidence: float | None = None
    confidence: float | None = None


class ActorSceneKnowledgeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    actor_id: str
    session_id: str
    scene_id: str
    world_anchor_id: str = ""
    subject_ref: str
    target_ref: str = ""
    knowledge_type: KnowledgeType
    summary: str
    source_kind: KnowledgeSourceKind
    source_refs: list[str] = Field(default_factory=list)
    source_ref_lineage: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness: ActorSceneKnowledgeFreshness = Field(default_factory=ActorSceneKnowledgeFreshness)
    conflicts: list[ActorSceneKnowledgeConflict] = Field(default_factory=list)
    revisions: list[ActorSceneKnowledgeRevision] = Field(default_factory=list)
    advisory: bool = False
    world_truth_marker: Literal["subjective_not_world_truth", "l1_projected_fact_ref"] = "subjective_not_world_truth"

    @model_validator(mode="after")
    def validate_authority_boundary(self) -> "ActorSceneKnowledgeEntry":
        if self.target_ref == "":
            self.target_ref = self.subject_ref
        if self.world_anchor_id == "":
            self.world_anchor_id = derive_world_anchor_id(
                target_ref=self.target_ref or self.subject_ref,
                source_ref_lineage=self.source_ref_lineage,
            )
        self.source_ref_lineage = append_unique_lineage(self.source_ref_lineage, self.source_refs)
        if self.source_kind == "vla_advisory":
            self.advisory = True
        if self.advisory and self.world_truth_marker != "subjective_not_world_truth":
            raise ValueError("advisory ASK entries cannot be marked as world truth")
        return self

    @property
    def conflict_state(self) -> Literal["clear", "conflicted"]:
        return "conflicted" if any(not conflict.resolved for conflict in self.conflicts) else "clear"


class ActorSceneKnowledgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: RevisionOperation
    entry: ActorSceneKnowledgeEntry
    conflict: ActorSceneKnowledgeConflict | None = None
    active_perception_reasons: list[str] = Field(default_factory=list)


class ActorSceneKnowledgeStore:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str, str, KnowledgeType], ActorSceneKnowledgeEntry] = {}
        self.trace: list[dict[str, object]] = []

    def entries_for_actor(self, actor_id: str, *, session_id: str | None = None, scene_id: str | None = None) -> list[ActorSceneKnowledgeEntry]:
        entries = [entry for key, entry in self._entries.items() if key[0] == actor_id]
        if session_id is not None:
            entries = [entry for entry in entries if entry.session_id == session_id]
        if scene_id is not None:
            entries = [entry for entry in entries if entry.scene_id == scene_id]
        return entries

    def get(
        self,
        *,
        actor_id: str,
        session_id: str,
        scene_id: str,
        subject_ref: str,
        knowledge_type: KnowledgeType,
    ) -> ActorSceneKnowledgeEntry | None:
        world_anchor_id = derive_world_anchor_id(target_ref=subject_ref)
        return self._entries.get((actor_id, session_id, scene_id, world_anchor_id, knowledge_type)) or self._entries.get(
            (actor_id, session_id, scene_id, subject_ref, knowledge_type)
        )

    def upsert(self, incoming: ActorSceneKnowledgeEntry, *, producer_ts: int) -> ActorSceneKnowledgeUpdate:
        key = self._key(incoming)
        existing = self._entries.get(key)
        if existing is None:
            entry = incoming.model_copy(
                update={
                    "freshness": incoming.freshness.model_copy(
                        update={"observed_at": producer_ts, "last_confirmed_at": producer_ts}
                    ),
                    "revisions": [
                        self._revision(
                            incoming,
                            operation="add",
                            producer_ts=producer_ts,
                            previous_confidence=None,
                        )
                    ],
                }
            )
            self._entries[key] = entry
            update = ActorSceneKnowledgeUpdate(operation="add", entry=entry)
            self._trace(update)
            return update

        if self._is_conflict(existing, incoming):
            conflict = ActorSceneKnowledgeConflict(
                conflict_id=f"ask_conflict:{incoming.actor_id}:{incoming.world_anchor_id}:{producer_ts}:{len(existing.conflicts) + 1}",
                world_anchor_id=incoming.world_anchor_id,
                subject_ref=incoming.subject_ref,
                target_ref=incoming.target_ref,
                reason=f"{existing.source_kind}_vs_{incoming.source_kind}",
                source_refs=[*existing.source_refs, *incoming.source_refs],
                source_ref_lineage=append_unique_lineage(existing.source_ref_lineage, incoming.source_ref_lineage),
            )
            entry = existing.model_copy(
                update={
                    "freshness": existing.freshness.model_copy(update={"state": "contested"}),
                    "conflicts": [*existing.conflicts, conflict],
                    "revisions": [
                        *existing.revisions,
                        self._revision(
                            incoming,
                            operation="conflict",
                            producer_ts=producer_ts,
                            previous_confidence=existing.confidence,
                        ),
                    ],
                }
            )
            self._entries[key] = entry
            update = ActorSceneKnowledgeUpdate(
                operation="conflict",
                entry=entry,
                conflict=conflict,
                active_perception_reasons=["conflict"],
            )
            self._trace(update)
            return update

        operation: RevisionOperation = "hit"
        entry = existing.model_copy(
            update={
                "freshness": existing.freshness.model_copy(update={"state": "fresh", "last_confirmed_at": producer_ts}),
                "source_refs": self._append_unique(existing.source_refs, incoming.source_refs),
                "source_ref_lineage": self._append_unique(existing.source_ref_lineage, incoming.source_ref_lineage),
            }
        )
        if incoming.confidence > existing.confidence or incoming.summary != existing.summary:
            operation = "revise"
            entry = entry.model_copy(
                update={
                    "summary": incoming.summary,
                    "source_kind": incoming.source_kind,
                    "confidence": max(existing.confidence, incoming.confidence),
                    "world_truth_marker": incoming.world_truth_marker,
                }
            )
        entry = entry.model_copy(
            update={
                "revisions": [
                    *entry.revisions,
                    self._revision(
                        incoming,
                        operation=operation,
                        producer_ts=producer_ts,
                        previous_confidence=existing.confidence,
                    ),
                ]
            }
        )
        self._entries[key] = entry
        update = ActorSceneKnowledgeUpdate(operation=operation, entry=entry)
        self._trace(update)
        return update

    def apply_canonical_percept_bundle(
        self,
        bundle: CanonicalPerceptBundle,
        *,
        session_id: str = "default",
        producer_ts: int = 0,
    ) -> list[ActorSceneKnowledgeUpdate]:
        if bundle.consumer_kind != "character":
            raise ValueError("ActorSceneKnowledgeStore only accepts character CanonicalPerceptBundle payloads")
        scene_id = str(bundle.local_spatial_state.get("scene_id", "") or "scene_demo")
        updates: list[ActorSceneKnowledgeUpdate] = []
        target_ref = self._bundle_target_ref(bundle)
        world_anchor_id = str(bundle.target_state.get("world_anchor_id", "") or bundle.world_anchor_id or "")
        world_anchor_id = derive_world_anchor_id(
            target_ref=target_ref,
            world_anchor_id=world_anchor_id,
            source_ref_lineage=bundle.source_ref_lineage,
            candidate_object_ids=[
                str(item)
                for item in bundle.target_state.get("target_object_ids", [])
                if isinstance(item, str) and item
            ],
            candidate_actor_ids=[
                str(item)
                for item in bundle.target_state.get("target_actor_ids", [])
                if isinstance(item, str) and item
            ],
        )
        source_lineage = append_unique_lineage(bundle.source_ref_lineage, [bundle.bundle_id, bundle.query_id, *bundle.structured_fact_refs])
        if target_ref:
            updates.append(
                self.upsert(
                    ActorSceneKnowledgeEntry(
                        entry_id=f"ask:{bundle.subject_id}:{target_ref}:target",
                        actor_id=bundle.subject_id,
                        session_id=session_id,
                        scene_id=scene_id,
                        world_anchor_id=world_anchor_id,
                        subject_ref=target_ref,
                        target_ref=target_ref,
                        knowledge_type="target",
                        summary=str(bundle.target_state.get("summary", "") or f"target observed: {target_ref}"),
                        source_kind="canonical_percept_bundle",
                        source_refs=[bundle.bundle_id, bundle.query_id, *bundle.structured_fact_refs],
                        source_ref_lineage=source_lineage,
                        confidence=float(bundle.target_state.get("confidence", 0.75) or 0.75),
                    ),
                    producer_ts=producer_ts,
                )
            )
        for fact_ref in bundle.structured_fact_refs:
            fact_target_ref = target_ref or fact_ref
            updates.append(
                self.upsert(
                    ActorSceneKnowledgeEntry(
                        entry_id=f"ask:{bundle.subject_id}:{fact_target_ref}:l1",
                        actor_id=bundle.subject_id,
                        session_id=session_id,
                        scene_id=scene_id,
                        world_anchor_id=world_anchor_id
                        or derive_world_anchor_id(
                            target_ref=fact_target_ref,
                            source_ref_lineage=append_unique_lineage(source_lineage, [fact_ref]),
                        ),
                        subject_ref=fact_target_ref,
                        target_ref=fact_target_ref,
                        knowledge_type=self._knowledge_type_for_fact(fact_ref),
                        summary=f"L1 projected fact available: {fact_ref}",
                        source_kind="l1_projected_fact",
                        source_refs=[bundle.bundle_id, bundle.query_id, fact_ref],
                        source_ref_lineage=append_unique_lineage(source_lineage, [fact_ref]),
                        confidence=0.95,
                        world_truth_marker="l1_projected_fact_ref",
                    ),
                    producer_ts=producer_ts,
                )
            )
        advisory = bundle.uncertainty.get("vla_advisory") if isinstance(bundle.uncertainty, dict) else None
        if isinstance(advisory, dict):
            advisory_target_ref = str(advisory.get("target_ref", "") or target_ref or "")
            advisory_subject_ref = str(advisory.get("subject_ref", "") or advisory_target_ref or f"vla:{bundle.bundle_id}")
            advisory_anchor = str(advisory.get("world_anchor_id", "") or world_anchor_id or "")
            advisory_lineage = append_unique_lineage(
                source_lineage,
                [str(ref) for ref in advisory.get("source_ref_lineage", []) if isinstance(ref, str)],
            )
            updates.append(
                self.upsert(
                    ActorSceneKnowledgeEntry(
                        entry_id=f"ask:{bundle.subject_id}:{advisory_subject_ref}:vla",
                        actor_id=bundle.subject_id,
                        session_id=session_id,
                        scene_id=scene_id,
                        world_anchor_id=derive_world_anchor_id(
                            target_ref=advisory_target_ref or advisory_subject_ref,
                            world_anchor_id=advisory_anchor,
                            source_ref_lineage=advisory_lineage,
                        ),
                        subject_ref=advisory_subject_ref,
                        target_ref=advisory_target_ref or advisory_subject_ref,
                        knowledge_type=self._knowledge_type_for_fact(advisory_subject_ref),
                        summary=str(advisory.get("summary", "") or "VLA advisory spatial finding"),
                        source_kind="vla_advisory",
                        source_refs=[bundle.bundle_id, bundle.query_id, *[str(ref) for ref in advisory.get("source_refs", [])]],
                        source_ref_lineage=advisory_lineage,
                        confidence=float(advisory.get("confidence", 0.55) or 0.55),
                        advisory=True,
                    ),
                    producer_ts=producer_ts,
                )
            )
        return updates

    def record_failure(
        self,
        *,
        actor_id: str,
        session_id: str,
        scene_id: str,
        subject_ref: str,
        failure_kind: Literal["interaction_failure", "world_failure", "embodied_failure"],
        reason: str,
        source_refs: list[str],
        producer_ts: int,
    ) -> ActorSceneKnowledgeUpdate:
        return self.upsert(
            ActorSceneKnowledgeEntry(
                entry_id=f"ask:{actor_id}:{subject_ref}:{failure_kind}",
                actor_id=actor_id,
                session_id=session_id,
                scene_id=scene_id,
                world_anchor_id=derive_world_anchor_id(target_ref=subject_ref),
                subject_ref=subject_ref,
                target_ref=subject_ref,
                knowledge_type="failure",
                summary=reason,
                source_kind=failure_kind,
                source_refs=source_refs,
                source_ref_lineage=list(source_refs),
                confidence=0.8,
            ),
            producer_ts=producer_ts,
        )

    def mark_stale(self, entry_id: str, *, producer_ts: int, reason: str = "stale_before_action") -> ActorSceneKnowledgeUpdate:
        entry = self._entry_by_id(entry_id)
        updated = entry.model_copy(
            update={
                "freshness": entry.freshness.model_copy(update={"state": "stale"}),
                "revisions": [
                    *entry.revisions,
                    ActorSceneKnowledgeRevision(
                        revision_id=f"ask_revision:{entry.entry_id}:{producer_ts}:stale",
                        operation="stale",
                        producer_ts=producer_ts,
                        summary=reason,
                        source_refs=[],
                        previous_confidence=entry.confidence,
                        confidence=entry.confidence,
                    ),
                ],
            }
        )
        self._entries[self._key(updated)] = updated
        update = ActorSceneKnowledgeUpdate(operation="stale", entry=updated, active_perception_reasons=["stale"])
        self._trace(update)
        return update

    def expire(self, *, now: int) -> list[ActorSceneKnowledgeUpdate]:
        updates: list[ActorSceneKnowledgeUpdate] = []
        for entry in list(self._entries.values()):
            if entry.freshness.expires_at is None or now < entry.freshness.expires_at:
                continue
            if entry.freshness.state == "expired":
                continue
            updated = entry.model_copy(update={"freshness": entry.freshness.model_copy(update={"state": "expired"})})
            self._entries[self._key(updated)] = updated
            update = ActorSceneKnowledgeUpdate(operation="expire", entry=updated, active_perception_reasons=["expired"])
            self._trace(update)
            updates.append(update)
        return updates

    def resolve_conflict(self, *, entry_id: str, conflict_id: str, result_ref: str, producer_ts: int) -> ActorSceneKnowledgeUpdate:
        entry = self._entry_by_id(entry_id)
        conflicts = [
            conflict.model_copy(update={"resolved": True, "resolved_by_ref": result_ref})
            if conflict.conflict_id == conflict_id
            else conflict
            for conflict in entry.conflicts
        ]
        freshness_state: FreshnessState = "fresh" if all(conflict.resolved for conflict in conflicts) else "contested"
        updated = entry.model_copy(
            update={
                "conflicts": conflicts,
                "freshness": entry.freshness.model_copy(update={"state": freshness_state, "last_confirmed_at": producer_ts}),
                "revisions": [
                    *entry.revisions,
                    ActorSceneKnowledgeRevision(
                        revision_id=f"ask_revision:{entry.entry_id}:{producer_ts}:resolve",
                        operation="resolve",
                        producer_ts=producer_ts,
                        summary=f"resolved by {result_ref}",
                        source_refs=[result_ref],
                        previous_confidence=entry.confidence,
                        confidence=entry.confidence,
                    ),
                ],
            }
        )
        self._entries[self._key(updated)] = updated
        update = ActorSceneKnowledgeUpdate(operation="resolve", entry=updated)
        self._trace(update)
        return update

    def _entry_by_id(self, entry_id: str) -> ActorSceneKnowledgeEntry:
        for entry in self._entries.values():
            if entry.entry_id == entry_id:
                return entry
        raise KeyError(entry_id)

    def _is_conflict(self, existing: ActorSceneKnowledgeEntry, incoming: ActorSceneKnowledgeEntry) -> bool:
        if existing.summary == incoming.summary:
            return False
        if existing.world_truth_marker == "l1_projected_fact_ref" and incoming.source_kind == "vla_advisory":
            return True
        if existing.source_kind == "vla_advisory" and incoming.world_truth_marker == "l1_projected_fact_ref":
            return True
        if incoming.source_kind.endswith("failure") and existing.confidence >= 0.7:
            return True
        return False

    def _revision(
        self,
        incoming: ActorSceneKnowledgeEntry,
        *,
        operation: RevisionOperation,
        producer_ts: int,
        previous_confidence: float | None,
    ) -> ActorSceneKnowledgeRevision:
        return ActorSceneKnowledgeRevision(
            revision_id=f"ask_revision:{incoming.entry_id}:{producer_ts}:{operation}",
            operation=operation,
            producer_ts=producer_ts,
            summary=incoming.summary,
            source_refs=list(incoming.source_refs),
            previous_confidence=previous_confidence,
            confidence=incoming.confidence,
        )

    def _trace(self, update: ActorSceneKnowledgeUpdate) -> None:
        self.trace.append(
            {
                "operation": update.operation,
                "entry_id": update.entry.entry_id,
                "actor_id": update.entry.actor_id,
                "session_id": update.entry.session_id,
                "scene_id": update.entry.scene_id,
                "world_anchor_id": update.entry.world_anchor_id,
                "subject_ref": update.entry.subject_ref,
                "target_ref": update.entry.target_ref,
                "freshness": update.entry.freshness.state,
                "conflict_state": update.entry.conflict_state,
                "active_perception_reasons": list(update.active_perception_reasons),
            }
        )

    def _key(self, entry: ActorSceneKnowledgeEntry) -> tuple[str, str, str, str, KnowledgeType]:
        return (entry.actor_id, entry.session_id, entry.scene_id, entry.world_anchor_id or entry.subject_ref, entry.knowledge_type)

    def _append_unique(self, existing: list[str], incoming: list[str]) -> list[str]:
        merged = list(existing)
        for value in incoming:
            if value not in merged:
                merged.append(value)
        return merged

    def _bundle_target_ref(self, bundle: CanonicalPerceptBundle) -> str:
        target_ref = str(bundle.target_state.get("target_ref", "") or "")
        if target_ref:
            return target_ref
        attention = bundle.attention_state
        for key in ("target_actor_ids", "target_object_ids", "target_environment_ids"):
            values = attention.get(key, [])
            if isinstance(values, list) and values:
                return str(values[0])
        return ""

    def _knowledge_type_for_fact(self, fact_ref: str) -> KnowledgeType:
        if "occlusion" in fact_ref or "line_of_sight" in fact_ref:
            return "occlusion"
        if "path" in fact_ref or "reachable" in fact_ref or "target_unreachable" in fact_ref:
            return "path"
        if "environment" in fact_ref or "light" in fact_ref or "visibility" in fact_ref:
            return "environment"
        if "affordance" in fact_ref or "grabbable" in fact_ref:
            return "affordance"
        return "space"
