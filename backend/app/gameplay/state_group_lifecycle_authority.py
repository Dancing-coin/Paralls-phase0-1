"""Authority-only state-group lifecycle commands over the Gameplay event store."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Literal, Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, StrictGameplayModel
from app.gameplay.runtime_state import (
    StateGroupLifecycleProjection,
    StateGroupLifecycleProjector,
    StateGroupRegistry,
)


LifecycleOperation = Literal["enable", "dormant", "disabled"]


class StateGroupLifecycleAuthorityError(ValueError):
    """Raised before a state-group lifecycle command can enter authority storage."""


class StateAssemblyContext(StrictGameplayModel):
    """Explicit authority inputs; no policy is inferred from an actor or Godot node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    registry_revision: str = Field(min_length=1)
    world_config_revision: str = Field(min_length=1)
    active_patch_set_revision: str = Field(min_length=1)
    eligible_group_ids: tuple[str, ...] = ()
    required_group_ids: tuple[str, ...] = ()
    forbidden_group_ids: tuple[str, ...] = ()
    initialization_refs: Mapping[str, str] = Field(default_factory=dict)
    state_group_definition_versions: Mapping[str, str] = Field(default_factory=dict)


class StateAssemblyInputs(StrictGameplayModel):
    """Versioned backend facts used to compile policy, never Godot/cognition input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    actor_archetype_ref: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    registry_revision: str = Field(min_length=1)
    world_config_revision: str = Field(min_length=1)
    active_patch_set_revision: str = Field(min_length=1)


class StateGroupEligibilityRule(StrictGameplayModel):
    """One declarative rule for a group; empty constraint lists mean unrestricted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(min_length=1)
    actor_archetype_refs: tuple[str, ...] = ()
    world_config_revisions: tuple[str, ...] = ()
    active_patch_set_revisions: tuple[str, ...] = ()
    required: bool = False
    initialization_ref: str = Field(min_length=1)


class StateGroupEligibilityCatalog(StrictGameplayModel):
    """Versioned policy catalog owned by backend configuration/package activation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_revision: str = Field(min_length=1)
    rules: list[StateGroupEligibilityRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_group_rules(self) -> StateGroupEligibilityCatalog:
        group_ids = [rule.group_id for rule in self.rules]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("state-group eligibility catalog contains duplicate group rules")
        return self


class StateGroupLifecycleCommand(StrictGameplayModel):
    """Trusted backend command. It is deliberately not a public client contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    operation: LifecycleOperation
    requested_group_ids: tuple[str, ...] = Field(min_length=1)
    policy_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def reject_duplicate_requested_groups(self) -> StateGroupLifecycleCommand:
        if len(set(self.requested_group_ids)) != len(self.requested_group_ids):
            raise ValueError("requested_group_ids must be unique")
        return self


