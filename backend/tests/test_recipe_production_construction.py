from __future__ import annotations

import copy
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    Recipe,
)
from app.gameplay.construction_production_content import ReservationRequirementContent
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry, _canonical_digest
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay import recipe_production_family as recipe_family

from test_recipe_production_descriptor_binding import PACKAGE_REVISION, _manifest


def _build_authority(*manifests: GameplayPatchManifest) -> tuple[GameplayEventStore, ConstructionProductionAuthority]:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    active_manifests = manifests or (_manifest(),)
    for manifest in active_manifests:
        registry.install(manifest)
    registry.activate(tuple(manifest.patch_revision_id for manifest in active_manifests))
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    return store, authority


def _acquire_facility(
    authority: ConstructionProductionAuthority,
    *,
    facility: Facility,
    owner_ref: str,
    command_id: str,
    idempotency_key: str,
    causation_id: str,
    correlation_id: str,
) -> Facility:
    facility = Facility(
        facility_ref=facility.facility_ref,
        plot_ref=facility.plot_ref,
        facility_kind=facility.facility_kind,
        facility_definition_ref=facility.facility_definition_ref,
        condition=facility.condition,
        revision=facility.revision,
    )
    authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref=facility.plot_ref,
            jurisdiction_ref="jurisdiction:local",
            owner_ref=owner_ref,
            revision=1,
        ),
        facility=facility,
        command_id=command_id,
        idempotency_key=idempotency_key,
        causation_id=causation_id,
        correlation_id=correlation_id,
    )
    return facility


def _authority() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Facility]:
    store, authority = _build_authority()
    facility = _acquire_facility(
        authority,
        facility=Facility(
            facility_ref="facility:bakery:1",
            plot_ref="plot:bakery:1",
            facility_kind="bakery",
            condition=1.0,
            revision=3,
        ),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire",
        idempotency_key="idempotency:facility-acquire",
        causation_id="causation:facility-acquire",
        correlation_id="correlation:facility-acquire",
    )
    return store, authority, facility


def _alternate_manifest() -> GameplayPatchManifest:
    from closed_generic_manifest_fixtures import load_manifest

    return load_manifest("recipe-production-kiln-v1")


def _mill_manifest() -> GameplayPatchManifest:
    from closed_generic_manifest_fixtures import load_manifest

    return load_manifest("recipe-production-mill-v1")


def _intent(
    *,
    facility: Facility,
    recipe_ref: str = "recipe:flour-to-bread@1",
    run_ref: str = "run:bakery:1",
    tick: int = 10,
    expected_stream_revision: int = 1,
    command_id: str = "command:recipe-start",
    causation_id: str = "causation:recipe-start",
    correlation_id: str = "correlation:recipe-start",
):
    assert hasattr(recipe_family, "RecipeProductionStartIntent")
    return recipe_family.RecipeProductionStartIntent(
        facility_ref=facility.facility_ref,
        recipe_ref=recipe_ref,
        run_ref=run_ref,
        tick=tick,
        expected_facility_revision=facility.revision,
        expected_stream_revision=expected_stream_revision,
        command_id=command_id,
        causation_id=causation_id,
        correlation_id=correlation_id,
    )


def test_recipe_production_adapter_resolves_content_and_uses_existing_construction_append() -> None:
    store, authority, facility = _authority()

    result = authority.settle_recipe_production_start(intent=_intent(facility=facility))

    assert result.committed
    event = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[-1]
    assert event.event_type == "gameplay.construction_production.run_started"
    assert event.payload["recipe_ref"] == "recipe:flour-to-bread@1"
    assert event.payload["output_item"] == "item:bread@1"
    assert event.payload["finish_tick"] == 20
    assert result.committed_event_ids


