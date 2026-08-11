from __future__ import annotations

import re

from pydantic import Field, model_validator

from app.gameplay.p5.contracts import (
    P5FrozenModel,
    P5RevisionVector,
    P5ResolutionRequest,
    P5SchemaPin,
    QuestPackageDefinition,
    canonical_sha256_digest,
)


def _stable_unique(values: tuple[str, ...], error_code: str) -> tuple[str, ...]:
    if len(set(values)) != len(values):
        raise ValueError(error_code)
    return values


class TrustedEvidenceProvider(P5FrozenModel):
    provider_ref: str = Field(min_length=1)
    provider_revision: str = Field(min_length=1)
    provider_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    allowed_evidence_kinds: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_provider(self) -> "TrustedEvidenceProvider":
        _stable_unique(self.allowed_evidence_kinds, "p5_provider_evidence_kinds_must_be_unique")
        return self


class OwnerAdapterAllowance(P5FrozenModel):
    owner_ref: str = Field(min_length=1)
    allowed_event_names: tuple[str, ...] = Field(min_length=1)
    allowed_stream_grammar_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_owner(self) -> "OwnerAdapterAllowance":
        _stable_unique(self.allowed_event_names, "p5_owner_allowed_events_must_be_unique")
        _stable_unique(self.allowed_stream_grammar_refs, "p5_owner_stream_grammars_must_be_unique")
        return self


class P5EventCatalogEntry(P5FrozenModel):
    event_name: str = Field(min_length=1)
    namespace_ref: str = Field(min_length=1)
    schema_ref: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    stream_grammar_ref: str = Field(min_length=1)


class P5EventNamespace(P5FrozenModel):
    namespace_ref: str = Field(min_length=1)
    event_name_prefix: str = Field(min_length=1)
    allowed_event_names: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_namespace(self) -> "P5EventNamespace":
        _stable_unique(self.allowed_event_names, "p5_event_namespace_duplicate_event")
        for event_name in self.allowed_event_names:
            if not event_name.startswith(self.event_name_prefix):
                raise ValueError("p5_event_namespace_prefix_mismatch")
        return self


class P5StreamGrammar(P5FrozenModel):
    grammar_ref: str = Field(min_length=1)
    pattern: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_pattern(self) -> "P5StreamGrammar":
        try:
            re.compile(self.pattern)
        except re.error as exc:  # pragma: no cover - defensive validation
            raise ValueError("p5_stream_grammar_pattern_invalid") from exc
        return self


