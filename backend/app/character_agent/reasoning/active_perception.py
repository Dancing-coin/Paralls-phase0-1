from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeStore
from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef
from app.world_runtime.l1_perception_frame import L1PerceptionFrameService


ActivePerceptionReason = Literal[
    "conflict",
    "stale",
    "expired",
    "expected_target_missing",
    "repeated_reachability_failure",
    "embodied_reachability_failure",
]


class ActivePerceptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    actor_id: str
    session_id: str
    room_id: str
    scene_id: str
    zone_id: str
    subject_ref: str
    reason: ActivePerceptionReason
    source_entry_ids: list[str] = Field(default_factory=list)
    required_provider_kinds: list[str] = Field(
        default_factory=lambda: ["visual_patch", "spatial_patch", "embodied_state", "environment_field"]
    )
    pqf_query_id: str = ""
    must_use_provider_chain: bool = True

    def to_pqf(self, *, started_at: int, ended_at: int) -> PerceptionQueryFrame:
        service = L1PerceptionFrameService()
        provider_ref = SampleInputRef(
            provider_kind="spatial_patch",
            ref_id=f"provider_ref:{self.request_id}:spatial_patch",
            summary=f"active perception recheck for {self.subject_ref}",
            runtime_source_refs=[self.request_id, *self.source_entry_ids],
        )
        frame = service.build_character_frame(
            subject_id=self.actor_id,
            room_id=self.room_id,
            scene_id=self.scene_id,
            zone_id=self.zone_id,
            started_at=started_at,
            ended_at=ended_at,
            spatial_inputs=[provider_ref],
            structured_fact_refs=[f"active_perception_request:{self.request_id}"],
            attention_target_object_ids=[self.subject_ref],
        )
        self.pqf_query_id = frame.query_id
        return frame


class ActivePerceptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    request_id: str
    actor_id: str
    session_id: str
    scene_id: str
    subject_ref: str
    pqf_query_id: str
    provider_result_refs: list[str]
    source_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness: Literal["fresh", "stale", "expired", "contested"] = "fresh"
    summary: str
    conflict_refs: list[str] = Field(default_factory=list)
    failure_reason: str = ""

    @model_validator(mode="after")
    def validate_provider_chain(self) -> "ActivePerceptionResult":
        if not self.pqf_query_id.startswith("pqf:"):
            raise ValueError("ActivePerceptionResult must reference a PerceptionQueryFrame")
        if not self.provider_result_refs:
            raise ValueError("ActivePerceptionResult must carry provider result refs")
        return self


class ActivePerceptionPlanner:
    def requests_for_actor(
        self,
        store: ActorSceneKnowledgeStore,
        *,
        actor_id: str,
        session_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
    ) -> list[ActivePerceptionRequest]:
        requests: list[ActivePerceptionRequest] = []
        for entry in store.entries_for_actor(actor_id, session_id=session_id, scene_id=scene_id):
            reason: ActivePerceptionReason | None = None
            if entry.conflict_state == "conflicted":
                reason = "conflict"
            elif entry.freshness.state == "stale":
                reason = "stale"
            elif entry.freshness.state == "expired":
                reason = "expired"
            elif entry.source_kind == "interaction_failure":
                reason = "repeated_reachability_failure"
            elif entry.source_kind == "embodied_failure":
                reason = "embodied_reachability_failure"
            if reason is None:
                continue
            requests.append(
                ActivePerceptionRequest(
                    request_id=f"active_perception:{actor_id}:{entry.subject_ref}:{reason}:{len(requests) + 1}",
                    actor_id=actor_id,
                    session_id=session_id,
                    room_id=room_id,
                    scene_id=scene_id,
                    zone_id=zone_id,
                    subject_ref=entry.subject_ref,
                    reason=reason,
                    source_entry_ids=[entry.entry_id],
                )
            )
        return requests

    def apply_result(self, store: ActorSceneKnowledgeStore, result: ActivePerceptionResult, *, producer_ts: int):
        from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry

        update = store.upsert(
            ActorSceneKnowledgeEntry(
                entry_id=f"ask:{result.actor_id}:{result.subject_ref}:active_perception",
                actor_id=result.actor_id,
                session_id=result.session_id,
                scene_id=result.scene_id,
                subject_ref=result.subject_ref,
                knowledge_type="space",
                summary=result.summary,
                source_kind="active_perception",
                source_refs=[result.result_id, result.request_id, result.pqf_query_id, *result.provider_result_refs],
                confidence=result.confidence,
            ),
            producer_ts=producer_ts,
        )
        if result.conflict_refs and update.entry.conflicts:
            store.resolve_conflict(
                entry_id=update.entry.entry_id,
                conflict_id=update.entry.conflicts[-1].conflict_id,
                result_ref=result.result_id,
                producer_ts=producer_ts,
            )
        return update
