"""Authority-owned control-plane lifecycle for immutable Gameplay patches.

The registry remains a manifest/rule container. This module is the only first
closure path that records candidate installation and active-set changes in the
Gameplay event ledger. It supports direct state-group lifecycle transitions and
the narrow manifest-declared identity rebind for compatible same-patch revision
cutovers; grant/modifier and data-transform migration effects remain excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, StrictGameplayModel
from app.gameplay.patch_runtime import (
    GameplayPatchManifest,
    GameplayPatchRegistry,
    GameplayPatchRuntimeError,
    PatchSetRevision,
    StateGroupMigration,
)
from app.gameplay.resource_body_runtime import (
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID,
    RESOURCE_BOUNDS_MIGRATED_SCHEMA_DIGEST,
    RESOURCE_MATERIALIZED_SCHEMA_DIGEST,
    ResourceBodyRuntimeError,
    ResourceBodyRuntimeProjector,
    ResourceBoundsMigrationAuthorityService,
    ResourceBoundsMigrationPlan,
    ResourceBoundsMigrationRequest,
    ResourceDefinitionRegistry,
)
from app.gameplay.runtime_state import StateGroupRegistry
from app.gameplay.state_group_lifecycle_authority import (
    StateAssemblyContext,
    StateGroupDefinitionMigration,
    StateGroupLifecycleAuthorityError,
    StateGroupLifecycleAuthorityService,
    StateGroupLifecycleCommand,
)


class GameplayPatchLifecycleAuthorityError(ValueError):
    """A patch lifecycle command was rejected before registry cutover."""


class GameplayPatchLifecycleReplayError(ValueError):
    """Committed patch lifecycle history cannot be replayed safely."""


class PatchLifecycleAuthorityContext(StrictGameplayModel):
    """Pinned authority inputs for one control-plane command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_principal: str = Field(min_length=1)
    expected_registry_revision: str = Field(min_length=1)
    expected_active_patch_set_revision: str | None = None
    world_config_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    state_group_contexts: tuple[StateAssemblyContext, ...] = ()
    resource_bounds_migration_contexts: tuple["ResourceBoundsMigrationContext", ...] = ()


class ResourceBoundsMigrationContext(StrictGameplayModel):
    """Pinned authoritative projection identity for one resource migration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    expected_projection_revision: str = Field(min_length=1)


class PatchCandidateInstallCommand(StrictGameplayModel):
    """Install one validated immutable candidate without activating it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    manifest: GameplayPatchManifest


