from __future__ import annotations

from hashlib import sha256
import json

import pytest

from app.gameplay.event_schema_registry import EventSchemaRegistry
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionPublisher,
    GameplayGodotProjectionRepository,
    GameplayMirrorAfterCommitDelivery,
    GameplayMirrorOutboxRefreshConsumer,
    GameplayMirrorSubscriptionRegistry,
)
from app.gameplay.models import ProjectionRefreshHint
from app.gameplay.phase3_mirror_source import (
    Phase3MirrorActorConfiguration,
    install_phase3_mirror_sources,
)
from app.gameplay.patch_lifecycle_authority import (
    GameplayPatchLifecycleAuthorityError,
    GameplayPatchLifecycleAuthorityService,
    GameplayPatchLifecycleProjector,
    GameplayPatchLifecycleReplayError,
    PatchActiveSetCommand,
    PatchCandidateInstallCommand,
    PatchLifecycleAuthorityContext,
    ResourceBoundsMigrationContext,
)
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry, PatchEventSchema, StateGroupMigration
from app.gameplay.resource_body_runtime import (
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID,
    ResourceBodyRuntimeProjector,
    ResourceDefinition,
    ResourceDefinitionRegistry,
)
from app.gameplay.runtime_state import StateGroupDefinition, StateGroupLifecycleProjector, StateGroupRegistry
from app.gameplay.state_group_lifecycle_authority import StateAssemblyContext
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy
from app.services.authority_event_bus import InMemoryAuthorityEventBus


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _manifest(
    *,
    revision: str = "patch:camp@1.0.0",
    version: str = "1.0.0",
    state_group_ids: tuple[str, ...] = (),
    state_group_migrations: tuple[StateGroupMigration, ...] = (),
    event_schemas: tuple[PatchEventSchema, ...] = (),
) -> GameplayPatchManifest:
    manifest = GameplayPatchManifest(
        manifest_schema_version=1,
        patch_id="patch:camp",
        patch_version=version,
        patch_revision_id=revision,
        content_digest="pending",
        author_id="author:repo",
        trust_policy_ref="trust:repo",
        state_group_ids=state_group_ids,
        state_group_migrations=state_group_migrations,
        event_schemas=event_schemas,
        granted_effect_types=("resource.consume",),
        verification_profiles=("gameplay-patch-runtime",),
    )
    return manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})


def _identity_rebind(group_id: str = "core.resources") -> StateGroupMigration:
    payload = {
        "group_id": group_id,
        "from_definition_version": "1.0.0",
        "to_definition_version": "1.0.0",
        "migration_kind": "identity_rebind",
    }
    return StateGroupMigration(**payload, migration_digest=_digest(payload))


def _resource_bounds_clamp() -> StateGroupMigration:
    input_schema = PatchEventSchema(event_type="gameplay.resource.materialized", schema_version=1, schema_digest="schema:resource-materialized:v1")
    output_schema = PatchEventSchema(event_type="gameplay.resource.bounds_migrated", schema_version=1, schema_digest="schema:resource-bounds-migrated:v1")
    payload = {
        "group_id": "core.resources",
        "from_definition_version": "1.0.0",
        "to_definition_version": "2.0.0",
        "migration_kind": "resource_bounds_clamp",
        "resource_id": "core.stamina",
        "migrator_id": RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID,
        "migrator_code_digest": RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
        "input_event_schema": input_schema.model_dump(mode="json"),
        "output_event_schema": output_schema.model_dump(mode="json"),
        "rollback_mode": "forward_fix_only",
    }
    return StateGroupMigration(
        group_id=payload["group_id"],
        from_definition_version=payload["from_definition_version"],
        to_definition_version=payload["to_definition_version"],
        migration_kind="resource_bounds_clamp",
        migration_digest=_digest(payload),
        resource_id="core.stamina",
        migrator_id=RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID,
        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
        input_event_schema=input_schema,
        output_event_schema=output_schema,
        rollback_mode="forward_fix_only",
    )


def _context(
    registry: GameplayPatchRegistry,
    *,
    active_revision: str | None = None,
    state_group_contexts: tuple[StateAssemblyContext, ...] = (),
    resource_bounds_migration_contexts: tuple[ResourceBoundsMigrationContext, ...] = (),
) -> PatchLifecycleAuthorityContext:
    return PatchLifecycleAuthorityContext(
        authority_principal="gameplay_patch_authority",
        expected_registry_revision=registry.registry_revision,
        expected_active_patch_set_revision=active_revision,
        world_config_revision="world:demo:v1",
        policy_revision="policy:demo:v1",
        state_group_contexts=state_group_contexts,
        resource_bounds_migration_contexts=resource_bounds_migration_contexts,
    )


def _install_command(manifest: GameplayPatchManifest, *, command_id: str = "cmd:patch:install") -> PatchCandidateInstallCommand:
    payload = {
        "command_id": command_id,
        "authority_principal": "gameplay_patch_authority",
        "idempotency_key": f"key:{command_id}",
        "causation_id": command_id,
        "correlation_id": "corr:patch:1",
        "manifest": manifest.model_dump(mode="json"),
    }
    return PatchCandidateInstallCommand(**payload, payload_digest=_digest(payload))


