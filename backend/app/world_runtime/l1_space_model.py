from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.world_runtime.intelligence_upgrade import Scene3DSpaceModel, SceneSpaceElement, SpaceElementType


GROUP_TO_SPACE_TYPE: dict[str, SpaceElementType] = {
    "l1_zone": "zone",
    "l1_static_obstacle": "static_obstacle",
    "l1_occluder": "occluder",
    "l1_environment_anchor": "environment_anchor",
    "l1_interaction_object": "interaction_object",
    "l1_navigation_lane": "navigation_lane",
}


class SceneSpaceModelExtractor:
    """Builds a Scene3DSpaceModel from runtime scene refs, not a hand-filled table."""

    def __init__(self, artifact_dir: str | Path | None = None) -> None:
        self._artifact_dir = Path(artifact_dir) if artifact_dir is not None else None

    def extract_from_runtime_scene(
        self,
        *,
        room_id: str,
        scene_id: str,
        runtime_nodes: list[dict[str, Any]],
        artifact_name: str | None = None,
    ) -> Scene3DSpaceModel:
        elements: list[SceneSpaceElement] = []
        for node in runtime_nodes:
            element_type = self._space_type_for(node)
            if element_type is None:
                continue
            node_path = str(node.get("node_path", "") or "")
            metadata = node.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            element_id = str(
                metadata.get("element_id")
                or metadata.get("zone_id")
                or node.get("element_id")
                or self._fallback_element_id(node_path)
            )
            source_refs = self._source_refs_for(node)
            if not source_refs:
                continue
            elements.append(
                SceneSpaceElement(
                    element_id=element_id,
                    element_type=element_type,
                    source_refs=source_refs,
                    semantic_tags=self._semantic_tags_for(node),
                    confidence=0.9 if self._has_geometry_source(source_refs) else 0.75,
                )
            )

        model = Scene3DSpaceModel(
            model_id=f"scene_space:{room_id}:{scene_id}",
            room_id=room_id,
            scene_id=scene_id,
            elements=elements,
        )
        if artifact_name is not None:
            self.write_artifact(model, artifact_name)
        return model

    def write_artifact(self, model: Scene3DSpaceModel, artifact_name: str) -> Path:
        if self._artifact_dir is None:
            raise ValueError("artifact_dir is required to write a Scene3DSpaceModel artifact")
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self._artifact_dir / artifact_name
        path.write_text(json.dumps(model.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _space_type_for(self, node: dict[str, Any]) -> SpaceElementType | None:
        metadata = node.get("metadata", {})
        if isinstance(metadata, dict):
            raw_type = str(metadata.get("l1_space_type", "") or "")
            if raw_type in SpaceElementType.__args__:
                return raw_type  # type: ignore[return-value]
        groups = node.get("groups", [])
        if not isinstance(groups, list):
            return None
        for group in groups:
            mapped = GROUP_TO_SPACE_TYPE.get(str(group))
            if mapped is not None:
                return mapped
        return None

    def _source_refs_for(self, node: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        node_path = str(node.get("node_path", "") or "")
        if node_path != "":
            refs.append(f"node_path:{node_path}")
        groups = node.get("groups", [])
        if isinstance(groups, list):
            refs.extend(f"group:{group}" for group in groups if str(group) != "")
        metadata = node.get("metadata", {})
        if isinstance(metadata, dict) and metadata:
            refs.append(f"metadata:{node_path or self._fallback_element_id(str(node.get('element_id', '')))}")
        for key in ("collision_shape_ref", "navigation_region_ref"):
            value = str(node.get(key, "") or "")
            if value != "":
                refs.append(value)
        for value in node.get("source_refs", []) if isinstance(node.get("source_refs", []), list) else []:
            if str(value) != "":
                refs.append(str(value))
        return refs

    def _semantic_tags_for(self, node: dict[str, Any]) -> list[str]:
        metadata = node.get("metadata", {})
        tags: list[str] = []
        if isinstance(metadata, dict):
            raw_tags = metadata.get("semantic_tags", [])
            if isinstance(raw_tags, list):
                tags.extend(str(tag) for tag in raw_tags if str(tag) != "")
        groups = node.get("groups", [])
        if isinstance(groups, list):
            tags.extend(str(group).replace("l1_", "") for group in groups if str(group).startswith("l1_"))
        return sorted(set(tags))

    @staticmethod
    def _fallback_element_id(node_path: str) -> str:
        if node_path == "":
            return "unnamed_space_element"
        return node_path.rstrip("/").split("/")[-1]

    @staticmethod
    def _has_geometry_source(source_refs: list[str]) -> bool:
        return any(ref.startswith("collision_shape:") or ref.startswith("navigation_region:") for ref in source_refs)
