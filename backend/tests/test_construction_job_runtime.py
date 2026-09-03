from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import Blueprint, ConstructionProductionAuthority, Plot
from app.gameplay.construction_production_content import BlueprintContent, ReservationRequirementContent, validate_permit_evidence
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry, GameplayPatchRuntimeError, _canonical_digest
from app.gameplay.event_store import GameplayEventStore


def _authority() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Plot, Blueprint]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(plot_ref="plot:job:1", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)
    blueprint = Blueprint(
        blueprint_ref="blueprint:job:mill@1",
        facility_kind="mill",
        required_permit_ref="permit:construction@1",
        revision=1,
    )
    return store, authority, plot, blueprint


def _construction_blueprint_manifest_payload(
    *,
    predicate_family_ref: str = "predicate:construction-plot-available@1",
    proposal_effect_types: tuple[str, ...] = ("effect:construction-job-placement@1",),
) -> dict[str, object]:
    payload: dict[str, object] = {
        "manifest_schema_version": 2,
        "patch_id": "package:construction-blueprint-test",
        "patch_version": "1.0.0",
        "patch_revision_id": "package:construction-blueprint-test:v1",
        "content_digest": "sha256:" + "0" * 64,
        "author_id": "author:repo",
        "trust_policy_ref": "trust:repo",
        "dependencies": [],
        "state_group_ids": [],
        "state_group_migrations": [],
        "event_schemas": [],
        "rules": [],
        "requested_capabilities": [],
        "economic_outcomes": [],
        "granted_effect_types": [],
        "verification_profiles": [],
        "platform_extension": {
            "platform_schema_version": "1.0",
            "package_identity": {
                "package_id": "package:construction-blueprint-test",
                "package_version": "1.0.0",
                "package_revision": "package:construction-blueprint-test:v1",
            },
            "package_definitions": [
                {
                    "definition_ref": "definition:construction-blueprint-test@1",
                    "definition_schema_ref": "schema:construction-blueprint@1",
                    "source_package_revision": "package:construction-blueprint-test:v1",
                    "typed_content": {
                        "blueprint_ref": "blueprint:job:mill@1",
                        "facility_definition_ref": "definition:mill@1",
                        "facility_schema_ref": "schema:facility@1",
                        "facility_kind": "mill",
                        "footprint": {"width": 2, "depth": 1},
                        "allowed_orientations": [0, 90],
                        "components": [
                            {
                                "component_ref": "component:foundation@1",
                                "component_kind": "foundation",
                                "width": 2,
                                "depth": 1,
                            }
                        ],
                        "material_requirements": {"item:stone@1": 1},
                        "tool_refs": [],
                        "qualification_refs": [],
                        "duration_ticks": 1,
                        "required_permit_ref": "permit:construction@1",
                    },
                }
            ],
            "outcome_declarations": [
                {
                    "declaration_ref": "declaration:construction-blueprint-test@1",
                    "outcome_family_ref": "outcome:construction-blueprint-placement@1",
                    "definition_refs": ["definition:construction-blueprint-test@1"],
                    "eligibility_refs": ["construction:plot-available@1"],
                    "policy_revision_ref": "policy:construction-blueprint-placement@1",
                    "source_package_revision": "package:construction-blueprint-test:v1",
                    "declaration_digest": "sha256:" + "0" * 64,
                }
            ],
            "capability_binding_requests": [
                {
                    "binding_ref": "binding:construction-blueprint-test@1",
                    "capability_ref": "capability:construction-blueprint-placement@1",
                    "source_package_revision": "package:construction-blueprint-test:v1",
                    "declaration_ref": "declaration:construction-blueprint-test@1",
                    "typed_read_requirements": [
                        {
                            "requirement_ref": "requirement:construction-plot-available@1",
                            "predicate_family_ref": predicate_family_ref,
                            "subject_slot_ref": "slot:plot@1",
                        }
                    ],
                    "proposal_effect_types": list(proposal_effect_types),
                }
            ],
            "dependency_and_conflict_refs": [],
            "replay_reader_refs": [],
            "verification_profile_refs": [],
        },
    }
    declaration = payload["platform_extension"]["outcome_declarations"][0]
    declaration["declaration_digest"] = _canonical_digest({k: v for k, v in declaration.items() if k != "declaration_digest"})
    return payload