def _active_set_command(
    *,
    operation: str,
    patch_revision_ids: tuple[str, ...],
    command_id: str,
    state_group_actor_refs: tuple[str, ...] = (),
) -> PatchActiveSetCommand:
    payload = {
        "command_id": command_id,
        "authority_principal": "gameplay_patch_authority",
        "idempotency_key": f"key:{command_id}",
        "causation_id": command_id,
        "correlation_id": "corr:patch:1",
        "operation": operation,
        "patch_revision_ids": list(patch_revision_ids),
        "state_group_actor_refs": list(state_group_actor_refs),
    }
    return PatchActiveSetCommand(**payload, payload_digest=_digest(payload))


def _state_group_context(
    *,
    actor_ref: str,
    active_patch_set_revision: str,
    definition_version: str | None = None,
) -> StateAssemblyContext:
    return StateAssemblyContext(
        actor_ref=actor_ref,
        authority_principal="gameplay_patch_authority",
        registry_revision="state-groups:demo:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision=active_patch_set_revision,
        eligible_group_ids=("core.resources",),
        initialization_refs={"core.resources": "init:core.resources:v1"},
        state_group_definition_versions={"core.resources": definition_version} if definition_version is not None else {},
    )


def _materialize_versioned_resource(store: GameplayEventStore, *, current: int = 8) -> None:
    stream_id = "gameplay:resources:actor:char_a"
    result = store.append_batch(
        {
            "transaction_id": "tx:resource:init",
            "command_id": "cmd:resource:init",
            "expected_stream_revisions": {stream_id: store.get_stream_head(stream_id)},
            "pinned_revisions": {},
            "events": [{
                "event_id": "evt:resource:init",
                "event_type": "gameplay.resource.materialized",
                "schema_version": 1,
                "stream_id": stream_id,
                "stream_revision": 0,
                "global_sequence": 0,
                "transaction_id": "tx:resource:init",
                "command_id": "cmd:resource:init",
                "causation_id": "cmd:resource:init",
                "correlation_id": "corr:resource:init",
                "visibility_policy": "authority_only",
                "payload": {"actor_ref": "actor:char_a", "resource_id": "core.stamina", "definition_version": "1.0.0", "minimum": 0, "maximum": 10, "current": current},
            }],
            "idempotency_record": {"principal_ref": "test", "idempotency_key": "resource:init", "payload_digest": "sha256:resource:init"},
            "outbox_entries": [],
            "result_digest": "sha256:resource:init",
            "projection_refresh_hints": [],
        }
    )
    assert result.committed


def test_install_candidate_records_authority_audit_without_changing_active_set() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(store=store, registry=registry)
    manifest = _manifest()

    result = service.install_candidate(_install_command(manifest), _context(registry))

    assert result.changed is True
    assert registry.active_patch_set is None
    assert registry.candidate(manifest.patch_revision_id).content_digest == manifest.content_digest
    assert [event.event_type for event in store.read_events()] == ["gameplay.patch.candidate_installed"]


def test_enable_and_disable_commit_lifecycle_events_before_registry_cutover() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(store=store, registry=registry)
    manifest = _manifest()
    service.install_candidate(_install_command(manifest), _context(registry))

    enabled = service.apply_active_set(
        _active_set_command(operation="enable", patch_revision_ids=(manifest.patch_revision_id,), command_id="cmd:patch:enable"),
        _context(registry),
    )

    assert enabled.changed is True
    assert enabled.active_patch_set is not None
    assert enabled.active_patch_set.patch_revision_ids == (manifest.patch_revision_id,)
    disabled = service.apply_active_set(
        _active_set_command(operation="disable", patch_revision_ids=(), command_id="cmd:patch:disable"),
        _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision),
    )

    assert disabled.changed is True
    assert disabled.active_patch_set is None
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.patch.candidate_installed",
        "gameplay.patch.active_set_activated",
        "gameplay.patch.enabled",
        "gameplay.patch.disabled",
        "gameplay.patch.active_set_activated",
    ]


