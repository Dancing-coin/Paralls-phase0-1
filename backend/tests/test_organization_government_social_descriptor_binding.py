from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.gameplay.patch_runtime import (
    CapabilityBindingRequest,
    GameplayPatchManifest,
    GameplayPatchRegistry,
    GameplayPatchRuntimeError,
    OutcomeDeclarationAuthorInput,
    PackageDefinition,
    PackageIdentity,
    PlatformExtension,
    TypedReadRequirement,
    _canonical_digest,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.gameplay.organization_government_social_platform_runtime import (
    GovernmentPolicyLifecycleIntent,
    GovernmentTaxTreasuryProjectIntent,
    OrganizationLifecycleIntent,
    OrganizationMembershipDelegationIntent,
    OrganizationOperatingPeriodIntent,
    OrganizationCommitmentBudgetIntent,
    PopulationSignalMaterializationProposalIntent,
    SocialIdentityRelationshipIntent,
)
from app.gameplay.p5.social_knowledge import SocialFactAuthority


PACKAGE_REVISION = "package:ogs-millers:v1"
DECLARATION_REF = "declaration:ogs-millers-lifecycle@1"
BINDING_REF = "binding:ogs-millers-lifecycle@1"


def _manifest(*, family_ref: str = "organization_lifecycle@1") -> GameplayPatchManifest:
    is_government = family_ref == "government_jurisdiction_policy@1"
    is_population = family_ref == "population_signal_materialization@1"
    is_social = family_ref == "social_identity_relationship@1"
    is_case = family_ref == "government_permit_inspection_enforcement@1"
    is_tax = family_ref == "government_tax_treasury_project@1"
    is_notice = family_ref == "government_notice_audit@1"
    is_group = family_ref == "social_household_group@1"
    is_conflict = family_ref == "social_norm_conflict@1"
    is_private = family_ref == "social_private_projection@1"
    is_membership = family_ref == "organization_membership_delegation@1"
    is_period = family_ref == "organization_operating_period@1"
    is_commitment = family_ref == "organization_commitment_budget@1"
    slug = ("government-policy" if is_government else "population-materialization" if is_population else "social-relationship" if is_social else "government-case" if is_case else "government-tax" if is_tax else "government-notice" if is_notice else "social-group" if is_group else "social-conflict" if is_conflict else "social-private" if is_private else "ogs-millers")
    package_revision = f"package:{slug}:v1"
    definition_ref = f"definition:{slug}@1"
    unique_family = is_government or is_population or is_social or is_case or is_tax or is_notice or is_group or is_conflict or is_private or is_membership or is_period or is_commitment
    declaration_ref = f"declaration:{slug}@1" if unique_family else DECLARATION_REF
    binding_ref = f"binding:{slug}@1" if unique_family else BINDING_REF
    outcome_ref = f"outcome:{family_ref.replace('_', '-')}"
    capability_ref = f"capability:{family_ref.replace('_', '-')}"
    predicate_ref = f"predicate:{family_ref.replace('_', '-')}"
    effect_ref = f"effect:{family_ref.replace('_', '-')}"
    typed_content = (
        {
            "policy_ref": "policy:riverward-milling@1",
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "policy_kind": "permit",
            "calendar_ref": "calendar:riverward@1",
            "activation_mode": "explicit_owner_event",
            "delegation_evidence_kind_ref": "evidence:government-delegation@1",
        }
        if is_government
        else {
            "materialization_policy_ref": "policy:riverward-organization-materialization@1",
            "target_subject_kind": "organization",
            "required_signal_kind_refs": (),
            "identity_policy_ref": "policy:riverward-identity@1",
        }
        if is_population
        else {
            "relationship_ref": "relationship:ada-bryn@1",
            "relationship_kind_ref": "relationship-kind:colleague@1",
            "acceptance_policy_ref": "policy:relationship-mutual@1",
            "required_party_count": 2,
            "shared_visibility_scope": "project",
        }
        if is_social
        else {
            "permit_policy_ref": "policy:permit@1", "jurisdiction_ref": "jurisdiction:riverward@1",
            "activity_kind_refs": (), "inspection_policy_ref": "policy:inspection@1", "appeal_policy_ref": "policy:appeal@1",
        }
        if is_case
        else {
            "tax_policy_ref": "policy:tax@1", "jurisdiction_ref": "jurisdiction:riverward@1", "currency_ref": "currency:local@1",
            "tax_kind_ref": "tax-kind:sales@1", "rate_basis_points": 500, "treasury_budget_policy_ref": "policy:treasury@1",
        }
        if is_tax
        else {
            "public_project_policy_ref": "policy:public-project@1", "jurisdiction_ref": "jurisdiction:riverward@1",
            "project_kind_ref": "project-kind:notice@1", "audit_policy_ref": "policy:audit@1",
        }
        if is_notice
        else {
            "group_ref": "group:millers@1", "group_schema_ref": "schema:social-group@1",
            "membership_policy_ref": "policy:membership@1", "representative_role_refs": (),
        }
        if is_group
        else {
            "norm_policy_ref": "policy:norm@1", "conflict_kind_ref": "conflict-kind:dispute@1",
            "mediation_policy_ref": "policy:mediation@1", "appeal_policy_ref": "policy:appeal@1", "allowed_resolution_refs": (),
        }
        if is_conflict
        else {
            "identity_schema_ref": "schema:social-identity@1", "subject_kind": "character", "identity_policy_ref": "policy:identity@1",
        }
        if is_private
        else {
            "role_ref": "role:steward@1", "organization_ref": "organization:millers@1",
            "delegation_policy_ref": "policy:millers-delegation@1", "allowed_capability_refs": (),
        }
        if is_membership
        else {
            "operating_period_policy_ref": "policy:operating@1", "organization_ref": "organization:millers@1",
            "calendar_ref": "calendar:riverward@1", "minimum_window_ticks": 1, "contribution_evidence_kind_refs": (),
        }
        if is_period
        else {
            "commitment_policy_ref": "policy:commitment@1", "organization_ref": "organization:millers@1",
            "budget_policy_ref": "policy:budget@1", "allowed_commitment_kind_refs": (),
        }
        if is_commitment
        else {
            "organization_ref": "organization:millers@1",
            "organization_schema_ref": "schema:organization@1",
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "charter_policy_ref": "policy:ogs-millers-charter@1",
            "role_policy_refs": (),
        }
    )
    declaration_payload = {
        "declaration_ref": declaration_ref,
        "outcome_family_ref": outcome_ref,
        "definition_refs": (definition_ref,),
        "eligibility_refs": ("eligibility:organization-charter@1",),
        "policy_revision_ref": "policy:ogs-millers-charter@1",
        "source_package_revision": package_revision,
    }
    declaration = {**declaration_payload, "declaration_digest": _canonical_digest(declaration_payload)}
    extension = PlatformExtension(
        platform_schema_version="2.0",
        package_identity=PackageIdentity(
            package_id=f"package:{slug}", package_version="1.0.0", package_revision=package_revision
        ),
        package_definitions=(
            PackageDefinition(
                definition_ref=definition_ref,
                definition_schema_ref=("schema:organization-role-delegation@1" if is_membership else "schema:organization-operating-period@1" if is_period else "schema:organization-commitment@1" if is_commitment else "schema:organization@1"),
                source_package_revision=package_revision,
                typed_content=typed_content,
            ),
        ),
        outcome_declarations=(declaration,),
        capability_binding_requests=(
            CapabilityBindingRequest(
                binding_ref=binding_ref,
                capability_ref=capability_ref,
                source_package_revision=package_revision,
                declaration_ref=declaration_ref,
                typed_read_requirements=(
                    TypedReadRequirement(
                        requirement_ref=f"requirement:{family_ref.replace('_', '-')}@1",
                        predicate_family_ref=predicate_ref,
                        subject_slot_ref="slot:organization@1",
                    ),
                ),
                proposal_effect_types=(effect_ref,),
            ),
        ),
        dependency_and_conflict_refs=(), replay_reader_refs=(), verification_profile_refs=(),
    )
    manifest = GameplayPatchManifest(
        manifest_schema_version=3,
        patch_id=f"package:{slug}",
        patch_version="1.0.0",
        patch_revision_id=package_revision,
        content_digest="sha256:" + "0" * 64,
        author_id="author:repo",
        trust_policy_ref="trust:repo",
        platform_extension=extension.model_dump(mode="json"),
    )
    return manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})


