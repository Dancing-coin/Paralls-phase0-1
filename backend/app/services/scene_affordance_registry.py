from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.embodied_interaction import AnchorRole, SceneAffordanceRecord
from app.world_runtime.intelligence_upgrade import Scene3DSpaceModel
from app.world_runtime.l1_occupancy import SpatialOccupancySnapshot


RegistryResolveStatus = Literal[
    "available",
    "blocked",
    "registry_target_unknown",
    "registry_binding_stale",
    "registry_binding_unhealthy",
    "registry_cross_scene_binding_rejected",
    "registry_occupancy_stale",
    "registry_catalog_identity_mismatch",
]
RegistryView = Literal["public", "controller"]


class SceneAffordanceResolveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RegistryResolveStatus
    record: SceneAffordanceRecord | None = None
    projection: dict[str, object] = Field(default_factory=dict)
    explanation_refs: list[str] = Field(default_factory=list)


class SceneAffordanceRegistry:
    def __init__(
        self,
        *,
        records: list[SceneAffordanceRecord],
        space_model: Scene3DSpaceModel,
        occupancy_snapshot: SpatialOccupancySnapshot,
        grounding_catalog: dict[str, list[str]],
        current_tick: int,
        occupancy_freshness_ticks: int,
    ) -> None:
        self._records = {(record.scene_id, record.scene_instance_id, record.entity_ref): record for record in records}
        self._space_model = space_model
        self._occupancy = occupancy_snapshot
        self._catalog = {key: list(value) for key, value in grounding_catalog.items()}
        self._current_tick = current_tick
        self._occupancy_freshness_ticks = occupancy_freshness_ticks
        self._vla_conflicts: list[dict[str, object]] = []

    @classmethod
    def from_reviewed_records(
        cls,
        *,
        records: list[SceneAffordanceRecord],
        space_model: Scene3DSpaceModel,
        occupancy_snapshot: SpatialOccupancySnapshot,
        grounding_catalog: dict[str, list[str]],
        current_tick: int,
        occupancy_freshness_ticks: int,
    ) -> "SceneAffordanceRegistry":
        return cls(
            records=records,
            space_model=space_model,
            occupancy_snapshot=occupancy_snapshot,
            grounding_catalog=grounding_catalog,
            current_tick=current_tick,
            occupancy_freshness_ticks=occupancy_freshness_ticks,
        )

    def resolve(
        self,
        *,
        scene_id: str,
        scene_instance_id: str,
        entity_ref: str,
        affordance_id: str,
        expected_binding_revision: int,
        required_anchor_roles: list[AnchorRole],
        view: RegistryView,
    ) -> SceneAffordanceResolveResult:
        candidates = [record for key, record in self._records.items() if key[2] == entity_ref]
        if candidates and not any(record.scene_id == scene_id and record.scene_instance_id == scene_instance_id for record in candidates):
            return self._reject("registry_cross_scene_binding_rejected", "scene_instance_id")
        record = self._records.get((scene_id, scene_instance_id, entity_ref))
        if record is None:
            return self._reject("registry_target_unknown", "entity_ref")
        if record.binding_revision != expected_binding_revision:
            return self._reject("registry_binding_stale", "binding_revision")
        if not any(affordance.affordance_id == affordance_id for affordance in record.affordances):
            return self._reject("registry_target_unknown", "affordance_id")
        anchor_roles = {anchor.role for anchor in record.anchors}
        if not set(required_anchor_roles).issubset(anchor_roles):
            return self._reject("registry_target_unknown", "anchor_role")
        if not self._catalog_contains_record(record):
            return self._reject("registry_catalog_identity_mismatch", "grounding_catalog")
        if not self._space_model_contains_binding(record):
            return self._reject("registry_binding_unhealthy", "space_model")
        if self._occupancy_is_stale(record):
            return self._reject("registry_occupancy_stale", "occupancy")
        return SceneAffordanceResolveResult(
            status="available",
            record=record,
            projection=self._project(record, view),
            explanation_refs=[f"binding_revision:{record.binding_revision}"],
        )

    def review_vla_candidate(self, *, entity_ref: str, candidate_refs: dict[str, list[str]]) -> dict[str, object]:
        record = next((entry for entry in self._records.values() if entry.entity_ref == entity_ref), None)
        if record is None:
            return {"status": "vla_unknown_entity", "entity_ref": entity_ref}
        conflict = {
            "status": "vla_conflict_recorded",
            "entity_ref": entity_ref,
            "candidate_refs": {key: list(value) for key, value in candidate_refs.items()},
            "retained_registry_entity_ref": record.entity_ref,
        }
        allowed_entity_refs = set(self._catalog.get("entity_refs", []))
        allowed_collider_refs = set(self._catalog.get("collider_refs", []))
        candidate_entity_refs = set(candidate_refs.get("entity_refs", []))
        candidate_collider_refs = set(candidate_refs.get("collider_refs", []))
        if candidate_entity_refs.issubset(allowed_entity_refs) and candidate_collider_refs.issubset(allowed_collider_refs):
            conflict["status"] = "vla_candidate_matches_reviewed_catalog"
        self._vla_conflicts.append(conflict)
        return dict(conflict)

    def _catalog_contains_record(self, record: SceneAffordanceRecord) -> bool:
        entity_refs = set(self._catalog.get("entity_refs", []))
        collider_refs = set(self._catalog.get("collider_refs", []))
        anchor_refs = set(self._catalog.get("anchor_refs", []))
        affordance_refs = set(self._catalog.get("affordance_refs", []))
        return (
            record.entity_ref in entity_refs
            and set(record.local_binding.collider_refs).issubset(collider_refs)
            and set(record.grounding_catalog_refs.anchor_refs).issubset(anchor_refs)
            and {affordance.affordance_id for affordance in record.affordances}.issubset(affordance_refs)
        )

    def _space_model_contains_binding(self, record: SceneAffordanceRecord) -> bool:
        refs = [
            str(ref)
            for element in self._space_model.elements
            for ref in element.source_refs
        ]
        element_ids = {element.element_id for element in self._space_model.elements}
        if record.entity_ref not in element_ids:
            return False
        if not set(record.local_binding.collider_refs).issubset(set(refs)):
            return False
        if record.local_binding.navigation_footprint_ref not in element_ids and record.local_binding.navigation_footprint_ref not in refs:
            return False
        anchor_refs = {anchor.anchor_id for anchor in record.anchors}
        return anchor_refs.issubset(set(refs))

    def _occupancy_is_stale(self, record: SceneAffordanceRecord) -> bool:
        object_state = self._occupancy.object_states.get(record.entity_ref)
        if object_state is None:
            return True
        return self._current_tick - object_state.updated_at > self._occupancy_freshness_ticks

    @staticmethod
    def _project(record: SceneAffordanceRecord, view: RegistryView) -> dict[str, object]:
        common: dict[str, object] = {
            "entity_ref": record.entity_ref,
            "scene_id": record.scene_id,
            "scene_instance_id": record.scene_instance_id,
            "binding_revision": record.binding_revision,
            "semantic_type": record.semantic_type,
            "semantic_tags": list(record.semantic_tags),
            "affordance_ids": [affordance.affordance_id for affordance in record.affordances],
            "anchor_roles": [anchor.role for anchor in record.anchors],
            "visibility_policy": record.visibility_policy,
        }
        if view == "controller":
            common["local_binding"] = record.local_binding.model_dump(mode="json")
            common["anchors"] = [anchor.model_dump(mode="json") for anchor in record.anchors]
        return common

    @staticmethod
    def _reject(status: RegistryResolveStatus, reason: str) -> SceneAffordanceResolveResult:
        return SceneAffordanceResolveResult(status=status, explanation_refs=[reason])