def test_stateful_enable_materializes_explicit_actor_groups_in_the_same_patch_batch() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_group_registry = StateGroupRegistry()
    state_group_registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="1.0.0",
            projection_schema_version=1,
        )
    )
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_group_registry,
    )
    manifest = _manifest(state_group_ids=("core.resources",))
    service.install_candidate(_install_command(manifest), _context(registry))
    target = registry.compose_active_set((manifest.patch_revision_id,))
    actor_context = _state_group_context(
        actor_ref="actor:char_a",
        active_patch_set_revision=target.active_patch_set_revision,
    )

    result = service.apply_active_set(
        _active_set_command(
            operation="enable",
            patch_revision_ids=(manifest.patch_revision_id,),
            command_id="cmd:patch:enable-stateful",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(registry, state_group_contexts=(actor_context,)),
    )

    assert result.active_patch_set == target
    events = store.read_events()
    assert [event.event_type for event in events] == [
        "gameplay.patch.candidate_installed",
        "gameplay.state_group.materialized",
        "gameplay.state_group.enabled",
        "gameplay.patch.active_set_activated",
        "gameplay.patch.enabled",
    ]
    assert {event.transaction_id for event in events[1:]} == {"tx:cmd:patch:enable-stateful"}
    assert events[1].payload["source_patch_revision"] == target.active_patch_set_revision
    lifecycle = StateGroupLifecycleProjector(state_group_registry).rebuild("actor:char_a", store.read_events())
    assert lifecycle.enabled_group_ids == ("core.resources",)


def test_stateful_disable_marks_owned_actor_groups_disabled_in_the_same_patch_batch() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_group_registry = StateGroupRegistry()
    state_group_registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="1.0.0",
            projection_schema_version=1,
        )
    )
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_group_registry,
    )
    manifest = _manifest(state_group_ids=("core.resources",))
    service.install_candidate(_install_command(manifest), _context(registry))
    target = registry.compose_active_set((manifest.patch_revision_id,))
    enabled = service.apply_active_set(
        _active_set_command(
            operation="enable",
            patch_revision_ids=(manifest.patch_revision_id,),
            command_id="cmd:patch:enable-stateful-for-disable",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=target.active_patch_set_revision,
                ),
            ),
        ),
    )
    assert enabled.active_patch_set == target

    disabled = service.apply_active_set(
        _active_set_command(
            operation="disable",
            patch_revision_ids=(),
            command_id="cmd:patch:disable-stateful",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            active_revision=target.active_patch_set_revision,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=target.active_patch_set_revision,
                ),
            ),
        ),
    )

    assert disabled.active_patch_set is None
    events = store.read_events()
    assert [event.event_type for event in events][-3:] == [
        "gameplay.state_group.disabled",
        "gameplay.patch.disabled",
        "gameplay.patch.active_set_activated",
    ]
    assert {event.transaction_id for event in events[-3:]} == {"tx:cmd:patch:disable-stateful"}
    lifecycle = StateGroupLifecycleProjector(state_group_registry).rebuild("actor:char_a", events)
    assert lifecycle.records["core.resources"].lifecycle_state == "disabled"


def test_stateful_enable_rejection_commits_neither_groups_nor_patch_cutover() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_group_registry = StateGroupRegistry()
    state_group_registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="1.0.0",
            projection_schema_version=1,
        )
    )
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_group_registry,
    )
    manifest = _manifest(state_group_ids=("core.resources",))
    service.install_candidate(_install_command(manifest), _context(registry))
    target = registry.compose_active_set((manifest.patch_revision_id,))
    before = store.read_events()

    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="patch_state_group_actor_context_required"):
        service.apply_active_set(
            _active_set_command(
                operation="enable",
                patch_revision_ids=(manifest.patch_revision_id,),
                command_id="cmd:patch:enable-stateful-rejected",
            ),
            _context(registry),
        )

    assert store.read_events() == before
    assert registry.active_patch_set is None
    actor_context = _state_group_context(
        actor_ref="actor:char_a",
        active_patch_set_revision=target.active_patch_set_revision,
    )
    store.set_write_readiness(False)
    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="projection_not_ready"):
        service.apply_active_set(
            _active_set_command(
                operation="enable",
                patch_revision_ids=(manifest.patch_revision_id,),
                command_id="cmd:patch:enable-stateful-store-rejected",
                state_group_actor_refs=("actor:char_a",),
            ),
            _context(registry, state_group_contexts=(actor_context,)),
        )
    assert store.read_events() == before
    assert registry.active_patch_set is None


def test_stateful_enable_does_not_expand_to_unowned_required_state_groups() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_group_registry = StateGroupRegistry()
    for group_id in ("core.resources", "adventure.body_runtime"):
        state_group_registry.register(
            StateGroupDefinition(
                group_id=group_id,
                definition_version="1.0.0",
                projection_schema_version=1,
            )
        )
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_group_registry,
    )
    manifest = _manifest(state_group_ids=("core.resources",))
    service.install_candidate(_install_command(manifest), _context(registry))
    target = registry.compose_active_set((manifest.patch_revision_id,))
    actor_context = _state_group_context(
        actor_ref="actor:char_a",
        active_patch_set_revision=target.active_patch_set_revision,
    ).model_copy(
        update={
            "eligible_group_ids": ("core.resources", "adventure.body_runtime"),
            "required_group_ids": ("adventure.body_runtime",),
            "initialization_refs": {
                "core.resources": "init:core.resources:v1",
                "adventure.body_runtime": "init:adventure.body_runtime:v1",
            },
        }
    )
    before = store.read_events()

    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="patch_state_group_policy_expansion_unsupported"):
        service.apply_active_set(
            _active_set_command(
                operation="enable",
                patch_revision_ids=(manifest.patch_revision_id,),
                command_id="cmd:patch:enable-policy-expansion",
                state_group_actor_refs=("actor:char_a",),
            ),
            _context(registry, state_group_contexts=(actor_context,)),
        )

    assert store.read_events() == before
    assert registry.active_patch_set is None


