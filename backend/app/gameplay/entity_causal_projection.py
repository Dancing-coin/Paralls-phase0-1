from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

from app.gameplay.models import GameplayEvent
from app.gameplay.shared_contracts import (
    CausalEventRecord,
    EntityRecord,
    EntityRef,
    EnvironmentRecord,
    RelationshipRecord,
    RevisionVector,
    ThingRecord,
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _entity_ref(value: object, *, fallback_type: str = "entity", fallback_id: str = "unknown") -> EntityRef:
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, dict):
        return EntityRef.model_validate(value)
    text = str(value or "")
    if ":" in text:
        entity_type, entity_id = text.split(":", 1)
        return EntityRef(entity_type=entity_type or fallback_type, entity_id=entity_id or fallback_id)
    return EntityRef(entity_type=fallback_type, entity_id=text or fallback_id)


def _string_refs(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list, set)):
        return tuple(sorted({str(item) for item in value}))
    return (str(value),)


class EntityCausalProjection:
    """Read-only, deterministic dossier and causal projection over committed events."""

    def __init__(self) -> None:
        self.entities: dict[str, EntityRecord] = {}
        self.things: dict[str, ThingRecord] = {}
        self.environments: dict[str, EnvironmentRecord] = {}
        self.relationships: dict[str, RelationshipRecord] = {}
        self.causal_events: dict[str, CausalEventRecord] = {}

    def rebuild(self, events: Iterable[GameplayEvent], *, initial: "EntityCausalProjection | None" = None) -> "EntityCausalProjection":
        projection = initial.clone() if initial is not None else EntityCausalProjection()
        known_events = set(projection.causal_events)
        for event in sorted(events, key=lambda item: item.global_sequence):
            payload = event.payload
            ref_value = payload.get("entity_ref", payload.get("subject_ref", event.stream_id))
            ref = _entity_ref(ref_value, fallback_id=event.stream_id)
            revision = RevisionVector(entries={event.stream_id: event.stream_revision})
            entity_kind = str(payload.get("entity_kind", ref.entity_type))
            key = f"{ref.entity_type}:{ref.entity_id}"
            current = projection.entities.get(key)
            entity = EntityRecord(
                entity_ref=ref,
                entity_kind=entity_kind,
                lifecycle=str(payload.get("lifecycle", "active")),
                location_ref=_entity_ref(payload["location_ref"]) if payload.get("location_ref") else (current.location_ref if current else None),
                component_refs=tuple(sorted(set(payload.get("component_refs", current.component_refs if current else ()) or ()))),
                source_refs=current.source_refs if current else (),
                revision=revision,
            )
            projection.entities[key] = entity

            if any(name in payload for name in ("type_refs", "material_refs", "property_refs", "status_refs", "ownership_ref")):
                thing = ThingRecord(
                    entity_ref=ref,
                    type_refs=tuple(sorted(set(payload.get("type_refs", ()) or ()))),
                    material_refs=tuple(sorted(set(payload.get("material_refs", ()) or ()))),
                    property_refs=tuple(sorted(set(payload.get("property_refs", ()) or ()))),
                    status_refs=tuple(sorted(set(payload.get("status_refs", ()) or ()))),
                    ownership_ref=str(payload["ownership_ref"]) if payload.get("ownership_ref") is not None else None,
                    domain_projection_refs=tuple(sorted(set(payload.get("domain_projection_refs", ()) or ()))),
                    revision=revision,
                )
                projection.things[key] = thing
                if entity_kind == "environment":
                    projection.environments[key] = EnvironmentRecord.model_validate(thing.model_dump(mode="json"))

            relationship = payload.get("relationship")
            if isinstance(relationship, dict):
                record = RelationshipRecord(
                    relationship_ref=str(relationship.get("relationship_ref", f"relationship:{event.event_id}")),
                    source_ref=_entity_ref(relationship.get("source_ref", ref_value)),
                    target_ref=_entity_ref(relationship.get("target_ref", payload.get("target_ref", "entity:unknown"))),
                    relation_kind=str(relationship.get("relation_kind", "related_to")),
                    terms_ref=str(relationship["terms_ref"]) if relationship.get("terms_ref") is not None else None,
                    visibility_scope=str(relationship.get("visibility_scope", event.visibility_policy)),
                    lifecycle=str(relationship.get("lifecycle", "active")),
                    revision=revision,
                )
                projection.relationships[record.relationship_ref] = record

            parents = payload.get("causal_parent_refs", ())
            if isinstance(parents, str):
                parents = (parents,)
            parent_refs = tuple(sorted({str(parent) for parent in parents if str(parent) in known_events or str(parent) in projection.causal_events}))
            if event.causation_id in known_events or event.causation_id in projection.causal_events:
                parent_refs = tuple(sorted(set(parent_refs) | {event.causation_id}))
            affected = payload.get("affected_entity_refs", (ref,))
            if isinstance(affected, (str, dict)):
                affected = (affected,)
            causal = CausalEventRecord(
                event_ref=event.event_id,
                trigger_ref=event.event_type,
                causal_parent_refs=parent_refs,
                affected_entity_refs=tuple(_entity_ref(item) for item in affected),
                observed_by=_string_refs(payload.get("observed_by")),
                rule_revision_refs=_string_refs(payload.get("rule_revision_refs")),
                evidence_refs=_string_refs(payload.get("evidence_refs", payload.get("evidence_ref"))),
                settlement_refs=_string_refs(payload.get("settlement_refs")),
            )
            projection.causal_events[event.event_id] = causal
            known_events.add(event.event_id)
        return projection

    def clone(self) -> "EntityCausalProjection":
        clone = EntityCausalProjection()
        clone.entities = dict(self.entities)
        clone.things = dict(self.things)
        clone.environments = dict(self.environments)
        clone.relationships = dict(self.relationships)
        clone.causal_events = dict(self.causal_events)
        return clone

    def causal_parents(self, event_ref: str) -> tuple[CausalEventRecord, ...]:
        event = self.causal_events[event_ref]
        return tuple(self.causal_events[parent] for parent in event.causal_parent_refs if parent in self.causal_events)

    def causal_children(self, event_ref: str) -> tuple[CausalEventRecord, ...]:
        return tuple(sorted((event for event in self.causal_events.values() if event_ref in event.causal_parent_refs), key=lambda item: item.event_ref))

    def dossier(self, entity_ref: str) -> dict[str, object]:
        entity = self.entities[entity_ref]
        causal_refs = tuple(sorted(event.event_ref for event in self.causal_events.values() if any(ref.entity_id == entity.entity_ref.entity_id and ref.entity_type == entity.entity_ref.entity_type for ref in event.affected_entity_refs)))
        return {
            "entity": entity.model_dump(mode="json"),
            "thing": self.things.get(entity_ref).model_dump(mode="json") if entity_ref in self.things else None,
            "environment": self.environments.get(entity_ref).model_dump(mode="json") if entity_ref in self.environments else None,
            "relationships": [item.model_dump(mode="json") for item in self.relationships.values() if item.source_ref == entity.entity_ref or item.target_ref == entity.entity_ref],
            "causal_event_refs": causal_refs,
            "digest": _digest({"entity": entity.model_dump(mode="json"), "causal_event_refs": causal_refs}),
        }


__all__ = ["EntityCausalProjection"]