def test_construction_job_start_commits_authoritative_grid_placement_and_replays() -> None:
    store, authority, plot, blueprint = _authority()

    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:mill:1",
        anchor=(2, 3),
        footprint=(2, 1),
        orientation=0,
        command_id="command:job-start:1",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:1:v1",
        causation_id="causation:job-start:1",
        correlation_id="correlation:job-start:1",
    )

    assert result.committed
    projection = authority.projector()
    job = projection.jobs["job:mill:1"]
    assert job.status == "started"
    assert job.occupied_cells == ((2, 3), (3, 3))
    assert authority.projector(checkpoint_at=1).jobs == projection.jobs
    assert store.read_stream("gameplay:construction_production:plot:plot:job:1")[-1].event_type.endswith(
        "construction_job_started@1"
    )


def test_construction_job_rejects_overlapping_grid_placement_without_writing() -> None:
    store, authority, plot, blueprint = _authority()
    authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:mill:1",
        anchor=(2, 3),
        footprint=(2, 1),
        orientation=0,
        command_id="command:job-start:1",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:1:v1",
        causation_id="causation:job-start:1",
        correlation_id="correlation:job-start:1",
    )
    before = tuple(store.read_events())

    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:mill:2",
        anchor=(3, 3),
        footprint=(1, 1),
        orientation=0,
        command_id="command:job-start:2",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:2:v1",
        causation_id="causation:job-start:2",
        correlation_id="correlation:job-start:2",
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_job_placement_conflict"
    assert tuple(store.read_events()) == before


def test_construction_job_completion_is_terminal_and_idempotent() -> None:
    store, authority, plot, blueprint = _authority()
    authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:mill:1",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:job-start:1",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:1:v1",
        causation_id="causation:job-start:1",
        correlation_id="correlation:job-start:1",
    )

    result = authority.complete_construction_job(
        job_ref="job:mill:1",
        expected_plot_revision=1,
        command_id="command:job-complete:1",
        idempotency_key="construction:job-complete:job:mill:1:1:v1",
        causation_id="causation:job-complete:1",
        correlation_id="correlation:job-complete:1",
    )
    duplicate = authority.complete_construction_job(
        job_ref="job:mill:1",
        expected_plot_revision=1,
        command_id="command:job-complete:duplicate",
        idempotency_key="construction:job-complete:job:mill:1:1:v1",
        causation_id="causation:job-complete:1",
        correlation_id="correlation:job-complete:1",
    )

    assert result.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert authority.projector().jobs["job:mill:1"].status == "completed"


def test_construction_job_start_rejects_blueprint_content_identity_conflict_before_append() -> None:
    store, authority, plot, blueprint = _authority()
    content = BlueprintContent.model_validate(
        {
            "blueprint_ref": blueprint.blueprint_ref,
            "facility_definition_ref": "definition:mill@1",
            "facility_schema_ref": "schema:facility@1",
            "facility_kind": "kiln",
            "footprint": {"width": 2, "depth": 1},
            "allowed_orientations": [0],
            "components": [{"component_ref": "component:foundation@1", "component_kind": "foundation", "width": 2, "depth": 1}],
            "material_requirements": {"item:stone@1": 1},
            "tool_refs": [],
            "qualification_refs": [],
            "duration_ticks": 1,
            "required_permit_ref": blueprint.required_permit_ref,
        }
    )
    before = tuple(store.read_events())

    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        content=content,
        job_ref="job:mill:identity-conflict",
        anchor=(0, 0),
        footprint=(2, 1),
        orientation=0,
        command_id="command:job-start:identity-conflict",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:identity-conflict:v1",
        causation_id="causation:identity-conflict",
        correlation_id="correlation:identity-conflict",
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_job_blueprint_binding_conflict"


def test_construction_job_rejects_caller_supplied_authority_shaped_binding_pins_before_append() -> None:
    store, authority, plot, blueprint = _authority()
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:caller-pins:1",
        anchor=(0, 0),
        footprint=(2, 1),
        orientation=0,
        command_id="command:caller-pins:1",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:caller-pins:1:v1",
        causation_id="cause:caller-pins:1",
        correlation_id="corr:caller-pins:1",
        binding_pins={"owner_ref": "caller:owner"},
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_job_binding_pins_invalid"
    assert store.read_events() == []


def test_construction_job_start_accepts_matching_blueprint_content() -> None:
    store, authority, plot, blueprint = _authority()
    content = BlueprintContent.model_validate(
        {
            "blueprint_ref": blueprint.blueprint_ref,
            "facility_definition_ref": "definition:mill@1",
            "facility_schema_ref": "schema:facility@1",
            "facility_kind": "mill",
            "footprint": {"width": 2, "depth": 1},
            "allowed_orientations": [0, 90],
            "components": [{"component_ref": "component:foundation@1", "component_kind": "foundation", "width": 2, "depth": 1}],
            "material_requirements": {"item:stone@1": 1},
            "tool_refs": [],
            "qualification_refs": [],
            "duration_ticks": 1,
            "required_permit_ref": blueprint.required_permit_ref,
        }
    )
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        content=content,
        job_ref="job:mill:matching-content",
        anchor=(0, 0),
        footprint=(2, 1),
        orientation=0,
        command_id="command:job-start:matching-content",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:matching-content:v1",
        causation_id="causation:matching-content",
        correlation_id="correlation:matching-content",
    )
    assert result.committed
    assert store.read_events()[-1].payload["blueprint_ref"] == blueprint.blueprint_ref