class PatchActiveSetCommand(StrictGameplayModel):
    """Atomically change a complete active patch-set selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    operation: Literal["enable", "disable", "upgrade", "rollback"]
    patch_revision_ids: tuple[str, ...] = ()
    state_group_actor_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_selection(self) -> "PatchActiveSetCommand":
        if len(set(self.patch_revision_ids)) != len(self.patch_revision_ids):
            raise ValueError("patch_revision_ids must be unique")
        if len(set(self.state_group_actor_refs)) != len(self.state_group_actor_refs):
            raise ValueError("state_group_actor_refs must be unique")
        if self.operation in {"enable", "upgrade", "rollback"} and not self.patch_revision_ids:
            raise ValueError(f"{self.operation} requires a non-empty complete active set")
        return self


@dataclass(frozen=True)
class GameplayPatchLifecycleAuthorityResult:
    accepted: bool
    changed: bool
    active_patch_set: PatchSetRevision | None
    append_result: AppendBatchResult


@dataclass(frozen=True)
class GameplayPatchLifecycleProjection:
    installed_patch_revision_ids: tuple[str, ...]
    active_patch_set: PatchSetRevision | None
    applied_event_ids: tuple[str, ...]


class GameplayPatchLifecycleAuthorityService:
    """Append control-plane events, then cut over only validated registry state."""

    _PRINCIPAL = "gameplay_patch_lifecycle_authority"
    _STREAM_ID = "gameplay:patch_lifecycle"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        registry: GameplayPatchRegistry,
        state_group_registry: StateGroupRegistry | None = None,
        resource_definition_registry: ResourceDefinitionRegistry | None = None,
    ) -> None:
        self._store = store
        self._registry = registry
        self._state_group_registry = state_group_registry
        self._resource_definition_registry = resource_definition_registry

    def install_candidate(
        self,
        command: PatchCandidateInstallCommand,
        context: PatchLifecycleAuthorityContext,
    ) -> GameplayPatchLifecycleAuthorityResult:
        self._validate_context(command.authority_principal, context)
        self._validate_install_digest(command)
        try:
            self._registry.validate_install_many((command.manifest,))
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc

        append_result = self._append(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            payload_digest=command.payload_digest,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            context=context,
            events=(
                (
                    "gameplay.patch.candidate_installed",
                    {
                        "patch_revision_id": command.manifest.patch_revision_id,
                        "patch_id": command.manifest.patch_id,
                        "patch_version": command.manifest.patch_version,
                        "content_digest": command.manifest.content_digest,
                        "author_id": command.manifest.author_id,
                        "registry_revision_before": context.expected_registry_revision,
                    },
                ),
            ),
        )
        if append_result.idempotency_status == "duplicate_replayed":
            self._require_existing_candidate(command.manifest)
            return GameplayPatchLifecycleAuthorityResult(True, False, self._registry.active_patch_set, append_result)

        try:
            self._registry.install(command.manifest)
        except GameplayPatchRuntimeError as exc:
            # Validation above makes this unreachable in the in-memory single-writer
            # closure. Treat it as recovery-required rather than claiming success.
            raise GameplayPatchLifecycleAuthorityError("patch_registry_cutover_failed") from exc
        return GameplayPatchLifecycleAuthorityResult(True, True, self._registry.active_patch_set, append_result)

    def apply_active_set(
        self,
        command: PatchActiveSetCommand,
        context: PatchLifecycleAuthorityContext,
    ) -> GameplayPatchLifecycleAuthorityResult:
        if command.authority_principal != context.authority_principal:
            raise GameplayPatchLifecycleAuthorityError("authority_principal_mismatch")
        self._validate_active_set_digest(command)
        existing = self._store.get_idempotency_record(self._PRINCIPAL, command.idempotency_key)
        if existing is not None:
            if existing.payload_digest != command.payload_digest:
                raise GameplayPatchLifecycleAuthorityError("idempotency_key_reused")
            append_result = self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key)
            if append_result is None:
                raise GameplayPatchLifecycleAuthorityError("patch_idempotency_recovery_required")
            return GameplayPatchLifecycleAuthorityResult(
                True,
                False,
                self._registry.active_patch_set,
                append_result.model_copy(update={"idempotency_status": "duplicate_replayed"}),
            )
        self._validate_context(command.authority_principal, context)
        current = self._registry.active_patch_set
        current_ids = set(current.patch_revision_ids if current is not None else ())
        target_ids = set(command.patch_revision_ids)

        if command.operation == "enable":
            if not current_ids.issubset(target_ids):
                raise GameplayPatchLifecycleAuthorityError("patch_enable_cannot_remove")
            changed_ids = tuple(sorted(target_ids.difference(current_ids)))
            if not changed_ids:
                raise GameplayPatchLifecycleAuthorityError("patch_enable_no_change")
        elif command.operation == "disable":
            if current is None:
                raise GameplayPatchLifecycleAuthorityError("patch_disable_not_active")
            if not target_ids.issubset(current_ids):
                raise GameplayPatchLifecycleAuthorityError("patch_disable_cannot_enable")
            changed_ids = tuple(sorted(current_ids.difference(target_ids)))
            if not changed_ids:
                raise GameplayPatchLifecycleAuthorityError("patch_disable_no_change")
        else:
            if current is None:
                raise GameplayPatchLifecycleAuthorityError(f"patch_{command.operation}_not_active")
            removed_ids = tuple(sorted(current_ids.difference(target_ids)))
            added_ids = tuple(sorted(target_ids.difference(current_ids)))
            if len(removed_ids) != 1 or len(added_ids) != 1 or len(current_ids) != len(target_ids):
                raise GameplayPatchLifecycleAuthorityError(f"patch_{command.operation}_replacement_invalid")
            self._validate_version_replacement(command.operation, removed_ids[0], added_ids[0])
            changed_ids = added_ids

        try:
            target = self._registry.compose_active_set(tuple(sorted(target_ids))) if target_ids else None
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc

        event_specs: list[tuple[str, dict[str, object]]] = []
        if command.operation in {"upgrade", "rollback"}:
            old_revision_id = next(iter(current_ids.difference(target_ids)))
            state_group_events, state_group_expected_revisions = self._plan_state_group_rebind(
                command=command,
                context=context,
                current=current,
                target=target,
                new_patch_revision_id=changed_ids[0],
            )
        else:
            state_group_events, state_group_expected_revisions = self._plan_state_group_materialization(
                command=command,
                context=context,
                current=current,
                target=target,
                changed_patch_revision_ids=changed_ids,
            )
        if command.operation == "enable":
            event_specs.append(("gameplay.patch.active_set_activated", self._active_set_payload(current, target, context)))
            event_specs.extend(("gameplay.patch.enabled", {"patch_revision_id": revision_id}) for revision_id in changed_ids)
        elif command.operation == "disable":
            event_specs.extend(("gameplay.patch.disabled", {"patch_revision_id": revision_id}) for revision_id in changed_ids)
            event_specs.append(("gameplay.patch.active_set_activated", self._active_set_payload(current, target, context)))
        else:
            old_revision_id = next(iter(current_ids.difference(target_ids)))
            event_specs.append(
                (
                    f"gameplay.patch.{command.operation}_activated",
                    {"previous_patch_revision_id": old_revision_id, "next_patch_revision_id": changed_ids[0]},
                )
            )
            event_specs.append(("gameplay.patch.active_set_activated", self._active_set_payload(current, target, context)))

        append_result = self._append(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            payload_digest=command.payload_digest,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            context=context,
            events=tuple(event_specs),
            extra_events=state_group_events,
            extra_expected_stream_revisions=state_group_expected_revisions,
            projection_refresh_hints=self._resource_migration_refresh_hints(state_group_events),
        )
        if append_result.idempotency_status == "duplicate_replayed":
            if self._registry.active_patch_set != target:
                raise GameplayPatchLifecycleAuthorityError("patch_registry_recovery_required")
            return GameplayPatchLifecycleAuthorityResult(True, False, target, append_result)

        try:
            applied = self._registry.replace_active_set(tuple(sorted(target_ids)))
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchLifecycleAuthorityError("patch_registry_cutover_failed") from exc
        if applied != target:
            raise GameplayPatchLifecycleAuthorityError("patch_registry_cutover_failed")
        return GameplayPatchLifecycleAuthorityResult(True, True, applied, append_result)

    def _append(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        payload_digest: str,
        causation_id: str,
        correlation_id: str,
        context: PatchLifecycleAuthorityContext,
        events: tuple[tuple[str, dict[str, object]], ...],
        extra_events: list[dict[str, object]] | None = None,
        extra_expected_stream_revisions: dict[str, int] | None = None,
        projection_refresh_hints: list[dict[str, object]] | None = None,
    ) -> AppendBatchResult:
        transaction_id = f"tx:{command_id}"
        serialized_events = []
        for index, (event_type, payload) in enumerate(events, start=1):
            serialized_events.append(
                {
                    "event_id": f"evt:{command_id}:patch:{index}",
                    "event_type": event_type,
                    "schema_version": 1,
                    "stream_id": self._STREAM_ID,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": transaction_id,
                    "command_id": command_id,
                    "causation_id": causation_id,
                    "correlation_id": correlation_id,
                    "visibility_policy": "authority_only",
                    "payload": {
                        **payload,
                        "registry_revision": context.expected_registry_revision,
                        "active_patch_set_revision": context.expected_active_patch_set_revision,
                        "world_config_revision": context.world_config_revision,
                        "policy_revision": context.policy_revision,
                    },
                }
            )
        all_events = [*(extra_events or []), *serialized_events]
        expected_stream_revisions = {
            self._STREAM_ID: self._store.get_stream_head(self._STREAM_ID),
            **(extra_expected_stream_revisions or {}),
        }
        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": expected_stream_revisions,
                "pinned_revisions": {},
                "events": all_events,
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": idempotency_key,
                    "payload_digest": payload_digest,
                },
                "outbox_entries": [],
                "result_digest": self._digest(
                    {
                        "command_id": command_id,
                        "events": [{"event_type": event_type, "payload": payload} for event_type, payload in events],
                        "state_group_events": [
                            {"event_type": event["event_type"], "payload": event["payload"]}
                            for event in extra_events or []
                        ],
                        "context": context.model_dump(mode="json"),
                    }
                ),
                "projection_refresh_hints": projection_refresh_hints or [],
            }
        )
        if not append_result.committed:
            raise GameplayPatchLifecycleAuthorityError(
                append_result.failure.error_code if append_result.failure is not None else "append_batch_failed"
            )
        return append_result

    @staticmethod
    def _resource_migration_refresh_hints(
        events: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        actor_refs = tuple(
            dict.fromkeys(
                str(payload.get("actor_ref", ""))
                for event in events
                if str(event.get("event_type", "")) == "gameplay.resource.bounds_migrated"
                for payload in [event.get("payload", {})]
                if isinstance(payload, dict) and str(payload.get("actor_ref", ""))
            )
        )
        return [
            {
                "projection_id": "godot_mirror",
                "stream_id": f"gameplay:resources:{actor_ref}",
                "reason": "patch_resource_migration_committed",
                "actor_refs": [actor_ref],
            }
            for actor_ref in actor_refs
        ]

    def _plan_state_group_materialization(
        self,
        *,
        command: PatchActiveSetCommand,
        context: PatchLifecycleAuthorityContext,
        current: PatchSetRevision | None,
        target: PatchSetRevision | None,
        changed_patch_revision_ids: tuple[str, ...],
    ) -> tuple[list[dict[str, object]], dict[str, int]]:
        """Plan bounded state-group enable/disable work before one Patch batch.

        The actor list and contexts are explicit trusted backend inputs. This
        intentionally does not infer population, policy, migration, or
        grant/modifier compensation.
        """

        state_group_ids: set[str] = set()
        for patch_revision_id in changed_patch_revision_ids:
            try:
                state_group_ids.update(self._registry.candidate(patch_revision_id).state_group_ids)
            except GameplayPatchRuntimeError as exc:
                raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc
        if not state_group_ids:
            if command.state_group_actor_refs or context.state_group_contexts:
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_context_unexpected")
            return [], {}
        if command.operation not in {"enable", "disable"}:
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_effects_not_supported")
        if command.operation == "enable" and target is None:
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_effects_not_supported")
        if command.operation == "disable" and current is None:
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_effects_not_supported")
        if self._state_group_registry is None:
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_registry_unavailable")
        if not command.state_group_actor_refs:
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_actor_context_required")
        contexts_by_actor = {item.actor_ref: item for item in context.state_group_contexts}
        if len(contexts_by_actor) != len(context.state_group_contexts):
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_actor_context_duplicate")
        if set(command.state_group_actor_refs) != set(contexts_by_actor):
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_actor_context_mismatch")

        if command.operation == "disable":
            assert current is not None
            remaining_group_ids = {
                group_id
                for patch_revision_id in (target.patch_revision_ids if target is not None else ())
                for group_id in self._registry.candidate(patch_revision_id).state_group_ids
            }
            if state_group_ids.intersection(remaining_group_ids):
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_shared_ownership_unsupported")

        planner = StateGroupLifecycleAuthorityService(store=self._store, registry=self._state_group_registry)
        transaction_id = f"tx:{command.command_id}"
        definition_versions_by_group: dict[str, str] = {}
        for group_id in state_group_ids:
            versions = {
                state_context.state_group_definition_versions.get(group_id)
                for state_context in contexts_by_actor.values()
            }
            specified_versions = {version for version in versions if version is not None}
            if len(specified_versions) > 1 or (specified_versions and None in versions):
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_definition_version_mismatch")
            if specified_versions:
                definition_versions_by_group[group_id] = next(iter(specified_versions))
        allowed_group_ids = set(
            self._state_group_registry.resolve_load_order(
                sorted(state_group_ids),
                definition_versions=definition_versions_by_group,
            )
        )
        events: list[dict[str, object]] = []
        expected_revisions: dict[str, int] = {}
        for actor_ref in command.state_group_actor_refs:
            state_context = contexts_by_actor[actor_ref]
            if state_context.authority_principal != command.authority_principal:
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_authority_principal_mismatch")
            expected_source_revision = (
                target.active_patch_set_revision if command.operation == "enable" else current.active_patch_set_revision
            )
            if state_context.active_patch_set_revision != expected_source_revision:
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_target_revision_mismatch")
            try:
                plan = planner.plan(
                    StateGroupLifecycleCommand(
                        command_id=command.command_id,
                        authority_principal=command.authority_principal,
                        idempotency_key=f"{command.idempotency_key}:{actor_ref}",
                        payload_digest=command.payload_digest,
                        causation_id=command.causation_id,
                        correlation_id=command.correlation_id,
                        operation="enable" if command.operation == "enable" else "disabled",
                        requested_group_ids=tuple(sorted(state_group_ids)),
                        policy_revision=0,
                    ),
                    state_context,
                )
            except StateGroupLifecycleAuthorityError as exc:
                raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc
            if not set(plan.target_group_ids).issubset(allowed_group_ids):
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_policy_expansion_unsupported")
            if command.operation == "disable":
                for group_id in state_group_ids:
                    record = plan.lifecycle.records.get(group_id)
                    if record is None or record.source_patch_revision != expected_source_revision:
                        raise GameplayPatchLifecycleAuthorityError("patch_state_group_source_revision_mismatch")
            expected_revisions[plan.stream_id] = plan.expected_stream_revision
            events.extend(
                planner.serialize_plan_events(
                    plan,
                    transaction_id=transaction_id,
                    command_id=command.command_id,
                    causation_id=command.causation_id,
                    correlation_id=command.correlation_id,
                    event_id_namespace=f"state-group:{actor_ref}",
                )
            )
        return events, expected_revisions

    def _plan_state_group_rebind(
        self,
        *,
        command: PatchActiveSetCommand,
        context: PatchLifecycleAuthorityContext,
        current: PatchSetRevision | None,
        target: PatchSetRevision | None,
        new_patch_revision_id: str,
    ) -> tuple[list[dict[str, object]], dict[str, int]]:
        """Plan a manifest-declared identity rebind for same-patch cutover only."""

        assert current is not None and target is not None
        new = self._registry.candidate(new_patch_revision_id)
        state_group_ids = tuple(sorted(new.state_group_ids))
        if not state_group_ids:
            if command.state_group_actor_refs or context.state_group_contexts:
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_context_unexpected")
            return [], {}
        if self._state_group_registry is None:
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_registry_unavailable")
        if not command.state_group_actor_refs:
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_actor_context_required")
        other_active_group_ids = {
            group_id
            for patch_revision_id in target.patch_revision_ids
            if patch_revision_id != new_patch_revision_id
            for group_id in self._registry.candidate(patch_revision_id).state_group_ids
        }
        if set(state_group_ids).intersection(other_active_group_ids):
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_shared_ownership_unsupported")
        if command.operation == "rollback":
            source_revision_ids = set(current.patch_revision_ids).difference(target.patch_revision_ids)
            if any(
                migration.migration_kind == "resource_bounds_clamp"
                for source_revision_id in source_revision_ids
                for migration in self._registry.candidate(source_revision_id).state_group_migrations
            ):
                raise GameplayPatchLifecycleAuthorityError("patch_data_migration_rollback_unsupported")
        migrations = {migration.group_id: migration for migration in new.state_group_migrations}
        if set(migrations) != set(state_group_ids):
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_migration_declaration_required")
        if any(migration.migration_kind != "identity_rebind" for migration in migrations.values()):
            return self._plan_resource_bounds_migration(
                command=command,
                context=context,
                current=current,
                target=target,
                migrations=migrations,
            )
        for group_id, migration in migrations.items():
            definition = self._state_group_registry.resolve(group_id)
            if (
                migration.migration_kind != "identity_rebind"
                or migration.from_definition_version != definition.definition_version
                or migration.to_definition_version != definition.definition_version
            ):
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_migration_incompatible")
        contexts_by_actor = {item.actor_ref: item for item in context.state_group_contexts}
        if len(contexts_by_actor) != len(context.state_group_contexts):
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_actor_context_duplicate")
        if set(command.state_group_actor_refs) != set(contexts_by_actor):
            raise GameplayPatchLifecycleAuthorityError("patch_state_group_actor_context_mismatch")

        planner = StateGroupLifecycleAuthorityService(store=self._store, registry=self._state_group_registry)
        transaction_id = f"tx:{command.command_id}"
        events: list[dict[str, object]] = []
        expected_revisions: dict[str, int] = {}
        for actor_ref in command.state_group_actor_refs:
            state_context = contexts_by_actor[actor_ref]
            if state_context.authority_principal != command.authority_principal:
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_authority_principal_mismatch")
            if state_context.active_patch_set_revision != current.active_patch_set_revision:
                raise GameplayPatchLifecycleAuthorityError("patch_state_group_source_revision_mismatch")
            try:
                plan = planner.plan_identity_rebind(
                    context=state_context,
                    group_ids=state_group_ids,
                    next_source_patch_revision=target.active_patch_set_revision,
                    migration_digests={group_id: migration.migration_digest for group_id, migration in migrations.items()},
                )
            except StateGroupLifecycleAuthorityError as exc:
                raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc
            expected_revisions[plan.stream_id] = plan.expected_stream_revision
            events.extend(
                planner.serialize_plan_events(
                    plan,
                    transaction_id=transaction_id,
                    command_id=command.command_id,
                    causation_id=command.causation_id,
                    correlation_id=command.correlation_id,
                    event_id_namespace=f"state-group-rebind:{actor_ref}",
                )
            )
        return events, expected_revisions

    def _plan_resource_bounds_migration(
        self,
        *,
        command: PatchActiveSetCommand,
        context: PatchLifecycleAuthorityContext,
        current: PatchSetRevision,
        target: PatchSetRevision,
        migrations: dict[str, StateGroupMigration],
    ) -> tuple[list[dict[str, object]], dict[str, int]]:
        """Plan the first data-transform slice: one resource maximum reduction.

        This coordinator owns the atomic batch only.  It rebuilds a pinned
        resource projection, delegates the typed fact to the resource planner,
        then asks the state-group layer only to transition its definition and
        source metadata after that fact.  Generic payload mutation is not an
        available path here.
        """

        if command.operation != "upgrade":
            raise GameplayPatchLifecycleAuthorityError("patch_data_migration_rollback_unsupported")
        if self._resource_definition_registry is None:
            raise GameplayPatchLifecycleAuthorityError("patch_resource_definition_registry_unavailable")
        if set(migrations) != {"core.resources"}:
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_group_unsupported")
        migration = migrations["core.resources"]
        if migration.migration_digest != migration.expected_migration_digest():
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_digest_mismatch")
        if (
            migration.input_event_schema is None
            or migration.output_event_schema is None
            or migration.input_event_schema.schema_digest != RESOURCE_MATERIALIZED_SCHEMA_DIGEST
            or migration.output_event_schema.schema_digest != RESOURCE_BOUNDS_MIGRATED_SCHEMA_DIGEST
        ):
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_schema_digest_mismatch")
        if (
            migration.migration_kind != "resource_bounds_clamp"
            or migration.migrator_id != RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID
            or migration.migrator_code_digest != RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST
            or migration.resource_id is None
            or migration.input_event_schema.event_type != "gameplay.resource.materialized"
            or migration.input_event_schema.schema_version != 1
            or migration.output_event_schema.event_type != "gameplay.resource.bounds_migrated"
            or migration.output_event_schema.schema_version != 1
            or migration.rollback_mode != "forward_fix_only"
        ):
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_contract_invalid")
        try:
            self._state_group_registry.resolve("core.resources", migration.from_definition_version)
            self._state_group_registry.resolve("core.resources", migration.to_definition_version)
        except Exception as exc:
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_definition_invalid") from exc
        state_contexts = {item.actor_ref: item for item in context.state_group_contexts}
        resource_contexts = {item.actor_ref: item for item in context.resource_bounds_migration_contexts}
        if (
            len(state_contexts) != len(context.state_group_contexts)
            or len(resource_contexts) != len(context.resource_bounds_migration_contexts)
        ):
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_context_duplicate")
        if set(command.state_group_actor_refs) != set(state_contexts) or set(state_contexts) != set(resource_contexts):
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_context_mismatch")

        lifecycle_planner = StateGroupLifecycleAuthorityService(store=self._store, registry=self._state_group_registry)
        resource_planner = ResourceBoundsMigrationAuthorityService(definitions=self._resource_definition_registry)
        resource_projector = ResourceBodyRuntimeProjector(resource_definitions=self._resource_definition_registry)
        transaction_id = f"tx:{command.command_id}"
        events: list[dict[str, object]] = []
        expected_revisions: dict[str, int] = {}
        for actor_ref in command.state_group_actor_refs:
            state_context = state_contexts[actor_ref]
            resource_context = resource_contexts[actor_ref]
            if (
                state_context.authority_principal != command.authority_principal
                or state_context.active_patch_set_revision != current.active_patch_set_revision
                or resource_context.resource_id != migration.resource_id
            ):
                raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_source_mismatch")
            resource_stream_id = f"gameplay:resources:{actor_ref}"
            projection = resource_projector.rebuild_resources(actor_ref, self._store.read_stream(resource_stream_id))
            try:
                resource_plan = resource_planner.plan(
                    ResourceBoundsMigrationRequest(
                        actor_ref=actor_ref,
                        resource_id=migration.resource_id,
                        from_definition_version=migration.from_definition_version,
                        to_definition_version=migration.to_definition_version,
                        expected_projection_revision=resource_context.expected_projection_revision,
                        migration_digest=migration.migration_digest,
                        migrator_code_digest=migration.migrator_code_digest,
                    ),
                    projection,
                )
            except ResourceBodyRuntimeError as exc:
                raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc
            if self._store.get_stream_head(resource_stream_id) != resource_plan.expected_stream_revision:
                raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_revision_conflict")
            domain_event_id = f"evt:{command.command_id}:resource-migration:{actor_ref}:{migration.resource_id}"
            self._verify_resource_migration_shadow_replay(
                projector=resource_projector,
                actor_ref=actor_ref,
                resource_stream_id=resource_stream_id,
                plan=resource_plan,
                event_id=domain_event_id,
                transaction_id=transaction_id,
                command=command,
            )
            events.append(
                {
                    "event_id": domain_event_id,
                    "event_type": resource_plan.event_type,
                    "schema_version": 1,
                    "stream_id": resource_stream_id,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": transaction_id,
                    "command_id": command.command_id,
                    "causation_id": command.causation_id,
                    "correlation_id": command.correlation_id,
                    "visibility_policy": "authority_only",
                    "payload": dict(resource_plan.payload),
                }
            )
            try:
                lifecycle_plan = lifecycle_planner.plan_definition_migration(
                    context=state_context,
                    migrations=(
                        StateGroupDefinitionMigration(
                            group_id="core.resources",
                            from_definition_version=migration.from_definition_version,
                            to_definition_version=migration.to_definition_version,
                            migration_kind=migration.migration_kind,
                            migration_digest=migration.migration_digest,
                            migrator_code_digest=migration.migrator_code_digest,
                            domain_event_id=domain_event_id,
                        ),
                    ),
                    next_source_patch_revision=target.active_patch_set_revision,
                )
            except StateGroupLifecycleAuthorityError as exc:
                raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc
            expected_revisions[resource_stream_id] = resource_plan.expected_stream_revision
            expected_revisions[lifecycle_plan.stream_id] = lifecycle_plan.expected_stream_revision
            events.extend(
                lifecycle_planner.serialize_plan_events(
                    lifecycle_plan,
                    transaction_id=transaction_id,
                    command_id=command.command_id,
                    causation_id=command.causation_id,
                    correlation_id=command.correlation_id,
                    event_id_namespace=f"state-group-migration:{actor_ref}",
                )
            )
        return events, expected_revisions

    def _verify_resource_migration_shadow_replay(
        self,
        *,
        projector: ResourceBodyRuntimeProjector,
        actor_ref: str,
        resource_stream_id: str,
        plan: ResourceBoundsMigrationPlan,
        event_id: str,
        transaction_id: str,
        command: PatchActiveSetCommand,
    ) -> None:
        """Require deterministic full and checkpoint-plus-tail shadow replay.

        The synthetic event is never appended.  It is exactly the domain event
        that the coordinator would bind if every later validation succeeds.
        """

        existing = self._store.read_stream(resource_stream_id)
        shadow_event = GameplayEvent(
            event_id=event_id,
            event_type=plan.event_type,
            schema_version=1,
            stream_id=resource_stream_id,
            stream_revision=self._store.get_stream_head(resource_stream_id) + 1,
            global_sequence=max((event.global_sequence for event in self._store.read_events()), default=0) + 1,
            transaction_id=transaction_id,
            command_id=command.command_id,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            visibility_policy="authority_only",
            payload=dict(plan.payload),
        )
        try:
            full = projector.rebuild_resources(actor_ref, [*existing, shadow_event])
            checkpoint_index = max(1, len(existing) // 2)
            checkpoint = projector.rebuild_resources(actor_ref, existing[:checkpoint_index])
            checkpointed = projector.rebuild_resources(
                actor_ref,
                [*existing[checkpoint_index:], shadow_event],
                checkpoint=checkpoint,
            )
        except ResourceBodyRuntimeError as exc:
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_shadow_replay_failed") from exc
        if checkpointed != full:
            raise GameplayPatchLifecycleAuthorityError("patch_resource_migration_shadow_replay_mismatch")

    def _validate_context(self, command_principal: str, context: PatchLifecycleAuthorityContext) -> None:
        if command_principal != context.authority_principal:
            raise GameplayPatchLifecycleAuthorityError("authority_principal_mismatch")
        if context.expected_registry_revision != self._registry.registry_revision:
            raise GameplayPatchLifecycleAuthorityError("patch_registry_revision_conflict")
        current = self._registry.active_patch_set
        actual = current.active_patch_set_revision if current is not None else None
        if context.expected_active_patch_set_revision != actual:
            raise GameplayPatchLifecycleAuthorityError("patch_active_set_revision_conflict")

    def _validate_version_replacement(
        self,
        operation: Literal["upgrade", "rollback"],
        old_revision_id: str,
        new_revision_id: str,
    ) -> None:
        try:
            old = self._registry.candidate(old_revision_id)
            new = self._registry.candidate(new_revision_id)
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchLifecycleAuthorityError(str(exc)) from exc
        if old.patch_id != new.patch_id:
            raise GameplayPatchLifecycleAuthorityError(f"patch_{operation}_replacement_invalid")
        if set(old.state_group_ids) != set(new.state_group_ids):
            raise GameplayPatchLifecycleAuthorityError(f"patch_{operation}_state_group_set_mismatch")
        comparison = _compare_versions(new.patch_version, old.patch_version)
        if (operation == "upgrade" and comparison <= 0) or (operation == "rollback" and comparison >= 0):
            raise GameplayPatchLifecycleAuthorityError(f"patch_{operation}_direction_invalid")

    @staticmethod
    def _active_set_payload(
        current: PatchSetRevision | None,
        target: PatchSetRevision | None,
        context: PatchLifecycleAuthorityContext,
    ) -> dict[str, object]:
        return {
            "previous_active_patch_set_revision": current.active_patch_set_revision if current is not None else None,
            "next_active_patch_set_revision": target.active_patch_set_revision if target is not None else None,
            "next_patch_revision_ids": list(target.patch_revision_ids) if target is not None else [],
            "registry_revision_after": target.registry_revision if target is not None else context.expected_registry_revision,
            "capability_bindings": (
                [
                    {
                        "binding_ref": binding.binding_ref,
                        "package_revision": binding.package_revision,
                        "content_digest": binding.content_digest,
                        "declaration_digest": binding.declaration_digest,
                        "descriptor_ref": binding.descriptor_ref,
                        "descriptor_revision": binding.descriptor_revision,
                        "active_patch_set_revision": binding.active_patch_set_revision,
                    }
                    for binding in target.capability_bindings
                ]
                if target is not None
                else []
            ),
        }

    def _require_existing_candidate(self, manifest: GameplayPatchManifest) -> None:
        try:
            existing = self._registry.candidate(manifest.patch_revision_id)
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchLifecycleAuthorityError("patch_registry_recovery_required") from exc
        if existing.content_digest != manifest.content_digest:
            raise GameplayPatchLifecycleAuthorityError("patch_registry_recovery_required")

    @classmethod
    def _validate_install_digest(cls, command: PatchCandidateInstallCommand) -> None:
        payload = {
            "command_id": command.command_id,
            "authority_principal": command.authority_principal,
            "idempotency_key": command.idempotency_key,
            "causation_id": command.causation_id,
            "correlation_id": command.correlation_id,
            "manifest": command.manifest.model_dump(mode="json"),
        }
        if command.payload_digest != cls._digest(payload):
            raise GameplayPatchLifecycleAuthorityError("patch_command_digest_mismatch")

    @classmethod
    def _validate_active_set_digest(cls, command: PatchActiveSetCommand) -> None:
        payload = {
            "command_id": command.command_id,
            "authority_principal": command.authority_principal,
            "idempotency_key": command.idempotency_key,
            "causation_id": command.causation_id,
            "correlation_id": command.correlation_id,
            "operation": command.operation,
            "patch_revision_ids": list(command.patch_revision_ids),
            "state_group_actor_refs": list(command.state_group_actor_refs),
        }
        if command.payload_digest != cls._digest(payload):
            raise GameplayPatchLifecycleAuthorityError("patch_command_digest_mismatch")

    @staticmethod
    def _digest(payload: object) -> str:
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{sha256(encoded).hexdigest()}"


class GameplayPatchLifecycleProjector:
    """Rebuild control-plane lifecycle state from committed ledger events only."""

    _EVENT_TYPES = {
        "gameplay.patch.candidate_installed",
        "gameplay.patch.active_set_activated",
        "gameplay.patch.enabled",
        "gameplay.patch.disabled",
        "gameplay.patch.upgrade_activated",
        "gameplay.patch.rollback_activated",
    }

    def __init__(self, *, registry: GameplayPatchRegistry) -> None:
        self._registry = registry

    def rebuild(self, events: list[GameplayEvent | dict[str, Any]]) -> GameplayPatchLifecycleProjection:
        installed: set[str] = set()
        active: PatchSetRevision | None = None
        applied: list[str] = []
        ordered = sorted((self._event(event) for event in events), key=lambda event: (event.global_sequence, event.event_id))
        for event in ordered:
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            if event.event_type == "gameplay.patch.candidate_installed":
                revision_id = self._required_text(payload, "patch_revision_id")
                digest = self._required_text(payload, "content_digest")
                try:
                    candidate = self._registry.candidate(revision_id)
                except GameplayPatchRuntimeError as exc:
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_candidate_missing") from exc
                if candidate.content_digest != digest:
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_candidate_digest_mismatch")
                installed.add(revision_id)
            elif event.event_type == "gameplay.patch.active_set_activated":
                revision_ids = payload.get("next_patch_revision_ids")
                if not isinstance(revision_ids, list) or not all(isinstance(value, str) for value in revision_ids):
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_active_set_invalid")
                if not set(revision_ids).issubset(installed):
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_candidate_not_installed")
                if revision_ids:
                    try:
                        composed = self._registry.compose_active_set(tuple(revision_ids))
                    except GameplayPatchRuntimeError as exc:
                        raise GameplayPatchLifecycleReplayError("patch_lifecycle_active_set_invalid") from exc
                    expected = payload.get("next_active_patch_set_revision")
                    if expected != composed.active_patch_set_revision:
                        raise GameplayPatchLifecycleReplayError("patch_lifecycle_active_set_mismatch")
                    expected_bindings = [
                        {
                            "binding_ref": binding.binding_ref,
                            "package_revision": binding.package_revision,
                            "content_digest": binding.content_digest,
                            "declaration_digest": binding.declaration_digest,
                            "descriptor_ref": binding.descriptor_ref,
                            "descriptor_revision": binding.descriptor_revision,
                            "active_patch_set_revision": binding.active_patch_set_revision,
                        }
                        for binding in composed.capability_bindings
                    ]
                    persisted_bindings = payload.get("capability_bindings")
                    if persisted_bindings is None and not expected_bindings:
                        persisted_bindings = []
                    if persisted_bindings != expected_bindings:
                        raise GameplayPatchLifecycleReplayError("patch_lifecycle_capability_binding_mismatch")
                    active = composed
                else:
                    if payload.get("next_active_patch_set_revision") is not None:
                        raise GameplayPatchLifecycleReplayError("patch_lifecycle_active_set_mismatch")
                    active = None
            elif event.event_type == "gameplay.patch.enabled":
                if active is None or self._required_text(payload, "patch_revision_id") not in active.patch_revision_ids:
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_enable_history_invalid")
            elif event.event_type == "gameplay.patch.disabled":
                if active is None or self._required_text(payload, "patch_revision_id") not in active.patch_revision_ids:
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_disable_history_invalid")
            else:
                if active is None or self._required_text(payload, "previous_patch_revision_id") not in active.patch_revision_ids:
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_revision_history_invalid")
                if self._required_text(payload, "next_patch_revision_id") not in installed:
                    raise GameplayPatchLifecycleReplayError("patch_lifecycle_candidate_not_installed")
            applied.append(event.event_id)
        return GameplayPatchLifecycleProjection(tuple(sorted(installed)), active, tuple(applied))

    @staticmethod
    def _event(value: GameplayEvent | dict[str, Any]) -> GameplayEvent:
        try:
            return value if isinstance(value, GameplayEvent) else GameplayEvent.model_validate(value)
        except ValueError as exc:
            raise GameplayPatchLifecycleReplayError("patch_lifecycle_event_invalid") from exc

    @staticmethod
    def _required_text(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise GameplayPatchLifecycleReplayError("patch_lifecycle_event_payload_invalid")
        return value


def _compare_versions(left: str, right: str) -> int:
    try:
        left_parts = tuple(int(part) for part in left.split("."))
        right_parts = tuple(int(part) for part in right.split("."))
    except ValueError as exc:
        raise GameplayPatchLifecycleAuthorityError("patch_version_invalid") from exc
    if not left_parts or not right_parts or len(left_parts) > 3 or len(right_parts) > 3:
        raise GameplayPatchLifecycleAuthorityError("patch_version_invalid")
    left_normalized = (*left_parts, *(0 for _ in range(3 - len(left_parts))))
    right_normalized = (*right_parts, *(0 for _ in range(3 - len(right_parts))))
    return (left_normalized > right_normalized) - (left_normalized < right_normalized)


__all__ = [
    "GameplayPatchLifecycleAuthorityError",
    "GameplayPatchLifecycleAuthorityResult",
    "GameplayPatchLifecycleAuthorityService",
    "GameplayPatchLifecycleProjection",
    "GameplayPatchLifecycleProjector",
    "GameplayPatchLifecycleReplayError",
    "PatchActiveSetCommand",
    "PatchCandidateInstallCommand",
    "PatchLifecycleAuthorityContext",
]
