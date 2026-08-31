from __future__ import annotations

import copy
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry, _canonical_digest
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
