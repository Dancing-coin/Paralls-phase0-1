"""Read-only composition of Phase 3 owned projections into the runtime facade."""

from __future__ import annotations

from decimal import Decimal
from dataclasses import dataclass
from typing import Mapping

from app.gameplay.ability_runtime import AbilityStateProjection
from app.gameplay.effective_stats import EffectiveStatEntry, EffectiveStatResolver, StatBaseline
from app.gameplay.inventory_runtime import EncumbranceProjection, InventoryProjection
from app.gameplay.resource_body_runtime import BodyRuntimeProjection, ResourceBodyRuntimeProjector, ResourceStateProjection
from app.gameplay.runtime_state import CharacterGameRuntimeState, CharacterGameRuntimeStateBuilder, StateGroupLifecycleProjection, StateGroupLifecycleProjector
from app.gameplay.status_tags import StatusTagProjector, StatusTagStateProjection, active_status_tag_modifiers
from app.gameplay.models import GameplayEvent


@dataclass(frozen=True)
class Phase3ProjectionCheckpoint:
    """In-memory domain projection checkpoint; persistence is intentionally external."""

    lifecycle: StateGroupLifecycleProjection
    resources: ResourceStateProjection
    body: BodyRuntimeProjection
    tags: StatusTagStateProjection

    @property
    def actor_ref(self) -> str:
        return self.lifecycle.actor_ref


class Phase3StateComposerError(ValueError):
    """Raised when independently-owned projections cannot be safely composed."""


class Phase3StateComposer:
    """A read-only adapter. Group lifecycle and all domain writes remain external."""

    def __init__(self, *, facade_builder: CharacterGameRuntimeStateBuilder) -> None:
        self._facade_builder = facade_builder

    def compose(
        self,
        *,
        lifecycle: StateGroupLifecycleProjection,
        resources: ResourceStateProjection,
        body: BodyRuntimeProjection,
        tags: StatusTagStateProjection,
        effective_stats: Mapping[str, EffectiveStatEntry],
        registry_revision: str,
        world_config_revision: str,
        active_patch_set_revision: str,
        abilities: AbilityStateProjection | None = None,
        inventory: InventoryProjection | None = None,
        encumbrance: EncumbranceProjection | None = None,
    ) -> CharacterGameRuntimeState:
        actor_ref = lifecycle.actor_ref
        if {resources.actor_ref, body.actor_ref, tags.actor_ref} != {actor_ref} or (abilities is not None and abilities.actor_ref != actor_ref) or (inventory is not None and inventory.actor_ref != actor_ref) or (encumbrance is not None and encumbrance.carrier_ref != actor_ref):
            raise Phase3StateComposerError("actor_ref_mismatch")
        payloads: dict[str, dict[str, object]] = {}
        enabled = set(lifecycle.enabled_group_ids)
        if "core.resources" in enabled:
            payloads["core.resources"] = {"entries": {entry.resource_id: {"current": entry.current, "minimum": entry.minimum, "maximum": entry.maximum, "reserved": entry.reserved, "available": entry.available, "source_event_id": entry.source_event_id} for entry in resources.entries.values()}}
        if "core.body_runtime" in enabled:
            payloads["core.body_runtime"] = {"functions": {function.function_id: {"capacity_ratio": function.capacity_ratio, "status": function.status, "contributing_source_refs": list(function.contributing_source_refs)} for function in body.functions.values()}}
        if "core.status_tags" in enabled:
            payloads["core.status_tags"] = {"active_instances": {instance.instance_id: {"tag_id": instance.tag_id, "source_ref": instance.source_ref, "stack_count": instance.stack_count, "source_event_id": instance.source_event_id} for instance in tags.active_instances.values()}}
        if "core.effective_stats" in enabled:
            payloads["core.effective_stats"] = {"entries": {stat_id: _stat_payload(entry) for stat_id, entry in sorted(effective_stats.items())}}
        if "core.skills" in enabled:
            if abilities is None:
                raise Phase3StateComposerError("ability_projection_required")
            payloads["core.skills"] = {
                "learned": {skill_id: {"rank": state.rank, "source_event_id": state.source_event_id} for skill_id, state in abilities.learned.items()},
                "active_grants": {grant_id: {"skill_ids": list(grant.skill_ids), "path_ids": list(grant.path_ids), "source_ref": grant.source_ref} for grant_id, grant in abilities.grants.items() if grant.status == "active"},
            }
        if "core.inventory" in enabled:
            if inventory is None:
                raise Phase3StateComposerError("inventory_projection_required")
            payloads["core.inventory"] = {
                "locations": dict(inventory.locations),
                "items": {item_id: {"definition_id": item.definition_id, "quantity": item.quantity} for item_id, item in inventory.items.items()},
            }
        if "core.encumbrance" in enabled:
            if encumbrance is None:
                raise Phase3StateComposerError("encumbrance_projection_required")
            payloads["core.encumbrance"] = {"carried_weight": encumbrance.carried_weight, "carried_volume": encumbrance.carried_volume, "source_breakdown": dict(encumbrance.source_breakdown)}
        return self._facade_builder.build_from_lifecycle(lifecycle=lifecycle, group_payloads=payloads, registry_revision=registry_revision, world_config_revision=world_config_revision, active_patch_set_revision=active_patch_set_revision)


