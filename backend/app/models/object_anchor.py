from __future__ import annotations

from typing import Any


def object_ref_kind(ref: str) -> str:
    if ref.startswith("obj_"):
        return "object"
    if ref.startswith("char_"):
        return "actor"
    if ref.startswith("env_"):
        return "environment"
    return "entity"


def derive_world_anchor_id(*, target_ref: str = "", world_anchor_id: str = "") -> str:
    if world_anchor_id:
        return world_anchor_id
    if target_ref == "":
        return ""
    return f"world_anchor:{object_ref_kind(target_ref)}:{target_ref}"


def first_target_ref(
    *,
    target_actor_ids: list[str] | None = None,
    target_object_ids: list[str] | None = None,
    target_environment_ids: list[str] | None = None,
) -> str:
    for values in (target_object_ids or [], target_actor_ids or [], target_environment_ids or []):
        if values:
            return str(values[0])
    return ""


def target_ref_from_event_parts(
    *,
    target_actor_id: str = "",
    target_object_id: str = "",
    target_environment_id: str = "",
) -> str:
    return target_object_id or target_actor_id or target_environment_id


def subject_ref_from_event_parts(
    *,
    source_actor_id: str = "",
    source_object_id: str = "",
    source_environment_id: str = "",
) -> str:
    return source_actor_id or source_object_id or source_environment_id


def append_unique_lineage(existing: list[str] | None, values: list[str]) -> list[str]:
    lineage = list(existing or [])
    for value in values:
        if value and value not in lineage:
            lineage.append(value)
    return lineage


def object_anchor_trace(value: Any) -> dict[str, object]:
    if isinstance(value, dict):
        getter = value.get
    else:
        getter = lambda key, default=None: getattr(value, key, default)
    return {
        "world_anchor_id": getter("world_anchor_id", ""),
        "subject_ref": getter("subject_ref", ""),
        "target_ref": getter("target_ref", ""),
        "source_ref_lineage": list(getter("source_ref_lineage", []) or []),
    }
