from __future__ import annotations

from typing import Any

from .artifacts import ArtifactStatus, NonRuntimeProductionArtifact, ProductionArtifactKind, assert_no_runtime_private_context


class SceneSemanticExtractor:
    def extract(self, *, scene_id: str, source_scene: dict[str, Any], source_ref: str) -> NonRuntimeProductionArtifact:
        assert_no_runtime_private_context(source_scene, path="source_scene")
        nodes = source_scene.get("nodes", [])
        if not isinstance(nodes, list):
            raise ValueError("source_scene.nodes must be a list")
        candidates: list[dict[str, Any]] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("name", "") or node.get("node_path", "")).strip()
            if not name:
                continue
            groups = [str(group) for group in node.get("groups", []) if str(group)]
            metadata = node.get("metadata", {}) if isinstance(node.get("metadata", {}), dict) else {}
            semantic_tags = sorted(
                set(
                    [tag for group in groups for tag in [group.replace("l1_", "").replace("production_", "")]]
                    + [str(tag) for tag in metadata.get("semantic_tags", []) if str(tag)]
                )
            )
            candidates.append(
                {
                    "element_id": str(metadata.get("element_id") or metadata.get("zone_id") or name),
                    "node_path": str(node.get("node_path", "")),
                    "node_type": str(node.get("type", "Node3D")),
                    "semantic_tags": semantic_tags,
                    "source_refs": self._node_source_refs(node),
                    "confidence": 0.75 if not metadata else 0.85,
                    "review_required": True,
                }
            )
        return NonRuntimeProductionArtifact(
            artifact_id=f"nrpp:{scene_id}:scene-semantic-draft",
            artifact_kind=ProductionArtifactKind.SCENE_SEMANTIC_DRAFT.value,
            scene_id=scene_id,
            status=ArtifactStatus.DRAFT.value,
            source_refs=[source_ref],
            payload={
                "semantic_candidates": candidates,
                "manual_role": "review_only",
                "truth_status": "draft_not_runtime_truth",
            },
            provenance={
                "module": "SceneSemanticExtractor",
                "input_source_ref": source_ref,
                "context_namespace": "tool_mm:production_scene_knowledge",
            },
        )

    @staticmethod
    def _node_source_refs(node: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        for key in ("node_path", "asset_ref", "collision_shape_ref", "navigation_region_ref"):
            value = str(node.get(key, "") or "")
            if value:
                refs.append(f"{key}:{value}" if key == "node_path" else value)
        return refs
