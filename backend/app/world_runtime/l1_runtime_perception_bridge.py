from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.models.raw_fact import RawFactEvent
from app.world_runtime.intelligence_upgrade import SampleInputRef
from app.world_runtime.l1_occupancy import SpatialOccupancySnapshot
from app.world_runtime.l1_perception_frame import L1PerceptionFrameService


class CharacterBundleConsumer(Protocol):
    def ingest_canonical_percept_bundle(self, bundle: Any) -> Any: ...


class SimingBundleConsumer(Protocol):
    def ingest_canonical_percept_bundle(self, bundle: Any) -> Any: ...


class L1PerceptionBridgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_frame: dict[str, Any]
    character_bundle: dict[str, Any]
    character_private_snapshot: dict[str, Any]
    character_working_memory: dict[str, Any] = Field(default_factory=dict)
    siming_frame: dict[str, Any]
    siming_bundle: dict[str, Any]
    siming_result: dict[str, Any]
    context_isolation: dict[str, str | bool]


class L1RuntimePerceptionBridge:
    """Adapts projected L1 facts into existing character/Siming runtime ingestion APIs."""

    def __init__(self, frame_service: L1PerceptionFrameService | None = None) -> None:
        self._frame_service = frame_service or L1PerceptionFrameService()

    def consume_projected_facts(
        self,
        *,
        occupancy: SpatialOccupancySnapshot,
        projected_facts: list[RawFactEvent],
        character_runtime: CharacterBundleConsumer,
        siming_runtime: SimingBundleConsumer,
        actor_id: str,
        provider_refs: dict[str, list[dict[str, str]]] | None = None,
    ) -> L1PerceptionBridgeResult | None:
        if not projected_facts:
            return None

        refs = provider_refs or self._default_provider_refs(
            occupancy=occupancy,
            facts=projected_facts,
            actor_id=actor_id,
        )
        fact_refs = [self._structured_fact_ref(fact) for fact in projected_facts]
        first_fact = projected_facts[0]
        ended_at = max(fact.producer_ts for fact in projected_facts)
        started_at = min(fact.producer_ts for fact in projected_facts)
        zone_id = self._zone_for_actor(occupancy, actor_id) or first_fact.zone_id
        target_actor_ids = sorted({fact.targets.actor_id for fact in projected_facts if fact.targets.actor_id})
        target_object_ids = sorted({fact.targets.object_id for fact in projected_facts if fact.targets.object_id})

        character_frame = self._frame_service.build_character_frame(
            subject_id=actor_id,
            room_id=first_fact.room_id,
            scene_id=first_fact.scene_id,
            zone_id=zone_id,
            started_at=started_at,
            ended_at=ended_at,
            visual_inputs=self._sample_refs(refs.get("visual_inputs", [])),
            spatial_inputs=self._sample_refs(refs.get("spatial_inputs", [])),
            auditory_inputs=self._sample_refs(refs.get("auditory_inputs", [])),
            embodied_inputs=self._sample_refs(refs.get("embodied_inputs", [])),
            skeletal_inputs=self._sample_refs(refs.get("skeletal_inputs", [])),
            environment_inputs=self._sample_refs(refs.get("environment_inputs", [])),
            structured_fact_refs=fact_refs,
            attention_target_actor_ids=target_actor_ids,
            attention_target_object_ids=target_object_ids,
        )
        character_bundle = self._frame_service.build_canonical_bundle(
            character_frame,
            local_spatial_state=self._local_spatial_state(occupancy, zone_id),
            target_state=self._target_state(occupancy, target_actor_ids, target_object_ids),
            environment_state=self._environment_state(occupancy, zone_id),
            embodied_state=self._embodied_state(refs),
            uncertainty=self._uncertainty(projected_facts),
        )
        character_snapshot = character_runtime.ingest_canonical_percept_bundle(character_bundle)
        working_memory = {}
        get_working_memory = getattr(character_runtime, "get_working_memory_state", None)
        if callable(get_working_memory):
            working_memory = get_working_memory(actor_id, character_snapshot.model_dump())

        siming_frame = self._frame_service.build_siming_frame(
            room_id=first_fact.room_id,
            scene_id=first_fact.scene_id,
            zone_id=zone_id,
            started_at=started_at,
            ended_at=ended_at,
            environment_inputs=self._sample_refs(refs.get("environment_inputs", refs.get("spatial_inputs", []))),
            structured_fact_refs=fact_refs,
        )
        siming_bundle = self._frame_service.build_canonical_bundle(
            siming_frame,
            local_spatial_state={
                "room_id": first_fact.room_id,
                "scene_id": first_fact.scene_id,
                "zone_id": zone_id,
                "dirty_zone_ids": list(occupancy.dirty_zone_ids),
            },
            target_state={
                "affected_actors": target_actor_ids or [actor_id],
                "affected_objects": target_object_ids,
            },
            environment_state=self._environment_state(occupancy, zone_id),
            uncertainty=self._uncertainty(projected_facts),
        )
        siming_result = siming_runtime.ingest_canonical_percept_bundle(siming_bundle)

        return L1PerceptionBridgeResult(
            character_frame=character_frame.model_dump(),
            character_bundle=character_bundle.model_dump(),
            character_private_snapshot=character_snapshot.model_dump(),
            character_working_memory=working_memory,
            siming_frame=siming_frame.model_dump(),
            siming_bundle=siming_bundle.model_dump(),
            siming_result=siming_result.model_dump(),
            context_isolation={
                "character_context": character_frame.multimodal_context_id,
                "siming_context": siming_frame.multimodal_context_id,
                "character_cache": character_frame.cache_namespace,
                "siming_cache": siming_frame.cache_namespace,
                "isolated": (
                    character_frame.multimodal_context_id.startswith("character_mm:")
                    and siming_frame.multimodal_context_id.startswith("siming_mm:")
                    and character_frame.cache_namespace != siming_frame.cache_namespace
                ),
            },
        )

    def _default_provider_refs(
        self,
        *,
        occupancy: SpatialOccupancySnapshot,
        facts: list[RawFactEvent],
        actor_id: str,
    ) -> dict[str, list[dict[str, str]]]:
        first_fact = facts[0]
        zone_id = self._zone_for_actor(occupancy, actor_id) or first_fact.zone_id
        ended_at = max(fact.producer_ts for fact in facts)
        return {
            "visual_inputs": [
                {
                    "provider_kind": "visual_patch",
                    "ref_id": f"runtime://camera/MainCamera/frame/{ended_at}",
                    "summary": "runtime camera pose and viewport capture ref",
                    "retention": "debug_artifact",
                }
            ],
            "spatial_inputs": [
                {
                    "provider_kind": "spatial_patch",
                    "ref_id": f"runtime://space/{zone_id}/occupancy/{ended_at}",
                    "summary": "dirty-zone occupancy patch from L1 subsystem",
                    "retention": "debug_artifact",
                }
            ],
            "auditory_inputs": [
                {
                    "provider_kind": "auditory_context",
                    "ref_id": f"runtime://auditory/{actor_id}/window/{ended_at}",
                    "summary": "short auditory window source refs",
                    "retention": "ref_only",
                }
            ],
            "embodied_inputs": [
                {
                    "provider_kind": "embodied_state",
                    "ref_id": f"runtime://embodied/{actor_id}/state/{ended_at}",
                    "summary": "actor posture, locomotion, grounded and failure flags",
                    "retention": "ref_only",
                }
            ],
            "skeletal_inputs": [
                {
                    "provider_kind": "skeletal_state",
                    "ref_id": f"runtime://embodied_skeletal/{actor_id}/high_mid/{ended_at}",
                    "summary": "high and mid-level skeletal refs; full bones stay debug replay only",
                    "retention": "ref_only",
                }
            ],
            "environment_inputs": [
                {
                    "provider_kind": "environment_field",
                    "ref_id": f"runtime://environment/{zone_id}/field/{ended_at}",
                    "summary": "local light, occlusion, hazard and passability field refs",
                    "retention": "ref_only",
                }
            ],
        }

    @staticmethod
    def _sample_refs(entries: list[dict[str, str]]) -> list[SampleInputRef]:
        return [SampleInputRef(**entry) for entry in entries]

    @staticmethod
    def _structured_fact_ref(fact: RawFactEvent) -> str:
        return f"raw_fact_event:{fact.fact_family}:{fact.fact_type}:{fact.producer_ts}"

    @staticmethod
    def _zone_for_actor(occupancy: SpatialOccupancySnapshot, actor_id: str) -> str:
        for zone_id, zone in occupancy.zone_states.items():
            if actor_id in zone.actor_ids:
                return zone_id
        return ""

    @staticmethod
    def _local_spatial_state(occupancy: SpatialOccupancySnapshot, zone_id: str) -> dict[str, Any]:
        zone = occupancy.zone_states.get(zone_id)
        if zone is None:
            return {"zone_id": zone_id, "visibility": "unknown", "passability": "unknown"}
        return {
            "zone_id": zone.zone_id,
            "actor_ids": list(zone.actor_ids),
            "object_ids": list(zone.object_ids),
            "temporary_blockers": list(zone.temporary_blockers),
            "visibility": zone.visibility,
            "passability": zone.passability,
            "environment_field_ref": zone.environment_field_ref,
            "dirty_update_kinds": [event.update_kind for event in occupancy.dirty_events if event.zone_id == zone_id],
        }

    @staticmethod
    def _target_state(
        occupancy: SpatialOccupancySnapshot,
        target_actor_ids: list[str],
        target_object_ids: list[str],
    ) -> dict[str, Any]:
        object_states = {
            object_id: occupancy.object_states[object_id].model_dump()
            for object_id in target_object_ids
            if object_id in occupancy.object_states
        }
        return {
            "target_actor_ids": target_actor_ids,
            "target_object_ids": target_object_ids,
            "object_states": object_states,
        }

    @staticmethod
    def _environment_state(occupancy: SpatialOccupancySnapshot, zone_id: str) -> dict[str, Any]:
        field = occupancy.environment_fields.get(zone_id)
        return field.model_dump() if field is not None else {}

    @staticmethod
    def _embodied_state(provider_refs: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
        refs = provider_refs.get("embodied_inputs", [])
        return {
            "provider_input_refs": [entry.get("ref_id", "") for entry in refs],
            "skeletal_input_refs": [
                entry.get("ref_id", "") for entry in provider_refs.get("skeletal_inputs", [])
            ],
            "source": "runtime_provider_refs",
        }

    @staticmethod
    def _uncertainty(facts: list[RawFactEvent]) -> dict[str, Any]:
        return {
            "occluded_fact_count": sum(1 for fact in facts if fact.observability.occluded),
            "negative_fact_types": [
                fact.fact_type
                for fact in facts
                if fact.fact_type.startswith("expected_") or "unreachable" in fact.fact_type
            ],
        }