def test_construction_job_start_rejects_missing_owner_issued_reservation_before_append() -> None:
    store, authority, plot, blueprint = _authority()
    requirements = (
        ReservationRequirementContent(
            reservation_kind="material",
            owner_family_ref="inventory",
            reservation_ref="reservation:stone:job",
            revision=1,
        ),
    )

    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        reservation_requirements=requirements,
        reservation_refs=(),
        job_ref="job:mill:missing-reservation",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:job-start:missing-reservation",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:missing-reservation:v1",
        causation_id="causation:missing-reservation",
        correlation_id="correlation:missing-reservation",
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_job_reservation_missing"
    assert tuple(store.read_events()) == ()


def test_construction_job_start_persists_owner_reservation_evidence_for_replay() -> None:
    store, authority, plot, blueprint = _authority()
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:stone:job-proof",
        revision=1,
    )
    evidence = {
        requirement.reservation_ref: {
            "owner_family_ref": "inventory",
            "status": "active",
            "revision": 1,
        }
    }
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        reservation_requirements=(requirement,),
        reservation_refs=(requirement.reservation_ref,),
        reservation_evidence=evidence,
        job_ref="job:mill:reservation-proof",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:job-start:reservation-proof",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:reservation-proof:v1",
        causation_id="cause:reservation-proof",
        correlation_id="corr:reservation-proof",
    )
    assert result.committed
    event = store.read_events()[-1]
    assert event.payload["reservation_evidence"] == evidence
    assert authority.projector().jobs["job:mill:reservation-proof"].reservation_evidence == evidence


def test_construction_job_terminal_events_inherit_reservation_provenance() -> None:
    store, authority, plot, blueprint = _authority()
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:stone:terminal",
        revision=1,
    )
    evidence = {
        requirement.reservation_ref: {
            "owner_family_ref": "inventory",
            "status": "active",
            "revision": 1,
        }
    }
    assert authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        reservation_requirements=(requirement,),
        reservation_refs=(requirement.reservation_ref,),
        reservation_evidence=evidence,
        job_ref="job:terminal-reservation",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:terminal-reservation:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:terminal-reservation:v1",
        causation_id="cause:terminal-reservation:start",
        correlation_id="corr:terminal-reservation:start",
    ).committed
    completed = authority.complete_construction_job(
        job_ref="job:terminal-reservation",
        expected_plot_revision=1,
        command_id="command:terminal-reservation:complete",
        idempotency_key="construction:job-complete:job:terminal-reservation:1:v1",
        causation_id="cause:terminal-reservation:complete",
        correlation_id="corr:terminal-reservation:complete",
    )
    assert completed.committed
    event = store.get_event(completed.committed_event_ids[0])
    assert event.payload["reservation_refs"] == (requirement.reservation_ref,)
    assert event.payload["reservation_evidence"] == evidence