def test_recipe_production_adapter_supports_two_immutable_contents_via_same_family() -> None:
    primary_manifest = _manifest()
    primary_extension = primary_manifest.platform_extension
    assert primary_extension is not None
    primary_definition = primary_extension.package_definitions[0]
    primary_snapshot = copy.deepcopy(primary_definition.typed_content)
    alternate_manifest = _alternate_manifest()
    alternate_extension = alternate_manifest.platform_extension
    assert alternate_extension is not None

    primary_content = recipe_family.RecipeProductionContent.from_package_definition(primary_definition)
    alternate_content = recipe_family.RecipeProductionContent.from_package_definition(
        alternate_extension.package_definitions[0]
    )
    assert primary_content.recipe_ref != alternate_content.recipe_ref
    assert primary_content.output_slots[0].item_definition_ref != alternate_content.output_slots[0].item_definition_ref
    assert primary_content.duration_ticks != alternate_content.duration_ticks

    store, authority = _build_authority(primary_manifest, alternate_manifest)
    bakery = _acquire_facility(
        authority,
        facility=Facility(
            facility_ref="facility:bakery:7",
            plot_ref="plot:bakery:7",
            facility_kind="bakery",
            condition=1.0,
            revision=3,
        ),
        owner_ref="organization:bakery-seven",
        command_id="command:facility-acquire:bakery-seven",
        idempotency_key="idempotency:facility-acquire:bakery-seven",
        causation_id="causation:facility-acquire:bakery-seven",
        correlation_id="correlation:facility-acquire:bakery-seven",
    )
    kiln = _acquire_facility(
        authority,
        facility=Facility(
            facility_ref="facility:kiln:2",
            plot_ref="plot:kiln:2",
            facility_kind="kiln",
            condition=1.0,
            revision=4,
        ),
        owner_ref="organization:kiln-two",
        command_id="command:facility-acquire:kiln-two",
        idempotency_key="idempotency:facility-acquire:kiln-two",
        causation_id="causation:facility-acquire:kiln-two",
        correlation_id="correlation:facility-acquire:kiln-two",
    )

    bread_run = authority.settle_recipe_production_start(intent=_intent(facility=bakery))
    brick_run = authority.settle_recipe_production_start(
        intent=_intent(
            facility=kiln,
            recipe_ref=alternate_content.recipe_ref,
            run_ref="run:kiln:2",
            tick=30,
            command_id="command:recipe-start:kiln-two",
            causation_id="causation:recipe-start:kiln-two",
            correlation_id="correlation:recipe-start:kiln-two",
        )
    )

    assert bread_run.committed
    assert brick_run.committed
    bread_event = store.read_stream(f"gameplay:construction_production:{bakery.facility_ref}")[-1]
    brick_event = store.read_stream(f"gameplay:construction_production:{kiln.facility_ref}")[-1]
    assert bread_event.payload["recipe_ref"] == primary_content.recipe_ref
    assert bread_event.payload["output_item"] == primary_content.output_slots[0].item_definition_ref
    assert bread_event.payload["finish_tick"] == 20
    assert brick_event.payload["recipe_ref"] == alternate_content.recipe_ref
    assert brick_event.payload["output_item"] == alternate_content.output_slots[0].item_definition_ref
    assert brick_event.payload["finish_tick"] == 54
    assert primary_definition.typed_content == primary_snapshot


def test_recipe_production_adapter_accepts_explicit_construction_policy_content() -> None:
    base = _manifest()
    extension = base.platform_extension
    assert extension is not None
    typed = {
        **extension.package_definitions[0].typed_content,
        "recipe_schema_ref": "schema:construction-recipe@1",
        "batch_size": 2,
        "quality_policy_revision_ref": "policy:quality:bread@1",
        "quality_value": 0.8,
        "output_quantity": 1,
        "wear_policy_ref": "policy:wear:bakery@1",
        "failure_policy_mode": "rework",
        "failure_policy_revision_ref": "policy:failure:rework@1",
    }
    definition = extension.package_definitions[0].model_copy(update={"typed_content": typed}, deep=True)
    changed_extension = extension.model_copy(update={"package_definitions": (definition,)}, deep=True)
    declaration = changed_extension.outcome_declarations[0]
    declaration_payload = declaration.model_dump(mode="json", exclude={"declaration_digest"})
    changed_declaration = declaration.model_copy(
        update={"declaration_digest": _canonical_digest(declaration_payload)}, deep=True
    )
    changed_extension = changed_extension.model_copy(
        update={"outcome_declarations": (changed_declaration,)}, deep=True
    )
    manifest = base.model_copy(update={"platform_extension": changed_extension}, deep=True)
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})

    store, authority = _build_authority(manifest)
    facility = _acquire_facility(
        authority,
        facility=Facility(
            facility_ref="facility:bakery:construction-content",
            plot_ref="plot:bakery:construction-content",
            facility_kind="bakery",
            condition=1.0,
            revision=1,
        ),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire:construction-content",
        idempotency_key="idempotency:facility-acquire:construction-content",
        causation_id="causation:facility-acquire:construction-content",
        correlation_id="correlation:facility-acquire:construction-content",
    )

    result = authority.settle_recipe_production_start(intent=_intent(facility=facility))

    assert result.committed
    event = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[-1]
    assert event.payload["recipe_ref"] == "recipe:flour-to-bread@1"
    committed_recipe = authority.projector().recipes_by_run["run:bakery:1"].recipe
    assert committed_recipe.batch_size == 2
    assert committed_recipe.quality_policy_revision == "policy:quality:bread@1"
    assert committed_recipe.wear_policy_ref == "policy:wear:bakery@1"
    assert committed_recipe.failure_policy_mode == "rework"
    pinned = authority.projector().recipes_by_run["run:bakery:1"]
    assert pinned.package_revision == manifest.patch_revision_id
    assert pinned.content_digest == manifest.content_digest
    assert pinned.declaration_digest == changed_declaration.declaration_digest


