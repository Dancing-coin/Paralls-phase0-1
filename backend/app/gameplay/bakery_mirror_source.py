"""Read-only Godot mirror projection for committed bakery facts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.models import GameplayEvent
from app.gameplay.state_group_views import CharacterGameRuntimeStateView, StateGroupRuntimeViewEnvelope


class BakeryMirrorSourceError(ValueError):
    pass


@dataclass(frozen=True)
class BakeryMirrorSource:
    """Build a presentation view strictly from already committed event facts."""

    scenario: BakeryReferenceScenario
    events: Sequence[GameplayEvent]

    def godot_view(self) -> CharacterGameRuntimeStateView:
        events = tuple(sorted(self.events, key=lambda event: (event.global_sequence, event.event_id)))
        event_types = {event.event_type for event in events}
        if "gameplay.construction_production.facility_acquired" not in event_types:
            raise BakeryMirrorSourceError("bakery_facility_commit_missing")
        if "gameplay.inventory.output_received" not in event_types:
            raise BakeryMirrorSourceError("bakery_output_commit_missing")
        output_events = [event for event in events if event.event_type == "gameplay.inventory.output_received"]
        facility_events = [event for event in events if event.event_type == "gameplay.construction_production.facility_acquired"]
        if not output_events or not facility_events:
            raise BakeryMirrorSourceError("bakery_committed_facts_missing")
        source_revision_vector = MappingProxyType(_revision_vector(events))
        source_digest = _digest({"events": [event.model_dump(mode="json") for event in events]})
        group_id = "bakery.gameplay"
        payload = MappingProxyType(
            {
                "facility_ref": self.scenario.facility.facility_ref,
                "facility_state": "acquired",
                "facility_source_event_id": facility_events[-1].event_id,
                "output_item": self.scenario.recipe.output_item,
                "output_state": "sold" if any(event.event_type == "gameplay.economy.sale_posted" for event in events) else "received",
                "output_count": len(output_events),
                "source_event_digest": source_digest,
            }
        )
        envelope = StateGroupRuntimeViewEnvelope(
            group_id=group_id,
            definition_version="1",
            projection_schema_version=1,
            projection_revision=source_digest,
            source_revision_vector=source_revision_vector,
            payload=payload,
        )
        return CharacterGameRuntimeStateView(
            actor_ref=self.scenario.owner_character_ref,
            consumer="godot",
            source_facade_revision=source_digest,
            source_revision_vector=source_revision_vector,
            groups=MappingProxyType({group_id: envelope}),
            view_checksum=_digest(
                {
                    "actor_ref": self.scenario.owner_character_ref,
                    "consumer": "godot",
                    "source_facade_revision": source_digest,
                    "groups": {group_id: {"projection_revision": source_digest, "payload": dict(payload)}},
                }
            ),
        )


def _revision_vector(events: Sequence[GameplayEvent]) -> dict[str, int]:
    revisions: dict[str, int] = {}
    for event in events:
        revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
    return dict(sorted(revisions.items()))


def _digest(value: Mapping[str, object]) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


__all__ = ["BakeryMirrorSource", "BakeryMirrorSourceError"]