def test_stale_revision_and_contextless_state_group_disable_reject_before_mutation() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    store = GameplayEventStore()
    state_group_registry = StateGroupRegistry()
    state_group_registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="1.0.0",
            projection_schema_version=1,
        )
    )
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_group_registry,
    )
    manifest = _manifest(state_group_ids=("core.resources",))
    service.install_candidate(_install_command(manifest), _context(registry))
    target = registry.compose_active_set((manifest.patch_revision_id,))
    enabled = service.apply_active_set(
        _active_set_command(
            operation="enable",
            patch_revision_ids=(manifest.patch_revision_id,),
            command_id="cmd:patch:enable",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            state_group_contexts=(
                _state_group_context(actor_ref="actor:char_a", active_patch_set_revision=target.active_patch_set_revision),
            ),
        ),
    )
    assert enabled.active_patch_set is not None
    event_count = len(store.read_events())

    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="patch_active_set_revision_conflict"):
        service.apply_active_set(
            _active_set_command(operation="disable", patch_revision_ids=(), command_id="cmd:patch:stale"),
            _context(registry, active_revision="sha256:stale"),
        )
    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="patch_state_group_actor_context_required"):
        service.apply_active_set(
            _active_set_command(operation="disable", patch_revision_ids=(), command_id="cmd:patch:disable"),
            _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision),
        )

    assert len(store.read_events()) == event_count
    assert registry.active_patch_set == enabled.active_patch_set


def test_store_rejection_leaves_candidate_registry_unchanged() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    store = GameplayEventStore(event_schema_registry=EventSchemaRegistry())
    service = GameplayPatchLifecycleAuthorityService(store=store, registry=registry)

    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="event_schema_unregistered"):
        service.install_candidate(_install_command(_manifest()), _context(registry))

    assert registry.registry_revision == _digest({"patch_revision_ids": []})
    assert store.read_events() == []


def test_rule_only_upgrade_and_rollback_replace_one_revision_in_atomic_lifecycle_batches() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(store=store, registry=registry)
    v1 = _manifest(revision="patch:camp@1.0.0", version="1.0.0")
    v2 = _manifest(revision="patch:camp@2.0.0", version="2.0.0")
    service.install_candidate(_install_command(v1, command_id="cmd:patch:install-v1"), _context(registry))
    service.install_candidate(_install_command(v2, command_id="cmd:patch:install-v2"), _context(registry))
    enabled = service.apply_active_set(
        _active_set_command(operation="enable", patch_revision_ids=(v1.patch_revision_id,), command_id="cmd:patch:enable-v1"),
        _context(registry),
    )
    assert enabled.active_patch_set is not None

    upgraded = service.apply_active_set(
        _active_set_command(operation="upgrade", patch_revision_ids=(v2.patch_revision_id,), command_id="cmd:patch:upgrade"),
        _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision),
    )
    assert upgraded.active_patch_set is not None
    assert upgraded.active_patch_set.patch_revision_ids == (v2.patch_revision_id,)
    rolled_back = service.apply_active_set(
        _active_set_command(operation="rollback", patch_revision_ids=(v1.patch_revision_id,), command_id="cmd:patch:rollback"),
        _context(registry, active_revision=upgraded.active_patch_set.active_patch_set_revision),
    )
    assert rolled_back.active_patch_set is not None
    assert rolled_back.active_patch_set.patch_revision_ids == (v1.patch_revision_id,)
    assert [event.event_type for event in store.read_events()][-4:] == [
        "gameplay.patch.upgrade_activated",
        "gameplay.patch.active_set_activated",
        "gameplay.patch.rollback_activated",
        "gameplay.patch.active_set_activated",
    ]