def test_construction_job_replay_rejects_tampered_reservation_evidence_shape() -> None:
    store, authority, plot, blueprint = _authority()
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:stone:job-shape",
        revision=1,
    )
    evidence = {
        requirement.reservation_ref: {
            "owner_family_ref": "inventory",
            "status": "active",
            "revision": 1,
        }
    }
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        reservation_requirements=(requirement,),
        reservation_refs=(requirement.reservation_ref,),
        reservation_evidence=evidence,
        job_ref="job:mill:reservation-shape",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:job-start:reservation-shape",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:mill:reservation-shape:v1",
        causation_id="cause:reservation-shape",
        correlation_id="corr:reservation-shape",
    )
    assert result.committed
    event = store.read_events()[-1]
    tampered = event.model_copy(
        update={"payload": {**event.payload, "reservation_evidence": {"reservation:other": evidence[requirement.reservation_ref]}}},
        deep=True,
    )
    with pytest.raises(ValueError, match="construction_job_reservation_evidence_invalid"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_construction_job_replay_rejects_missing_reservation_source_event_pin() -> None:
    store, authority, plot, blueprint = _authority()
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:stone:job-source-pin",
        revision=1,
    )
    evidence = {
        requirement.reservation_ref: {
            "owner_family_ref": "inventory",
            "status": "active",
            "revision": 1,
        }
    }
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        reservation_requirements=(requirement,),
        reservation_refs=(requirement.reservation_ref,),
        reservation_evidence=evidence,
        job_ref="job:reservation-source-pin",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:job-start:reservation-source-pin",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:reservation-source-pin:v1",
        causation_id="cause:reservation-source-pin",
        correlation_id="corr:reservation-source-pin",
    )
    assert result.committed
    event = store.read_events()[-1]
    tampered_evidence = {
        requirement.reservation_ref: {
            **evidence[requirement.reservation_ref],
            "source_event_id": "event:missing-reservation-source",
        }
    }
    tampered = event.model_copy(update={"payload": {**event.payload, "reservation_evidence": tampered_evidence}}, deep=True)
    with pytest.raises(ValueError, match="construction_job_reservation_evidence_source_missing"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_permit_evidence_requires_exact_active_jurisdiction_and_revision() -> None:
    evidence = {
        "permit_ref": "permit:construction@1",
        "jurisdiction_ref": "jurisdiction:local",
        "status": "active",
        "revision": 2,
    }
    validate_permit_evidence(
        permit_evidence=evidence,
        required_permit_ref="permit:construction@1",
        jurisdiction_ref="jurisdiction:local",
    )
    with pytest.raises(ValueError, match="permit_evidence_conflict"):
        validate_permit_evidence(
            permit_evidence={**evidence, "jurisdiction_ref": "jurisdiction:other"},
            required_permit_ref="permit:construction@1",
            jurisdiction_ref="jurisdiction:local",
        )


def test_packaged_construction_job_resolves_blueprint_from_active_immutable_manifest() -> None:
    from app.gameplay.patch_runtime import PackageDefinition, GameplayPatchRegistry

    manifest = GameplayPatchManifest.model_validate(_construction_blueprint_manifest_payload())
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    active = registry.activate((manifest.patch_revision_id,))
    binding = active.capability_bindings[0]
    definition = manifest.platform_extension.package_definitions[0]
    assert binding.content_digest == manifest.content_digest
    assert binding.family_content_digest == _canonical_digest(definition.typed_content)
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    plot = Plot(plot_ref="plot:packaged", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)

    result = authority.start_packaged_construction_job(
        plot=plot,
        package_revision=manifest.patch_revision_id,
        definition_ref="definition:construction-blueprint-test@1",
        job_ref="job:packaged:1",
        anchor=(1, 1),
        orientation=90,
        command_id="command:packaged:1",
        causation_id="cause:packaged:1",
        correlation_id="corr:packaged:1",
        permit_evidence={"permit_ref": "permit:construction@1", "jurisdiction_ref": "jurisdiction:local", "status": "active", "revision": 1},
    )

    assert result.committed
    event = store.read_events()[-1]
    assert event.payload["facility_kind"] == "mill"
    assert event.payload["package_revision"] == manifest.patch_revision_id
    assert event.payload["content_digest"] == manifest.content_digest
    assert event.payload["declaration_digest"] == manifest.platform_extension.outcome_declarations[0].declaration_digest
    assert event.payload["descriptor_ref"] == "descriptor:construction-blueprint-placement@1"
    assert event.payload["descriptor_revision"] == "descriptor:construction-blueprint-placement@1"
    assert event.payload["active_patch_set_revision"] == active.active_patch_set_revision
    assert event.payload["component_refs"] == ("component:foundation@1",)
    assert event.payload["permit_evidence"] == {
        "permit_ref": "permit:construction@1",
        "jurisdiction_ref": "jurisdiction:local",
        "status": "active",
        "revision": 1,
    }
    projected_job = authority.projector().jobs["job:packaged:1"]
    assert projected_job.binding_pins["package_revision"] == manifest.patch_revision_id
    assert projected_job.binding_pins["content_digest"] == manifest.content_digest
    assert projected_job.binding_pins["descriptor_ref"] == "descriptor:construction-blueprint-placement@1"


def test_packaged_construction_job_replay_rejects_tampered_binding_pins() -> None:
    from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry

    manifest = GameplayPatchManifest.model_validate(_construction_blueprint_manifest_payload())
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    active = registry.activate((manifest.patch_revision_id,))
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    plot = Plot(plot_ref="plot:tamper", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)
    result = authority.start_packaged_construction_job(
        plot=plot,
        package_revision=manifest.patch_revision_id,
        definition_ref="definition:construction-blueprint-test@1",
        job_ref="job:tamper:1",
        anchor=(1, 1),
        orientation=90,
        command_id="command:tamper:1",
        causation_id="cause:tamper:1",
        correlation_id="corr:tamper:1",
        permit_evidence={"permit_ref": "permit:construction@1", "jurisdiction_ref": "jurisdiction:local", "status": "active", "revision": 1},
    )
    assert result.committed
    event = store.read_events()[-1]
    tampered = event.model_copy(
        update={"payload": {**event.payload, "binding_pins": {**event.payload["binding_pins"], "content_digest": "sha256:" + "f" * 64}}},
        deep=True,
    )
    with pytest.raises(ValueError, match="construction_job_binding_pins_invalid"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_packaged_construction_job_replay_rejects_tampered_permit_evidence() -> None:
    manifest = GameplayPatchManifest.model_validate(_construction_blueprint_manifest_payload())
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    plot = Plot(plot_ref="plot:permit-tamper", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)
    result = authority.start_packaged_construction_job(
        plot=plot,
        package_revision=manifest.patch_revision_id,
        definition_ref="definition:construction-blueprint-test@1",
        job_ref="job:permit-tamper:1",
        anchor=(1, 1),
        orientation=90,
        command_id="command:permit-tamper:1",
        causation_id="cause:permit-tamper:1",
        correlation_id="corr:permit-tamper:1",
        permit_evidence={"permit_ref": "permit:construction@1", "jurisdiction_ref": "jurisdiction:local", "status": "active", "revision": 1},
    )
    assert result.committed
    event = store.read_events()[-1]
    tampered = event.model_copy(
        update={"payload": {**event.payload, "permit_evidence": {**event.payload["permit_evidence"], "status": "revoked"}}},
        deep=True,
    )
    with pytest.raises(ValueError, match="construction_job_permit_evidence_invalid"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_packaged_construction_job_completion_carries_and_replays_start_provenance() -> None:
    manifest = GameplayPatchManifest.model_validate(_construction_blueprint_manifest_payload())
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    active = registry.activate((manifest.patch_revision_id,))
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    plot = Plot(plot_ref="plot:completion-pins", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)
    started = authority.start_packaged_construction_job(
        plot=plot,
        package_revision=manifest.patch_revision_id,
        definition_ref="definition:construction-blueprint-test@1",
        job_ref="job:completion-pins:1",
        anchor=(1, 1),
        orientation=90,
        command_id="command:completion-pins:start",
        causation_id="cause:completion-pins:start",
        correlation_id="corr:completion-pins:start",
        permit_evidence={"permit_ref": "permit:construction@1", "jurisdiction_ref": "jurisdiction:local", "status": "active", "revision": 1},
    )
    assert started.committed
    completed = authority.complete_construction_job(
        job_ref="job:completion-pins:1",
        expected_plot_revision=1,
        command_id="command:completion-pins:complete",
        idempotency_key="construction:job-complete:job:completion-pins:1:1:v1",
        causation_id="cause:completion-pins:complete",
        correlation_id="corr:completion-pins:complete",
    )
    assert completed.committed
    event = store.get_event(completed.committed_event_ids[0])
    assert event.payload["binding_pins"]["package_revision"] == manifest.patch_revision_id
    assert event.payload["permit_evidence"]["status"] == "active"
    tampered = event.model_copy(update={"payload": {**event.payload, "binding_pins": {**event.payload["binding_pins"], "descriptor_ref": "descriptor:tampered@1"}}}, deep=True)
    with pytest.raises(ValueError, match="construction_job_completion_binding_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_construction_job_completion_replay_rejects_plot_or_blueprint_identity_tamper() -> None:
    store, authority, plot, blueprint = _authority()
    assert authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:identity-tamper",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:identity-tamper:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:identity-tamper:v1",
        causation_id="cause:identity-tamper:start",
        correlation_id="corr:identity-tamper:start",
    ).committed
    completed = authority.complete_construction_job(
        job_ref="job:identity-tamper",
        expected_plot_revision=1,
        command_id="command:identity-tamper:complete",
        idempotency_key="construction:job-complete:job:identity-tamper:1:v1",
        causation_id="cause:identity-tamper:complete",
        correlation_id="corr:identity-tamper:complete",
    )
    assert completed.committed
    event = store.get_event(completed.committed_event_ids[0])
    tampered = event.model_copy(update={"payload": {**event.payload, "plot_ref": "plot:other"}}, deep=True)
    with pytest.raises(ValueError, match="construction_job_completion_identity_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_construction_job_completion_replay_rejects_content_pin_tamper() -> None:
    manifest = GameplayPatchManifest.model_validate(_construction_blueprint_manifest_payload())
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    plot = Plot(plot_ref="plot:content-tamper", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)
    assert authority.start_packaged_construction_job(
        plot=plot,
        package_revision=manifest.patch_revision_id,
        definition_ref="definition:construction-blueprint-test@1",
        job_ref="job:content-tamper:1",
        anchor=(1, 1),
        orientation=90,
        command_id="command:content-tamper:start",
        causation_id="cause:content-tamper:start",
        correlation_id="corr:content-tamper:start",
        permit_evidence={"permit_ref": "permit:construction@1", "jurisdiction_ref": "jurisdiction:local", "status": "active", "revision": 1},
    ).committed
    completed = authority.complete_construction_job(
        job_ref="job:content-tamper:1",
        expected_plot_revision=1,
        command_id="command:content-tamper:complete",
        idempotency_key="construction:job-complete:job:content-tamper:1:1:v1",
        causation_id="cause:content-tamper:complete",
        correlation_id="corr:content-tamper:complete",
    )
    assert completed.committed
    event = store.get_event(completed.committed_event_ids[0])
    tampered = event.model_copy(update={"payload": {**event.payload, "duration_ticks": 999}}, deep=True)
    with pytest.raises(ValueError, match="construction_job_completion_content_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_construction_projection_checkpoint_round_trip_and_tail_replay() -> None:
    store, authority, plot, blueprint = _authority()
    assert authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:checkpoint:1",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:checkpoint:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:checkpoint:1:v1",
        causation_id="cause:checkpoint:start",
        correlation_id="corr:checkpoint:start",
    ).committed
    assert authority.complete_construction_job(
        job_ref="job:checkpoint:1",
        expected_plot_revision=1,
        command_id="command:checkpoint:complete",
        idempotency_key="construction:job-complete:job:checkpoint:1:1:v1",
        causation_id="cause:checkpoint:complete",
        correlation_id="corr:checkpoint:complete",
    ).committed
    events = store.read_events()
    checkpoint = authority._projector.export_checkpoint(
        authority._projector.rebuild(events[:1]),
        checkpoint_id="checkpoint:construction:1",
        last_global_sequence=events[0].global_sequence,
    )
    restored = authority._projector.restore_checkpoint(checkpoint)
    full = authority._projector.rebuild(events)
    tail = authority._projector.rebuild(events[1:], checkpoint=restored)
    assert tail.jobs == full.jobs
    assert tail.source_revision_vector == full.source_revision_vector


def test_construction_projection_checkpoint_rejects_tampering() -> None:
    store, authority, plot, blueprint = _authority()
    assert authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:checkpoint-tamper:1",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:checkpoint-tamper:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:checkpoint-tamper:1:v1",
        causation_id="cause:checkpoint-tamper:start",
        correlation_id="corr:checkpoint-tamper:start",
    ).committed
    checkpoint = authority._projector.export_checkpoint(
        authority.projector(),
        checkpoint_id="checkpoint:construction:tamper",
        last_global_sequence=1,
    )
    checkpoint["state"]["jobs"]["job:checkpoint-tamper:1"]["status"] = "completed"
    with pytest.raises(ValueError, match="construction_projection_checkpoint_digest_mismatch"):
        authority._projector.restore_checkpoint(checkpoint)


def test_construction_projection_checkpoint_rejects_tampered_last_global_sequence() -> None:
    store, authority, plot, blueprint = _authority()
    assert authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:checkpoint-sequence:1",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:checkpoint-sequence:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:checkpoint-sequence:1:v1",
        causation_id="cause:checkpoint-sequence:start",
        correlation_id="corr:checkpoint-sequence:start",
    ).committed
    checkpoint = authority._projector.export_checkpoint(
        authority.projector(),
        checkpoint_id="checkpoint:construction:sequence",
        last_global_sequence=1,
    )
    checkpoint["last_global_sequence"] = -1
    with pytest.raises(ValueError, match="construction_projection_checkpoint_invalid"):
        authority._projector.restore_checkpoint(checkpoint)


def test_construction_projection_checkpoint_rejects_invalid_revision_vector_values() -> None:
    store, authority, plot, blueprint = _authority()
    assert authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:checkpoint-revision-vector:1",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:checkpoint-revision-vector:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:checkpoint-revision-vector:1:v1",
        causation_id="cause:checkpoint-revision-vector:start",
        correlation_id="corr:checkpoint-revision-vector:start",
    ).committed
    checkpoint = authority._projector.export_checkpoint(
        authority.projector(),
        checkpoint_id="checkpoint:construction:revision-vector",
        last_global_sequence=1,
    )
    checkpoint["source_revision_vector"] = {"stream": True}
    with pytest.raises(ValueError, match="construction_projection_checkpoint_invalid"):
        authority._projector.restore_checkpoint(checkpoint)


def test_construction_job_failure_is_terminal_idempotent_and_replays() -> None:
    store, authority, plot, blueprint = _authority()
    assert authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:failed:1",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:failed:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:failed:1:v1",
        causation_id="cause:failed:start",
        correlation_id="corr:failed:start",
    ).committed
    first = authority.fail_construction_job(
        job_ref="job:failed:1",
        expected_plot_revision=1,
        failure_reason="permit_revoked",
        command_id="command:failed:fail",
        idempotency_key="construction:job-fail:job:failed:1:1:v1",
        causation_id="cause:failed:fail",
        correlation_id="corr:failed:fail",
    )
    duplicate = authority.fail_construction_job(
        job_ref="job:failed:1",
        expected_plot_revision=1,
        failure_reason="permit_revoked",
        command_id="command:failed:fail",
        idempotency_key="construction:job-fail:job:failed:1:1:v1",
        causation_id="cause:failed:fail",
        correlation_id="corr:failed:fail",
    )
    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert authority.projector().jobs["job:failed:1"].status == "failed"
    assert authority.projector(checkpoint_at=1).jobs == authority.projector().jobs


