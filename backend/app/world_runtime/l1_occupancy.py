from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.environment_field import EnvironmentFieldState
from app.models.world_result import EnvironmentStateResult
from app.world_runtime.intelligence_upgrade import Scene3DSpaceModel


Passability = Literal["passable", "blocked", "requires_detour", "unknown"]
Visibility = Literal["clear", "reduced", "blocked", "unknown"]


class SpatialObjectState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str
    zone_id: str
    state: str = "unknown"
    affordances: list[str] = Field(default_factory=list)
    occludes: bool = False
    source_refs: list[str] = Field(default_factory=list)
    updated_at: int = 0


class SpatialZoneState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str
    actor_ids: list[str] = Field(default_factory=list)
    nearby_refs: dict[str, list[str]] = Field(default_factory=dict)
    object_ids: list[str] = Field(default_factory=list)
    temporary_blockers: list[str] = Field(default_factory=list)
    visibility: Visibility = "clear"
    passability: Passability = "passable"
    environment_field_ref: str = ""
    updated_at: int = 0


class SpatialOccupancyDirtyEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_kind: str
    zone_id: str
    producer_ts: int
    source_refs: list[str] = Field(default_factory=list)


class SpatialOccupancySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    static_model_ref: str = ""
    zone_states: dict[str, SpatialZoneState] = Field(default_factory=dict)
    object_states: dict[str, SpatialObjectState] = Field(default_factory=dict)
    environment_fields: dict[str, EnvironmentFieldState] = Field(default_factory=dict)
    dirty_zone_ids: list[str] = Field(default_factory=list)
    dirty_events: list[SpatialOccupancyDirtyEvent] = Field(default_factory=list)
    full_scene_rescan_count: int = 0
    update_strategy: str = "dirty_zone_event_driven_incremental"