def test_stateful_identity_rebind_upgrade_and_rollback_are_atomic_for_each_explicit_actor() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_group_registry = StateGroupRegistry()
    state_group_registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="1.0.0",
            projection_schema_version=1,
        )
    )
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_group_registry,
    )
    v1 = _manifest(
        revision="patch:camp@1.0.0",
        version="1.0.0",
        state_group_ids=("core.resources",),
        state_group_migrations=(_identity_rebind(),),
    )
    v2 = _manifest(
        revision="patch:camp@2.0.0",
        version="2.0.0",
        state_group_ids=("core.resources",),
        state_group_migrations=(_identity_rebind(),),
    )
    service.install_candidate(_install_command(v1, command_id="cmd:patch:install-stateful-v1"), _context(registry))
    service.install_candidate(_install_command(v2, command_id="cmd:patch:install-stateful-v2"), _context(registry))
    v1_target = registry.compose_active_set((v1.patch_revision_id,))
    enabled = service.apply_active_set(
        _active_set_command(
            operation="enable",
            patch_revision_ids=(v1.patch_revision_id,),
            command_id="cmd:patch:enable-stateful-upgrade",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=v1_target.active_patch_set_revision,
                ),
            ),
        ),
    )
    assert enabled.active_patch_set == v1_target
    v2_target = registry.compose_active_set((v2.patch_revision_id,))

    upgraded = service.apply_active_set(
        _active_set_command(
            operation="upgrade",
            patch_revision_ids=(v2.patch_revision_id,),
            command_id="cmd:patch:upgrade-stateful",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            active_revision=v1_target.active_patch_set_revision,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=v1_target.active_patch_set_revision,
                ),
            ),
        ),
    )

    assert upgraded.active_patch_set == v2_target
    assert [event.event_type for event in store.read_events()][-3:] == [
        "gameplay.state_group.rebound",
        "gameplay.patch.upgrade_activated",
        "gameplay.patch.active_set_activated",
    ]
    assert {event.transaction_id for event in store.read_events()[-3:]} == {"tx:cmd:patch:upgrade-stateful"}
    after_upgrade = StateGroupLifecycleProjector(state_group_registry).rebuild("actor:char_a", store.read_events())
    assert after_upgrade.records["core.resources"].source_patch_revision == v2_target.active_patch_set_revision
    assert after_upgrade.records["core.resources"].lifecycle_state == "enabled"

    rolled_back = service.apply_active_set(
        _active_set_command(
            operation="rollback",
            patch_revision_ids=(v1.patch_revision_id,),
            command_id="cmd:patch:rollback-stateful",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            active_revision=v2_target.active_patch_set_revision,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=v2_target.active_patch_set_revision,
                ),
            ),
        ),
    )

    assert rolled_back.active_patch_set == v1_target
    after_rollback = StateGroupLifecycleProjector(state_group_registry).rebuild("actor:char_a", store.read_events())
    assert after_rollback.records["core.resources"].source_patch_revision == v1_target.active_patch_set_revision


def test_stateful_upgrade_requires_a_target_manifest_migration_declaration_before_write() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_group_registry = StateGroupRegistry()
    state_group_registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="1.0.0",
            projection_schema_version=1,
        )
    )
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_group_registry,
    )
    v1 = _manifest(revision="patch:camp@1.0.0", version="1.0.0", state_group_ids=("core.resources",))
    v2 = _manifest(revision="patch:camp@2.0.0", version="2.0.0", state_group_ids=("core.resources",))
    service.install_candidate(_install_command(v1, command_id="cmd:patch:install-missing-migration-v1"), _context(registry))
    service.install_candidate(_install_command(v2, command_id="cmd:patch:install-missing-migration-v2"), _context(registry))
    v1_target = registry.compose_active_set((v1.patch_revision_id,))
    service.apply_active_set(
        _active_set_command(
            operation="enable",
            patch_revision_ids=(v1.patch_revision_id,),
            command_id="cmd:patch:enable-missing-migration",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=v1_target.active_patch_set_revision,
                ),
            ),
        ),
    )
    before = store.read_events()

    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="patch_state_group_migration_declaration_required"):
        service.apply_active_set(
            _active_set_command(
                operation="upgrade",
                patch_revision_ids=(v2.patch_revision_id,),
                command_id="cmd:patch:upgrade-missing-migration",
                state_group_actor_refs=("actor:char_a",),
            ),
            _context(
                registry,
                active_revision=v1_target.active_patch_set_revision,
                state_group_contexts=(
                    _state_group_context(
                        actor_ref="actor:char_a",
                        active_patch_set_revision=v1_target.active_patch_set_revision,
                    ),
                ),
            ),
        )

    assert store.read_events() == before
    assert registry.active_patch_set == v1_target


def test_upgrade_and_rollback_reject_direction_or_state_group_migration_before_write() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(store=store, registry=registry)
    v1 = _manifest(revision="patch:camp@1.0.0", version="1.0.0")
    v2 = _manifest(revision="patch:camp@2.0.0", version="2.0.0", state_group_ids=("core.resources",))
    v2_rule_only = _manifest(revision="patch:camp@2.0.0:rule-only", version="2.0.0")
    service.install_candidate(_install_command(v1, command_id="cmd:patch:install-v1"), _context(registry))
    service.install_candidate(_install_command(v2, command_id="cmd:patch:install-v2"), _context(registry))
    service.install_candidate(_install_command(v2_rule_only, command_id="cmd:patch:install-v2-rule-only"), _context(registry))
    enabled = service.apply_active_set(
        _active_set_command(operation="enable", patch_revision_ids=(v1.patch_revision_id,), command_id="cmd:patch:enable-v1"),
        _context(registry),
    )
    assert enabled.active_patch_set is not None
    event_count = len(store.read_events())

    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="patch_upgrade_state_group_set_mismatch"):
        service.apply_active_set(
            _active_set_command(operation="upgrade", patch_revision_ids=(v2.patch_revision_id,), command_id="cmd:patch:upgrade-v2"),
            _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision),
        )
    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="patch_rollback_direction_invalid"):
        service.apply_active_set(
            _active_set_command(operation="rollback", patch_revision_ids=(v2_rule_only.patch_revision_id,), command_id="cmd:patch:rollback-v2"),
            _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision),
        )
    assert len(store.read_events()) == event_count
    assert registry.active_patch_set == enabled.active_patch_set