def test_construction_job_failure_rejects_empty_reason_or_nonstarted_job_without_append() -> None:
    store, authority, plot, blueprint = _authority()
    rejected = authority.fail_construction_job(
        job_ref="job:missing",
        expected_plot_revision=1,
        failure_reason="permit_revoked",
        command_id="command:failed:missing",
        idempotency_key="construction:job-fail:job:missing:1:v1",
        causation_id="cause:failed:missing",
        correlation_id="corr:failed:missing",
    )
    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "construction_job_source_missing"
    assert store.read_events() == []


def test_job_replay_rejects_malformed_binding_pins_even_without_permit_payload() -> None:
    manifest = GameplayPatchManifest.model_validate(_construction_blueprint_manifest_payload())
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    plot = Plot(plot_ref="plot:pin-shape", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)
    result = authority.start_packaged_construction_job(
        plot=plot,
        package_revision=manifest.patch_revision_id,
        definition_ref="definition:construction-blueprint-test@1",
        job_ref="job:pin-shape:1",
        anchor=(1, 1),
        orientation=90,
        command_id="command:pin-shape:1",
        causation_id="cause:pin-shape:1",
        correlation_id="corr:pin-shape:1",
        permit_evidence={"permit_ref": "permit:construction@1", "jurisdiction_ref": "jurisdiction:local", "status": "active", "revision": 1},
    )
    assert result.committed
    event = store.read_events()[-1]
    tampered_payload = dict(event.payload)
    tampered_payload.pop("permit_evidence", None)
    tampered_payload["binding_pins"] = {**event.payload["binding_pins"], "content_digest": "not-a-digest"}
    tampered = event.model_copy(update={"payload": tampered_payload}, deep=True)
    with pytest.raises(ValueError, match="construction_job_binding_pins_invalid"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_job_replay_rejects_zoning_ref_mismatch_in_permit_evidence() -> None:
    store, authority, plot, blueprint = _authority()
    content = BlueprintContent.model_validate(
        {
            "blueprint_ref": blueprint.blueprint_ref,
            "facility_definition_ref": "definition:mill@1",
            "facility_schema_ref": "schema:facility@1",
            "facility_kind": blueprint.facility_kind,
            "footprint": {"width": 1, "depth": 1},
            "allowed_orientations": [0],
            "components": [
                {
                    "component_ref": "component:foundation@1",
                    "component_kind": "foundation",
                    "width": 1,
                    "depth": 1,
                }
            ],
            "material_requirements": {},
            "tool_refs": [],
            "qualification_refs": [],
            "duration_ticks": 1,
            "required_permit_ref": blueprint.required_permit_ref,
            "zoning_ref": "zoning:industrial@1",
        }
    )
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        content=content,
        permit_evidence={
            "permit_ref": blueprint.required_permit_ref,
            "jurisdiction_ref": plot.jurisdiction_ref,
            "zoning_ref": "zoning:industrial@1",
            "status": "active",
            "revision": 1,
        },
        job_ref="job:zoning-replay",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:zoning-replay:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:zoning-replay:v1",
        causation_id="cause:zoning-replay:start",
        correlation_id="corr:zoning-replay:start",
    )
    assert result.committed
    event = store.read_events()[-1]
    tampered = event.model_copy(
        update={
            "payload": {
                **event.payload,
                "permit_evidence": {**event.payload["permit_evidence"], "zoning_ref": "zoning:other@1"},
            }
        },
        deep=True,
    )
    with pytest.raises(ValueError, match="construction_job_permit_evidence_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_job_replay_rejects_malformed_occupied_cells_without_filtering() -> None:
    store, authority, plot, blueprint = _authority()
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:malformed-cells",
        anchor=(1, 1),
        footprint=(2, 1),
        orientation=0,
        command_id="command:malformed-cells:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:malformed-cells:v1",
        causation_id="cause:malformed-cells:start",
        correlation_id="corr:malformed-cells:start",
    )
    assert result.committed
    event = store.read_events()[-1]
    tampered = event.model_copy(
        update={"payload": {**event.payload, "occupied_cells": [[1, 1], ["bad", 2]]}},
        deep=True,
    )
    with pytest.raises(ValueError, match="construction_job_occupied_cells_invalid"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_job_replay_rejects_plot_stream_or_privacy_tamper() -> None:
    store, authority, plot, blueprint = _authority()
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:source-fence",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:source-fence:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:source-fence:v1",
        causation_id="cause:source-fence:start",
        correlation_id="corr:source-fence:start",
    )
    assert result.committed
    event = store.read_events()[-1]
    wrong_stream = event.model_copy(update={"stream_id": "gameplay:construction_production:plot:other"}, deep=True)
    with pytest.raises(ValueError, match="construction_job_source_conflict"):
        authority._projector.rebuild([wrong_stream])
    private = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="construction_job_source_conflict"):
        authority._projector.rebuild([private])


