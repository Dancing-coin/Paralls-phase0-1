"""Event-derived, reversible modifier sources for effective-stat resolution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from app.gameplay.effective_stats import ModifierOperation, StackingPolicy, StatModifier
from app.gameplay.models import GameplayEvent


class ModifierRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class ModifierTemplate:
    template_id: str
    stat_id: str
    operation: ModifierOperation
    value: Decimal
    stacking_key: str
    priority: int = 0
    stacking_policy: StackingPolicy = "stack"
    condition_ref: str | None = None


@dataclass(frozen=True)
class ModifierInstanceState:
    modifier_instance_id: str
    template_id: str
    source_ref: str
    modifier: StatModifier
    status: Literal["active", "inactive"]
    source_event_id: str


@dataclass(frozen=True)
class ModifierStateProjection:
    actor_ref: str
    instances: Mapping[str, ModifierInstanceState]
    active_modifiers: Mapping[str, StatModifier]
    source_revision_vector: Mapping[str, int]
    projection_revision: str


class ModifierDefinitionRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, ModifierTemplate] = {}

    def register_template(self, template: ModifierTemplate) -> None:
        if (
            not template.template_id
            or not template.stat_id
            or not template.stacking_key
            or template.template_id in self._templates
            or not isinstance(template.value, Decimal)
        ):
            raise ModifierRuntimeError("modifier_template_invalid")
        self._templates[template.template_id] = template

    def template(self, template_id: str) -> ModifierTemplate:
        try:
            return self._templates[template_id]
        except KeyError as exc:
            raise ModifierRuntimeError("modifier_template_unknown") from exc


class ModifierStateProjector:
    """Rebuilds modifier source lifecycle; it never resolves effective values."""

    _EVENT_TYPES = {
        "gameplay.modifier.source_activated",
        "gameplay.modifier.source_deactivated",
    }

    def __init__(self, registry: ModifierDefinitionRegistry) -> None:
        self._registry = registry

    def rebuild(self, actor_ref: str, events: Sequence[GameplayEvent]) -> ModifierStateProjection:
        instances: dict[str, ModifierInstanceState] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            if str(payload.get("actor_ref", "")) != actor_ref:
                raise ModifierRuntimeError("modifier_actor_mismatch")
            instance_id = _text(payload, "modifier_instance_id")
            if event.event_type == "gameplay.modifier.source_activated":
                if instance_id in instances and instances[instance_id].status == "active":
                    raise ModifierRuntimeError("modifier_instance_duplicate")
                template_id = _text(payload, "template_id")
                source_ref = _text(payload, "source_ref")
                template = self._registry.template(template_id)
                modifier = StatModifier(
                    modifier_id=instance_id,
                    stat_id=template.stat_id,
                    operation=template.operation,
                    value=template.value,
                    priority=template.priority,
                    stacking_key=template.stacking_key,
                    stacking_policy=template.stacking_policy,
                    source_ref=source_ref,
                    source_event_id=event.event_id,
                    condition_ref=template.condition_ref,
                )
                instances[instance_id] = ModifierInstanceState(
                    instance_id,
                    template_id,
                    source_ref,
                    modifier,
                    "active",
                    event.event_id,
                )
            else:
                prior = instances.get(instance_id)
                if prior is None or prior.status != "active":
                    raise ModifierRuntimeError("modifier_instance_inactive")
                instances[instance_id] = ModifierInstanceState(
                    prior.modifier_instance_id,
                    prior.template_id,
                    prior.source_ref,
                    prior.modifier,
                    "inactive",
                    event.event_id,
                )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        frozen_instances = MappingProxyType(dict(sorted(instances.items())))
        active_modifiers = MappingProxyType(
            {
                instance_id: state.modifier
                for instance_id, state in sorted(frozen_instances.items())
                if state.status == "active"
            }
        )
        frozen_revisions = MappingProxyType(dict(sorted(revisions.items())))
        digest = _digest(
            {
                "actor_ref": actor_ref,
                "instances": frozen_instances,
                "revisions": frozen_revisions,
            }
        )
        return ModifierStateProjection(actor_ref, frozen_instances, active_modifiers, frozen_revisions, f"modifiers:{digest[:16]}")


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ModifierRuntimeError("modifier_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    def default(item: object) -> object:
        if isinstance(item, Mapping):
            return dict(item)
        if hasattr(item, "__dict__"):
            return item.__dict__
        if isinstance(item, Decimal):
            return str(item)
        raise TypeError(type(item).__name__)

    return sha256(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = [
    "ModifierDefinitionRegistry",
    "ModifierInstanceState",
    "ModifierRuntimeError",
    "ModifierStateProjection",
    "ModifierStateProjector",
    "ModifierTemplate",
]