def test_lifecycle_replay_rebuilds_rule_only_upgrade_and_rollback_history() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(store=store, registry=registry)
    v1 = _manifest(revision="patch:camp@1.0.0", version="1.0.0")
    v2 = _manifest(revision="patch:camp@2.0.0", version="2.0.0")
    service.install_candidate(_install_command(v1, command_id="cmd:patch:install-v1"), _context(registry))
    service.install_candidate(_install_command(v2, command_id="cmd:patch:install-v2"), _context(registry))
    enabled = service.apply_active_set(_active_set_command(operation="enable", patch_revision_ids=(v1.patch_revision_id,), command_id="cmd:patch:enable"), _context(registry))
    assert enabled.active_patch_set is not None
    upgraded = service.apply_active_set(_active_set_command(operation="upgrade", patch_revision_ids=(v2.patch_revision_id,), command_id="cmd:patch:upgrade"), _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision))
    assert upgraded.active_patch_set is not None
    service.apply_active_set(_active_set_command(operation="rollback", patch_revision_ids=(v1.patch_revision_id,), command_id="cmd:patch:rollback"), _context(registry, active_revision=upgraded.active_patch_set.active_patch_set_revision))

    projection = GameplayPatchLifecycleProjector(registry=registry).rebuild(store.read_events())

    assert projection.active_patch_set is not None
    assert projection.active_patch_set.patch_revision_ids == (v1.patch_revision_id,)
    assert projection.installed_patch_revision_ids == (v1.patch_revision_id, v2.patch_revision_id)


def test_lifecycle_replay_rejects_candidate_digest_or_active_set_history_mismatch() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    registry.install(manifest)
    projector = GameplayPatchLifecycleProjector(registry=registry)
    event = {
        "event_id": "evt:bad:candidate",
        "event_type": "gameplay.patch.candidate_installed",
        "schema_version": 1,
        "stream_id": "gameplay:patch_lifecycle",
        "stream_revision": 1,
        "global_sequence": 1,
        "transaction_id": "tx:bad",
        "command_id": "cmd:bad",
        "causation_id": "cmd:bad",
        "correlation_id": "corr:bad",
        "visibility_policy": "authority_only",
        "payload": {"patch_revision_id": manifest.patch_revision_id, "content_digest": "sha256:tampered"},
    }

    with pytest.raises(GameplayPatchLifecycleReplayError, match="patch_lifecycle_candidate_digest_mismatch"):
        projector.rebuild([event])


