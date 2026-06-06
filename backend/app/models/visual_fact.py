from typing import Any

from pydantic import model_validator

from app.models.raw_fact import RawFactEvent


class VisualFactEvent(RawFactEvent):
    fact_family: str = "visual_fact"

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_visual_fact_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        payload.setdefault("event_type", "raw_fact_event")
        payload.setdefault("fact_family", "visual_fact")
        legacy_source = {
            "layer": payload.get("layer", "L1"),
            "system": payload.get("system", "godot.raw_fact_emitter"),
            "actor_id": payload.get("actor_id", ""),
            "object_id": payload.get("object_id", ""),
            "environment_id": payload.get("environment_id", ""),
        }
        legacy_targets = {
            "actor_id": payload.get("target_actor_id") or "",
            "object_id": payload.get("target_object_id") or "",
            "environment_id": payload.get("target_environment_id") or "",
        }
        normalized = {
            "event_type": payload["event_type"],
            "fact_family": payload["fact_family"],
            "fact_type": payload["fact_type"],
            "relation_type": payload.get("relation_type", ""),
            "producer_ts": payload["producer_ts"],
            "room_id": payload["room_id"],
            "scene_id": payload["scene_id"],
            "zone_id": payload["zone_id"],
            "source": legacy_source,
            "targets": legacy_targets,
            "world": payload.get("world", {}),
            "observability": payload.get("observability", {}),
            "causation_id": payload.get("causation_id", ""),
            "correlation_id": payload.get("correlation_id", ""),
        }
        if "source" in payload:
            normalized["source"] = cls._merge_nested_payload(legacy_source, payload["source"])
        if "targets" in payload:
            normalized["targets"] = cls._merge_nested_payload(legacy_targets, payload["targets"])
        return normalized

    @property
    def actor_id(self) -> str:
        return self.source.actor_id

    @property
    def target_actor_id(self) -> str | None:
        return self.targets.actor_id or None

    @property
    def target_object_id(self) -> str | None:
        return self.targets.object_id or None

    @property
    def target_environment_id(self) -> str | None:
        return self.targets.environment_id or None

    def to_legacy_payload(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "room_id": self.room_id,
            "scene_id": self.scene_id,
            "zone_id": self.zone_id,
            "producer_ts": self.producer_ts,
            "fact_type": self.fact_type,
            "relation_type": self.relation_type,
            "target_actor_id": self.target_actor_id,
            "target_object_id": self.target_object_id,
            "target_environment_id": self.target_environment_id,
        }

    @staticmethod
    def _merge_nested_payload(base: dict[str, Any], nested: Any) -> dict[str, Any]:
        if not isinstance(nested, dict):
            return base
        merged = dict(base)
        for key, value in nested.items():
            merged[str(key)] = value
        return merged
