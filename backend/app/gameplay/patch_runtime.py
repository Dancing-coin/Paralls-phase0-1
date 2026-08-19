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
import re
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


_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_AUTHORITY_SHAPED_KEYS = frozenset(
    {
        "owner",
        "owner_ref",
        "stream",
        "stream_ref",
        "event",
        "event_family",
        "event_ref",
        "privacy",
        "privacy_scope",
        "receipt",
        "receipt_rule",
        "compensation",
        "settlement",
        "fragment",
        "router",
        "registry",
        "coordinator",
        "writer",
        "authority",
        "authority_coordinate",
        "target_owner",
        "target_stream",
        "proof",
        "caller_proof",
        "lookup",
        "arbitrary_code",
        "script",
        "executable",
    }
)


def _require_platform_ref(value: str, *, prefix: str, error: str = "platform_reference_invalid") -> str:
    if not value.startswith(prefix) or "@" not in value or value.endswith("@"):
        raise ValueError(error)
    return value


def _validate_platform_content(value: object) -> None:
    """Reject package content that could smuggle authority coordinates."""
    if value is None:
        raise ValueError("platform_typed_content_invalid")
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str) or key in _AUTHORITY_SHAPED_KEYS:
                raise ValueError("platform_authority_shaped_payload")
            _validate_platform_content(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _validate_platform_content(nested)
    elif not isinstance(value, (str, int, float, bool)):
        raise ValueError("platform_typed_content_invalid")


def _require_author_canonical(
    values: tuple[object, ...],
    *,
    identity: Callable[[object], object],
) -> None:
    keys = tuple(identity(value) for value in values)
    if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
        raise ValueError("platform_array_not_canonical")


class StrictPlatformExtensionModel(StrictPatchModel):
    # JSON arrays are accepted as the immutable transport representation and
    # become tuples in the frozen model; semantic coercion is still rejected
    # by the field-level validation below.
    model_config = ConfigDict(extra="forbid", frozen=True)


class PackageIdentity(StrictPlatformExtensionModel):
    package_id: str = Field(min_length=1)
    package_version: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)


class PackageDefinition(StrictPlatformExtensionModel):
    definition_ref: str = Field(min_length=1)
    definition_schema_ref: str = Field(min_length=1)
    source_package_revision: str = Field(min_length=1)
    typed_content: dict[str, object]

    @model_validator(mode="after")
    def _validate_definition(self) -> "PackageDefinition":
        _require_platform_ref(self.definition_ref, prefix="definition:")
        _require_platform_ref(self.definition_schema_ref, prefix="schema:")
        _validate_platform_content(self.typed_content)
        return self


