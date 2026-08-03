from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.runtime_state import (
    StateGroupDefinition,
    StateGroupLifecycleError,
    StateGroupLifecycleProjector,
    StateGroupRegistry,
)
from app.gameplay.state_group_lifecycle_authority import (
    StateAssemblyContext,
    StateAssemblyInputs,
    StateGroupEligibilityCatalog,
    StateGroupEligibilityRule,
    StateGroupLifecycleAuthorityError,
    StateGroupLifecycleAuthorityService,
    StateGroupLifecycleCommand,
    compile_state_assembly_context,
)


def _definition(group_id: str, *, dependencies: tuple[str, ...] = ()) -> StateGroupDefinition:
    return StateGroupDefinition(
        group_id=group_id,
        definition_version="1.0.0",
        projection_schema_version=1,
        dependencies=dependencies,
    )


def _context(**overrides: object) -> StateAssemblyContext:
    values: dict[str, object] = {
        "actor_ref": "actor:char_a",
        "authority_principal": "gameplay_authority",
        "registry_revision": "registry:core:v1",
        "world_config_revision": "world:demo:v1",
        "active_patch_set_revision": "patches:demo:v1",
        "eligible_group_ids": ("core.resources", "adventure.body_runtime"),
        "required_group_ids": (),
        "forbidden_group_ids": (),
        "initialization_refs": {
            "core.resources": "init:core.resources:v1",
            "adventure.body_runtime": "init:adventure.body_runtime:v1",
        },
    }
    values.update(overrides)
    return StateAssemblyContext(**values)


def _command(
    operation: str,
    groups: tuple[str, ...],
    *,
    command_id: str = "cmd:state-groups:1",
    key: str = "state-groups:1",
    digest: str = "sha256:state-groups:1",
) -> StateGroupLifecycleCommand:
    return StateGroupLifecycleCommand(
        command_id=command_id,
        authority_principal="gameplay_authority",
        idempotency_key=key,
        payload_digest=digest,
        causation_id=command_id,
        correlation_id="corr:state-groups:1",
        operation=operation,
        requested_group_ids=groups,
        policy_revision=1,
    )


def test_authority_service_materializes_and_enables_dependency_order_in_one_batch() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    registry.register(_definition("adventure.body_runtime", dependencies=("core.resources",)))
    store = GameplayEventStore()
    service = StateGroupLifecycleAuthorityService(store=store, registry=registry)

    result = service.apply(_command("enable", ("adventure.body_runtime",)), _context())

    assert result.accepted is True
    assert result.changed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.state_group.materialized",
        "gameplay.state_group.enabled",
        "gameplay.state_group.materialized",
        "gameplay.state_group.enabled",
    ]
    rebuilt = StateGroupLifecycleProjector(registry).rebuild("actor:char_a", store.read_events())
    assert rebuilt.enabled_group_ids == ("core.resources", "adventure.body_runtime")


def test_planning_state_group_lifecycle_is_non_mutating_and_returns_bound_event_specs() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    store = GameplayEventStore()
    service = StateGroupLifecycleAuthorityService(store=store, registry=registry)
    command = _command("enable", ("core.resources",))

    plan = service.plan(command, _context())

    assert store.read_events() == []
    assert plan.stream_id == "gameplay:state_groups:actor:char_a"
    assert plan.expected_stream_revision == 0
    assert [event_type for event_type, _ in plan.event_specs] == [
        "gameplay.state_group.materialized",
        "gameplay.state_group.enabled",
    ]
    assert plan.event_specs[0][1]["source_patch_revision"] == "patches:demo:v1"


def test_apply_binds_the_same_event_contents_returned_by_the_non_mutating_plan() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    store = GameplayEventStore()
    service = StateGroupLifecycleAuthorityService(store=store, registry=registry)
    command = _command("enable", ("core.resources",))
    plan = service.plan(command, _context())
    expected_events = service.serialize_plan_events(
        plan,
        transaction_id="tx:cmd:state-groups:1",
        command_id=command.command_id,
        causation_id=command.causation_id,
        correlation_id=command.correlation_id,
        event_id_namespace="state-group",
    )

    result = service.apply(command, _context())

    assert result.changed is True
    actual_events = [event.model_dump(mode="json") for event in store.read_events()]
    for actual, expected in zip(actual_events, expected_events, strict=True):
        assert actual["event_id"] == expected["event_id"]
        assert actual["event_type"] == expected["event_type"]
        assert actual["transaction_id"] == expected["transaction_id"]
        assert actual["command_id"] == expected["command_id"]
        assert actual["payload"] == expected["payload"]


def test_lifecycle_projector_rejects_a_tampered_identity_rebind_event() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    store = GameplayEventStore()
    service = StateGroupLifecycleAuthorityService(store=store, registry=registry)
    service.apply(_command("enable", ("core.resources",)), _context())
    enabled_event = store.read_events()[-1]
    tampered_rebind = enabled_event.model_copy(
        update={
            "event_id": "evt:tampered:rebind",
            "event_type": "gameplay.state_group.rebound",
            "stream_revision": 3,
            "global_sequence": 3,
            "payload": {
                "actor_ref": "actor:char_a",
                "group_id": "core.resources",
                "definition_version": "1.0.0",
                "previous_source_patch_revision": "patches:demo:v1",
                "next_source_patch_revision": "patches:demo:v2",
                "migration_kind": "identity_rebind",
                "migration_digest": "sha256:tampered",
            },
        },
        deep=True,
    )

    with pytest.raises(StateGroupLifecycleError, match="rebind_migration_invalid"):
        StateGroupLifecycleProjector(registry).rebuild("actor:char_a", [*store.read_events(), tampered_rebind])


