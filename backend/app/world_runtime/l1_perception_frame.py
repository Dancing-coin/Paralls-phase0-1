from __future__ import annotations

from app.world_runtime.intelligence_upgrade import (
    CanonicalPerceptBundle,
    PerceptionQueryFrame,
    SampleInputRef,
    SpatialReference,
    TimeWindow,
)


class L1PerceptionFrameService:
    def build_character_frame(
        self,
        *,
        subject_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        started_at: int,
        ended_at: int,
        visual_inputs: list[SampleInputRef] | None = None,
        spatial_inputs: list[SampleInputRef] | None = None,
        auditory_inputs: list[SampleInputRef] | None = None,
        embodied_inputs: list[SampleInputRef] | None = None,
        structured_fact_refs: list[str] | None = None,
        attention_target_actor_ids: list[str] | None = None,
        attention_target_object_ids: list[str] | None = None,
    ) -> PerceptionQueryFrame:
        return PerceptionQueryFrame(
            query_id=f"pqf:{subject_id}:{ended_at}",
            consumer_kind="character",
            subject_id=subject_id,
            time_window=TimeWindow(started_at=started_at, ended_at=ended_at),
            spatial_reference=SpatialReference(room_id=room_id, scene_id=scene_id, zone_id=zone_id),
            attention_context={
                "target_actor_ids": attention_target_actor_ids or [],
                "target_object_ids": attention_target_object_ids or [],
                "target_environment_ids": [],
                "reason_tags": ["l1_world_fact_projection"],
            },
            visual_inputs=visual_inputs or [],
            spatial_inputs=spatial_inputs or [],
            auditory_inputs=auditory_inputs or [],
            embodied_inputs=embodied_inputs or [],
            structured_fact_refs=structured_fact_refs or [],
            multimodal_context_id=f"character_mm:{subject_id}",
            cache_namespace=f"character_mm:{subject_id}:l1_world_fact_cache",
            inference_history_ref=f"character_mm:{subject_id}:l1_world_fact_history",
        )

    def build_siming_frame(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        started_at: int,
        ended_at: int,
        environment_inputs: list[SampleInputRef] | None = None,
        structured_fact_refs: list[str] | None = None,
    ) -> PerceptionQueryFrame:
        return PerceptionQueryFrame(
            query_id=f"pqf:siming:{room_id}:{ended_at}",
            consumer_kind="siming",
            subject_id="siming",
            time_window=TimeWindow(started_at=started_at, ended_at=ended_at),
            spatial_reference=SpatialReference(room_id=room_id, scene_id=scene_id, zone_id=zone_id),
            environment_inputs=environment_inputs or [],
            structured_fact_refs=structured_fact_refs or [],
            multimodal_context_id=f"siming_mm:{room_id}:{scene_id}",
            cache_namespace=f"siming_mm:{room_id}:{scene_id}:l1_world_fact_cache",
            inference_history_ref=f"siming_mm:{room_id}:{scene_id}:l1_world_fact_history",
        )

    def build_canonical_bundle(
        self,
        frame: PerceptionQueryFrame,
        *,
        local_spatial_state: dict[str, object],
        target_state: dict[str, object],
        environment_state: dict[str, object],
        embodied_state: dict[str, object] | None = None,
        uncertainty: dict[str, object] | None = None,
    ) -> CanonicalPerceptBundle:
        return CanonicalPerceptBundle(
            bundle_id=f"bundle:{frame.consumer_kind}:{frame.subject_id}:{frame.time_window.ended_at}",
            consumer_kind=frame.consumer_kind,
            subject_id=frame.subject_id,
            query_id=frame.query_id,
            percept_context_id=frame.multimodal_context_id,
            local_spatial_state=local_spatial_state,
            target_state=target_state,
            environment_state=environment_state,
            embodied_state=embodied_state or {},
            attention_state=frame.attention_context.model_dump(),
            structured_fact_refs=list(frame.structured_fact_refs),
            uncertainty=uncertainty or {},
        )