class OutcomeDeclarationAuthorInput(StrictPlatformExtensionModel):
    declaration_ref: str = Field(min_length=1)
    outcome_family_ref: str = Field(min_length=1)
    definition_refs: tuple[str, ...]
    eligibility_refs: tuple[str, ...]
    policy_revision_ref: str = Field(min_length=1)
    source_package_revision: str = Field(min_length=1)
    declaration_digest: str | None = None

    @model_validator(mode="after")
    def _validate_and_derive_digest(self) -> "OutcomeDeclarationAuthorInput":
        _require_platform_ref(self.declaration_ref, prefix="declaration:")
        _require_platform_ref(self.outcome_family_ref, prefix="outcome:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        for value in self.definition_refs:
            _require_platform_ref(value, prefix="definition:")
        for value in self.eligibility_refs:
            if ":" not in value or "@" not in value or value.endswith("@"):
                raise ValueError("platform_reference_invalid")
        _require_author_canonical(self.definition_refs, identity=lambda value: value)
        _require_author_canonical(self.eligibility_refs, identity=lambda value: value)
        if self.declaration_digest is None or not re.fullmatch(_DIGEST_PATTERN, self.declaration_digest):
            raise ValueError("platform_declaration_digest_missing")
        payload = self.model_dump(mode="json", exclude={"declaration_digest"})
        if self.declaration_digest != _canonical_digest(payload):
            raise ValueError("platform_declaration_digest_mismatch")
        return self

    def normalized(self) -> "NormalizedOutcomeDeclaration":
        payload = self.model_dump(mode="json", exclude={"declaration_digest"})
        return NormalizedOutcomeDeclaration.model_validate(
            {**payload, "declaration_digest": _canonical_digest(payload)}
        )


class NormalizedOutcomeDeclaration(StrictPlatformExtensionModel):
    declaration_ref: str = Field(min_length=1)
    outcome_family_ref: str = Field(min_length=1)
    definition_refs: tuple[str, ...]
    eligibility_refs: tuple[str, ...]
    policy_revision_ref: str = Field(min_length=1)
    source_package_revision: str = Field(min_length=1)
    declaration_digest: str = Field(pattern=_DIGEST_PATTERN)


class TypedReadRequirement(StrictPlatformExtensionModel):
    requirement_ref: str = Field(min_length=1)
    predicate_family_ref: str = Field(min_length=1)
    subject_slot_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_references(self) -> "TypedReadRequirement":
        _require_platform_ref(self.requirement_ref, prefix="requirement:")
        _require_platform_ref(self.predicate_family_ref, prefix="predicate:")
        if not self.subject_slot_ref.startswith("slot:"):
            raise ValueError("platform_reference_invalid")
        return self


class CapabilityBindingRequest(StrictPlatformExtensionModel):
    binding_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    source_package_revision: str = Field(min_length=1)
    declaration_ref: str = Field(min_length=1)
    typed_read_requirements: tuple[TypedReadRequirement, ...]
    proposal_effect_types: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_references(self) -> "CapabilityBindingRequest":
        _require_platform_ref(self.binding_ref, prefix="binding:")
        _require_platform_ref(self.capability_ref, prefix="capability:")
        _require_platform_ref(self.declaration_ref, prefix="declaration:")
        for effect_ref in self.proposal_effect_types:
            _require_platform_ref(effect_ref, prefix="effect:")
        _require_author_canonical(self.typed_read_requirements, identity=lambda value: value.requirement_ref)
        _require_author_canonical(self.proposal_effect_types, identity=lambda value: value)
        return self


class DependencyConflictRef(StrictPlatformExtensionModel):
    relation: Literal["requires", "conflicts"]
    ref: str = Field(min_length=1)
    revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_reference(self) -> "DependencyConflictRef":
        if not self.ref.startswith(("package:", "patch:", "capability:", "schema:")):
            raise ValueError("platform_reference_invalid")
        return self


class ReplayReaderRef(StrictPlatformExtensionModel):
    reader_ref: str = Field(min_length=1)
    reader_revision: str = Field(min_length=1)
    replay_mode: Literal["full", "checkpoint-tail"]

    @model_validator(mode="after")
    def _validate_reference(self) -> "ReplayReaderRef":
        if not self.reader_ref.startswith("reader:"):
            raise ValueError("platform_reference_invalid")
        return self


class PlatformExtension(StrictPlatformExtensionModel):
    platform_schema_version: Literal["1.0"]
    package_identity: PackageIdentity
    package_definitions: tuple[PackageDefinition, ...]
    outcome_declarations: tuple[NormalizedOutcomeDeclaration, ...]
    capability_binding_requests: tuple[CapabilityBindingRequest, ...]
    dependency_and_conflict_refs: tuple[DependencyConflictRef, ...]
    replay_reader_refs: tuple[ReplayReaderRef, ...]
    verification_profile_refs: tuple[str, ...]

    @model_validator(mode="before")
    @classmethod
    def _normalize_author_declarations(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        raw = dict(value)
        declarations = raw.get("outcome_declarations")
        if not isinstance(declarations, (list, tuple)):
            return value
        try:
            raw["outcome_declarations"] = [
                OutcomeDeclarationAuthorInput.model_validate(item).normalized().model_dump(mode="json")
                for item in declarations
            ]
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        return raw

    @model_validator(mode="after")
    def _validate_shape(self) -> "PlatformExtension":
        _require_author_canonical(self.package_definitions, identity=lambda value: value.definition_ref)
        _require_author_canonical(self.outcome_declarations, identity=lambda value: value.declaration_ref)
        _require_author_canonical(self.capability_binding_requests, identity=lambda value: value.binding_ref)
        _require_author_canonical(
            self.dependency_and_conflict_refs,
            identity=lambda value: (value.relation, value.ref, value.revision),
        )
        _require_author_canonical(
            self.replay_reader_refs,
            identity=lambda value: (value.replay_mode, value.reader_ref, value.reader_revision),
        )
        _require_author_canonical(self.verification_profile_refs, identity=lambda value: value)
        for verification_ref in self.verification_profile_refs:
            _require_platform_ref(verification_ref, prefix="verification:")
        return self


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


class PackageExchangePricePolicy(StrictPatchModel):
    price_policy_revision: str = Field(min_length=1)
    currency_ref: str = Field(min_length=1)
    fixed_amount: int | None = Field(default=None, gt=0)
    minimum_amount: int | None = Field(default=None, gt=0)
    maximum_amount: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_shape(self) -> "PackageExchangePricePolicy":
        fixed = self.fixed_amount is not None
        bounded = self.minimum_amount is not None or self.maximum_amount is not None
        if fixed == bounded:
            raise ValueError("package_exchange_price_policy_shape_invalid")
        if bounded:
            if self.minimum_amount is None or self.maximum_amount is None:
                raise ValueError("package_exchange_price_policy_bounds_incomplete")
            if self.minimum_amount > self.maximum_amount:
                raise ValueError("package_exchange_price_policy_bounds_invalid")
        return self


class PackageDeclaredNegotiatedExchangeDefinition(StrictPatchModel):
    economic_outcome_id: str = Field(min_length=1)
    outcome_ref: str = Field(min_length=1)
    tradeable_ref: str | None = Field(default=None, min_length=1)
    typed_service_ref: str | None = Field(default=None, min_length=1)
    source_evidence_mode: Literal["inventory_custody@1", "ownership_right@1", "completed_service@1"]
    source_owner_ref: str = Field(min_length=1)
    source_evidence_kind: str = Field(min_length=1)
    price_policy: PackageExchangePricePolicy
    consent_rule_ref: str = Field(min_length=1)
    eligibility_refs: tuple[str, ...] = ()
    privacy_policy_ref: str = "authority_only"
    compensation_policy_ref: str = "none"
    source_selection_rule_ref: str = "exchange:unique-owned-source@1"
    capability_ref: str = "capability:package-declared-negotiated-exchange@1"

    @model_validator(mode="after")
    def _validate_contract(self) -> "PackageDeclaredNegotiatedExchangeDefinition":
        source_owner_by_mode = {
            "inventory_custody@1": "actor_gameplay.inventory_domain",
            "ownership_right@1": "actor_gameplay.ownership_domain",
            "completed_service@1": "actor_gameplay.contract_domain",
        }
        if self.economic_outcome_id != "package_declared_negotiated_exchange@1":
            raise ValueError("package_exchange_outcome_id_invalid")
        if (self.tradeable_ref is None) == (self.typed_service_ref is None):
            raise ValueError("package_exchange_source_shape_invalid")
        if self.source_owner_ref != source_owner_by_mode[self.source_evidence_mode]:
            raise ValueError("package_exchange_source_owner_invalid")
        if self.source_evidence_kind != self.source_evidence_mode:
            raise ValueError("package_exchange_source_evidence_kind_invalid")
        if self.privacy_policy_ref != "authority_only":
            raise ValueError("package_exchange_privacy_policy_invalid")
        if self.compensation_policy_ref != "none":
            raise ValueError("package_exchange_compensation_policy_invalid")
        if self.source_selection_rule_ref != "exchange:unique-owned-source@1":
            raise ValueError("package_exchange_source_selection_rule_invalid")
        if self.capability_ref != "capability:package-declared-negotiated-exchange@1":
            raise ValueError("package_exchange_capability_ref_invalid")
        if len(set(self.eligibility_refs)) != len(self.eligibility_refs):
            raise ValueError("package_exchange_eligibility_refs_duplicate")
        if self.source_evidence_mode == "completed_service@1" and self.typed_service_ref is None:
            raise ValueError("package_exchange_service_ref_required")
        if self.source_evidence_mode != "completed_service@1" and self.tradeable_ref is None:
            raise ValueError("package_exchange_tradeable_ref_required")
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

    def expected_migration_digest(self) -> str:
        """Return the digest of the immutable manifest-declared descriptor."""
        return _canonical_digest(self.model_dump(mode="json", exclude={"migration_digest"}, exclude_none=True))

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
    economic_outcomes: tuple[PackageDeclaredNegotiatedExchangeDefinition, ...] = ()
    granted_effect_types: tuple[str, ...] = ()
    verification_profiles: tuple[str, ...] = ()
    platform_extension: PlatformExtension | None = None

    def model_dump(self, **kwargs: object) -> dict[str, object]:
        """Keep every v1 serialized form byte-compatible with the old model."""
        if self.manifest_schema_version == 1:
            requested_exclude = kwargs.pop("exclude", None)
            if isinstance(requested_exclude, Mapping):
                excluded = {**requested_exclude, "platform_extension": True}
            else:
                excluded = set(requested_exclude) if requested_exclude is not None else set()
                excluded.add("platform_extension")
            kwargs["exclude"] = excluded
        return super().model_dump(**kwargs)

    @model_validator(mode="before")
    @classmethod
    def _validate_platform_schema_pair(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        schema_version = value.get("manifest_schema_version")
        extension_present = "platform_extension" in value
        extension = value.get("platform_extension")
        if schema_version == 1:
            if extension_present:
                raise ValueError("platform_schema_pair_invalid")
            return value
        if schema_version != 2 or not isinstance(extension, Mapping) or extension.get("platform_schema_version") != "1.0":
            raise ValueError("platform_schema_pair_invalid")
        return value

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
        outcome_refs = [definition.outcome_ref for definition in self.economic_outcomes]
        if len(set(outcome_refs)) != len(outcome_refs):
            raise ValueError("patch economic_outcomes must be unique")
        if len(set(self.granted_effect_types)) != len(self.granted_effect_types):
            raise ValueError("patch granted_effect_types must be unique")
        if self.manifest_schema_version == 2:
            assert self.platform_extension is not None
            if self.platform_extension.package_identity.package_id != self.patch_id:
                raise ValueError("platform_package_identity_mismatch")
            if self.platform_extension.package_identity.package_version != self.patch_version:
                raise ValueError("platform_package_identity_mismatch")
            if self.platform_extension.package_identity.package_revision != self.patch_revision_id:
                raise ValueError("platform_package_identity_mismatch")
            for definition in self.platform_extension.package_definitions:
                if definition.source_package_revision != self.patch_revision_id:
                    raise ValueError("platform_package_revision_mismatch")
            for declaration in self.platform_extension.outcome_declarations:
                if declaration.source_package_revision != self.patch_revision_id:
                    raise ValueError("platform_package_revision_mismatch")
                if not set(declaration.definition_refs).issubset(
                    {definition.definition_ref for definition in self.platform_extension.package_definitions}
                ):
                    raise ValueError("platform_definition_reference_unknown")
            declarations = {
                declaration.declaration_ref: declaration
                for declaration in self.platform_extension.outcome_declarations
            }
            for binding in self.platform_extension.capability_binding_requests:
                if binding.source_package_revision != self.patch_revision_id:
                    raise ValueError("platform_package_revision_mismatch")
                if binding.declaration_ref not in declarations:
                    raise ValueError("platform_binding_declaration_unknown")
        elif self.platform_extension is not None:
            raise ValueError("platform_schema_pair_invalid")
        self._validate_v2_outer_arrays()
        return self

    def expected_content_digest(self) -> str:
        excluded = {"content_digest"}
        if self.manifest_schema_version == 1:
            excluded.add("platform_extension")
        payload = self.model_dump(mode="json", exclude=excluded)
        if self.manifest_schema_version == 1 and not self.economic_outcomes:
            payload.pop("economic_outcomes", None)
        return _canonical_digest(payload)

    def _validate_v2_outer_arrays(self) -> None:
        if self.manifest_schema_version != 2:
            return
        _require_author_canonical(
            self.dependencies,
            identity=lambda value: (
                value.dependency_kind,
                value.target_ref,
                value.version_range,
                value.required,
                value.reason,
            ),
        )
        _require_author_canonical(self.state_group_ids, identity=lambda value: value)
        _require_author_canonical(self.state_group_migrations, identity=lambda value: value.group_id)
        _require_author_canonical(self.event_schemas, identity=lambda value: (value.event_type, value.schema_version))
        _require_author_canonical(self.rules, identity=lambda value: value.rule_id)
        _require_author_canonical(
            self.requested_capabilities,
            identity=lambda value: (value.capability_id, value.capability_version),
        )
        _require_author_canonical(self.economic_outcomes, identity=lambda value: value.outcome_ref)
        _require_author_canonical(self.granted_effect_types, identity=lambda value: value)
        _require_author_canonical(self.verification_profiles, identity=lambda value: value)


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
class ReadOnlyCapabilityBinding:
    """An activation-derived pin; package input never supplies descriptor data."""

    binding_ref: str
    package_revision: str
    content_digest: str
    declaration_digest: str
    descriptor_ref: str
    descriptor_revision: str
    active_patch_set_revision: str


@dataclass(frozen=True)
class PatchSetRevision:
    registry_revision: str
    active_patch_set_revision: str
    patch_revision_ids: tuple[str, ...]
    capability_bindings: tuple[ReadOnlyCapabilityBinding, ...] = ()


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
                manifest.model_dump(
                    mode="json",
                    exclude_none=manifest.manifest_schema_version == 1,
                )
                for _, manifest in sorted(self._candidates.items())
            ],
            "active_patch_set": (
                {
                    "registry_revision": self._active.registry_revision,
                    "active_patch_set_revision": self._active.active_patch_set_revision,
                    "patch_revision_ids": list(self._active.patch_revision_ids),
                    "capability_bindings": [
                        self._binding_snapshot_payload(binding)
                        for binding in self._active.capability_bindings
                    ],
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
            or active_value.get("capability_bindings", [])
            != [registry._binding_snapshot_payload(binding) for binding in active.capability_bindings]
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
        return PatchSetRevision(
            registry_revision,
            active_revision,
            tuple(item.patch_revision_id for item in selected),
            self._resolve_capability_bindings(tuple(selected), active_revision),
        )

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
    def _binding_snapshot_payload(binding: ReadOnlyCapabilityBinding) -> dict[str, str]:
        return {
            "binding_ref": binding.binding_ref,
            "package_revision": binding.package_revision,
            "content_digest": binding.content_digest,
            "declaration_digest": binding.declaration_digest,
            "descriptor_ref": binding.descriptor_ref,
            "descriptor_revision": binding.descriptor_revision,
            "active_patch_set_revision": binding.active_patch_set_revision,
        }

    @staticmethod
    def _resolve_capability_bindings(
        selected: tuple[GameplayPatchManifest, ...],
        active_patch_set_revision: str,
    ) -> tuple[ReadOnlyCapabilityBinding, ...]:
        # The catalog is immutable/read-only.  Package content cannot nominate
        # a descriptor, owner, stream, event, receipt, or settlement fragment.
        from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog

        descriptors = GovernedAuthorityContractCatalog.descriptors()
        bindings: list[ReadOnlyCapabilityBinding] = []
        for manifest in selected:
            extension = manifest.platform_extension
            if extension is None:
                continue
            declarations = {
                declaration.declaration_ref: declaration
                for declaration in extension.outcome_declarations
            }
            for request in extension.capability_binding_requests:
                declaration = declarations[request.declaration_ref]
                capability_matches = tuple(
                    descriptor
                    for descriptor in descriptors
                    if descriptor.capability_ref == request.capability_ref
                )
                if not capability_matches:
                    raise GameplayPatchRuntimeError("patch_capability_binding_unknown")
                matches = tuple(
                    descriptor
                    for descriptor in capability_matches
                    if descriptor.outcome_family_ref == declaration.outcome_family_ref
                )
                if not matches:
                    raise GameplayPatchRuntimeError("patch_capability_binding_mismatch")
                if len(matches) != 1:
                    raise GameplayPatchRuntimeError("patch_capability_binding_ambiguous")
                descriptor = matches[0]
                predicate_families = tuple(
                    requirement.predicate_family_ref
                    for requirement in request.typed_read_requirements
                )
                if (
                    predicate_families != descriptor.allowed_predicate_family_refs
                    or request.proposal_effect_types != descriptor.allowed_proposal_effect_types
                ):
                    raise GameplayPatchRuntimeError("patch_capability_binding_mismatch")
                bindings.append(
                    ReadOnlyCapabilityBinding(
                        binding_ref=request.binding_ref,
                        package_revision=manifest.patch_revision_id,
                        content_digest=manifest.content_digest,
                        declaration_digest=declaration.declaration_digest,
                        descriptor_ref=descriptor.descriptor_ref,
                        descriptor_revision=descriptor.descriptor_revision,
                        active_patch_set_revision=active_patch_set_revision,
                    )
                )
        return tuple(bindings)

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
