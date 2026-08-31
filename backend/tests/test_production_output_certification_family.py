from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from app.gameplay.closed_generic_gameplay_families import ProductionOutputCertificationContent
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import CapabilityBindingRequest, GameplayPatchManifest, GameplayPatchRegistry, OutcomeDeclarationAuthorInput, PackageDefinition, PackageIdentity, PlatformExtension, TypedReadRequirement
from test_inf1am_mill_flour_output_certification import _completed_case as _mill_completed_case
from closed_generic_manifest_fixtures import load_manifest


REVISION = "package:output-certification-demo@1"
MILL_REVISION = "package:output-certification-mill-demo@1"


def _digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _manifest() -> GameplayPatchManifest:
    return load_manifest("production-output-certification-demo-v1")


def _mill_manifest() -> GameplayPatchManifest:
    return load_manifest("production-output-certification-mill-demo-v1")


def _setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority, str]:
    store = GameplayEventStore()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    registry.install(manifest)
    registry.activate((REVISION,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    facility = Facility(facility_ref="facility:bakery:certification", plot_ref="plot:bakery:certification", facility_kind="bakery", condition=1.0)
    assert authority.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:local", owner_ref="organization:bakery"),
        facility=facility, command_id="command:acquire", idempotency_key="idempotency:acquire", causation_id="cause:acquire", correlation_id="corr:acquire",
    ).committed
    recipe = Recipe(recipe_ref="recipe:flour-to-bread@1", inputs={}, output_item="item:bread@1", duration_ticks=1)
    assert authority.settle_start_run(
        facility=facility, recipe=recipe, run_ref="run:certification", tick=10, command_id="command:start", idempotency_key="idempotency:start", causation_id="cause:start", correlation_id="corr:start",
    ).committed
    run = authority.projector().runs["run:certification"]
    assert authority.settle_finish_run(
        run, tick=11, recipe=recipe, command_id="command:finish", idempotency_key="idempotency:finish", causation_id="cause:finish", correlation_id="corr:finish",
    ).committed
    finished = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[-1]
    return store, authority, finished.event_id


def _mill_setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority, str]:
    store, _legacy_authority, _started, finished = _mill_completed_case()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _mill_manifest()
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    return store, authority, finished.event_id


def _intent(finished_event_id: str) -> object:
    from app.gameplay.closed_generic_gameplay_families import ProductionOutputCertificationIntent

    return ProductionOutputCertificationIntent(
        run_finished_event_id=finished_event_id,
        expected_run_finished_revision=3,
        expected_stream_revision=3,
        expected_facility_revision=0,
        command_id="command:certification",
        causation_id=finished_event_id,
        correlation_id="corr:certification",
        submitted_at="2026-08-30T00:00:00Z",
    )


def _mill_intent(finished_event_id: str) -> object:
    from app.gameplay.closed_generic_gameplay_families import ProductionOutputCertificationIntent

    return ProductionOutputCertificationIntent(
        run_finished_event_id=finished_event_id,
        expected_run_finished_revision=4,
        expected_stream_revision=4,
        expected_facility_revision=1,
        command_id="command:mill-certification",
        causation_id=finished_event_id,
        correlation_id="corr:mill-certification",
        submitted_at="2026-08-30T00:00:00Z",
    )


def test_output_certification_family_appends_construction_owned_certification() -> None:
    store, authority, finished_id = _setup()

    result = authority.settle_production_output_certification(intent=_intent(finished_id))

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.production_output_certified@1"
    assert event.payload["family_ref"] == "production_output_certification@1"
    assert event.payload["quantity"] == 1
    assert authority.projector().production_output_certifications["run:certification"].quantity == 1


@pytest.mark.parametrize(
    ("setup", "intent_factory", "expected_recipe_ref", "expected_output_item", "expected_quantity"),
    [
        (_setup, _intent, "recipe:flour-to-bread@1", "item:bread@1", 1),
        (_mill_setup, _mill_intent, "recipe:industrial-facilities:mill-flour@1", "item:industrial-facilities:flour@1", 10),
    ],
)
def test_output_certification_family_consumes_multiple_admitted_content_instances_through_one_adapter(
    setup,
    intent_factory,
    expected_recipe_ref: str,
    expected_output_item: str,
    expected_quantity: int,
) -> None:
    store, authority, finished_id = setup()
    result = authority.settle_production_output_certification(intent=intent_factory(finished_id))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["family_ref"] == "production_output_certification@1"
    assert event.payload["recipe_ref"] == expected_recipe_ref
    assert event.payload["output_item"] == expected_output_item
    assert event.payload["quantity"] == expected_quantity


def test_output_certification_rejects_forged_run_source_without_writing() -> None:
    store, authority, finished_id = _setup()
    finished = store.get_event(finished_id)
    store._events_by_id[finished_id] = finished.model_copy(update={"payload": {**finished.payload, "output_item": "item:forged@1"}}, deep=True)
    before = tuple(store.read_events())

    result = authority.settle_production_output_certification(intent=_intent(finished_id))

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "production_output_certification_source_conflict"
    assert tuple(store.read_events()) == before


def test_output_certification_intent_rejects_caller_quantity_or_event_coordinates() -> None:
    from app.gameplay.closed_generic_gameplay_families import ProductionOutputCertificationIntent

    with pytest.raises(Exception):
        ProductionOutputCertificationIntent.model_validate({
            "run_finished_event_id": "event:finished", "expected_run_finished_revision": 3,
            "expected_stream_revision": 3, "expected_facility_revision": 0, "command_id": "command:cert",
            "causation_id": "cause:cert", "correlation_id": "corr:cert", "submitted_at": "2026-08-30T00:00:00Z",
            "quantity": 99, "event_type": "caller.event",
        })


def test_output_certification_replays_duplicate_and_matches_checkpoint_tail() -> None:
    store, authority, finished_id = _setup()
    intent = _intent(finished_id)
    first = authority.settle_production_output_certification(intent=intent)
    before = tuple(store.read_events())

    duplicate = authority.settle_production_output_certification(intent=intent)
    changed = authority.settle_production_output_certification(
        intent=intent.model_copy(update={"correlation_id": "corr:certification:changed"})
    )
    full = authority.projector()
    tail = authority.projector(checkpoint_at=3)

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert tuple(store.read_events()) == before
    assert full.production_output_certifications == tail.production_output_certifications


def test_output_certification_rejects_tampered_activation_content_pin_without_writing() -> None:
    store, authority, finished_id = _setup()
    registry = authority._package_registry
    active = registry.active_patch_set
    assert active is not None
    assert len(active.capability_bindings) == 1
    registry._active = replace(
        active,
        capability_bindings=(
            replace(
                active.capability_bindings[0],
                family_content_digest="sha256:" + "f" * 64,
            ),
        ),
    )
    before = tuple(store.read_events())

    result = authority.settle_production_output_certification(intent=_intent(finished_id))

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "production_output_certification_binding_invalid"
    assert tuple(store.read_events()) == before
