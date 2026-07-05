from __future__ import annotations

from app.world_runtime.intelligence_upgrade import (
    CanonicalPerceptBundle,
    PerceptionInputFrame,
    PerceptionQueryFrame,
    SampleInputRef,
    SpatialReference,
    TimeWindow,
)
from app.models.capture_clock import derive_capture_id, derive_capture_root_id
from app.models.object_anchor import append_unique_lineage, derive_world_anchor_id, first_target_ref


class L1PerceptionFrameService:
    def build_character_input_frame(
        self,
        *,
        subject_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        started_at: int,
        ended_at: int,
        capture_root_id: str = "",
        capture_id: str = "",
        clock_domain: str = "backend_monotonic",
        monotonic_tick: int | None = None,
        source_frame_index: int | None = None,
        wall_clock_ts: int | None = None,
        subject_ref: str = "",
        target_ref: str = "",
        world_anchor_id: str = "",
        source_ref_lineage: list[str] | None = None,
        actor_frame_ref: str = "",
        camera_frame_ref: str = "",
        listener_frame_ref: str = "",
        visual_inputs: list[SampleInputRef] | None = None,
        spatial_inputs: list[SampleInputRef] | None = None,
        auditory_inputs: list[SampleInputRef] | None = None,
        embodied_inputs: list[SampleInputRef] | None = None,
        skeletal_inputs: list[SampleInputRef] | None = None,
        environment_inputs: list[SampleInputRef] | None = None,
        structured_fact_refs: list[str] | None = None,
        attention_target_actor_ids: list[str] | None = None,
        attention_target_object_ids: list[str] | None = None,
        reason_tags: list[str] | None = None,
    ) -> PerceptionInputFrame:
        return PerceptionInputFrame(
            capture_root_id=capture_root_id,
            capture_id=capture_id,
            consumer_kind="character",
            subject_id=subject_id,
            subject_ref=subject_ref or subject_id,
            target_ref=target_ref,
            world_anchor_id=world_anchor_id,
            source_ref_lineage=list(source_ref_lineage or []),
            clock_domain=clock_domain,
            monotonic_tick=monotonic_tick,
            source_frame_index=source_frame_index,
            wall_clock_ts=wall_clock_ts,
            started_at=started_at,
            ended_at=ended_at,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_frame_ref=actor_frame_ref,
            camera_frame_ref=camera_frame_ref,
            listener_frame_ref=listener_frame_ref,
            visual_inputs=visual_inputs or [],
            spatial_inputs=spatial_inputs or [],
            auditory_inputs=auditory_inputs or [],
            embodied_inputs=embodied_inputs or [],
            skeletal_inputs=skeletal_inputs or [],
            environment_inputs=environment_inputs or [],
            structured_fact_refs=structured_fact_refs or [],
            target_actor_ids=attention_target_actor_ids or [],
            target_object_ids=attention_target_object_ids or [],
            target_environment_ids=[],
            reason_tags=reason_tags or ["l1_world_fact_projection"],
        )

    def build_siming_input_frame(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        started_at: int,
        ended_at: int,
        capture_root_id: str = "",
        capture_id: str = "",
        clock_domain: str = "backend_monotonic",
        monotonic_tick: int | None = None,
        source_frame_index: int | None = None,
        wall_clock_ts: int | None = None,
        subject_ref: str = "siming",
        target_ref: str = "",
        world_anchor_id: str = "",
        source_ref_lineage: list[str] | None = None,
        actor_frame_ref: str = "",
        camera_frame_ref: str = "",
        listener_frame_ref: str = "",
        environment_inputs: list[SampleInputRef] | None = None,
        structured_fact_refs: list[str] | None = None,
        reason_tags: list[str] | None = None,
    ) -> PerceptionInputFrame:
        return PerceptionInputFrame(
            capture_root_id=capture_root_id,
            capture_id=capture_id,
            consumer_kind="siming",
            subject_id="siming",
            subject_ref=subject_ref,
            target_ref=target_ref,
            world_anchor_id=world_anchor_id,
            source_ref_lineage=list(source_ref_lineage or []),
            clock_domain=clock_domain,
            monotonic_tick=monotonic_tick,
            source_frame_index=source_frame_index,
            wall_clock_ts=wall_clock_ts,
            started_at=started_at,
            ended_at=ended_at,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_frame_ref=actor_frame_ref,
            camera_frame_ref=camera_frame_ref,
            listener_frame_ref=listener_frame_ref,
            environment_inputs=environment_inputs or [],
            structured_fact_refs=structured_fact_refs or [],
            reason_tags=reason_tags or ["l1_world_fact_projection"],
        )

    def build_frame_from_input(self, input_frame: PerceptionInputFrame) -> PerceptionQueryFrame:
        attention_context = {
            "target_actor_ids": list(input_frame.target_actor_ids),
            "target_object_ids": list(input_frame.target_object_ids),
            "target_environment_ids": list(input_frame.target_environment_ids),
            "reason_tags": list(input_frame.reason_tags),
        }
        return PerceptionQueryFrame(
            query_id=f"pqf:{input_frame.subject_id}:{input_frame.ended_at}",
            consumer_kind=input_frame.consumer_kind,
            subject_id=input_frame.subject_id,
            subject_ref=input_frame.subject_ref,
            target_ref=input_frame.target_ref,
            world_anchor_id=derive_world_anchor_id(
                target_ref=input_frame.target_ref,
                world_anchor_id=input_frame.world_anchor_id,
                source_ref_lineage=input_frame.source_ref_lineage,
                candidate_object_ids=input_frame.target_object_ids,
                candidate_actor_ids=input_frame.target_actor_ids,
                candidate_environment_ids=input_frame.target_environment_ids,
            ),
            source_ref_lineage=list(input_frame.source_ref_lineage),
            capture_root_id=input_frame.capture_root_id,
            capture_id=input_frame.capture_id,
            clock_domain=input_frame.clock_domain,
            monotonic_tick=input_frame.monotonic_tick,
            source_frame_index=input_frame.source_frame_index,
            wall_clock_ts=input_frame.wall_clock_ts,
            time_window=TimeWindow(started_at=input_frame.started_at, ended_at=input_frame.ended_at),
            spatial_reference=SpatialReference(
                room_id=input_frame.room_id,
                scene_id=input_frame.scene_id,
                zone_id=input_frame.zone_id,
                actor_frame_ref=input_frame.actor_frame_ref,
                camera_frame_ref=input_frame.camera_frame_ref,
                listener_frame_ref=input_frame.listener_frame_ref,
            ),
            attention_context=attention_context,
            visual_inputs=self._inherit_capture_clock(input_frame.visual_inputs, **self._capture_kwargs(input_frame)),
            spatial_inputs=self._inherit_capture_clock(input_frame.spatial_inputs, **self._capture_kwargs(input_frame)),
            auditory_inputs=self._inherit_capture_clock(input_frame.auditory_inputs, **self._capture_kwargs(input_frame)),
            embodied_inputs=self._inherit_capture_clock(input_frame.embodied_inputs, **self._capture_kwargs(input_frame)),
            skeletal_inputs=self._inherit_capture_clock(input_frame.skeletal_inputs, **self._capture_kwargs(input_frame)),
            environment_inputs=self._inherit_capture_clock(input_frame.environment_inputs, **self._capture_kwargs(input_frame)),
            structured_fact_refs=list(input_frame.structured_fact_refs),
            multimodal_context_id=(
                f"character_mm:{input_frame.subject_id}"
                if input_frame.consumer_kind == "character"
                else f"siming_mm:{input_frame.room_id}:{input_frame.scene_id}"
            ),
            cache_namespace=(
                f"character_mm:{input_frame.subject_id}:l1_world_fact_cache"
                if input_frame.consumer_kind == "character"
                else f"siming_mm:{input_frame.room_id}:{input_frame.scene_id}:l1_world_fact_cache"
            ),
            inference_history_ref=(
                f"character_mm:{input_frame.subject_id}:l1_world_fact_history"
                if input_frame.consumer_kind == "character"
                else f"siming_mm:{input_frame.room_id}:{input_frame.scene_id}:l1_world_fact_history"
            ),
        )

    @staticmethod
    def _capture_kwargs(input_frame: PerceptionInputFrame) -> dict[str, object]:
        return {
            "capture_root_id": input_frame.capture_root_id,
            "capture_id": input_frame.capture_id,
            "clock_domain": input_frame.clock_domain,
            "monotonic_tick": input_frame.monotonic_tick,
            "source_frame_index": input_frame.source_frame_index,
            "wall_clock_ts": input_frame.wall_clock_ts,
        }

    def build_character_frame(
        self,
        *,
        subject_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        started_at: int,
        ended_at: int,
        capture_root_id: str = "",
        capture_id: str = "",
        clock_domain: str = "backend_monotonic",
        monotonic_tick: int | None = None,
        source_frame_index: int | None = None,
        wall_clock_ts: int | None = None,
        subject_ref: str = "",
        target_ref: str = "",
        world_anchor_id: str = "",
        source_ref_lineage: list[str] | None = None,
        actor_frame_ref: str = "",
        camera_frame_ref: str = "",
        listener_frame_ref: str = "",
        visual_inputs: list[SampleInputRef] | None = None,
        spatial_inputs: list[SampleInputRef] | None = None,
        auditory_inputs: list[SampleInputRef] | None = None,
        embodied_inputs: list[SampleInputRef] | None = None,
        skeletal_inputs: list[SampleInputRef] | None = None,
        environment_inputs: list[SampleInputRef] | None = None,
        structured_fact_refs: list[str] | None = None,
        attention_target_actor_ids: list[str] | None = None,
        attention_target_object_ids: list[str] | None = None,
    ) -> PerceptionQueryFrame:
        input_frame = self.build_character_input_frame(
            subject_id=subject_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            started_at=started_at,
            ended_at=ended_at,
            capture_root_id=capture_root_id,
            capture_id=capture_id,
            clock_domain=clock_domain,
            monotonic_tick=monotonic_tick,
            source_frame_index=source_frame_index,
            wall_clock_ts=wall_clock_ts,
            subject_ref=subject_ref,
            target_ref=target_ref,
            world_anchor_id=world_anchor_id,
            source_ref_lineage=source_ref_lineage,
            actor_frame_ref=actor_frame_ref,
            camera_frame_ref=camera_frame_ref,
            listener_frame_ref=listener_frame_ref,
            visual_inputs=visual_inputs,
            spatial_inputs=spatial_inputs,
            auditory_inputs=auditory_inputs,
            embodied_inputs=embodied_inputs,
            skeletal_inputs=skeletal_inputs,
            environment_inputs=environment_inputs,
            structured_fact_refs=structured_fact_refs,
            attention_target_actor_ids=attention_target_actor_ids,
            attention_target_object_ids=attention_target_object_ids,
        )
        return self.build_frame_from_input(input_frame)

    def build_siming_frame(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        started_at: int,
        ended_at: int,
        capture_root_id: str = "",
        capture_id: str = "",
        clock_domain: str = "backend_monotonic",
        monotonic_tick: int | None = None,
        source_frame_index: int | None = None,
        wall_clock_ts: int | None = None,
        subject_ref: str = "siming",
        target_ref: str = "",
        world_anchor_id: str = "",
        source_ref_lineage: list[str] | None = None,
        actor_frame_ref: str = "",
        camera_frame_ref: str = "",
        listener_frame_ref: str = "",
        environment_inputs: list[SampleInputRef] | None = None,
        structured_fact_refs: list[str] | None = None,
    ) -> PerceptionQueryFrame:
        input_frame = self.build_siming_input_frame(
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            started_at=started_at,
            ended_at=ended_at,
            capture_root_id=capture_root_id,
            capture_id=capture_id,
            clock_domain=clock_domain,
            monotonic_tick=monotonic_tick,
            source_frame_index=source_frame_index,
            wall_clock_ts=wall_clock_ts,
            subject_ref=subject_ref,
            target_ref=target_ref,
            world_anchor_id=world_anchor_id,
            source_ref_lineage=source_ref_lineage,
            actor_frame_ref=actor_frame_ref,
            camera_frame_ref=camera_frame_ref,
            listener_frame_ref=listener_frame_ref,
            environment_inputs=environment_inputs,
            structured_fact_refs=structured_fact_refs,
        )
        return self.build_frame_from_input(input_frame)

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
        target_state = dict(target_state)
        if frame.subject_ref:
            target_state.setdefault("subject_ref", frame.subject_ref)
        if frame.target_ref:
            target_state.setdefault("target_ref", frame.target_ref)
        if frame.world_anchor_id:
            target_state.setdefault("world_anchor_id", frame.world_anchor_id)
        if frame.source_ref_lineage:
            target_state.setdefault("source_ref_lineage", list(frame.source_ref_lineage))
        target_state.setdefault("target_actor_ids", list(frame.attention_context.target_actor_ids))
        target_state.setdefault("target_object_ids", list(frame.attention_context.target_object_ids))
        target_state.setdefault("target_environment_ids", list(frame.attention_context.target_environment_ids))
        return CanonicalPerceptBundle(
            bundle_id=f"bundle:{frame.consumer_kind}:{frame.subject_id}:{frame.time_window.ended_at}",
            consumer_kind=frame.consumer_kind,
            subject_id=frame.subject_id,
            query_id=frame.query_id,
            subject_ref=frame.subject_ref,
            target_ref=frame.target_ref,
            world_anchor_id=frame.world_anchor_id,
            source_ref_lineage=list(frame.source_ref_lineage),
            capture_root_id=frame.capture_root_id,
            capture_id=frame.capture_id,
            clock_domain=frame.clock_domain,
            monotonic_tick=frame.monotonic_tick,
            source_frame_index=frame.source_frame_index,
            wall_clock_ts=frame.wall_clock_ts,
            percept_context_id=frame.multimodal_context_id,
            local_spatial_state=local_spatial_state,
            target_state=target_state,
            environment_state=environment_state,
            embodied_state=embodied_state or {},
            attention_state=frame.attention_context.model_dump(),
            structured_fact_refs=list(frame.structured_fact_refs),
            uncertainty=uncertainty or {},
        )

    @staticmethod
    def _inherit_capture_clock(
        refs: list[SampleInputRef],
        *,
        capture_root_id: str,
        capture_id: str,
        clock_domain: str,
        monotonic_tick: int | None,
        source_frame_index: int | None,
        wall_clock_ts: int | None,
    ) -> list[SampleInputRef]:
        updated: list[SampleInputRef] = []
        for ref in refs:
            changes: dict[str, object] = {}
            if ref.capture_root_id == "":
                changes["capture_root_id"] = capture_root_id
            if ref.capture_id == "":
                changes["capture_id"] = capture_id
            if ref.clock_domain == "":
                changes["clock_domain"] = clock_domain
            if ref.monotonic_tick is None:
                changes["monotonic_tick"] = monotonic_tick
            if ref.source_frame_index is None:
                changes["source_frame_index"] = source_frame_index
            if ref.wall_clock_ts is None:
                changes["wall_clock_ts"] = wall_clock_ts
            updated.append(SampleInputRef(**{**ref.model_dump(), **changes}) if changes else ref)
        return updated