def test_resource_bounds_patch_upgrade_commits_domain_fact_lifecycle_transition_and_cutover_atomically() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_groups = StateGroupRegistry()
    state_groups.register(StateGroupDefinition(group_id="core.resources", definition_version="1.0.0", projection_schema_version=1))
    state_groups.register(StateGroupDefinition(group_id="core.resources", definition_version="2.0.0", projection_schema_version=2))
    resource_definitions = ResourceDefinitionRegistry()
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="1.0.0", minimum=0, maximum=10))
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="2.0.0", minimum=0, maximum=6))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_groups,
        resource_definition_registry=resource_definitions,
    )
    v1 = _manifest(revision="patch:camp@1.0.0", version="1.0.0", state_group_ids=("core.resources",))
    migration = _resource_bounds_clamp()
    v2 = _manifest(
        revision="patch:camp@2.0.0",
        version="2.0.0",
        state_group_ids=("core.resources",),
        state_group_migrations=(migration,),
        event_schemas=(migration.input_event_schema, migration.output_event_schema),
    )
    service.install_candidate(_install_command(v1, command_id="cmd:install:v1"), _context(registry))
    service.install_candidate(_install_command(v2, command_id="cmd:install:v2"), _context(registry))
    v1_target = registry.compose_active_set((v1.patch_revision_id,))
    enabled = service.apply_active_set(
        _active_set_command(
            operation="enable",
            patch_revision_ids=(v1.patch_revision_id,),
            command_id="cmd:enable:v1",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=v1_target.active_patch_set_revision,
                    definition_version="1.0.0",
                ),
            ),
        ),
    )
    _materialize_versioned_resource(store)
    resources = ResourceBodyRuntimeProjector(resource_definitions=resource_definitions).rebuild_resources("actor:char_a", store.read_events())
    v2_target = registry.compose_active_set((v2.patch_revision_id,))

    before_rejected_migration = list(store.read_events())
    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="projection_revision_conflict"):
        service.apply_active_set(
            _active_set_command(
                operation="upgrade",
                patch_revision_ids=(v2.patch_revision_id,),
                command_id="cmd:upgrade:resource-bounds-stale",
                state_group_actor_refs=("actor:char_a",),
            ),
            _context(
                registry,
                active_revision=enabled.active_patch_set.active_patch_set_revision,
                state_group_contexts=(
                    _state_group_context(
                        actor_ref="actor:char_a",
                        active_patch_set_revision=enabled.active_patch_set.active_patch_set_revision,
                        definition_version="1.0.0",
                    ),
                ),
                resource_bounds_migration_contexts=(
                    ResourceBoundsMigrationContext(
                        actor_ref="actor:char_a",
                        resource_id="core.stamina",
                        expected_projection_revision="projection:stale",
                    ),
                ),
            ),
        )
    assert store.read_events() == before_rejected_migration
    assert registry.active_patch_set == enabled.active_patch_set

    upgrade_command = _active_set_command(
            operation="upgrade",
            patch_revision_ids=(v2.patch_revision_id,),
            command_id="cmd:upgrade:resource-bounds",
            state_group_actor_refs=("actor:char_a",),
        )
    upgrade_context = _context(
            registry,
            active_revision=enabled.active_patch_set.active_patch_set_revision,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=enabled.active_patch_set.active_patch_set_revision,
                    definition_version="1.0.0",
                ),
            ),
            resource_bounds_migration_contexts=(
                ResourceBoundsMigrationContext(
                    actor_ref="actor:char_a",
                    resource_id="core.stamina",
                    expected_projection_revision=resources.projection_revision,
                ),
            ),
        )
    upgraded = service.apply_active_set(upgrade_command, upgrade_context)

    assert upgraded.active_patch_set == v2_target
    transaction = store.read_transactions()[-1]
    assert [event.event_type for event in transaction.events] == [
        "gameplay.resource.bounds_migrated",
        "gameplay.state_group.migrated",
        "gameplay.patch.upgrade_activated",
        "gameplay.patch.active_set_activated",
    ]
    assert {event.transaction_id for event in transaction.events} == {"tx:cmd:upgrade:resource-bounds"}
    assert transaction.projection_refresh_hints == [
        ProjectionRefreshHint(
            projection_id="godot_mirror",
            stream_id="gameplay:resources:actor:char_a",
            reason="patch_resource_migration_committed",
            actor_refs=("actor:char_a",),
        )
    ]
    resource_entry = ResourceBodyRuntimeProjector(resource_definitions=resource_definitions).rebuild_resources("actor:char_a", store.read_events()).entries["core.stamina"]
    assert (resource_entry.definition_version, resource_entry.current, resource_entry.maximum) == ("2.0.0", 6, 6)
    lifecycle = StateGroupLifecycleProjector(state_groups).rebuild("actor:char_a", store.read_events())
    assert lifecycle.records["core.resources"].definition_version == "2.0.0"
    assert lifecycle.records["core.resources"].source_patch_revision == v2_target.active_patch_set_revision

    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    install_phase3_mirror_sources(
        configurations=(
            Phase3MirrorActorConfiguration(
                actor_ref="actor:char_a",
                state_group_definitions=(
                    StateGroupDefinition(group_id="core.resources", definition_version="1.0.0", projection_schema_version=1),
                    StateGroupDefinition(group_id="core.resources", definition_version="2.0.0", projection_schema_version=2),
                ),
                godot_view_policies=(
                    StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("entries",)),
                ),
                godot_allowed_group_ids=("core.resources",),
                resource_definitions=(
                    ResourceDefinition(resource_id="core.stamina", definition_version="1.0.0", minimum=0, maximum=10),
                    ResourceDefinition(resource_id="core.stamina", definition_version="2.0.0", minimum=0, maximum=6),
                ),
                registry_revision="registry:patch-migration:v1",
                world_config_revision="world:patch-migration:v1",
                active_patch_set_revision=v2_target.active_patch_set_revision,
            ),
        ),
        store=store,
        publisher=publisher,
    )
    publisher.refresh_actor(actor_ref="actor:char_a")
    subscriptions = GameplayMirrorSubscriptionRegistry(projection_source=repository.view_for)
    subscriptions.grant_read_scope(session_ref="session:patch-migration", actor_ref="actor:char_a")
    subscriptions.subscribe(session_ref="session:patch-migration", actor_ref="actor:char_a")
    delivered: list[tuple[str, dict[str, object]]] = []
    mirror_consumer = GameplayMirrorOutboxRefreshConsumer(
        delivery=GameplayMirrorAfterCommitDelivery(
            registry=subscriptions,
            deliver=lambda session_ref, payload: delivered.append((session_ref, payload)),
        )
    )
    dispatcher = GameplayOutboxDispatcher(
        store=store,
        bus=InMemoryAuthorityEventBus(),
        after_transaction_dispatched=lambda committed: (
            publisher.after_transaction_dispatched(committed),
            mirror_consumer.after_transaction_dispatched(committed),
        ),
    )

    assert transaction.outbox_entries == []
    assert dispatcher.dispatch_pending().published_count == 0
    assert [(session_ref, payload["actor_ref"]) for session_ref, payload in delivered] == [
        ("session:patch-migration", "actor:char_a"),
    ]
    mirror_payload = delivered[0][1]
    assert mirror_payload["groups"]["core.resources"]["payload"]["entries"]["core.stamina"]["maximum"] == 6
    assert "migration_digest" not in str(mirror_payload)
    assert "migrator_code_digest" not in str(mirror_payload)
    assert "authority_command" not in str(mirror_payload)

    duplicate = service.apply_active_set(upgrade_command, upgrade_context)
    assert duplicate.changed is False
    assert duplicate.append_result.idempotency_status == "duplicate_replayed"
    assert store.read_transactions()[-1] == transaction

    before_rollback_events = list(store.read_events())
    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="rollback_unsupported"):
        service.apply_active_set(
            _active_set_command(
                operation="rollback",
                patch_revision_ids=(v1.patch_revision_id,),
                command_id="cmd:rollback:resource-bounds",
                state_group_actor_refs=("actor:char_a",),
            ),
            _context(registry, active_revision=v2_target.active_patch_set_revision),
        )
    assert store.read_events() == before_rollback_events