def test_recipe_production_rejects_facility_definition_conflict_before_append() -> None:
    store, authority = _build_authority()
    facility = _acquire_facility(
        authority,
        facility=Facility(
            facility_ref="facility:bakery:definition-conflict",
            plot_ref="plot:bakery:definition-conflict",
            facility_kind="bakery",
            facility_definition_ref="definition:other-facility@1",
            condition=1.0,
            revision=1,
        ),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire:definition-conflict",
        idempotency_key="idempotency:facility-acquire:definition-conflict",
        causation_id="cause:facility-acquire:definition-conflict",
        correlation_id="corr:facility-acquire:definition-conflict",
    )
    before = tuple(store.read_events())
    result = authority.settle_recipe_production_start(
        intent=_intent(
            facility=facility,
            command_id="command:recipe-start:definition-conflict",
            causation_id="cause:recipe-start:definition-conflict",
            correlation_id="corr:recipe-start:definition-conflict",
        )
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "recipe_production_content_unknown"
    assert tuple(store.read_events()) == before


def test_recipe_production_content_gate_covers_bakery_kiln_and_mill_packages() -> None:
    manifests = (_manifest(), _alternate_manifest(), _mill_manifest())
    contents = tuple(
        recipe_family.RecipeProductionContent.from_package_definition(
            manifest.platform_extension.package_definitions[0]  # type: ignore[union-attr]
        )
        for manifest in manifests
    )

    assert {content.facility_kind for content in contents} == {"bakery", "kiln", "mill"}
    assert len({content.recipe_ref for content in contents}) == 3


def test_recipe_production_finish_derives_output_evidence_from_admitted_content() -> None:
    base = _manifest()
    extension = base.platform_extension
    assert extension is not None
    typed = {
        **extension.package_definitions[0].typed_content,
        "recipe_schema_ref": "schema:construction-recipe@1",
        "batch_size": 2,
        "output_quantity": 1,
        "quality_policy_revision_ref": "policy:quality:bread@1",
        "quality_value": 0.8,
        "wear_policy_ref": "policy:wear:bakery@1",
        "failure_policy_mode": "terminal",
        "failure_policy_revision_ref": "policy:failure:terminal@1",
    }
    definition = extension.package_definitions[0].model_copy(update={"typed_content": typed}, deep=True)
    changed_extension = extension.model_copy(update={"package_definitions": (definition,)}, deep=True)
    declaration = changed_extension.outcome_declarations[0]
    declaration_payload = declaration.model_dump(mode="json", exclude={"declaration_digest"})
    changed_declaration = declaration.model_copy(update={"declaration_digest": _canonical_digest(declaration_payload)}, deep=True)
    changed_extension = changed_extension.model_copy(update={"outcome_declarations": (changed_declaration,)}, deep=True)
    manifest = base.model_copy(update={"platform_extension": changed_extension}, deep=True)
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    store, authority = _build_authority(manifest)
    facility = _acquire_facility(
        authority,
        facility=Facility(facility_ref="facility:bakery:finish", plot_ref="plot:bakery:finish", facility_kind="bakery", condition=1.0, revision=1),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire:finish",
        idempotency_key="idempotency:facility-acquire:finish",
        causation_id="causation:facility-acquire:finish",
        correlation_id="correlation:facility-acquire:finish",
    )
    started = authority.settle_recipe_production_start(intent=_intent(facility=facility, tick=0, command_id="command:recipe-start:finish", causation_id="causation:recipe-start:finish", correlation_id="correlation:recipe-start:finish"))
    assert started.committed
    run = authority.projector().runs["run:bakery:1"]
    finish_intent = recipe_family.RecipeProductionFinishIntent(
        facility_ref=facility.facility_ref,
        run_ref=run.run_ref,
        tick=run.finish_tick,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        command_id="command:recipe-finish:finish",
        causation_id=run.run_ref,
        correlation_id="correlation:recipe-finish:finish",
    )

    result = authority.settle_recipe_production_finish(intent=finish_intent)

    assert result.committed
    event = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[-1]
    assert event.payload["output_quantity"] == 2
    assert event.payload["output_quality"] == 0.8
    assert event.payload["package_revision"] == manifest.patch_revision_id
    assert event.payload["content_digest"] == manifest.content_digest
    assert event.payload["declaration_digest"] == changed_declaration.declaration_digest
    assert event.payload["descriptor_ref"] == "descriptor:construction-recipe-production@1"


def test_recipe_production_finish_replays_duplicate_and_rejects_changed_duplicate() -> None:
    base = _manifest()
    extension = base.platform_extension
    assert extension is not None
    typed = {
        **extension.package_definitions[0].typed_content,
        "recipe_schema_ref": "schema:construction-recipe@1",
        "batch_size": 1,
        "output_quantity": 1,
        "quality_policy_revision_ref": "policy:quality:bread@1",
        "quality_value": 0.8,
        "wear_policy_ref": "policy:wear:bakery@1",
        "failure_policy_mode": "terminal",
        "failure_policy_revision_ref": "policy:failure:terminal@1",
    }
    definition = extension.package_definitions[0].model_copy(update={"typed_content": typed}, deep=True)
    changed_extension = extension.model_copy(update={"package_definitions": (definition,)}, deep=True)
    declaration = changed_extension.outcome_declarations[0]
    declaration_payload = declaration.model_dump(mode="json", exclude={"declaration_digest"})
    changed_declaration = declaration.model_copy(update={"declaration_digest": _canonical_digest(declaration_payload)}, deep=True)
    changed_extension = changed_extension.model_copy(update={"outcome_declarations": (changed_declaration,)}, deep=True)
    manifest = base.model_copy(update={"platform_extension": changed_extension}, deep=True)
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    store, authority = _build_authority(manifest)
    facility = _acquire_facility(
        authority,
        facility=Facility(facility_ref="facility:bakery:finish-dup", plot_ref="plot:bakery:finish-dup", facility_kind="bakery", condition=1.0, revision=1),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire:finish-dup",
        idempotency_key="idempotency:facility-acquire:finish-dup",
        causation_id="causation:facility-acquire:finish-dup",
        correlation_id="correlation:facility-acquire:finish-dup",
    )
    assert authority.settle_recipe_production_start(intent=_intent(facility=facility, tick=0, command_id="command:recipe-start:finish-dup", causation_id="causation:recipe-start:finish-dup", correlation_id="correlation:recipe-start:finish-dup")).committed
    run = authority.projector().runs["run:bakery:1"]
    finish = recipe_family.RecipeProductionFinishIntent(
        facility_ref=facility.facility_ref,
        run_ref=run.run_ref,
        tick=run.finish_tick,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        command_id="command:recipe-finish:dup",
        causation_id="cause:finish:dup",
        correlation_id="corr:finish:dup",
    )
    first = authority.settle_recipe_production_finish(intent=finish)
    duplicate = authority.settle_recipe_production_finish(intent=finish)
    changed = authority.settle_recipe_production_finish(intent=finish.model_copy(update={"tick": finish.tick + 1}, deep=True))

    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert len(store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")) == 3


def test_recipe_production_failure_derives_package_mode_and_replays() -> None:
    base = _manifest()
    extension = base.platform_extension
    assert extension is not None
    typed = {
        **extension.package_definitions[0].typed_content,
        "recipe_schema_ref": "schema:construction-recipe@1",
        "batch_size": 1,
        "output_quantity": 1,
        "quality_policy_revision_ref": "policy:quality:bread@1",
        "quality_value": 0.8,
        "wear_policy_ref": "policy:wear:bakery@1",
        "failure_policy_mode": "rework",
        "failure_policy_revision_ref": "policy:failure:rework@1",
    }
    definition = extension.package_definitions[0].model_copy(update={"typed_content": typed}, deep=True)
    changed_extension = extension.model_copy(update={"package_definitions": (definition,)}, deep=True)
    declaration = changed_extension.outcome_declarations[0]
    declaration_payload = declaration.model_dump(mode="json", exclude={"declaration_digest"})
    changed_declaration = declaration.model_copy(update={"declaration_digest": _canonical_digest(declaration_payload)}, deep=True)
    changed_extension = changed_extension.model_copy(update={"outcome_declarations": (changed_declaration,)}, deep=True)
    manifest = base.model_copy(update={"platform_extension": changed_extension}, deep=True)
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    store, authority = _build_authority(manifest)
    facility = _acquire_facility(
        authority,
        facility=Facility(facility_ref="facility:bakery:failure", plot_ref="plot:bakery:failure", facility_kind="bakery", condition=1.0, revision=1),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire:failure",
        idempotency_key="idempotency:facility-acquire:failure",
        causation_id="causation:facility-acquire:failure",
        correlation_id="correlation:facility-acquire:failure",
    )
    assert authority.settle_recipe_production_start(intent=_intent(facility=facility, tick=0, command_id="command:recipe-start:failure", causation_id="causation:recipe-start:failure", correlation_id="correlation:recipe-start:failure")).committed
    failure = recipe_family.RecipeProductionFailureIntent(
        facility_ref=facility.facility_ref,
        run_ref="run:bakery:1",
        tick=1,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        failure_reason="material_damaged",
        command_id="command:recipe-failure:1",
        causation_id="cause:recipe-failure:1",
        correlation_id="corr:recipe-failure:1",
    )

    first = authority.settle_recipe_production_failure(intent=failure)
    duplicate = authority.settle_recipe_production_failure(intent=failure)

    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    event = store.get_event(first.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.run_failed@1"
    assert event.payload["failure_mode"] == "rework"
    assert authority.projector().runs["run:bakery:1"].status == "failed"


def test_recipe_production_failure_replay_rejects_policy_revision_tamper() -> None:
    base = _manifest()
    extension = base.platform_extension
    assert extension is not None
    typed = {
        **extension.package_definitions[0].typed_content,
        "recipe_schema_ref": "schema:construction-recipe@1",
        "batch_size": 1,
        "output_quantity": 1,
        "quality_policy_revision_ref": "policy:quality:bread@1",
        "quality_value": 0.8,
        "wear_policy_ref": "policy:wear:bakery@1",
        "failure_policy_mode": "rework",
        "failure_policy_revision_ref": "policy:failure:rework@1",
    }
    definition = extension.package_definitions[0].model_copy(update={"typed_content": typed}, deep=True)
    changed_extension = extension.model_copy(update={"package_definitions": (definition,)}, deep=True)
    declaration = changed_extension.outcome_declarations[0]
    declaration_payload = declaration.model_dump(mode="json", exclude={"declaration_digest"})
    changed_declaration = declaration.model_copy(update={"declaration_digest": _canonical_digest(declaration_payload)}, deep=True)
    changed_extension = changed_extension.model_copy(update={"outcome_declarations": (changed_declaration,)}, deep=True)
    manifest = base.model_copy(update={"platform_extension": changed_extension}, deep=True)
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    store, authority = _build_authority(manifest)
    facility = _acquire_facility(
        authority,
        facility=Facility(facility_ref="facility:bakery:failure-tamper", plot_ref="plot:bakery:failure-tamper", facility_kind="bakery", condition=1.0, revision=1),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire:failure-tamper",
        idempotency_key="idempotency:facility-acquire:failure-tamper",
        causation_id="cause:facility-acquire:failure-tamper",
        correlation_id="corr:facility-acquire:failure-tamper",
    )
    assert authority.settle_recipe_production_start(intent=_intent(facility=facility, tick=0, command_id="command:recipe-start:failure-tamper", causation_id="cause:recipe-start:failure-tamper", correlation_id="corr:recipe-start:failure-tamper")).committed
    run = authority.projector().runs["run:bakery:1"]
    failure = recipe_family.RecipeProductionFailureIntent(
        facility_ref=facility.facility_ref,
        run_ref=run.run_ref,
        tick=1,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        failure_reason="material_damaged",
        command_id="command:recipe-failure:tamper",
        causation_id="cause:recipe-failure:tamper",
        correlation_id="corr:recipe-failure:tamper",
    )
    result = authority.settle_recipe_production_failure(intent=failure)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    tampered = event.model_copy(update={"payload": {**event.payload, "failure_policy_revision": "policy:failure:terminal@1"}}, deep=True)
    with pytest.raises(ValueError, match="production_failure_policy_revision_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_recipe_production_failure_replay_rejects_failure_mode_tamper() -> None:
    base = _manifest()
    extension = base.platform_extension
    assert extension is not None
    typed = {
        **extension.package_definitions[0].typed_content,
        "recipe_schema_ref": "schema:construction-recipe@1",
        "batch_size": 1,
        "output_quantity": 1,
        "quality_policy_revision_ref": "policy:quality:bread@1",
        "quality_value": 0.8,
        "wear_policy_ref": "policy:wear:bakery@1",
        "failure_policy_mode": "rework",
        "failure_policy_revision_ref": "policy:failure:rework@1",
    }
    definition = extension.package_definitions[0].model_copy(update={"typed_content": typed}, deep=True)
    changed_extension = extension.model_copy(update={"package_definitions": (definition,)}, deep=True)
    declaration = changed_extension.outcome_declarations[0]
    declaration_payload = declaration.model_dump(mode="json", exclude={"declaration_digest"})
    changed_declaration = declaration.model_copy(update={"declaration_digest": _canonical_digest(declaration_payload)}, deep=True)
    changed_extension = changed_extension.model_copy(update={"outcome_declarations": (changed_declaration,)}, deep=True)
    manifest = base.model_copy(update={"platform_extension": changed_extension}, deep=True)
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    store, authority = _build_authority(manifest)
    facility = _acquire_facility(
        authority,
        facility=Facility(facility_ref="facility:bakery:mode-tamper", plot_ref="plot:bakery:mode-tamper", facility_kind="bakery", condition=1.0, revision=1),
        owner_ref="organization:bakery",
        command_id="command:facility-acquire:mode-tamper",
        idempotency_key="idempotency:facility-acquire:mode-tamper",
        causation_id="cause:facility-acquire:mode-tamper",
        correlation_id="corr:facility-acquire:mode-tamper",
    )
    assert authority.settle_recipe_production_start(intent=_intent(facility=facility, tick=0, command_id="command:recipe-start:mode-tamper", causation_id="cause:recipe-start:mode-tamper", correlation_id="corr:recipe-start:mode-tamper")).committed
    run = authority.projector().runs["run:bakery:1"]
    failure = recipe_family.RecipeProductionFailureIntent(
        facility_ref=facility.facility_ref,
        run_ref=run.run_ref,
        tick=1,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        failure_reason="material_damaged",
        command_id="command:recipe-failure:mode-tamper",
        causation_id="cause:recipe-failure:mode-tamper",
        correlation_id="corr:recipe-failure:mode-tamper",
    )
    result = authority.settle_recipe_production_failure(intent=failure)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    tampered = event.model_copy(update={"payload": {**event.payload, "failure_mode": "loss"}}, deep=True)
    with pytest.raises(ValueError, match="production_failure_mode_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_recipe_production_failure_replay_rejects_empty_failure_reason() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:failure:empty-reason",
        plot_ref="plot:failure:empty-reason",
        facility_kind="bakery",
        condition=1.0,
        revision=1,
    )
    assert authority.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:local", owner_ref="organization:bakery"),
        facility=facility,
        command_id="command:acquire:empty-reason",
        idempotency_key="idempotency:acquire:empty-reason",
        causation_id="cause:acquire:empty-reason",
        correlation_id="corr:acquire:empty-reason",
    ).committed
    recipe = Recipe(
        recipe_ref="recipe:failure:empty-reason@1",
        inputs={},
        output_item="item:bread@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:failure:empty-reason",
        tick=0,
        command_id="command:start:empty-reason",
        idempotency_key="idempotency:start:empty-reason",
        causation_id="cause:start:empty-reason",
        correlation_id="corr:start:empty-reason",
    ).committed
    failure = recipe_family.RecipeProductionFailureIntent(
        facility_ref=facility.facility_ref,
        run_ref="run:failure:empty-reason",
        tick=1,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        failure_reason="invalid-source",
        command_id="command:failure:empty-reason",
        causation_id="cause:failure:empty-reason",
        correlation_id="corr:failure:empty-reason",
    )
    result = authority.settle_recipe_production_failure(intent=failure)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    tampered = event.model_copy(update={"payload": {**event.payload, "failure_reason": ""}}, deep=True)
    with pytest.raises(ValueError, match="production_failure_reason_invalid"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_recipe_production_failure_replay_rejects_facility_stream_or_privacy_tamper() -> None:
    store, authority, facility = _authority()
    recipe = Recipe(
        recipe_ref="recipe:failure:source-integrity@1",
        inputs={},
        output_item="item:bread@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:failure:source-integrity",
        tick=0,
        command_id="command:start:source-integrity",
        idempotency_key="idempotency:start:source-integrity",
        causation_id="cause:start:source-integrity",
        correlation_id="corr:start:source-integrity",
    ).committed
    failure = recipe_family.RecipeProductionFailureIntent(
        facility_ref=facility.facility_ref,
        run_ref="run:failure:source-integrity",
        tick=1,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        failure_reason="source-integrity-check",
        command_id="command:failure:source-integrity",
        causation_id="cause:failure:source-integrity",
        correlation_id="corr:failure:source-integrity",
    )
    result = authority.settle_recipe_production_failure(intent=failure)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["facility_ref"] == facility.facility_ref
    assert event.payload["recipe_ref"] == recipe.recipe_ref
    assert event.visibility_policy == "project"
    tampered = event.model_copy(
        update={
            "payload": {**event.payload, "facility_ref": "facility:other"},
            "stream_id": "gameplay:construction_production:facility:other",
        },
        deep=True,
    )
    with pytest.raises(ValueError, match="production_failure_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])

    private = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="production_failure_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], private])

    recipe_tampered = event.model_copy(
        update={"payload": {**event.payload, "recipe_ref": "recipe:other@1"}}, deep=True
    )
    with pytest.raises(ValueError, match="production_failure_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], recipe_tampered])

    revision_tampered = event.model_copy(
        update={
            "payload": {
                **event.payload,
                "source_revision_vector": {
                    **event.payload["source_revision_vector"],
                    "stream_head": 0,
                },
            }
        },
        deep=True,
    )
    with pytest.raises(ValueError, match="production_failure_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], revision_tampered])


def test_recipe_production_failure_preserves_reservation_lineage_for_replay() -> None:
    store, authority, facility = _authority()
    reservation_stream = "gameplay:inventory:organization:bakery"
    reservation = build_atomic_event_batch(
        command_id="reservation:failure-lineage",
        principal_ref="actor_gameplay.inventory_domain",
        stream_id=reservation_stream,
        expected_revision=0,
        event_specs=[
            (
                "gameplay.inventory.reservation_created",
                {"reservation_ref": "reservation:flour:failure-lineage"},
            )
        ],
        idempotency_key="reservation:failure-lineage",
        causation_id="cause:failure-lineage",
        correlation_id="corr:failure-lineage",
    )
    assert store.append_batch(reservation).committed
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:flour:failure-lineage",
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:failure:lineage@1",
        inputs={},
        output_item="item:bread@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    evidence = {
        requirement.reservation_ref: {
            "owner_family_ref": "inventory",
            "status": "active",
            "revision": 1,
            "source_event_id": reservation.events[0].event_id,
        }
    }
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:failure:lineage",
        tick=0,
        command_id="command:start:failure-lineage",
        idempotency_key="idempotency:start:failure-lineage",
        causation_id="cause:start:failure-lineage",
        correlation_id="corr:start:failure-lineage",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence=evidence,
    ).committed
    failure = recipe_family.RecipeProductionFailureIntent(
        facility_ref=facility.facility_ref,
        run_ref="run:failure:lineage",
        tick=1,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        failure_reason="lineage-check",
        command_id="command:failure:lineage",
        causation_id="cause:failure:lineage",
        correlation_id="corr:failure:lineage",
    )
    result = authority.settle_recipe_production_failure(intent=failure)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["reservation_refs"] == (requirement.reservation_ref,)
    assert event.payload["reservation_evidence"] == evidence
    projection = authority.projector()
    assert projection.runs["run:failure:lineage"].reservation_evidence == evidence
    tail = authority.projector(checkpoint_at=1)
    assert tail.runs["run:failure:lineage"].reservation_evidence == evidence
    tampered = event.model_copy(
        update={"payload": {**event.payload, "reservation_refs": ()}}, deep=True
    )
    with pytest.raises(ValueError, match="production_failure_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_recipe_production_failure_rejects_tick_before_run_start_without_write() -> None:
    store, authority, facility = _authority()
    recipe = Recipe(
        recipe_ref="recipe:failure:early@1",
        inputs={},
        output_item="item:bread@1",
        duration_ticks=3,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:failure:early",
        tick=10,
        command_id="command:start:early",
        idempotency_key="idempotency:start:early",
        causation_id="cause:start:early",
        correlation_id="corr:start:early",
    ).committed
    before = tuple(store.read_events())
    result = authority.settle_recipe_production_failure(
        intent=recipe_family.RecipeProductionFailureIntent(
            facility_ref=facility.facility_ref,
            run_ref="run:failure:early",
            tick=9,
            expected_stream_revision=2,
            expected_facility_revision=facility.revision,
            failure_reason="too-early",
            command_id="command:failure:early",
            causation_id="cause:failure:early",
            correlation_id="corr:failure:early",
        )
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "recipe_production_failure_tick_invalid"
    assert tuple(store.read_events()) == before


def test_recipe_production_failure_replay_rejects_tick_before_run_start() -> None:
    store, authority, facility = _authority()
    recipe = Recipe(
        recipe_ref="recipe:failure:early-replay@1",
        inputs={},
        output_item="item:bread@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:failure:early-replay",
        tick=10,
        command_id="command:start:early-replay",
        idempotency_key="idempotency:start:early-replay",
        causation_id="cause:start:early-replay",
        correlation_id="corr:start:early-replay",
    ).committed
    run = authority.projector().runs["run:failure:early-replay"]
    result = authority.settle_recipe_production_failure(
        intent=recipe_family.RecipeProductionFailureIntent(
            facility_ref=facility.facility_ref,
            run_ref=run.run_ref,
            tick=10,
            expected_stream_revision=2,
            expected_facility_revision=facility.revision,
            failure_reason="replay-chronology",
            command_id="command:failure:early-replay",
            causation_id="cause:failure:early-replay",
            correlation_id="corr:failure:early-replay",
        )
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    tampered = event.model_copy(update={"payload": {**event.payload, "failed_tick": 9}}, deep=True)
    with pytest.raises(ValueError, match="production_failure_chronology_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


@pytest.mark.parametrize(
    ("failure_mode", "expected_status"),
    (("release", "released"), ("loss", "lost")),
)
def test_recipe_production_failure_projects_explicit_release_or_loss_status(
    failure_mode: str,
    expected_status: str,
) -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref=f"facility:failure:{failure_mode}",
        plot_ref=f"plot:failure:{failure_mode}",
        facility_kind="bakery",
        condition=1.0,
        revision=1,
    )
    assert authority.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:local", owner_ref="organization:bakery"),
        facility=facility,
        command_id=f"command:acquire:{failure_mode}",
        idempotency_key=f"idempotency:acquire:{failure_mode}",
        causation_id=f"cause:acquire:{failure_mode}",
        correlation_id=f"corr:acquire:{failure_mode}",
    ).committed
    recipe = Recipe(
        recipe_ref=f"recipe:failure:{failure_mode}@1",
        inputs={},
        output_item="item:bread@1",
        duration_ticks=1,
        failure_policy_mode=failure_mode,
        failure_policy_revision=f"policy:failure:{failure_mode}@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref=f"run:failure:{failure_mode}",
        tick=0,
        command_id=f"command:start:{failure_mode}",
        idempotency_key=f"idempotency:start:{failure_mode}",
        causation_id=f"cause:start:{failure_mode}",
        correlation_id=f"corr:start:{failure_mode}",
    ).committed
    failure = recipe_family.RecipeProductionFailureIntent(
        facility_ref=facility.facility_ref,
        run_ref=f"run:failure:{failure_mode}",
        tick=1,
        expected_stream_revision=2,
        expected_facility_revision=facility.revision,
        failure_reason="policy-triggered",
        command_id=f"command:failure:{failure_mode}",
        causation_id=f"cause:failure:{failure_mode}",
        correlation_id=f"corr:failure:{failure_mode}",
    )
    assert authority.settle_recipe_production_failure(intent=failure).committed
    assert authority.projector().runs[f"run:failure:{failure_mode}"].status == expected_status


def test_recipe_production_adapter_rejects_unknown_recipe_without_writing() -> None:
    store, authority, facility = _authority()
    before = tuple(store.read_events())

    result = authority.settle_recipe_production_start(
        intent=_intent(facility=facility, recipe_ref="recipe:unknown@1")
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "recipe_production_content_unknown"
    assert tuple(store.read_events()) == before


def test_recipe_production_adapter_rejects_stale_facility_without_writing() -> None:
    store, authority, facility = _authority()
    before = tuple(store.read_events())

    result = authority.settle_recipe_production_start(
        intent=_intent(facility=facility, expected_stream_revision=0)
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "recipe_production_revision_conflict"
    assert tuple(store.read_events()) == before


def test_recipe_production_adapter_rejects_private_facility_source_without_writing() -> None:
    store, authority, facility = _authority()
    source = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0]
    store._events_by_id[source.event_id] = source.model_copy(update={"visibility_policy": "authority_only"})
    before = tuple(store.read_events())

    result = authority.settle_recipe_production_start(intent=_intent(facility=facility))

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "recipe_production_source_private"
    assert tuple(store.read_events()) == before


def test_recipe_production_adapter_replays_same_intent_without_a_second_event() -> None:
    store, authority, facility = _authority()
    intent = _intent(facility=facility)
    first = authority.settle_recipe_production_start(intent=intent)
    before = tuple(store.read_events())

    replay = authority.settle_recipe_production_start(intent=intent)

    assert replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    assert tuple(store.read_events()) == before


def test_recipe_production_adapter_rejects_changed_duplicate_without_writing() -> None:
    store, authority, facility = _authority()
    intent = _intent(facility=facility)
    authority.settle_recipe_production_start(intent=intent)
    before = tuple(store.read_events())

    changed = intent.model_copy(update={"tick": 11})
    result = authority.settle_recipe_production_start(intent=changed)

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "idempotency_key_reused"
    assert tuple(store.read_events()) == before


def test_recipe_production_intent_cannot_carry_authority_coordinates() -> None:
    with pytest.raises(ValidationError):
        recipe_family.RecipeProductionStartIntent.model_validate(
            {
                "facility_ref": "facility:bakery:1",
                "recipe_ref": "recipe:flour-to-bread@1",
                "run_ref": "run:bakery:1",
                "tick": 10,
                "expected_facility_revision": 3,
                "expected_stream_revision": 1,
                "command_id": "command:recipe-start",
                "causation_id": "causation:recipe-start",
                "correlation_id": "correlation:recipe-start",
                "owner_ref": "owner:caller@1",
                "stream_id": "gameplay:caller",
                "event_type": "caller.event",
                "idempotency_key": "caller-chosen",
            }
        )


def test_recipe_production_rejects_tampered_activation_definition_pin_without_writing() -> None:
    store, authority, facility = _authority()
    registry = authority._package_registry
    active = registry.active_patch_set
    assert active is not None
    assert len(active.capability_bindings) == 1
    registry._active = replace(
        active,
        capability_bindings=(
            replace(active.capability_bindings[0], definition_ref="definition:forged@1"),
        ),
    )
    before = tuple(store.read_events())

    result = authority.settle_recipe_production_start(intent=_intent(facility=facility))

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "recipe_production_binding_invalid"
    assert tuple(store.read_events()) == before