def test_job_terminal_replay_rejects_plot_stream_or_privacy_tamper() -> None:
    store, authority, plot, blueprint = _authority()
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:terminal-source-fence",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:terminal-source-fence:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:terminal-source-fence:v1",
        causation_id="cause:terminal-source-fence:start",
        correlation_id="corr:terminal-source-fence:start",
    )
    assert result.committed
    assert authority.complete_construction_job(
        job_ref="job:terminal-source-fence",
        expected_plot_revision=1,
        command_id="command:terminal-source-fence:complete",
        idempotency_key="construction:job-complete:job:terminal-source-fence:1:v1",
        causation_id="cause:terminal-source-fence:complete",
        correlation_id="corr:terminal-source-fence:complete",
    ).committed
    event = store.read_events()[-1]
    wrong_stream = event.model_copy(update={"stream_id": "gameplay:construction_production:plot:other"}, deep=True)
    with pytest.raises(ValueError, match="construction_job_completion_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], wrong_stream])
    private = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="construction_job_completion_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], private])


def test_job_failure_replay_rejects_plot_stream_or_privacy_tamper() -> None:
    store, authority, plot, blueprint = _authority()
    result = authority.start_construction_job(
        plot=plot,
        blueprint=blueprint,
        job_ref="job:failure-source-fence",
        anchor=(0, 0),
        footprint=(1, 1),
        orientation=0,
        command_id="command:failure-source-fence:start",
        idempotency_key="construction:job-start:plot:job:1:blueprint:job:mill@1:job:failure-source-fence:v1",
        causation_id="cause:failure-source-fence:start",
        correlation_id="corr:failure-source-fence:start",
    )
    assert result.committed
    assert authority.fail_construction_job(
        job_ref="job:failure-source-fence",
        expected_plot_revision=1,
        failure_reason="source-fence",
        command_id="command:failure-source-fence:fail",
        idempotency_key="construction:job-fail:job:failure-source-fence:1:v1",
        causation_id="cause:failure-source-fence:fail",
        correlation_id="corr:failure-source-fence:fail",
    ).committed
    event = store.read_events()[-1]
    wrong_stream = event.model_copy(update={"stream_id": "gameplay:construction_production:plot:other"}, deep=True)
    with pytest.raises(ValueError, match="construction_job_failure_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], wrong_stream])
    private = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="construction_job_failure_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], private])


def test_packaged_construction_job_rejects_mismatched_blueprint_binding_request() -> None:
    from app.gameplay.patch_runtime import GameplayPatchRegistry

    payload = _construction_blueprint_manifest_payload(
        predicate_family_ref="predicate:construction-plot-blocked@1",
        proposal_effect_types=("effect:construction-job-placement@1",),
    )
    manifest = GameplayPatchManifest.model_validate(payload)
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)

    with pytest.raises(GameplayPatchRuntimeError, match="patch_capability_binding_mismatch"):
        registry.activate((manifest.patch_revision_id,))
    assert registry.active_patch_set is None