def test_ogs_activation_derives_exact_one_binding_and_replay_pins() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    registry.install(manifest)
    active = registry.activate((PACKAGE_REVISION,))

    assert len(active.capability_bindings) == 1
    binding = active.capability_bindings[0]
    assert binding.binding_ref == BINDING_REF
    assert binding.package_revision == PACKAGE_REVISION
    assert binding.content_digest == manifest.content_digest
    assert binding.declaration_ref == DECLARATION_REF
    assert binding.descriptor_ref == "descriptor:organization-lifecycle@1"
    assert binding.active_patch_set_revision == active.active_patch_set_revision
    assert binding.family_content_digest == _canonical_digest(
        manifest.platform_extension.package_definitions[0].typed_content  # type: ignore[union-attr]
    )

    replayed = GameplayPatchRegistry.from_snapshot(
        registry.export_snapshot(), trusted_authors=frozenset({"author:repo"})
    )
    assert replayed.active_patch_set == active


def test_ogs_activation_rejects_tampered_typed_content_before_active_set_write() -> None:
    manifest = _manifest()
    extension = manifest.platform_extension
    assert extension is not None
    definition = extension.package_definitions[0].model_copy(
        update={"typed_content": {**extension.package_definitions[0].typed_content, "owner_ref": "forged"}},
        deep=True,
    )
    tampered_extension = extension.model_copy(update={"package_definitions": (definition,)}, deep=True)
    tampered = manifest.model_copy(update={"platform_extension": tampered_extension}, deep=True)
    tampered = tampered.model_copy(update={"content_digest": tampered.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(tampered)

    with pytest.raises(GameplayPatchRuntimeError, match="patch_capability_binding_content_invalid"):
        registry.activate((PACKAGE_REVISION,))
    assert registry.active_patch_set is None


def test_ogs_organization_append_derives_all_activation_pins_from_exact_binding() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    registry.install(manifest)
    active = registry.activate((PACKAGE_REVISION,))
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store, package_registry=registry)

    result = authority.transition_admitted_platform_organization_lifecycle(
        intent=OrganizationLifecycleIntent(
            organization_ref="organization:millers@1",
            provenance_ref="provenance:ogs-lifecycle@1",
            source_revision_pin=0,
            from_state="draft",
            to_state="active",
        ),
        binding_ref=BINDING_REF,
        command_id="command:ogs-lifecycle-admitted",
        idempotency_key="idempotency:ogs-lifecycle-admitted",
        causation_id="cause:ogs-lifecycle-admitted",
        correlation_id="corr:ogs-lifecycle-admitted",
        expected_revision=0,
    )

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    binding = active.capability_bindings[0]
    assert event.payload["package_revision_pin"] == binding.package_revision
    assert event.payload["content_digest_pin"] == binding.content_digest
    assert event.payload["declaration_digest_pin"] == binding.declaration_digest
    assert event.payload["descriptor_pin"] == binding.descriptor_ref
    assert event.payload["active_set_digest_pin"] == binding.active_patch_set_revision


def test_ogs_government_policy_append_requires_its_own_exact_active_binding() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest(family_ref="government_jurisdiction_policy@1")
    registry.install(manifest)
    active = registry.activate(("package:government-policy:v1",))
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store, package_registry=registry)

    result = authority.record_admitted_platform_government_policy_lifecycle(
        intent=GovernmentPolicyLifecycleIntent(
            jurisdiction_ref="jurisdiction:riverward@1",
            policy_ref="policy:riverward-milling@1",
            provenance_ref="provenance:government-policy@1",
            source_revision_pin=0,
            policy_state="active",
        ),
        binding_ref="binding:government-policy@1",
        command_id="command:government-policy",
        idempotency_key="idempotency:government-policy",
        causation_id="cause:government-policy",
        correlation_id="corr:government-policy",
        expected_revision=0,
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.government.policy_lifecycle_recorded@1"
    assert event.payload["active_set_digest_pin"] == active.active_patch_set_revision


def test_ogs_population_signal_is_social_owned_public_and_does_not_create_subject() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest(family_ref="population_signal_materialization@1")
    registry.install(manifest)
    active = registry.activate(("package:population-materialization:v1",))
    assert active.capability_bindings[0].binding_ref == "binding:population-materialization@1"
    assert active.capability_bindings[0].family_ref == "population_signal_materialization@1"
    store = GameplayEventStore()
    social = SocialFactAuthority(
        registry=SimpleNamespace(registry_ref="registry:test", registry_revision="registry:test@1", registry_digest="sha256:" + "f" * 64),
        store=store,
        package_registry=registry,
    )

    result = social.record_admitted_population_signal_materialization_proposal(
        intent=PopulationSignalMaterializationProposalIntent(
            signal_ref="signal:riverward-workforce@1",
            provenance_ref="provenance:population-signal@1",
            source_revision_pin=0,
            materialization_state="proposed",
            visibility_scope="public",
        ),
        binding_ref="binding:population-materialization@1",
        command_id="command:population-signal",
        idempotency_key="idempotency:population-signal",
        causation_id="cause:population-signal",
        correlation_id="corr:population-signal",
        expected_revision=0,
    )
    assert result.receipt is not None
    event = store.get_event(result.receipt.committed_event_ids[0])
    assert event.event_type == "gameplay.social.population_signal_recorded@1"
    assert event.visibility_policy == "public"
    assert "target_owner_created" not in event.payload
    assert event.payload["active_set_digest_pin"] == active.active_patch_set_revision


def test_population_materialization_requires_identity_allocated_signal_then_existing_organization_owner() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    population_manifest = _manifest(family_ref="population_signal_materialization@1")
    organization_manifest = _manifest()
    registry.install_many((population_manifest, organization_manifest))
    registry.activate(("package:ogs-millers:v1", "package:population-materialization:v1"))
    store = GameplayEventStore()
    social = SocialFactAuthority(
        registry=SimpleNamespace(registry_ref="registry:test", registry_revision="registry:test@1", registry_digest="sha256:" + "f" * 64),
        store=store, package_registry=registry,
    )
    proposed = social.record_admitted_population_signal_materialization_proposal(
        intent=PopulationSignalMaterializationProposalIntent(
            signal_ref="signal:riverward-mill-foundation@1", provenance_ref="provenance:population@1",
            source_revision_pin=0, materialization_state="identity_allocated", visibility_scope="public",
            allocated_subject_ref="organization:population-mill@1",
        ),
        binding_ref="binding:population-materialization@1", command_id="command:population-allocated",
        idempotency_key="idempotency:population-allocated", causation_id="cause:population-allocated",
        correlation_id="corr:population-allocated", expected_revision=0,
    )
    assert proposed.receipt is not None
    source_event_id = proposed.receipt.committed_event_ids[0]
    organization = OrganizationAuthority(store=store, package_registry=registry)
    result = organization.materialize_admitted_population_organization(
        intent=OrganizationLifecycleIntent(
            organization_ref="organization:population-mill@1", provenance_ref="provenance:org-materialization@1",
            source_revision_pin=0, from_state="draft", to_state="registered",
        ),
        binding_ref=BINDING_REF, population_signal_event_id=source_event_id,
        expected_population_signal_revision=1, command_id="command:organization-created",
        idempotency_key="idempotency:organization-created", causation_id=source_event_id,
        correlation_id="corr:organization-created", expected_revision=0,
    )
    assert result.committed
    created = store.get_event(result.committed_event_ids[0])
    assert created.payload["materialization_source_event_id"] == source_event_id
    assert created.payload["materialization_source_stream_revision"] == 1


def test_social_shared_relationship_uses_package_fixed_visibility_and_exact_parties() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest(family_ref="social_identity_relationship@1")
    registry.install(manifest)
    registry.activate(("package:social-relationship:v1",))
    store = GameplayEventStore()
    social = SocialFactAuthority(
        registry=SimpleNamespace(registry_ref="registry:test", registry_revision="registry:test@1", registry_digest="sha256:" + "f" * 64),
        store=store, package_registry=registry,
    )
    result = social.record_admitted_platform_social_relationship(
        intent=SocialIdentityRelationshipIntent(
            relationship_ref="relationship:ada-bryn@1", participant_refs=("character:ada", "character:bryn"),
            provenance_ref="provenance:relationship@1", source_revision_pin=0, relationship_state="active",
        ),
        binding_ref="binding:social-relationship@1", command_id="command:relationship",
        idempotency_key="idempotency:relationship", causation_id="cause:relationship",
        correlation_id="corr:relationship", expected_revision=0,
    )
    assert result.receipt is not None
    event = store.get_event(result.receipt.committed_event_ids[0])
    assert event.visibility_policy == "project"
    assert event.payload["participant_refs"] == ["character:ada", "character:bryn"]


def test_population_signal_cannot_materialize_a_different_organization_subject() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install_many((_manifest(), _manifest(family_ref="population_signal_materialization@1")))
    registry.activate(("package:ogs-millers:v1", "package:population-materialization:v1"))
    store = GameplayEventStore()
    social = SocialFactAuthority(registry=SimpleNamespace(registry_ref="registry:test", registry_revision="registry:test@1", registry_digest="sha256:" + "f" * 64), store=store, package_registry=registry)
    signal = social.record_admitted_population_signal_materialization_proposal(
        intent=PopulationSignalMaterializationProposalIntent(signal_ref="signal:one@1", provenance_ref="provenance:one@1", source_revision_pin=0, materialization_state="identity_allocated", visibility_scope="public", allocated_subject_ref="organization:approved@1"),
        binding_ref="binding:population-materialization@1", command_id="command:signal-one", idempotency_key="idempotency:signal-one", causation_id="cause:signal-one", correlation_id="corr:signal-one", expected_revision=0,
    )
    organization = OrganizationAuthority(store=store, package_registry=registry)
    rejected = organization.materialize_admitted_population_organization(
        intent=OrganizationLifecycleIntent(organization_ref="organization:other@1", provenance_ref="provenance:other@1", source_revision_pin=0, from_state="draft", to_state="registered"),
        binding_ref=BINDING_REF, population_signal_event_id=signal.receipt.committed_event_ids[0], expected_population_signal_revision=1,
        command_id="command:wrong-target", idempotency_key="idempotency:wrong-target", causation_id="cause:wrong-target", correlation_id="corr:wrong-target", expected_revision=0,
    )
    assert not rejected.committed
    assert store.get_stream_head("gameplay:organization:organization:other@1") == 0


def test_organization_membership_has_no_unbound_append_surface() -> None:
    assert not hasattr(OrganizationAuthority, "record_platform_organization_membership_delegation")


def test_government_tax_project_is_authority_only_proposal_and_binding_bound() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    result = authority.record_admitted_platform_government_tax_project(
        intent=GovernmentTaxTreasuryProjectIntent(
            jurisdiction_ref="jurisdiction:riverward@1", project_ref="project:tax@1",
            provenance_ref="provenance:tax@1", source_revision_pin=0,
            project_state="proposed", amount_minor=10,
        ), binding_ref="binding:missing@1", command_id="command:tax", idempotency_key="idempotency:tax",
        causation_id="cause:tax", correlation_id="corr:tax", expected_revision=0,
    )
    assert not result.committed


def test_organization_period_and_commitment_require_admitted_bindings() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    period = authority.record_admitted_platform_organization_operating_period(
        intent={"organization_ref": "organization:millers@1", "period_ref": "period:spring@1", "provenance_ref": "provenance:period@1", "source_revision_pin": 0, "period_state": "open", "opens_at_tick": 1, "closes_at_tick": 2},
        binding_ref="binding:missing@1", command_id="command:period", idempotency_key="idempotency:period", causation_id="cause:period", correlation_id="corr:period", expected_revision=0,
    )
    commitment = authority.record_admitted_platform_organization_commitment_budget(
        intent={"organization_ref": "organization:millers@1", "budget_ref": "budget:spring@1", "provenance_ref": "provenance:budget@1", "source_revision_pin": 0, "budget_state": "proposed", "amount_minor": 1},
        binding_ref="binding:missing@1", command_id="command:budget", idempotency_key="idempotency:budget", causation_id="cause:budget", correlation_id="corr:budget", expected_revision=0,
    )
    assert not period.committed
    assert not commitment.committed
    assert store.get_stream_head("gameplay:organization:organization:millers@1") == 0


def test_organization_membership_admitted_write_is_exact_binding_bound() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    extension = manifest.platform_extension
    assert extension is not None
    definition = extension.package_definitions[0].model_copy(update={
        "definition_ref": "definition:membership@1",
        "definition_schema_ref": "schema:organization-role-delegation@1",
        "source_package_revision": "package:ogs-membership:v1",
        "typed_content": {
            "role_ref": "role:steward@1", "organization_ref": "organization:millers@1",
            "delegation_policy_ref": "policy:millers-delegation@1", "allowed_capability_refs": (),
        },
    }, deep=True)
    declaration_payload = {
        "declaration_ref": "declaration:membership@1", "outcome_family_ref": "outcome:organization-membership-delegation@1",
        "definition_refs": ("definition:membership@1",), "eligibility_refs": ("eligibility:organization-membership@1",),
        "policy_revision_ref": "policy:millers-delegation@1", "source_package_revision": "package:ogs-membership:v1",
    }
    declaration = {**declaration_payload, "declaration_digest": _canonical_digest(declaration_payload)}
    request = {
        "binding_ref": "binding:membership@1", "capability_ref": "capability:organization-membership-delegation@1",
        "source_package_revision": "package:ogs-membership:v1", "declaration_ref": "declaration:membership@1",
        "typed_read_requirements": ({"requirement_ref": "requirement:organization-membership@1", "predicate_family_ref": "predicate:organization-membership-delegation@1", "subject_slot_ref": "slot:organization-membership@1"},),
        "proposal_effect_types": ("effect:organization-membership-delegation@1",),
    }
    extension = extension.model_copy(update={"package_identity": PackageIdentity(package_id="package:ogs-membership", package_version="1.0.0", package_revision="package:ogs-membership:v1"), "package_definitions": (definition,), "outcome_declarations": (declaration,), "capability_binding_requests": (request,)}, deep=True)
    extension = PlatformExtension.model_validate(extension.model_dump(mode="json"))
    candidate = GameplayPatchManifest.model_validate({**manifest.model_dump(mode="json"), "patch_id": "package:ogs-membership", "patch_revision_id": "package:ogs-membership:v1", "platform_extension": extension.model_dump(mode="json")})
    candidate = candidate.model_copy(update={"content_digest": candidate.expected_content_digest()})
    registry.install(candidate)
    registry.activate(("package:ogs-membership:v1",))
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store, package_registry=registry)
    result = authority.record_admitted_platform_organization_membership(
        intent=OrganizationMembershipDelegationIntent(organization_ref="organization:millers@1", member_ref="character:ada", role_ref="role:steward@1", provenance_ref="provenance:membership@1", source_revision_pin=0, delegation_state="active"),
        binding_ref="binding:membership@1", command_id="command:membership", idempotency_key="idempotency:membership", causation_id="cause:membership", correlation_id="corr:membership", expected_revision=0,
    )
    assert result.committed