class StateGroupDefinitionMigration(StrictGameplayModel):
    """A domain migration's lifecycle transition, not a domain write contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(min_length=1)
    from_definition_version: str = Field(min_length=1)
    to_definition_version: str = Field(min_length=1)
    migration_kind: str = Field(min_length=1)
    migration_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    migrator_code_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    domain_event_id: str = Field(min_length=1)


@dataclass(frozen=True)
class StateGroupLifecycleAuthorityResult:
    accepted: bool
    changed: bool
    lifecycle: StateGroupLifecycleProjection
    append_result: AppendBatchResult | None = None


@dataclass(frozen=True)
class StateGroupLifecycleBatchPlan:
    """Validated, non-mutating state-group lifecycle work for one actor stream.

    The event specifications deliberately have no transaction or command identity.
    A caller may therefore bind them into the regular state-group command batch or
    into a larger authority-owned transaction, without allowing the planner to
    write authority state itself.
    """

    lifecycle: StateGroupLifecycleProjection
    target_group_ids: tuple[str, ...]
    stream_id: str
    expected_stream_revision: int
    event_specs: tuple[tuple[str, dict[str, object]], ...]
    result_digest: str


class StateGroupLifecycleAuthorityService:
    """Creates lifecycle events; facade mutation and client transport are excluded."""

    _PRINCIPAL = "state_group_lifecycle_authority"

    def __init__(self, *, store: GameplayEventStore, registry: StateGroupRegistry) -> None:
        self._store = store
        self._registry = registry
        self._projector = StateGroupLifecycleProjector(registry)
        self._receipts: dict[tuple[str, str], tuple[str, StateGroupLifecycleAuthorityResult]] = {}

    def apply(
        self,
        command: StateGroupLifecycleCommand,
        context: StateAssemblyContext,
    ) -> StateGroupLifecycleAuthorityResult:
        self._validate_authority(command, context)
        receipt_key = (context.actor_ref, command.idempotency_key)
        existing = self._receipts.get(receipt_key)
        if existing is not None:
            existing_digest, existing_result = existing
            if existing_digest != command.payload_digest:
                raise StateGroupLifecycleAuthorityError("idempotency_key_reused")
            return StateGroupLifecycleAuthorityResult(
                accepted=True,
                changed=False,
                lifecycle=existing_result.lifecycle,
                append_result=existing_result.append_result,
            )

        plan = self.plan(command, context)
        if not plan.event_specs:
            result = StateGroupLifecycleAuthorityResult(accepted=True, changed=False, lifecycle=plan.lifecycle)
            self._receipts[receipt_key] = (command.payload_digest, result)
            return result

        transaction_id = f"tx:{command.command_id}"
        events = self.serialize_plan_events(
            plan,
            transaction_id=transaction_id,
            command_id=command.command_id,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            event_id_namespace="state-group",
        )
        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command.command_id,
                "expected_stream_revisions": {plan.stream_id: plan.expected_stream_revision},
                "pinned_revisions": {"policy": command.policy_revision},
                "events": events,
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": f"{context.actor_ref}:{command.idempotency_key}",
                    "payload_digest": command.payload_digest,
                },
                "outbox_entries": [],
                "result_digest": plan.result_digest,
                "projection_refresh_hints": [],
            }
        )
        if not append_result.committed:
            raise StateGroupLifecycleAuthorityError(
                append_result.failure.error_code if append_result.failure is not None else "append_batch_failed"
            )
        rebuilt = self._projector.rebuild(context.actor_ref, self._store.read_stream(plan.stream_id))
        result = StateGroupLifecycleAuthorityResult(
            accepted=True,
            changed=True,
            lifecycle=rebuilt,
            append_result=append_result,
        )
        self._receipts[receipt_key] = (command.payload_digest, result)
        return result

    def plan(
        self,
        command: StateGroupLifecycleCommand,
        context: StateAssemblyContext,
    ) -> StateGroupLifecycleBatchPlan:
        """Validate and describe lifecycle events without writing authority state."""

        self._validate_authority(command, context)
        stream_id = self._stream_id(context.actor_ref)
        expected_stream_revision = self._store.get_stream_head(stream_id)
        lifecycle = self._projector.rebuild(context.actor_ref, self._store.read_stream(stream_id))
        target_groups = self._target_groups(command, context)
        event_specs = self._event_specs(command, context, lifecycle, target_groups)
        serialized_specs: list[tuple[str, dict[str, object]]] = []
        for event_type, group_id in event_specs:
            definition = self._definition_for_context(context, group_id)
            payload: dict[str, object] = {
                "actor_ref": context.actor_ref,
                "group_id": group_id,
                "definition_version": definition.definition_version,
                "source_patch_revision": context.active_patch_set_revision,
            }
            if event_type == "gameplay.state_group.materialized":
                payload["initialization_ref"] = self._initialization_ref(context, group_id)
            serialized_specs.append((event_type, payload))
        return StateGroupLifecycleBatchPlan(
            lifecycle=lifecycle,
            target_group_ids=target_groups,
            stream_id=stream_id,
            expected_stream_revision=expected_stream_revision,
            event_specs=tuple(serialized_specs),
            result_digest=self._digest(
                {
                    "actor_ref": context.actor_ref,
                    "operation": command.operation,
                    "groups": target_groups,
                    "registry_revision": context.registry_revision,
                    "world_config_revision": context.world_config_revision,
                    "active_patch_set_revision": context.active_patch_set_revision,
                }
            ),
        )

    def plan_identity_rebind(
        self,
        *,
        context: StateAssemblyContext,
        group_ids: tuple[str, ...],
        next_source_patch_revision: str,
        migration_digests: Mapping[str, str],
    ) -> StateGroupLifecycleBatchPlan:
        """Plan source-revision rebinding for already materialized compatible groups."""

        if not next_source_patch_revision or next_source_patch_revision == context.active_patch_set_revision:
            raise StateGroupLifecycleAuthorityError("state_group_rebind_target_invalid")
        if not group_ids or len(set(group_ids)) != len(group_ids):
            raise StateGroupLifecycleAuthorityError("state_group_rebind_groups_invalid")
        stream_id = self._stream_id(context.actor_ref)
        expected_stream_revision = self._store.get_stream_head(stream_id)
        lifecycle = self._projector.rebuild(context.actor_ref, self._store.read_stream(stream_id))
        target_groups = tuple(sorted(group_ids))
        eligible = set(context.eligible_group_ids)
        forbidden = set(context.forbidden_group_ids)
        serialized_specs: list[tuple[str, dict[str, object]]] = []
        for group_id in target_groups:
            if group_id in forbidden or group_id not in eligible:
                raise StateGroupLifecycleAuthorityError("group_not_eligible")
            definition = self._registry.resolve(group_id)
            record = lifecycle.records.get(group_id)
            migration_digest = migration_digests.get(group_id, "")
            if (
                record is None
                or record.lifecycle_state == "disabled"
                or record.definition_version != definition.definition_version
                or record.source_patch_revision != context.active_patch_set_revision
            ):
                raise StateGroupLifecycleAuthorityError("state_group_rebind_source_invalid")
            if not _is_sha256_digest(migration_digest):
                raise StateGroupLifecycleAuthorityError("state_group_rebind_migration_invalid")
            serialized_specs.append(
                (
                    "gameplay.state_group.rebound",
                    {
                        "actor_ref": context.actor_ref,
                        "group_id": group_id,
                        "definition_version": definition.definition_version,
                        "previous_source_patch_revision": context.active_patch_set_revision,
                        "next_source_patch_revision": next_source_patch_revision,
                        "migration_kind": "identity_rebind",
                        "migration_digest": migration_digest,
                    },
                )
            )
        return StateGroupLifecycleBatchPlan(
            lifecycle=lifecycle,
            target_group_ids=target_groups,
            stream_id=stream_id,
            expected_stream_revision=expected_stream_revision,
            event_specs=tuple(serialized_specs),
            result_digest=self._digest(
                {
                    "actor_ref": context.actor_ref,
                    "group_ids": target_groups,
                    "previous_source_patch_revision": context.active_patch_set_revision,
                    "next_source_patch_revision": next_source_patch_revision,
                    "migration_digests": dict(sorted(migration_digests.items())),
                }
            ),
        )

    def plan_definition_migration(
        self,
        *,
        context: StateAssemblyContext,
        migrations: tuple[StateGroupDefinitionMigration, ...],
        next_source_patch_revision: str,
    ) -> StateGroupLifecycleBatchPlan:
        """Plan metadata transitions for already-planned domain migration facts.

        A caller must bind the referenced domain events in the same batch.  The
        lifecycle service cannot create or inspect domain projection payloads.
        """

        if not next_source_patch_revision or next_source_patch_revision == context.active_patch_set_revision:
            raise StateGroupLifecycleAuthorityError("state_group_migration_target_invalid")
        if not migrations or len({item.group_id for item in migrations}) != len(migrations):
            raise StateGroupLifecycleAuthorityError("state_group_migration_groups_invalid")
        stream_id = self._stream_id(context.actor_ref)
        expected_stream_revision = self._store.get_stream_head(stream_id)
        lifecycle = self._projector.rebuild(context.actor_ref, self._store.read_stream(stream_id))
        eligible = set(context.eligible_group_ids)
        forbidden = set(context.forbidden_group_ids)
        serialized_specs: list[tuple[str, dict[str, object]]] = []
        for migration in sorted(migrations, key=lambda item: item.group_id):
            if migration.group_id in forbidden or migration.group_id not in eligible:
                raise StateGroupLifecycleAuthorityError("group_not_eligible")
            record = lifecycle.records.get(migration.group_id)
            if (
                record is None
                or record.lifecycle_state == "disabled"
                or record.definition_version != migration.from_definition_version
                or record.source_patch_revision != context.active_patch_set_revision
            ):
                raise StateGroupLifecycleAuthorityError("state_group_migration_source_invalid")
            try:
                self._registry.resolve(migration.group_id, migration.to_definition_version)
            except Exception as exc:
                raise StateGroupLifecycleAuthorityError("state_group_migration_target_invalid") from exc
            serialized_specs.append(
                (
                    "gameplay.state_group.migrated",
                    {
                        "actor_ref": context.actor_ref,
                        "group_id": migration.group_id,
                        "from_definition_version": migration.from_definition_version,
                        "to_definition_version": migration.to_definition_version,
                        "previous_source_patch_revision": context.active_patch_set_revision,
                        "next_source_patch_revision": next_source_patch_revision,
                        "migration_kind": migration.migration_kind,
                        "migration_digest": migration.migration_digest,
                        "migrator_code_digest": migration.migrator_code_digest,
                        "domain_event_id": migration.domain_event_id,
                    },
                )
            )
        return StateGroupLifecycleBatchPlan(
            lifecycle=lifecycle,
            target_group_ids=tuple(item.group_id for item in sorted(migrations, key=lambda item: item.group_id)),
            stream_id=stream_id,
            expected_stream_revision=expected_stream_revision,
            event_specs=tuple(serialized_specs),
            result_digest=self._digest(
                {
                    "actor_ref": context.actor_ref,
                    "previous_source_patch_revision": context.active_patch_set_revision,
                    "next_source_patch_revision": next_source_patch_revision,
                    "migrations": [item.model_dump(mode="json") for item in sorted(migrations, key=lambda item: item.group_id)],
                }
            ),
        )

    @staticmethod
    def serialize_plan_events(
        plan: StateGroupLifecycleBatchPlan,
        *,
        transaction_id: str,
        command_id: str,
        causation_id: str,
        correlation_id: str,
        event_id_namespace: str,
    ) -> list[dict[str, object]]:
        """Bind a non-mutating plan to one caller-owned atomic event batch."""

        return [
            {
                "event_id": f"evt:{command_id}:{event_id_namespace}:{index}",
                "event_type": event_type,
                "schema_version": 1,
                "stream_id": plan.stream_id,
                "stream_revision": 0,
                "global_sequence": 0,
                "transaction_id": transaction_id,
                "command_id": command_id,
                "causation_id": causation_id,
                "correlation_id": correlation_id,
                "visibility_policy": "authority_only",
                "payload": payload,
            }
            for index, (event_type, payload) in enumerate(plan.event_specs, start=1)
        ]

    def _target_groups(
        self,
        command: StateGroupLifecycleCommand,
        context: StateAssemblyContext,
    ) -> tuple[str, ...]:
        requested = tuple(command.requested_group_ids)
        if command.operation == "enable":
            requested = tuple(sorted(set(requested).union(context.required_group_ids)))
            target_groups = tuple(
                self._registry.resolve_load_order(
                    requested,
                    definition_versions=context.state_group_definition_versions,
                )
            )
        else:
            target_groups = tuple(sorted(requested))
            for group_id in target_groups:
                self._definition_for_context(context, group_id)
        eligible = set(context.eligible_group_ids)
        forbidden = set(context.forbidden_group_ids)
        for group_id in target_groups:
            if group_id in forbidden or group_id not in eligible:
                raise StateGroupLifecycleAuthorityError("group_not_eligible")
        return target_groups

    def _event_specs(
        self,
        command: StateGroupLifecycleCommand,
        context: StateAssemblyContext,
        lifecycle: StateGroupLifecycleProjection,
        target_groups: tuple[str, ...],
    ) -> list[tuple[str, str]]:
        records = lifecycle.records
        if command.operation == "enable":
            specs: list[tuple[str, str]] = []
            for group_id in target_groups:
                current = records.get(group_id)
                if current is None or current.lifecycle_state == "disabled":
                    self._initialization_ref(context, group_id)
                    specs.append(("gameplay.state_group.materialized", group_id))
                    specs.append(("gameplay.state_group.enabled", group_id))
                elif current.lifecycle_state in {"materialized", "dormant"}:
                    specs.append(("gameplay.state_group.enabled", group_id))
            return specs

        enabled_group_ids = set(lifecycle.enabled_group_ids)
        if command.operation == "disabled":
            remaining_enabled = enabled_group_ids.difference(target_groups)
            record_versions = {
                group_id: record.definition_version
                for group_id, record in lifecycle.records.items()
                if record.lifecycle_state == "enabled"
            }
            for group_id in target_groups:
                for other_group_id in remaining_enabled:
                    if group_id in self._registry.resolve_load_order(
                        [other_group_id],
                        definition_versions=record_versions,
                    ):
                        raise StateGroupLifecycleAuthorityError("dependency_in_use")
        event_type = f"gameplay.state_group.{command.operation}"
        specs = []
        for group_id in target_groups:
            current = records.get(group_id)
            if current is None:
                raise StateGroupLifecycleAuthorityError(f"{command.operation}_before_materialization")
            if command.operation == "dormant" and current.lifecycle_state != "enabled":
                raise StateGroupLifecycleAuthorityError("dormant_transition_invalid")
            if command.operation == "disabled" and current.lifecycle_state not in {"materialized", "enabled", "dormant"}:
                raise StateGroupLifecycleAuthorityError("disable_transition_invalid")
            specs.append((event_type, group_id))
        return specs

    @staticmethod
    def _validate_authority(command: StateGroupLifecycleCommand, context: StateAssemblyContext) -> None:
        if command.authority_principal != context.authority_principal:
            raise StateGroupLifecycleAuthorityError("authority_principal_mismatch")

    @staticmethod
    def _initialization_ref(context: StateAssemblyContext, group_id: str) -> str:
        reference = context.initialization_refs.get(group_id)
        if not reference:
            raise StateGroupLifecycleAuthorityError("initialization_ref_missing")
        return reference

    def _definition_for_context(self, context: StateAssemblyContext, group_id: str):
        return self._registry.resolve(group_id, context.state_group_definition_versions.get(group_id))

    @staticmethod
    def _stream_id(actor_ref: str) -> str:
        return f"gameplay:state_groups:{actor_ref}"

    @staticmethod
    def _digest(payload: dict[str, object]) -> str:
        return "sha256:" + sha256(
            json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def _is_sha256_digest(value: str) -> bool:
    return re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def compile_state_assembly_context(
    inputs: StateAssemblyInputs,
    catalog: StateGroupEligibilityCatalog,
    registry: StateGroupRegistry,
) -> StateAssemblyContext:
    """Compile a trusted context from explicit backend policy facts.

    A group omitted from the catalog is forbidden by default. This deliberately
    leaves actor/world/patch persistence and package activation outside this
    small compiler; callers must provide their already-versioned facts.
    """

    known_groups = set(registry.list_group_ids())
    eligible: list[StateGroupEligibilityRule] = []
    for rule in catalog.rules:
        if rule.group_id not in known_groups:
            raise StateGroupLifecycleAuthorityError("eligibility_rule_group_unknown")
        if _rule_matches(rule, inputs):
            eligible.append(rule)
    eligible_group_ids = tuple(rule.group_id for rule in eligible)
    required_group_ids = tuple(rule.group_id for rule in eligible if rule.required)
    eligible_set = set(eligible_group_ids)
    for required_group_id in required_group_ids:
        dependencies = registry.resolve_load_order([required_group_id])
        if not set(dependencies).issubset(eligible_set):
            raise StateGroupLifecycleAuthorityError("required_dependency_ineligible")
    return StateAssemblyContext(
        actor_ref=inputs.actor_ref,
        authority_principal=inputs.authority_principal,
        registry_revision=inputs.registry_revision,
        world_config_revision=inputs.world_config_revision,
        active_patch_set_revision=inputs.active_patch_set_revision,
        eligible_group_ids=eligible_group_ids,
        required_group_ids=required_group_ids,
        forbidden_group_ids=tuple(sorted(known_groups.difference(eligible_set))),
        initialization_refs={rule.group_id: rule.initialization_ref for rule in eligible},
    )


def _rule_matches(rule: StateGroupEligibilityRule, inputs: StateAssemblyInputs) -> bool:
    return (
        (not rule.actor_archetype_refs or inputs.actor_archetype_ref in rule.actor_archetype_refs)
        and (not rule.world_config_revisions or inputs.world_config_revision in rule.world_config_revisions)
        and (not rule.active_patch_set_revisions or inputs.active_patch_set_revision in rule.active_patch_set_revisions)
    )


__all__ = [
    "StateAssemblyContext",
    "StateAssemblyInputs",
    "StateGroupEligibilityCatalog",
    "StateGroupEligibilityRule",
    "StateGroupLifecycleAuthorityError",
    "StateGroupLifecycleBatchPlan",
    "StateGroupLifecycleAuthorityResult",
    "StateGroupLifecycleAuthorityService",
    "StateGroupLifecycleCommand",
    "compile_state_assembly_context",
]