def test_resource_bounds_migration_manifest_requires_declared_event_schema_identities() -> None:
    with pytest.raises(ValueError, match="patch_resource_migration_schema_not_declared"):
        _manifest(
            revision="patch:camp@2.0.0",
            version="2.0.0",
            state_group_ids=("core.resources",),
            state_group_migrations=(_resource_bounds_clamp(),),
        )


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("input_schema_digest", "patch_resource_migration_schema_digest_mismatch"),
        ("migration_digest", "patch_resource_migration_digest_mismatch"),
        ("migrator_id", "patch_resource_migration_contract_invalid"),
        ("actor_context", "patch_resource_migration_context_mismatch"),
    ],
)
def test_resource_bounds_migration_rejects_tampered_manifest_descriptor_before_any_write(
    mutation: str,
    expected_error: str,
) -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_groups = StateGroupRegistry()
    state_groups.register(StateGroupDefinition(group_id="core.resources", definition_version="1.0.0", projection_schema_version=1))
    state_groups.register(StateGroupDefinition(group_id="core.resources", definition_version="2.0.0", projection_schema_version=2))
    resource_definitions = ResourceDefinitionRegistry()
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="1.0.0", minimum=0, maximum=10))
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="2.0.0", minimum=0, maximum=6))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(
        store=store,
        registry=registry,
        state_group_registry=state_groups,
        resource_definition_registry=resource_definitions,
    )
    v1 = _manifest(revision="patch:camp@1.0.0", version="1.0.0", state_group_ids=("core.resources",))
    migration = _resource_bounds_clamp()
    if mutation == "input_schema_digest":
        migration = migration.model_copy(
            update={"input_event_schema": migration.input_event_schema.model_copy(update={"schema_digest": "schema:tampered"})}
        )
    elif mutation == "migration_digest":
        migration = migration.model_copy(update={"migration_digest": "sha256:" + "0" * 64})
    elif mutation == "migrator_id":
        migration = migration.model_copy(update={"migrator_id": "resource.bounds.untrusted.v1"})
    if mutation != "migration_digest":
        migration = migration.model_copy(update={"migration_digest": migration.expected_migration_digest()})
    v2 = _manifest(
        revision="patch:camp@2.0.0",
        version="2.0.0",
        state_group_ids=("core.resources",),
        state_group_migrations=(migration,),
        event_schemas=(migration.input_event_schema, migration.output_event_schema),
    )
    service.install_candidate(_install_command(v1, command_id=f"cmd:install:v1:{mutation}"), _context(registry))
    service.install_candidate(_install_command(v2, command_id=f"cmd:install:v2:{mutation}"), _context(registry))
    v1_target = registry.compose_active_set((v1.patch_revision_id,))
    enabled = service.apply_active_set(
        _active_set_command(
            operation="enable",
            patch_revision_ids=(v1.patch_revision_id,),
            command_id=f"cmd:enable:v1:{mutation}",
            state_group_actor_refs=("actor:char_a",),
        ),
        _context(
            registry,
            state_group_contexts=(
                _state_group_context(
                    actor_ref="actor:char_a",
                    active_patch_set_revision=v1_target.active_patch_set_revision,
                    definition_version="1.0.0",
                ),
            ),
        ),
    )
    _materialize_versioned_resource(store)
    resources = ResourceBodyRuntimeProjector(resource_definitions=resource_definitions).rebuild_resources("actor:char_a", store.read_events())
    before_events = list(store.read_events())
    before_active = registry.active_patch_set

    with pytest.raises(GameplayPatchLifecycleAuthorityError, match=expected_error):
        service.apply_active_set(
            _active_set_command(
                operation="upgrade",
                patch_revision_ids=(v2.patch_revision_id,),
                command_id=f"cmd:upgrade:tampered:{mutation}",
                state_group_actor_refs=("actor:char_a",),
            ),
            _context(
                registry,
                active_revision=enabled.active_patch_set.active_patch_set_revision,
                state_group_contexts=(
                    _state_group_context(
                        actor_ref="actor:char_a",
                        active_patch_set_revision=enabled.active_patch_set.active_patch_set_revision,
                        definition_version="1.0.0",
                    ),
                ),
                resource_bounds_migration_contexts=(
                    ResourceBoundsMigrationContext(
                        actor_ref="actor:other" if mutation == "actor_context" else "actor:char_a",
                        resource_id="core.stamina",
                        expected_projection_revision=resources.projection_revision,
                    ),
                ),
            ),
        )

    assert store.read_events() == before_events
    assert registry.active_patch_set == before_active