class P5PolicyRegistry(P5FrozenModel):
    registry_ref: str = Field(min_length=1)
    registry_revision: str = Field(min_length=1)
    registry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    trusted_evidence_providers: tuple[TrustedEvidenceProvider, ...] = Field(min_length=1)
    owner_adapter_allowlist: tuple[OwnerAdapterAllowance, ...] = Field(min_length=1)
    quest_packages: tuple[QuestPackageDefinition, ...] = Field(min_length=1)
    ruleset_revisions: tuple[str, ...] = Field(min_length=1)
    schema_pins: tuple[P5SchemaPin, ...] = Field(min_length=1)
    event_namespaces: tuple[P5EventNamespace, ...] = Field(min_length=1)
    event_catalog: tuple[P5EventCatalogEntry, ...] = Field(min_length=1)
    stream_grammars: tuple[P5StreamGrammar, ...] = Field(min_length=1)

    @classmethod
    def build(
        cls,
        *,
        registry_ref: str,
        registry_revision: str,
        trusted_evidence_providers: tuple[TrustedEvidenceProvider, ...],
        owner_adapter_allowlist: tuple[OwnerAdapterAllowance, ...],
        quest_packages: tuple[QuestPackageDefinition, ...],
        ruleset_revisions: tuple[str, ...],
        schema_pins: tuple[P5SchemaPin, ...],
        event_namespaces: tuple[P5EventNamespace, ...],
        event_catalog: tuple[P5EventCatalogEntry, ...],
        stream_grammars: tuple[P5StreamGrammar, ...],
    ) -> "P5PolicyRegistry":
        registry_digest = cls.compute_digest(
            registry_ref=registry_ref,
            registry_revision=registry_revision,
            trusted_evidence_providers=trusted_evidence_providers,
            owner_adapter_allowlist=owner_adapter_allowlist,
            quest_packages=quest_packages,
            ruleset_revisions=ruleset_revisions,
            schema_pins=schema_pins,
            event_namespaces=event_namespaces,
            event_catalog=event_catalog,
            stream_grammars=stream_grammars,
        )
        return cls(
            registry_ref=registry_ref,
            registry_revision=registry_revision,
            registry_digest=registry_digest,
            trusted_evidence_providers=trusted_evidence_providers,
            owner_adapter_allowlist=owner_adapter_allowlist,
            quest_packages=quest_packages,
            ruleset_revisions=ruleset_revisions,
            schema_pins=schema_pins,
            event_namespaces=event_namespaces,
            event_catalog=event_catalog,
            stream_grammars=stream_grammars,
        )

    @classmethod
    def compute_digest(
        cls,
        *,
        registry_ref: str,
        registry_revision: str,
        trusted_evidence_providers: tuple[TrustedEvidenceProvider, ...],
        owner_adapter_allowlist: tuple[OwnerAdapterAllowance, ...],
        quest_packages: tuple[QuestPackageDefinition, ...],
        ruleset_revisions: tuple[str, ...],
        schema_pins: tuple[P5SchemaPin, ...],
        event_namespaces: tuple[P5EventNamespace, ...],
        event_catalog: tuple[P5EventCatalogEntry, ...],
        stream_grammars: tuple[P5StreamGrammar, ...],
    ) -> str:
        payload = {
            "registry_ref": registry_ref,
            "registry_revision": registry_revision,
            "trusted_evidence_providers": sorted(
                (provider.model_dump(mode="json") for provider in trusted_evidence_providers),
                key=lambda value: (value["provider_ref"], value["provider_revision"]),
            ),
            "owner_adapter_allowlist": sorted(
                (owner.model_dump(mode="json") for owner in owner_adapter_allowlist),
                key=lambda value: value["owner_ref"],
            ),
            "quest_packages": sorted(
                (
                    {
                        **package.model_dump(mode="json"),
                        "objectives": sorted(
                            (objective.model_dump(mode="json") for objective in package.objectives),
                            key=lambda value: value["objective_ref"],
                        ),
                    }
                    for package in quest_packages
                ),
                key=lambda value: (value["package_ref"], value["package_revision"]),
            ),
            "ruleset_revisions": sorted(ruleset_revisions),
            "schema_pins": sorted(
                (schema.model_dump(mode="json") for schema in schema_pins),
                key=lambda value: (value["schema_ref"], value["schema_version"]),
            ),
            "event_namespaces": sorted(
                (namespace.model_dump(mode="json") for namespace in event_namespaces),
                key=lambda value: value["namespace_ref"],
            ),
            "event_catalog": sorted(
                (entry.model_dump(mode="json") for entry in event_catalog),
                key=lambda value: (value["event_name"], value["schema_version"]),
            ),
            "stream_grammars": sorted(
                (grammar.model_dump(mode="json") for grammar in stream_grammars),
                key=lambda value: value["grammar_ref"],
            ),
        }
        return canonical_sha256_digest(payload)

    @model_validator(mode="after")
    def _validate_registry(self) -> "P5PolicyRegistry":
        provider_refs = tuple(provider.provider_ref for provider in self.trusted_evidence_providers)
        owner_refs = tuple(owner.owner_ref for owner in self.owner_adapter_allowlist)
        package_keys = tuple(f"{package.package_ref}@{package.package_revision}" for package in self.quest_packages)
        ruleset_revisions = self.ruleset_revisions
        schema_keys = tuple(f"{schema.schema_ref}@{schema.schema_version}" for schema in self.schema_pins)
        namespace_refs = tuple(namespace.namespace_ref for namespace in self.event_namespaces)
        event_keys = tuple(f"{entry.event_name}@{entry.schema_version}" for entry in self.event_catalog)
        grammar_refs = tuple(grammar.grammar_ref for grammar in self.stream_grammars)
        _stable_unique(provider_refs, "p5_provider_duplicate")
        _stable_unique(owner_refs, "p5_owner_duplicate")
        _stable_unique(package_keys, "p5_package_duplicate")
        _stable_unique(ruleset_revisions, "p5_ruleset_duplicate")
        _stable_unique(schema_keys, "p5_schema_duplicate")
        _stable_unique(namespace_refs, "p5_event_namespace_duplicate")
        _stable_unique(event_keys, "p5_event_duplicate")
        _stable_unique(grammar_refs, "p5_stream_grammar_duplicate")

        for entry in self.event_catalog:
            self.require_event_namespace_for_event(entry.namespace_ref, entry.event_name)
            self.require_schema(entry.schema_ref, entry.schema_version)
            self.require_stream_grammar(entry.stream_grammar_ref)

        expected_digest = self.compute_digest(
            registry_ref=self.registry_ref,
            registry_revision=self.registry_revision,
            trusted_evidence_providers=self.trusted_evidence_providers,
            owner_adapter_allowlist=self.owner_adapter_allowlist,
            quest_packages=self.quest_packages,
            ruleset_revisions=self.ruleset_revisions,
            schema_pins=self.schema_pins,
            event_namespaces=self.event_namespaces,
            event_catalog=self.event_catalog,
            stream_grammars=self.stream_grammars,
        )
        if self.registry_digest != expected_digest:
            raise ValueError("p5_policy_registry_digest_mismatch")

        for owner in self.owner_adapter_allowlist:
            for grammar_ref in owner.allowed_stream_grammar_refs:
                self.require_stream_grammar(grammar_ref)
        return self

    def require_provider(self, provider_ref: str) -> TrustedEvidenceProvider:
        for provider in self.trusted_evidence_providers:
            if provider.provider_ref == provider_ref:
                return provider
        raise ValueError("p5_provider_untrusted")

    def require_owner_adapter(self, owner_ref: str) -> OwnerAdapterAllowance:
        for owner in self.owner_adapter_allowlist:
            if owner.owner_ref == owner_ref:
                return owner
        raise ValueError("p5_owner_adapter_unregistered")

    def require_package(self, package_ref: str, package_revision: str) -> QuestPackageDefinition:
        for package in self.quest_packages:
            if package.package_ref == package_ref and package.package_revision == package_revision:
                return package
        raise ValueError("p5_package_revision_unregistered")

    def require_ruleset_revision(self, ruleset_revision: str) -> str:
        if ruleset_revision not in self.ruleset_revisions:
            raise ValueError("p5_ruleset_revision_unregistered")
        return ruleset_revision

    def require_schema(self, schema_ref: str, schema_version: int) -> P5SchemaPin:
        for schema in self.schema_pins:
            if schema.schema_ref == schema_ref and schema.schema_version == schema_version:
                return schema
        raise ValueError("p5_schema_unregistered")

    def require_schema_pin(self, required_schema_pin: P5SchemaPin) -> P5SchemaPin:
        schema_pin = self.require_schema(required_schema_pin.schema_ref, required_schema_pin.schema_version)
        if schema_pin.schema_digest != required_schema_pin.schema_digest:
            raise ValueError("p5_schema_unregistered")
        return schema_pin

    def require_event_namespace(self, namespace_ref: str) -> P5EventNamespace:
        for namespace in self.event_namespaces:
            if namespace.namespace_ref == namespace_ref:
                return namespace
        raise ValueError("p5_event_namespace_unregistered")

    def require_event_namespace_for_event(self, namespace_ref: str, event_name: str) -> P5EventNamespace:
        namespace = self.require_event_namespace(namespace_ref)
        if event_name not in namespace.allowed_event_names:
            raise ValueError("p5_event_namespace_event_mismatch")
        return namespace

    def require_event(self, event_name: str, schema_version: int) -> P5EventCatalogEntry:
        has_name = False
        for entry in self.event_catalog:
            if entry.event_name != event_name:
                continue
            has_name = True
            if entry.schema_version == schema_version:
                self.require_event_namespace_for_event(entry.namespace_ref, event_name)
                return entry
        if has_name:
            raise ValueError("p5_event_schema_unregistered")
        raise ValueError("p5_event_unregistered")

    def require_stream_grammar(self, grammar_ref: str) -> P5StreamGrammar:
        for grammar in self.stream_grammars:
            if grammar.grammar_ref == grammar_ref:
                return grammar
        raise ValueError("p5_stream_grammar_unregistered")

    def require_stream(self, stream_ref: str, grammar_ref: str) -> str:
        grammar = self.require_stream_grammar(grammar_ref)
        if re.fullmatch(grammar.pattern, stream_ref) is None:
            raise ValueError("p5_stream_grammar_mismatch")
        return stream_ref

    def _require_registered_stream_ref(self, stream_ref: str) -> str:
        for grammar in self.stream_grammars:
            if re.fullmatch(grammar.pattern, stream_ref) is not None:
                return stream_ref
        raise ValueError("p5_stream_grammar_unregistered")

    def _validate_revision_vector_streams(self, revision_vector: P5RevisionVector) -> None:
        for stream_ref in revision_vector.entries:
            self._require_registered_stream_ref(stream_ref)

    def validate_request(self, request: P5ResolutionRequest) -> P5ResolutionRequest:
        request = P5ResolutionRequest.model_validate(
            {field_name: getattr(request, field_name) for field_name in P5ResolutionRequest.model_fields}
        )
        if (
            request.registry_ref != self.registry_ref
            or request.registry_revision != self.registry_revision
            or request.registry_digest != self.registry_digest
        ):
            raise ValueError("p5_policy_registry_pin_mismatch")

        self.require_provider(request.evidence_provider_ref)
        owner = self.require_owner_adapter(request.owner_adapter_ref)
        package = self.require_package(request.package_ref, request.package_revision)
        self.require_ruleset_revision(request.ruleset_revision)
        if package.ruleset_revision != request.ruleset_revision:
            raise ValueError("p5_ruleset_revision_unregistered")
        self._validate_revision_vector_streams(request.expected_revisions)
        self._validate_revision_vector_streams(request.read_set_revisions)
        for required_schema_pin in request.required_schema_pins:
            self.require_schema_pin(required_schema_pin)

        required_schema_keys = {
            f"{schema_pin.schema_ref}@{schema_pin.schema_version}"
            for schema_pin in request.required_schema_pins
        }

        for proposed_event in request.proposed_events:
            event_entry = self.require_event(proposed_event.event_name, proposed_event.schema_version)
            if event_entry.event_name not in owner.allowed_event_names:
                raise ValueError("p5_owner_event_disallowed")
            if event_entry.stream_grammar_ref not in owner.allowed_stream_grammar_refs:
                raise ValueError("p5_owner_stream_grammar_disallowed")
            self.require_schema(event_entry.schema_ref, event_entry.schema_version)
            self.require_stream(proposed_event.stream_ref, event_entry.stream_grammar_ref)
            if proposed_event.stream_ref not in request.expected_revisions.entries:
                raise ValueError("p5_write_revision_missing")
            schema_key = f"{event_entry.schema_ref}@{event_entry.schema_version}"
            if schema_key not in required_schema_keys:
                raise ValueError("p5_required_schema_pin_missing")
        return request


__all__ = [
    "OwnerAdapterAllowance",
    "P5EventCatalogEntry",
    "P5EventNamespace",
    "P5PolicyRegistry",
    "P5StreamGrammar",
    "TrustedEvidenceProvider",
]
