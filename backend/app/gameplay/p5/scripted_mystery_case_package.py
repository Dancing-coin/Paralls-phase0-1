"""Immutable Stormnight package authoring and binding proof.

This module deliberately wraps the existing Manifest v3/platform 2.0 models;
it does not install a new runtime or mutate the global catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel
from app.gameplay.p5.scripted_mystery_content import CaseContentAdmissionResult, ScriptedMysteryCaseContent, stormnight_case_content
from app.gameplay.patch_runtime import (
    CapabilityBindingRequest,
    GameplayPatchManifest,
    NormalizedOutcomeDeclaration,
    PackageDefinition,
    PackageIdentity,
    PlatformExtension,
    ReplayReaderRef,
    TypedReadRequirement,
    _canonical_digest,
)


class CasePackageBinding(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_ref: str = Field(min_length=1)
    descriptor_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    declaration_ref: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    declaration_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    active_set_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_ref: str = "authority:p5:scripted-mystery-case"
    privacy_scope: str = "project"


@dataclass(frozen=True)
class StormnightCasePackage:
    content: ScriptedMysteryCaseContent
    manifest: GameplayPatchManifest
    binding: CasePackageBinding

    @property
    def canonical_content_digest(self) -> str:
        return self.manifest.content_digest

    @property
    def canonical_declaration_digest(self) -> str:
        return self.manifest.platform_extension.outcome_declarations[0].declaration_digest  # type: ignore[union-attr]

    def validate(self) -> None:
        if self.manifest.content_digest != self.manifest.expected_content_digest():
            raise ValueError("stormnight_manifest_content_digest_mismatch")
        extension = self.manifest.platform_extension
        if extension is None or len(extension.outcome_declarations) != 1 or len(extension.capability_binding_requests) != 1:
            raise ValueError("stormnight_binding_cardinality_invalid")
        declaration = extension.outcome_declarations[0]
        binding = extension.capability_binding_requests[0]
        if self.binding.package_revision != self.manifest.patch_revision_id:
            raise ValueError("stormnight_binding_package_revision_mismatch")
        if self.binding.content_digest != self.manifest.content_digest:
            raise ValueError("stormnight_binding_content_digest_mismatch")
        if self.binding.declaration_digest != declaration.declaration_digest:
            raise ValueError("stormnight_binding_declaration_digest_mismatch")
        if self.binding.binding_ref != binding.binding_ref or self.binding.declaration_ref != declaration.declaration_ref:
            raise ValueError("stormnight_binding_identity_mismatch")


def build_stormnight_case_package(
    content: ScriptedMysteryCaseContent | None = None,
    *,
    untrusted_content_digest_claim: str | None = None,
    untrusted_declaration_digest_claim: str | None = None,
) -> StormnightCasePackage:
    content = content or stormnight_case_content()
    admission = CaseContentAdmissionResult.admit(
        content,
        admitted_action_graph_refs=content.action_graph_refs,
        admitted_predicate_refs=(
            "predicate:stormnight:inspect@1",
            "predicate:stormnight:phase-transition@1",
        ),
    )
    if not admission.accepted or admission.content_digest is None:
        raise ValueError(admission.error_code or "stormnight_content_not_admitted")
    if untrusted_content_digest_claim is not None and untrusted_content_digest_claim != admission.content_digest:
        raise ValueError("stormnight_content_digest_claim_mismatch")

    package_revision = content.package_revision
    definition_ref = "definition:stormnight-copper-sanatorium@1"
    declaration_ref = "declaration:stormnight-copper-sanatorium@1"
    binding_ref = "binding:stormnight-copper-sanatorium@1"
    capability_ref = "capability:scripted-mystery-case@1"
    descriptor_ref = "descriptor:scripted-mystery-case@1"
    typed_content = content.model_dump(mode="json")
    package_definition = PackageDefinition(
        definition_ref=definition_ref,
        definition_schema_ref="schema:scripted-mystery-case@1",
        source_package_revision=package_revision,
        typed_content=typed_content,
    )
    declaration_payload = {
        "declaration_ref": declaration_ref,
        "outcome_family_ref": "outcome:scripted-mystery-case@1",
        "definition_refs": [definition_ref],
        "eligibility_refs": [content.case_ref],
        "policy_revision_ref": "policy:scripted-mystery-case@1",
        "source_package_revision": package_revision,
    }
    declaration_digest = _canonical_digest(declaration_payload)
    if untrusted_declaration_digest_claim is not None and untrusted_declaration_digest_claim != declaration_digest:
        raise ValueError("stormnight_declaration_digest_claim_mismatch")
    declaration = NormalizedOutcomeDeclaration.model_validate({**declaration_payload, "declaration_digest": declaration_digest})
    binding = CapabilityBindingRequest(
        binding_ref=binding_ref,
        capability_ref=capability_ref,
        source_package_revision=package_revision,
        declaration_ref=declaration_ref,
        typed_read_requirements=(
            TypedReadRequirement(
                requirement_ref="requirement:scripted-mystery-case@1",
                predicate_family_ref="predicate:scripted-mystery-case@1",
                subject_slot_ref="slot:case-project@1",
            ),
        ),
        proposal_effect_types=("effect:scripted-mystery-case@1",),
    )
    extension = PlatformExtension(
        platform_schema_version="2.0",
        package_identity=PackageIdentity(
            package_id=content.package_ref,
            package_version="1.0.0",
            package_revision=package_revision,
        ),
        package_definitions=(package_definition,),
        outcome_declarations=(declaration.model_dump(mode="json"),),
        capability_binding_requests=(binding,),
        dependency_and_conflict_refs=(),
        replay_reader_refs=(
            ReplayReaderRef(reader_ref="reader:scripted-mystery-case-tail@1", reader_revision="reader:scripted-mystery-case-tail@1", replay_mode="checkpoint-tail"),
            ReplayReaderRef(reader_ref="reader:scripted-mystery-case-full@1", reader_revision="reader:scripted-mystery-case-full@1", replay_mode="full"),
        ),
        verification_profile_refs=("verification:stormnight-copper-sanatorium@1",),
    )
    manifest = GameplayPatchManifest(
        manifest_schema_version=3,
        patch_id=content.package_ref,
        patch_version="1.0.0",
        patch_revision_id=package_revision,
        content_digest="sha256:" + "0" * 64,
        author_id="author:repo",
        trust_policy_ref="trust:repo",
        dependencies=(),
        state_group_ids=(),
        state_group_migrations=(),
        event_schemas=(),
        rules=(),
        requested_capabilities=(),
        economic_outcomes=(),
        granted_effect_types=(),
        verification_profiles=(),
        platform_extension=extension.model_dump(mode="json"),
    )
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()}, deep=True)
    package = StormnightCasePackage(
        content=content,
        manifest=manifest,
        binding=CasePackageBinding(
            binding_ref=binding_ref,
            descriptor_ref=descriptor_ref,
            capability_ref=capability_ref,
            declaration_ref=declaration_ref,
            package_revision=package_revision,
            content_digest=manifest.content_digest,
            declaration_digest=declaration_digest,
            active_set_digest=_canonical_digest({"package_revision": package_revision, "binding_ref": binding_ref}),
        ),
    )
    package.validate()
    return package


def load_stormnight_case_package() -> StormnightCasePackage:
    return build_stormnight_case_package()


def resolve_exact_one_binding(bindings: Iterable[CasePackageBinding], binding_ref: str) -> CasePackageBinding:
    matches = tuple(binding for binding in bindings if binding.binding_ref == binding_ref)
    if len(matches) != 1:
        raise ValueError("stormnight_binding_exact_one_required")
    return matches[0]


__all__ = ["CasePackageBinding", "StormnightCasePackage", "build_stormnight_case_package", "load_stormnight_case_package", "resolve_exact_one_binding"]
