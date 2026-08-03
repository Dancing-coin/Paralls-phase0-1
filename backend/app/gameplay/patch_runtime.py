"""Governed, proposal-only runtime primitives for Gameplay patches.

This is intentionally not a scripting surface. Patch manifests and rules are
immutable data; capability handlers receive frozen projection input and can only
return typed effect proposals for later authority settlement.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Callable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class GameplayPatchRuntimeError(ValueError):
    """A stable, typed rejection raised before authority settlement."""


class GameplayPatchRegistrySnapshotError(ValueError):
    """Raised when immutable patch registry state cannot be restored safely."""


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _read_path(value: object, path: tuple[str, ...]) -> object:
    current = value
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            raise GameplayPatchRuntimeError("rule_ir_input_path_missing")
        current = current[part]
    return current


def _version_matches(version: str, version_range: str) -> bool:
    """Evaluate the bounded semantic-version ranges accepted by this registry."""
    if version_range in {"", "*"}:
        return True
    try:
        actual = _semver(version)
    except ValueError:
        return False
    for raw_constraint in version_range.split(","):
        constraint = raw_constraint.strip()
        if not constraint:
            continue
        operator = next((item for item in (">=", "<=", "==", ">", "<") if constraint.startswith(item)), "==")
        candidate = constraint[len(operator) :] if constraint.startswith(operator) else constraint
        try:
            expected = _semver(candidate)
        except ValueError:
            return False
        if operator == ">=" and not actual >= expected:
            return False
        if operator == "<=" and not actual <= expected:
            return False
        if operator == ">" and not actual > expected:
            return False
        if operator == "<" and not actual < expected:
            return False
        if operator == "==" and actual != expected:
            return False
    return True


def _semver(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        raise ValueError(value)
    return tuple(int(part) for part in (*parts, "0", "0")[:3])


class StrictPatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PatchDependency(StrictPatchModel):
    dependency_kind: Literal["patch", "contract", "state_group", "capability"]
    target_ref: str = Field(min_length=1)
    version_range: str = Field(default="*", min_length=1)
    required: bool = True
    reason: str = Field(min_length=1)


class PatchEventSchema(StrictPatchModel):
    event_type: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    schema_digest: str = Field(min_length=1)


class RequestedCapability(StrictPatchModel):
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    call_sites: tuple[str, ...] = Field(min_length=1)
    requested_effect_types: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_values(self) -> "RequestedCapability":
        if len(set(self.call_sites)) != len(self.call_sites):
            raise ValueError("capability call_sites must be unique")
        if len(set(self.requested_effect_types)) != len(self.requested_effect_types):
            raise ValueError("capability requested_effect_types must be unique")
        return self


class RuleCondition(StrictPatchModel):
    path: tuple[str, ...] = Field(min_length=1)
    operator: Literal["equals", "exists"]
    expected_value: object | None = None


class RuleEffectTemplate(StrictPatchModel):
    effect_type: str = Field(min_length=1)
    payload: dict[str, object] = Field(default_factory=dict)


class RuleCapabilityCall(StrictPatchModel):
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    input_paths: dict[str, tuple[str, ...]] = Field(default_factory=dict)


class RuleDefinition(StrictPatchModel):
    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    conditions: tuple[RuleCondition, ...] = ()
    effect_templates: tuple[RuleEffectTemplate, ...] = ()
    capability_calls: tuple[RuleCapabilityCall, ...] = ()


class StateGroupMigration(StrictPatchModel):
    """A manifest-declared state-group migration gate for one target revision."""

    group_id: str = Field(min_length=1)
    from_definition_version: str = Field(min_length=1)
    to_definition_version: str = Field(min_length=1)
    migration_kind: Literal["identity_rebind", "resource_bounds_clamp"]
    migration_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    resource_id: str | None = None
    migrator_id: str | None = None
    migrator_code_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    input_event_schema: PatchEventSchema | None = None
    output_event_schema: PatchEventSchema | None = None
    rollback_mode: Literal["identity_rebind", "forward_fix_only"] | None = None

    @model_validator(mode="after")
    def _validate_kind_contract(self) -> "StateGroupMigration":
        if self.migration_kind == "identity_rebind":
            if (
                self.from_definition_version != self.to_definition_version
                or any(
                    value is not None
                    for value in (
                        self.resource_id,
                        self.migrator_id,
                        self.migrator_code_digest,
                        self.input_event_schema,
                        self.output_event_schema,
                        self.rollback_mode,
                    )
                )
            ):
                raise ValueError("identity_rebind_migration_contract_invalid")
            return self
        if (
            not self.resource_id
            or not self.migrator_id
            or not self.migrator_code_digest
            or self.input_event_schema is None
            or self.output_event_schema is None
            or self.rollback_mode != "forward_fix_only"
            or self.from_definition_version == self.to_definition_version
        ):
            raise ValueError("resource_bounds_clamp_migration_contract_invalid")
        return self


class GameplayPatchManifest(StrictPatchModel):
    manifest_schema_version: int = Field(ge=1)
    patch_id: str = Field(min_length=1)
    patch_version: str = Field(min_length=1)
    patch_revision_id: str = Field(min_length=1)
    content_digest: str = Field(min_length=1)
    author_id: str = Field(min_length=1)
    trust_policy_ref: str = Field(min_length=1)
    dependencies: tuple[PatchDependency, ...] = ()
    state_group_ids: tuple[str, ...] = ()
    state_group_migrations: tuple[StateGroupMigration, ...] = ()
    event_schemas: tuple[PatchEventSchema, ...] = ()
    rules: tuple[RuleDefinition, ...] = ()
    requested_capabilities: tuple[RequestedCapability, ...] = ()
    granted_effect_types: tuple[str, ...] = ()
    verification_profiles: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _reject_duplicate_definitions(self) -> "GameplayPatchManifest":
        if len(set(self.state_group_ids)) != len(self.state_group_ids):
            raise ValueError("patch state_group_ids must be unique")
        migration_group_ids = [migration.group_id for migration in self.state_group_migrations]
        if len(migration_group_ids) != len(set(migration_group_ids)):
            raise ValueError("patch state_group_migrations must be unique per group")
        if not set(migration_group_ids).issubset(set(self.state_group_ids)):
            raise ValueError("patch state_group_migration group must be declared")
        event_keys = [(schema.event_type, schema.schema_version) for schema in self.event_schemas]
        if len(set(event_keys)) != len(event_keys):
            raise ValueError("patch event schemas must be unique")
        declared_schema_identities = {
            (schema.event_type, schema.schema_version, schema.schema_digest)
            for schema in self.event_schemas
        }
        for migration in self.state_group_migrations:
            if migration.migration_kind != "resource_bounds_clamp":
                continue
            assert migration.input_event_schema is not None and migration.output_event_schema is not None
            input_identity = (
                migration.input_event_schema.event_type,
                migration.input_event_schema.schema_version,
                migration.input_event_schema.schema_digest,
            )
            output_identity = (
                migration.output_event_schema.event_type,
                migration.output_event_schema.schema_version,
                migration.output_event_schema.schema_digest,
            )
            if input_identity not in declared_schema_identities or output_identity not in declared_schema_identities:
                raise ValueError("patch_resource_migration_schema_not_declared")
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("patch rule_ids must be unique")
        capability_ids = [(item.capability_id, item.capability_version) for item in self.requested_capabilities]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("patch requested capabilities must be unique")
        if len(set(self.granted_effect_types)) != len(self.granted_effect_types):
            raise ValueError("patch granted_effect_types must be unique")
        return self

    def expected_content_digest(self) -> str:
        return _canonical_digest(self.model_dump(mode="json", exclude={"content_digest"}))


@dataclass(frozen=True)
class RegisteredCapability:
    capability_id: str
    capability_version: str
    handler_code_digest: str
    owner: str
    allowed_callers: frozenset[str]
    allowed_effect_types: frozenset[str]
    deterministic: bool
    side_effect_free: bool
    network_access: bool
    filesystem_access: bool
    handler: Callable[[Mapping[str, object], "CapabilityExecutionContext"], "CapabilityResult"]


@dataclass(frozen=True)
class CapabilityExecutionContext:
    evaluation_id: str
    patch_revision_id: str
    rule_id: str
    authority_tick: int
    projection_inputs: Mapping[str, object]


@dataclass(frozen=True)
class EffectProposal:
    effect_type: str
    payload: Mapping[str, object]
    source_ref: str


@dataclass(frozen=True)
class CapabilityResult:
    status: Literal["proposed", "no_op", "rejected"]
    effect_proposals: tuple[EffectProposal, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class PatchSetRevision:
    registry_revision: str
    active_patch_set_revision: str
    patch_revision_ids: tuple[str, ...]


@dataclass(frozen=True)
class RuleEvaluationRequest:
    evaluation_id: str
    trigger: str
    authority_tick: int
    pinned_registry_revision: str
    pinned_active_patch_set_revision: str
    projection_inputs: Mapping[str, object]


@dataclass(frozen=True)
class RuleEvaluationResult:
    evaluation_id: str
    status: Literal["proposed", "no_op"]
    matched_rule_refs: tuple[str, ...]
    effect_proposals: tuple[EffectProposal, ...]
    input_digest: str
    output_digest: str


class CapabilityRegistry:
    """Only deterministic, side-effect-free handlers may join authority evaluation."""

    def __init__(self) -> None:
        self._capabilities: dict[tuple[str, str], RegisteredCapability] = {}

    def register(self, capability: RegisteredCapability) -> None:
        key = (capability.capability_id, capability.capability_version)
        if not all((capability.capability_id, capability.capability_version, capability.handler_code_digest, capability.owner)):
            raise GameplayPatchRuntimeError("capability_registration_invalid")
        if not capability.deterministic or not capability.side_effect_free or capability.network_access or capability.filesystem_access:
            raise GameplayPatchRuntimeError("capability_authority_unsafe")
        if key in self._capabilities:
            raise GameplayPatchRuntimeError("capability_registration_duplicate")
        self._capabilities[key] = capability

    def resolve(self, capability_id: str, capability_version: str) -> RegisteredCapability:
        try:
            return self._capabilities[(capability_id, capability_version)]
        except KeyError as exc:
            raise GameplayPatchRuntimeError("capability_not_registered") from exc


class GameplayPatchRegistry:
    """Immutable candidate registry and atomic active-set composition only."""

    def __init__(self, *, trusted_authors: frozenset[str]) -> None:
        self._trusted_authors = trusted_authors
        self._candidates: dict[str, GameplayPatchManifest] = {}
        self._active: PatchSetRevision | None = None

    @property
    def active_patch_set(self) -> PatchSetRevision | None:
        return self._active

    @property
    def registry_revision(self) -> str:
        return _canonical_digest({"patch_revision_ids": sorted(self._candidates)})

    def export_snapshot(self) -> dict[str, object]:
        """Return JSON-safe candidate and active-set state; handlers stay external."""
        return {
            "snapshot_schema_version": 1,
            "candidates": [
                manifest.model_dump(mode="json")
                for _, manifest in sorted(self._candidates.items())
            ],
            "active_patch_set": (
                {
                    "registry_revision": self._active.registry_revision,
                    "active_patch_set_revision": self._active.active_patch_set_revision,
                    "patch_revision_ids": list(self._active.patch_revision_ids),
                }
                if self._active is not None
                else None
            ),
        }

    def save_snapshot(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(self.export_snapshot(), stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, target)
        except OSError as exc:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_write_failed") from exc

    @classmethod
    def load_snapshot(cls, path: str | Path, *, trusted_authors: frozenset[str]) -> "GameplayPatchRegistry":
        try:
            with Path(path).open("r", encoding="utf-8") as stream:
                snapshot = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_load_failed") from exc
        return cls.from_snapshot(snapshot, trusted_authors=trusted_authors)

    @classmethod
    def from_snapshot(cls, snapshot: object, *, trusted_authors: frozenset[str]) -> "GameplayPatchRegistry":
        if not isinstance(snapshot, dict) or snapshot.get("snapshot_schema_version") != 1:
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_schema_unsupported")
        candidate_values = snapshot.get("candidates")
        if not isinstance(candidate_values, list):
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_invalid")
        try:
            manifests = tuple(GameplayPatchManifest.model_validate(value) for value in candidate_values)
        except (ValidationError, TypeError) as exc:
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_invalid") from exc
        registry = cls(trusted_authors=trusted_authors)
        try:
            registry.install_many(manifests)
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_invalid") from exc
        active_value = snapshot.get("active_patch_set")
        if active_value is None:
            return registry
        if not isinstance(active_value, dict):
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_invalid")
        revision_ids = active_value.get("patch_revision_ids")
        if not isinstance(revision_ids, list) or not all(isinstance(item, str) for item in revision_ids):
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_invalid")
        try:
            active = registry.activate(tuple(revision_ids))
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_invalid") from exc
        if (
            active_value.get("registry_revision") != active.registry_revision
            or active_value.get("active_patch_set_revision") != active.active_patch_set_revision
        ):
            raise GameplayPatchRegistrySnapshotError("patch_registry_snapshot_active_set_mismatch")
        return registry

    def install(self, manifest: GameplayPatchManifest) -> GameplayPatchManifest:
        return self.install_many((manifest,))[0]

    def validate_install_many(self, manifests: tuple[GameplayPatchManifest, ...]) -> tuple[GameplayPatchManifest, ...]:
        """Validate an immutable candidate batch without mutating the registry."""
        staged = dict(self._candidates)
        for manifest in manifests:
            self._validate_manifest(manifest)
            existing = staged.get(manifest.patch_revision_id)
            if existing is not None:
                if existing.expected_content_digest() != manifest.expected_content_digest():
                    raise GameplayPatchRuntimeError("patch_revision_immutable_conflict")
                raise GameplayPatchRuntimeError("patch_candidate_duplicate")
            staged[manifest.patch_revision_id] = manifest.model_copy(deep=True)
        self._validate_dependencies_and_cycles(staged)
        self._validate_schema_collisions(staged)
        return tuple(manifest.model_copy(deep=True) for manifest in manifests)

    def install_many(self, manifests: tuple[GameplayPatchManifest, ...]) -> tuple[GameplayPatchManifest, ...]:
        self.validate_install_many(manifests)
        staged = dict(self._candidates)
        for manifest in manifests:
            staged[manifest.patch_revision_id] = manifest.model_copy(deep=True)
        self._candidates = staged
        return tuple(manifest.model_copy(deep=True) for manifest in manifests)

    def candidate(self, patch_revision_id: str) -> GameplayPatchManifest:
        try:
            return self._candidates[patch_revision_id].model_copy(deep=True)
        except KeyError as exc:
            raise GameplayPatchRuntimeError("patch_candidate_not_installed") from exc

    def compose_active_set(self, patch_revision_ids: tuple[str, ...]) -> PatchSetRevision:
        """Validate and compose a non-empty patch set without activating it."""
        if not patch_revision_ids or len(set(patch_revision_ids)) != len(patch_revision_ids):
            raise GameplayPatchRuntimeError("patch_activation_invalid")
        selected = []
        for revision_id in sorted(patch_revision_ids):
            try:
                selected.append(self._candidates[revision_id])
            except KeyError as exc:
                raise GameplayPatchRuntimeError("patch_candidate_not_installed") from exc
        self._validate_selected_dependencies(tuple(selected))
        registry_revision = self.registry_revision
        active_revision = _canonical_digest(
            {"registry_revision": registry_revision, "patch_revision_ids": [item.patch_revision_id for item in selected]}
        )
        return PatchSetRevision(registry_revision, active_revision, tuple(item.patch_revision_id for item in selected))

    def activate(self, patch_revision_ids: tuple[str, ...]) -> PatchSetRevision:
        self._active = self.compose_active_set(patch_revision_ids)
        return self._active

    def replace_active_set(self, patch_revision_ids: tuple[str, ...]) -> PatchSetRevision | None:
        """Apply a previously validated complete active set; empty means no active patches."""
        if not patch_revision_ids:
            self._active = None
            return None
        return self.activate(patch_revision_ids)

    def active_manifests(self, active_patch_set_revision: str) -> tuple[GameplayPatchManifest, ...]:
        if self._active is None or self._active.active_patch_set_revision != active_patch_set_revision:
            raise GameplayPatchRuntimeError("patch_revision_changed")
        return tuple(self._candidates[revision_id].model_copy(deep=True) for revision_id in self._active.patch_revision_ids)

    def _validate_manifest(self, manifest: GameplayPatchManifest) -> None:
        if manifest.author_id not in self._trusted_authors:
            raise GameplayPatchRuntimeError("patch_author_untrusted")
        if manifest.content_digest != manifest.expected_content_digest():
            raise GameplayPatchRuntimeError("patch_digest_mismatch")

    @staticmethod
    def _validate_dependencies_and_cycles(candidates: Mapping[str, GameplayPatchManifest]) -> None:
        by_patch_id: dict[str, list[GameplayPatchManifest]] = {}
        for manifest in candidates.values():
            by_patch_id.setdefault(manifest.patch_id, []).append(manifest)
        for manifest in candidates.values():
            for dependency in manifest.dependencies:
                if dependency.dependency_kind != "patch" or not dependency.required:
                    continue
                matching = [item for item in by_patch_id.get(dependency.target_ref, []) if _version_matches(item.patch_version, dependency.version_range)]
                if not matching:
                    raise GameplayPatchRuntimeError("patch_dependency_missing")
                if len(matching) > 1:
                    raise GameplayPatchRuntimeError("patch_dependency_ambiguous")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(revision_id: str) -> None:
            if revision_id in visiting:
                raise GameplayPatchRuntimeError("patch_dependency_cycle")
            if revision_id in visited:
                return
            visiting.add(revision_id)
            manifest = candidates[revision_id]
            for dependency in manifest.dependencies:
                if dependency.dependency_kind != "patch" or not dependency.required:
                    continue
                matching = [target for target in candidates.values() if target.patch_id == dependency.target_ref and _version_matches(target.patch_version, dependency.version_range)]
                if len(matching) != 1:
                    raise GameplayPatchRuntimeError("patch_dependency_ambiguous")
                visit(matching[0].patch_revision_id)
            visiting.remove(revision_id)
            visited.add(revision_id)

        for revision_id in candidates:
            visit(revision_id)

    @staticmethod
    def _validate_schema_collisions(candidates: Mapping[str, GameplayPatchManifest]) -> None:
        schemas: dict[tuple[str, int], str] = {}
        for manifest in candidates.values():
            for schema in manifest.event_schemas:
                key = (schema.event_type, schema.schema_version)
                known_digest = schemas.setdefault(key, schema.schema_digest)
                if known_digest != schema.schema_digest:
                    raise GameplayPatchRuntimeError("patch_schema_collision")

    @staticmethod
    def _validate_selected_dependencies(selected: tuple[GameplayPatchManifest, ...]) -> None:
        active_by_id = {manifest.patch_id: manifest for manifest in selected}
        for manifest in selected:
            for dependency in manifest.dependencies:
                if dependency.dependency_kind != "patch" or not dependency.required:
                    continue
                dependency_manifest = active_by_id.get(dependency.target_ref)
                if dependency_manifest is None or not _version_matches(dependency_manifest.patch_version, dependency.version_range):
                    raise GameplayPatchRuntimeError("patch_dependency_not_active")


class GameplayRuleEvaluator:
    """Evaluates data-only rules and returns proposals; it has no commit path."""

    def __init__(
        self,
        *,
        patch_registry: GameplayPatchRegistry,
        capability_registry: CapabilityRegistry,
        max_condition_nodes: int = 64,
        max_effect_proposals: int = 32,
        max_capability_calls: int = 16,
    ) -> None:
        self._patch_registry = patch_registry
        self._capability_registry = capability_registry
        self._max_condition_nodes = max_condition_nodes
        self._max_effect_proposals = max_effect_proposals
        self._max_capability_calls = max_capability_calls

    def evaluate(self, request: RuleEvaluationRequest) -> RuleEvaluationResult:
        active = self._patch_registry.active_patch_set
        if active is None or request.pinned_registry_revision != active.registry_revision:
            raise GameplayPatchRuntimeError("patch_revision_changed")
        manifests = self._patch_registry.active_manifests(request.pinned_active_patch_set_revision)
        frozen_inputs = _freeze(request.projection_inputs)
        input_digest = _canonical_digest(request.projection_inputs)
        matched: list[str] = []
        proposals: list[EffectProposal] = []
        condition_nodes = 0
        capability_calls = 0
        for manifest in manifests:
            allowed_effect_types = set(manifest.granted_effect_types)
            requested = {(item.capability_id, item.capability_version): item for item in manifest.requested_capabilities}
            for rule in manifest.rules:
                if rule.trigger != request.trigger:
                    continue
                condition_nodes += len(rule.conditions)
                if condition_nodes > self._max_condition_nodes:
                    raise GameplayPatchRuntimeError("rule_budget_exceeded")
                if not self._matches(rule.conditions, frozen_inputs):
                    continue
                matched.append(f"{manifest.patch_revision_id}:{rule.rule_id}:{rule.rule_version}")
                for effect in rule.effect_templates:
                    self._append_proposal(proposals, EffectProposal(effect.effect_type, _freeze(effect.payload), f"{manifest.patch_revision_id}:{rule.rule_id}"), allowed_effect_types)
                for call in rule.capability_calls:
                    capability_calls += 1
                    if capability_calls > self._max_capability_calls:
                        raise GameplayPatchRuntimeError("rule_budget_exceeded")
                    request_capability = requested.get((call.capability_id, call.capability_version))
                    if request_capability is None or rule.rule_id not in request_capability.call_sites:
                        raise GameplayPatchRuntimeError("capability_not_manifest_authorized")
                    capability = self._capability_registry.resolve(call.capability_id, call.capability_version)
                    if manifest.author_id not in capability.allowed_callers:
                        raise GameplayPatchRuntimeError("capability_not_manifest_authorized")
                    capability_input = _freeze({key: _read_path(frozen_inputs, path) for key, path in call.input_paths.items()})
                    try:
                        result = capability.handler(
                            capability_input,
                            CapabilityExecutionContext(request.evaluation_id, manifest.patch_revision_id, rule.rule_id, request.authority_tick, frozen_inputs),
                        )
                    except GameplayPatchRuntimeError:
                        raise
                    except Exception as exc:
                        raise GameplayPatchRuntimeError("capability_handler_failed") from exc
                    if result.status == "rejected":
                        raise GameplayPatchRuntimeError("capability_output_invalid")
                    for proposal in result.effect_proposals:
                        if proposal.effect_type not in request_capability.requested_effect_types or proposal.effect_type not in capability.allowed_effect_types:
                            raise GameplayPatchRuntimeError("effect_type_unauthorized")
                        self._append_proposal(proposals, proposal, allowed_effect_types)
        output_payload = [
            {"effect_type": proposal.effect_type, "payload": dict(proposal.payload), "source_ref": proposal.source_ref}
            for proposal in proposals
        ]
        return RuleEvaluationResult(
            request.evaluation_id,
            "proposed" if proposals else "no_op",
            tuple(matched),
            tuple(proposals),
            input_digest,
            _canonical_digest({"matched": matched, "proposals": output_payload}),
        )

    def _append_proposal(self, proposals: list[EffectProposal], proposal: EffectProposal, allowed_effect_types: set[str]) -> None:
        if proposal.effect_type not in allowed_effect_types:
            raise GameplayPatchRuntimeError("effect_type_unauthorized")
        if len(proposals) >= self._max_effect_proposals:
            raise GameplayPatchRuntimeError("rule_budget_exceeded")
        proposals.append(proposal)

    @staticmethod
    def _matches(conditions: tuple[RuleCondition, ...], inputs: object) -> bool:
        for condition in conditions:
            try:
                actual = _read_path(inputs, condition.path)
            except GameplayPatchRuntimeError:
                if condition.operator == "exists":
                    return False
                raise
            if condition.operator == "exists":
                continue
            if actual != condition.expected_value:
                return False
        return True