class SpatialOccupancyService:
    def __init__(self, *, field_id: str = "occupancy:runtime", static_model_ref: str = "") -> None:
        self._snapshot = SpatialOccupancySnapshot(field_id=field_id, static_model_ref=static_model_ref)

    @classmethod
    def from_space_model(cls, model: Scene3DSpaceModel) -> "SpatialOccupancyService":
        service = cls(field_id=f"occupancy:{model.room_id}:{model.scene_id}", static_model_ref=model.model_id)
        for element in model.elements:
            if element.element_type == "zone":
                service._ensure_zone(element.element_id)
            if element.element_type == "interaction_object":
                zone_id = service._first_zone_id(default="zone_focus")
                service.apply_object_state_update(
                    object_id=element.element_id,
                    zone_id=zone_id,
                    state="scene_registered",
                    affordances=[],
                    occludes=False,
                    producer_ts=0,
                    source_ref=element.source_refs[0] if element.source_refs else "",
                    mark_dirty=False,
                )
            if element.element_type in {"static_obstacle", "occluder"}:
                zone_id = service._first_zone_id(default="zone_focus")
                zone = service._ensure_zone(zone_id)
                if element.element_id not in zone.temporary_blockers:
                    zone.temporary_blockers.append(element.element_id)
                if element.element_type == "occluder":
                    zone.visibility = "reduced"
        return service

    def apply_actor_zone_update(
        self,
        *,
        actor_id: str,
        previous_zone_id: str,
        next_zone_id: str,
        producer_ts: int,
        source_ref: str,
    ) -> None:
        if previous_zone_id:
            previous = self._ensure_zone(previous_zone_id)
            previous.actor_ids = [entry for entry in previous.actor_ids if entry != actor_id]
            previous.updated_at = producer_ts
            self._mark_dirty(previous_zone_id, "actor_left_zone", producer_ts, source_ref)
        zone = self._ensure_zone(next_zone_id)
        if actor_id not in zone.actor_ids:
            zone.actor_ids.append(actor_id)
            zone.actor_ids.sort()
        zone.updated_at = producer_ts
        self._mark_dirty(next_zone_id, "actor_entered_zone", producer_ts, source_ref)

    def apply_actor_proximity_update(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        source_ref: str,
        target_actor_id: str = "",
        target_object_id: str = "",
        distance_m: float | None = None,
    ) -> None:
        zone_id = self.zone_for_actor(actor_id) or self._first_zone_id(default="zone_focus")
        zone = self._ensure_zone(zone_id)
        refs = zone.nearby_refs.setdefault(actor_id, [])
        target_ref = target_actor_id or target_object_id
        if target_ref and target_ref not in refs:
            refs.append(target_ref)
            refs.sort()
        if target_object_id and distance_m is not None and distance_m <= 3.0 and target_object_id not in zone.object_ids:
            zone.object_ids.append(target_object_id)
            zone.object_ids.sort()
        zone.updated_at = producer_ts
        self._mark_dirty(zone_id, "actor_proximity_changed", producer_ts, source_ref)

    def apply_environment_result(self, result: EnvironmentStateResult) -> None:
        field = EnvironmentFieldState(
            field_id=result.field_id,
            room_id=result.room_id,
            scene_id=result.scene_id,
            zone_id=result.zone_id,
            temperature=result.temperature,
            thermal_level=result.thermal_level,
            humidity=result.humidity,
            smoke_density=result.smoke_density,
            light_level=result.light_level,
            noise_level=result.noise_level,
            visibility_level=result.visibility_level,
            producer_ts=result.producer_ts,
            updated_at=result.updated_at,
            source_environment_id=result.source_environment_id,
        )
        self.apply_environment_field(field, source_ref=result.result_id)

    def apply_environment_field(self, field: EnvironmentFieldState, source_ref: str | None = None) -> None:
        zone = self._ensure_zone(field.zone_id)
        zone.environment_field_ref = field.field_id
        zone.visibility = self._visibility_from_environment(field)
        zone.passability = self._passability_from_environment(field)
        zone.updated_at = field.updated_at or field.producer_ts
        self._snapshot.environment_fields[field.zone_id] = field
        self._mark_dirty(
            field.zone_id,
            "environment_field_changed",
            field.updated_at or field.producer_ts,
            source_ref or field.field_id,
        )

    def apply_object_state_update(
        self,
        *,
        object_id: str,
        zone_id: str,
        state: str,
        affordances: list[str],
        occludes: bool,
        producer_ts: int,
        source_ref: str,
        mark_dirty: bool = True,
    ) -> None:
        zone = self._ensure_zone(zone_id)
        if object_id not in zone.object_ids:
            zone.object_ids.append(object_id)
            zone.object_ids.sort()
        self._snapshot.object_states[object_id] = SpatialObjectState(
            object_id=object_id,
            zone_id=zone_id,
            state=state,
            affordances=sorted(set(affordances)),
            occludes=occludes,
            source_refs=[source_ref] if source_ref else [],
            updated_at=producer_ts,
        )
        if occludes:
            zone.visibility = "reduced"
        zone.updated_at = producer_ts
        if mark_dirty:
            self._mark_dirty(zone_id, "object_state_changed", producer_ts, source_ref)

    def snapshot(self) -> SpatialOccupancySnapshot:
        return self._snapshot.model_copy(deep=True)

    def zone_for_actor(self, actor_id: str) -> str:
        for zone_id, zone in self._snapshot.zone_states.items():
            if actor_id in zone.actor_ids:
                return zone_id
        return ""

    def _ensure_zone(self, zone_id: str) -> SpatialZoneState:
        if zone_id not in self._snapshot.zone_states:
            self._snapshot.zone_states[zone_id] = SpatialZoneState(zone_id=zone_id)
        return self._snapshot.zone_states[zone_id]

    def _first_zone_id(self, *, default: str) -> str:
        if self._snapshot.zone_states:
            return sorted(self._snapshot.zone_states.keys())[0]
        return default

    def _mark_dirty(self, zone_id: str, update_kind: str, producer_ts: int, source_ref: str) -> None:
        if zone_id not in self._snapshot.dirty_zone_ids:
            self._snapshot.dirty_zone_ids.append(zone_id)
            self._snapshot.dirty_zone_ids.sort()
        self._snapshot.dirty_events.append(
            SpatialOccupancyDirtyEvent(
                update_kind=update_kind,
                zone_id=zone_id,
                producer_ts=producer_ts,
                source_refs=[source_ref] if source_ref else [],
            )
        )

    @staticmethod
    def _visibility_from_environment(field: EnvironmentFieldState) -> Visibility:
        if field.visibility_level in {"blocked", "opaque"} or field.smoke_density in {"dense", "heavy"}:
            return "reduced"
        if field.visibility_level in {"reduced", "soft_reduced"} or field.smoke_density in {"light", "trace"}:
            return "reduced"
        return "clear"

    @staticmethod
    def _passability_from_environment(field: EnvironmentFieldState) -> Passability:
        if field.smoke_density in {"dense", "heavy"}:
            return "requires_detour"
        if field.visibility_level in {"reduced", "soft_reduced", "blocked", "opaque"}:
            return "requires_detour"
        return "passable"


# Compatibility aliases for pre-boundary-governance imports.
RuntimeObjectState = SpatialObjectState
RuntimeZoneState = SpatialZoneState
RuntimeOccupancyDirtyEvent = SpatialOccupancyDirtyEvent
RuntimeSpatialOccupancySnapshot = SpatialOccupancySnapshot
RuntimeSpatialOccupancyService = SpatialOccupancyService