def test_authority_service_rejects_ineligible_groups_before_writing_events() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    store = GameplayEventStore()
    service = StateGroupLifecycleAuthorityService(store=store, registry=registry)

    with pytest.raises(StateGroupLifecycleAuthorityError, match="group_not_eligible"):
        service.apply(
            _command("enable", ("core.resources",)),
            _context(eligible_group_ids=(), forbidden_group_ids=("core.resources",)),
        )

    assert store.read_events() == []


def test_authority_service_replays_duplicate_enable_and_preserves_dependency_safety_on_disable() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    registry.register(_definition("adventure.body_runtime", dependencies=("core.resources",)))
    store = GameplayEventStore()
    service = StateGroupLifecycleAuthorityService(store=store, registry=registry)
    service.apply(_command("enable", ("adventure.body_runtime",)), _context())

    duplicate = service.apply(
        _command(
            "enable",
            ("adventure.body_runtime",),
            command_id="cmd:state-groups:duplicate",
            key="state-groups:1",
        ),
        _context(),
    )

    assert duplicate.accepted is True
    assert duplicate.changed is False
    assert len(store.read_events()) == 4
    with pytest.raises(StateGroupLifecycleAuthorityError, match="dependency_in_use"):
        service.apply(
            _command(
                "disabled",
                ("core.resources",),
                command_id="cmd:disable:resources",
                key="state-groups:disable",
                digest="sha256:state-groups:disable",
            ),
            _context(),
        )


def test_authority_service_dormant_then_reenables_without_rematerializing() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    store = GameplayEventStore()
    service = StateGroupLifecycleAuthorityService(store=store, registry=registry)
    service.apply(_command("enable", ("core.resources",)), _context())

    dormant = service.apply(
        _command(
            "dormant",
            ("core.resources",),
            command_id="cmd:dormant",
            key="state-groups:dormant",
            digest="sha256:state-groups:dormant",
        ),
        _context(),
    )
    restored = service.apply(_command("enable", ("core.resources",), command_id="cmd:restore", key="state-groups:restore"), _context())

    assert dormant.changed is True
    assert restored.changed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.state_group.materialized",
        "gameplay.state_group.enabled",
        "gameplay.state_group.dormant",
        "gameplay.state_group.enabled",
    ]


def test_policy_catalog_compiles_eligible_required_groups_and_initialization_refs() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    registry.register(_definition("adventure.body_runtime", dependencies=("core.resources",)))
    catalog = StateGroupEligibilityCatalog(
        catalog_revision="eligibility:demo:v1",
        rules=[
            StateGroupEligibilityRule(group_id="core.resources", initialization_ref="init:resources:v1"),
            StateGroupEligibilityRule(
                group_id="adventure.body_runtime",
                actor_archetype_refs=("archetype:adventurer",),
                world_config_revisions=("world:demo:v1",),
                active_patch_set_revisions=("patches:demo:v1",),
                required=True,
                initialization_ref="init:body:v1",
            ),
        ],
    )

    context = compile_state_assembly_context(
        StateAssemblyInputs(
            actor_ref="actor:char_a",
            actor_archetype_ref="archetype:adventurer",
            authority_principal="gameplay_authority",
            registry_revision="registry:core:v1",
            world_config_revision="world:demo:v1",
            active_patch_set_revision="patches:demo:v1",
        ),
        catalog,
        registry,
    )

    assert context.eligible_group_ids == ("core.resources", "adventure.body_runtime")
    assert context.required_group_ids == ("adventure.body_runtime",)
    assert context.forbidden_group_ids == ()
    assert context.initialization_refs["adventure.body_runtime"] == "init:body:v1"

    result = StateGroupLifecycleAuthorityService(store=GameplayEventStore(), registry=registry).apply(
        _command("enable", ("adventure.body_runtime",)),
        context,
    )

    assert result.lifecycle.enabled_group_ids == ("core.resources", "adventure.body_runtime")


def test_policy_catalog_fails_closed_when_a_required_group_dependency_is_not_eligible() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    registry.register(_definition("adventure.body_runtime", dependencies=("core.resources",)))
    catalog = StateGroupEligibilityCatalog(
        catalog_revision="eligibility:broken:v1",
        rules=[
            StateGroupEligibilityRule(
                group_id="adventure.body_runtime",
                required=True,
                initialization_ref="init:body:v1",
            )
        ],
    )

    with pytest.raises(StateGroupLifecycleAuthorityError, match="required_dependency_ineligible"):
        compile_state_assembly_context(
            StateAssemblyInputs(
                actor_ref="actor:char_a",
                actor_archetype_ref="archetype:adventurer",
                authority_principal="gameplay_authority",
                registry_revision="registry:core:v1",
                world_config_revision="world:demo:v1",
                active_patch_set_revision="patches:demo:v1",
            ),
            catalog,
            registry,
        )