def _stat_payload(entry: EffectiveStatEntry) -> dict[str, object]:
    return {"baseline": str(entry.baseline), "effective_value": str(entry.effective_value), "accepted_modifier_ids": list(entry.accepted_modifier_ids), "rejected_modifier_reasons": dict(entry.rejected_modifier_reasons), "explanation_digest": entry.explanation_digest}


class Phase3CheckpointReplay:
    """Rebuilds domain projections from a checkpoint plus tail without a write path."""

    def __init__(
        self,
        *,
        lifecycle_projector: StateGroupLifecycleProjector,
        resource_body_projector: ResourceBodyRuntimeProjector,
        status_tag_projector: StatusTagProjector,
        composer: Phase3StateComposer,
        baselines: Mapping[str, StatBaseline],
    ) -> None:
        self._lifecycle_projector = lifecycle_projector
        self._resource_body_projector = resource_body_projector
        self._status_tag_projector = status_tag_projector
        self._composer = composer
        self._baselines = dict(baselines)

    def checkpoint(self, actor_ref: str, events: list[GameplayEvent]) -> Phase3ProjectionCheckpoint:
        return Phase3ProjectionCheckpoint(
            lifecycle=self._lifecycle_projector.rebuild(actor_ref, events),
            resources=self._resource_body_projector.rebuild_resources(actor_ref, events),
            body=self._resource_body_projector.rebuild_body(actor_ref, events),
            tags=self._status_tag_projector.rebuild(actor_ref, events),
        )

    def checkpoint_plus_tail(
        self,
        checkpoint: Phase3ProjectionCheckpoint,
        tail_events: list[GameplayEvent],
        *,
        registry_revision: str,
        world_config_revision: str,
        active_patch_set_revision: str,
    ) -> CharacterGameRuntimeState:
        actor_ref = checkpoint.actor_ref
        lifecycle = self._lifecycle_projector.rebuild(actor_ref, tail_events, checkpoint=checkpoint.lifecycle)
        resources = self._resource_body_projector.rebuild_resources(actor_ref, tail_events, checkpoint=checkpoint.resources)
        body = self._resource_body_projector.rebuild_body(actor_ref, tail_events, checkpoint=checkpoint.body)
        tags = self._status_tag_projector.rebuild(actor_ref, tail_events, checkpoint=checkpoint.tags)
        modifiers = active_status_tag_modifiers(tags, self._status_tag_projector.registry)
        resolver = EffectiveStatResolver()
        effective_stats = {
            stat_id: resolver.resolve(baseline, [modifier for modifier in modifiers if modifier.stat_id == stat_id])
            for stat_id, baseline in self._baselines.items()
        }
        return self._composer.compose(lifecycle=lifecycle, resources=resources, body=body, tags=tags, effective_stats=effective_stats, registry_revision=registry_revision, world_config_revision=world_config_revision, active_patch_set_revision=active_patch_set_revision)
