from __future__ import annotations

from types import MappingProxyType

import pytest

from app.gameplay.ability_runtime import (
    AbilityAffordanceResolver,
    AbilityAuthorityService,
    AbilityDefinitionRegistry,
    AbilityPathDefinition,
    AbilityRuntimeError,
    AbilitySkillDefinition,
    AbilityStateProjector,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.resource_body_runtime import BodyRuntimeProjection, FunctionalCapacity, ResourceBodyRuntimeProjector


ACTOR = "actor:ability"


def _registry() -> AbilityDefinitionRegistry:
    registry = AbilityDefinitionRegistry()
    registry.register_skill(AbilitySkillDefinition("skill:sword", "1"))
    registry.register_path(AbilityPathDefinition("path:sword.slash", "skill:sword", "action:sword.slash", "basic", "core.stamina", 3, "grip.right"))
    return registry


def _empty_resources():
    return ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, [])


def _empty_body():
    return ResourceBodyRuntimeProjector().rebuild_body(ACTOR, [])


def _learn(store: GameplayEventStore, registry: AbilityDefinitionRegistry) -> None:
    result = AbilityAuthorityService(store=store, registry=registry).learn(
        command_id="cmd:learn", actor_ref=ACTOR, skill_id="skill:sword", rank="basic", source_ref="seed:sword", idempotency_key="learn", causation_id="cause:learn", correlation_id="corr:ability"
    )
    assert result.committed is True


def test_stable_learned_skill_is_event_derived_and_affordance_is_read_only() -> None:
    registry = _registry()
    store = GameplayEventStore()
    _learn(store, registry)
    abilities = AbilityStateProjector(registry).rebuild(ACTOR, store.read_events())

    result = AbilityAffordanceResolver(registry).resolve(actor_ref=ACTOR, action_ref="action:sword.slash", abilities=abilities, resources=_empty_resources(), body=_empty_body())

    assert abilities.learned["skill:sword"].rank == "basic"
    assert result.overall_status == "unknown"
    assert result.path_results[0].blocker_codes == ("affordance_input_unknown",)
    assert [event.event_type for event in store.read_events()] == ["gameplay.ability.learned"]


def test_body_block_does_not_remove_learned_ability() -> None:
    registry = _registry()
    store = GameplayEventStore()
    _learn(store, registry)
    abilities = AbilityStateProjector(registry).rebuild(ACTOR, store.read_events())
    projector = ResourceBodyRuntimeProjector()
    resources = projector.rebuild_resources(ACTOR, [])
    body = BodyRuntimeProjection(
        actor_ref=ACTOR,
        injuries=MappingProxyType({}),
        functions=MappingProxyType({"grip.right": FunctionalCapacity("grip.right", 0, "unavailable", ("injury:right",))}),
        source_revision_vector=MappingProxyType({"gameplay:body:actor:ability": 1}),
        projection_revision="body:injured",
    )

    result = AbilityAffordanceResolver(registry).resolve(actor_ref=ACTOR, action_ref="action:sword.slash", abilities=abilities, resources=resources, body=body)

    assert result.overall_status == "blocked"
    assert "required_body_function_unavailable" in result.path_results[0].blocker_codes
    assert abilities.learned["skill:sword"].rank == "basic"


def test_unknown_definition_and_cross_actor_projection_fail_closed() -> None:
    registry = _registry()
    store = GameplayEventStore()
    with pytest.raises(AbilityRuntimeError, match="ability_skill_definition_unknown"):
        AbilityAuthorityService(store=store, registry=registry).learn(
            command_id="cmd:unknown", actor_ref=ACTOR, skill_id="skill:unknown", rank="basic", source_ref="seed", idempotency_key="unknown", causation_id="cause", correlation_id="corr"
        )
    abilities = AbilityStateProjector(registry).rebuild(ACTOR, [])
    wrong_body = BodyRuntimeProjection("actor:other", MappingProxyType({}), MappingProxyType({}), MappingProxyType({}), "body:other")
    with pytest.raises(AbilityRuntimeError, match="ability_affordance_actor_mismatch"):
        AbilityAffordanceResolver(registry).resolve(actor_ref=ACTOR, action_ref="action:sword.slash", abilities=abilities, resources=_empty_resources(), body=wrong_body)
