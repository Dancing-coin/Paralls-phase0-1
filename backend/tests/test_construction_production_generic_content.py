from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.construction_production_content import (
    BlueprintContent,
    ComponentContent,
    FailurePolicyContent,
    FacilityContent,
    ProductionQualityPolicyContent,
    RecipeContent,
    grid_placement_conflict,
    occupied_grid_cells,
    resolve_failure_mode,
    ReservationRequirementContent,
    validate_reservation_requirements,
    validate_permit_evidence,
)
from app.gameplay.patch_runtime import PackageDefinition
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch


def _component(ref: str, *, width: int = 2, depth: int = 1) -> dict[str, object]:
    return {
        "component_ref": ref,
        "component_kind": "wall",
        "width": width,
        "depth": depth,
    }


def test_blueprint_content_requires_canonical_components_and_explicit_grid() -> None:
    content = BlueprintContent.model_validate(
        {
            "blueprint_ref": "blueprint:mill:standard@1",
            "facility_definition_ref": "definition:industrial-facilities-mill@1",
            "facility_schema_ref": "schema:industrial-facilities-facility@1",
            "facility_kind": "mill",
            "footprint": {"width": 4, "depth": 3},
            "allowed_orientations": [0, 90, 180, 270],
            "components": [_component("component:foundation@1"), _component("component:wall@1")],
            "material_requirements": {"item:stone@1": 10},
            "tool_refs": ["tool:masonry@1"],
            "qualification_refs": ["qualification:construction@1"],
            "duration_ticks": 12,
            "required_permit_ref": "permit:construction@1",
        }
    )

    assert content.footprint.width == 4
    assert tuple(component.component_ref for component in content.components) == (
        "component:foundation@1",
        "component:wall@1",
    )
    existing_blueprint = content.to_existing_blueprint()
    assert existing_blueprint.blueprint_ref == content.blueprint_ref
    assert existing_blueprint.facility_kind == "mill"
    assert existing_blueprint.required_permit_ref == "permit:construction@1"


def test_blueprint_content_accepts_explicit_zoning_ref_and_validates_zoning_evidence() -> None:
    content = BlueprintContent.model_validate(
        {
            "blueprint_ref": "blueprint:zoning:mill@1",
            "facility_definition_ref": "definition:mill@1",
            "facility_schema_ref": "schema:facility@1",
            "facility_kind": "mill",
            "footprint": {"width": 1, "depth": 1},
            "allowed_orientations": [0],
            "components": [_component("component:foundation@1", width=1, depth=1)],
            "material_requirements": {},
            "tool_refs": [],
            "qualification_refs": [],
            "duration_ticks": 1,
            "required_permit_ref": "permit:construction@1",
            "zoning_ref": "zoning:industrial@1",
        }
    )
    validate_permit_evidence(
        permit_evidence={
            "permit_ref": "permit:construction@1",
            "jurisdiction_ref": "jurisdiction:local",
            "zoning_ref": content.zoning_ref,
            "status": "active",
            "revision": 1,
        },
        required_permit_ref=content.required_permit_ref,
        jurisdiction_ref="jurisdiction:local",
        required_zoning_ref=content.zoning_ref,
    )


def test_blueprint_content_rejects_invalid_zoning_ref() -> None:
    with pytest.raises(ValidationError, match="platform_reference_invalid"):
        BlueprintContent.model_validate(
            {
                "blueprint_ref": "blueprint:zoning:invalid@1",
                "facility_definition_ref": "definition:mill@1",
                "facility_schema_ref": "schema:facility@1",
                "facility_kind": "mill",
                "footprint": {"width": 1, "depth": 1},
                "allowed_orientations": [0],
                "components": [_component("component:foundation@1", width=1, depth=1)],
                "material_requirements": {},
                "tool_refs": [],
                "qualification_refs": [],
                "duration_ticks": 1,
                "required_permit_ref": "permit:construction@1",
                "zoning_ref": "permit:not-zoning@1",
            }
        )


def test_blueprint_content_rejects_noncanonical_component_order() -> None:
    with pytest.raises(ValidationError, match="array_not_canonical"):
        BlueprintContent.model_validate(
            {
                "blueprint_ref": "blueprint:mill:standard@1",
                "facility_definition_ref": "definition:industrial-facilities-mill@1",
                "facility_schema_ref": "schema:industrial-facilities-facility@1",
                "facility_kind": "mill",
                "footprint": {"width": 4, "depth": 3},
                "allowed_orientations": [0, 90, 180, 270],
                "components": [_component("component:wall@1"), _component("component:foundation@1")],
                "material_requirements": {"item:stone@1": 10},
                "tool_refs": ["tool:masonry@1"],
                "qualification_refs": ["qualification:construction@1"],
                "duration_ticks": 12,
                "required_permit_ref": "permit:construction@1",
            }
        )


def test_content_rejects_authority_shaped_payload() -> None:
    with pytest.raises(ValidationError, match="authority_shaped"):
        BlueprintContent.model_validate(
            {
                "blueprint_ref": "blueprint:mill:standard@1",
                "facility_definition_ref": "definition:industrial-facilities-mill@1",
                "facility_schema_ref": "schema:industrial-facilities-facility@1",
                "facility_kind": "mill",
                "footprint": {"width": 1, "depth": 1},
                "allowed_orientations": [0],
                "components": [_component("component:foundation@1", width=1, depth=1)],
                "material_requirements": {"item:stone@1": 1},
                "tool_refs": [],
                "qualification_refs": [],
                "duration_ticks": 1,
                "required_permit_ref": "permit:construction@1",
                "owner_ref": "caller:owner",
            }
        )


def test_occupied_grid_cells_are_deterministic_for_discrete_orientation() -> None:
    components = (
        ComponentContent.model_validate(_component("component:foundation@1", width=2, depth=1)),
    )

    assert occupied_grid_cells(anchor=(3, 4), components=components, orientation=0) == frozenset(
        {(3, 4), (4, 4)}
    )
    assert occupied_grid_cells(anchor=(3, 4), components=components, orientation=90) == frozenset(
        {(3, 4), (3, 5)}
    )


def test_grid_placement_conflict_is_pure_and_only_uses_authoritative_cells() -> None:
    components = (ComponentContent.model_validate(_component("component:foundation@1", width=2, depth=1)),)
    committed = frozenset({(4, 4)})

    assert grid_placement_conflict(
        anchor=(3, 4), components=components, orientation=0, occupied_cells=committed
    ) is True
    assert grid_placement_conflict(
        anchor=(3, 4), components=components, orientation=0, occupied_cells=frozenset()
    ) is False


def test_facility_recipe_policy_content_is_strict_and_explicit() -> None:
    facility = FacilityContent.model_validate(
        {
            "facility_definition_ref": "definition:industrial-facilities-mill@1",
            "facility_schema_ref": "schema:industrial-facilities-facility@1",
            "facility_kind": "mill",
            "slot_capacity": 2,
            "condition_floor": 0.2,
            "maintenance_policy_ref": "policy:maintenance:mill@1",
            "procedural_component_refs": ["component:foundation@1"],
        }
    )
    recipe = RecipeContent.model_validate(
        {
            "recipe_ref": "recipe:industrial-facilities:flour@1",
            "recipe_schema_ref": "schema:construction-recipe@1",
            "input_slots": [{"item_definition_ref": "item:grain@1", "quantity": 2}],
            "tool_refs": ["tool:millstone@1"],
            "qualification_refs": ["qualification:milling@1"],
            "batch_size": 1,
            "duration_ticks": 4,
            "output_definition_ref": "item:flour@1",
            "quality_policy": {
                "policy_revision_ref": "policy:quality:flour@1",
                "minimum_quality": 0,
                "maximum_quality": 1,
            },
            "wear_policy_ref": "policy:wear:mill@1",
            "failure_policy": {"mode": "rework", "policy_revision_ref": "policy:failure:rework@1"},
        }
    )

    assert facility.slot_capacity == 2
    assert recipe.batch_size == 1
    assert recipe.failure_policy.mode == "rework"
    existing_recipe = recipe.to_existing_recipe()
    assert existing_recipe.batch_size == 1
    assert existing_recipe.quality_policy_revision == "policy:quality:flour@1"
    assert existing_recipe.wear_policy_ref == "policy:wear:mill@1"
    assert existing_recipe.failure_policy_mode == "rework"
    existing_facility = facility.to_existing_facility(
        facility_ref="facility:mill:content",
        plot_ref="plot:mill:content",
        condition=0.8,
        revision=2,
    )
    assert existing_facility.facility_kind == "mill"
    assert existing_facility.facility_definition_ref == "definition:industrial-facilities-mill@1"
    assert existing_facility.condition == 0.8
    assert existing_facility.revision == 2
    assert existing_facility.slot_capacity == 2
    assert existing_facility.maintenance_policy_ref == "policy:maintenance:mill@1"


def test_content_is_loaded_from_immutable_package_definition_with_revision_pin() -> None:
    definition = PackageDefinition.model_validate(
        {
            "definition_ref": "definition:industrial-facilities-mill@1",
            "definition_schema_ref": "schema:industrial-facilities-facility@1",
            "source_package_revision": "package:industrial-facilities:test@1",
            "typed_content": {
                "facility_definition_ref": "definition:industrial-facilities-mill@1",
                "facility_schema_ref": "schema:industrial-facilities-facility@1",
                "facility_kind": "mill",
                "slot_capacity": 1,
                "condition_floor": 0.1,
                "maintenance_policy_ref": "policy:maintenance:mill@1",
                "procedural_component_refs": ["component:foundation@1"],
            },
        }
    )

    content = FacilityContent.from_package_definition(definition)

    assert content.facility_kind == "mill"


def test_failure_policy_and_quality_bounds_are_validated() -> None:
    with pytest.raises(ValidationError):
        FailurePolicyContent.model_validate(
            {"mode": "release", "policy_revision_ref": "policy:failure@1", "unexpected": True}
        )


def test_facility_content_validates_runtime_condition_and_slot_capacity() -> None:
    facility = FacilityContent.model_validate(
        {
            "facility_definition_ref": "definition:industrial-facilities-mill@1",
            "facility_schema_ref": "schema:industrial-facilities-facility@1",
            "facility_kind": "mill",
            "slot_capacity": 2,
            "condition_floor": 0.2,
            "maintenance_policy_ref": "policy:maintenance:mill@1",
            "procedural_component_refs": ["component:foundation@1"],
        }
    )

    assert facility.validate_runtime(condition=0.5, active_slot_count=1) is None
    with pytest.raises(ValueError, match="condition_below_floor"):
        facility.validate_runtime(condition=0.1, active_slot_count=0)
    with pytest.raises(ValueError, match="slot_capacity_exceeded"):
        facility.validate_runtime(condition=0.5, active_slot_count=2)


def test_failure_policy_resolution_is_explicit_and_has_no_default() -> None:
    policy = FailurePolicyContent(mode="rework", policy_revision_ref="policy:failure:rework@1")
    assert resolve_failure_mode(policy=policy, failure_reason="quality_below_minimum") == "rework"

    with pytest.raises(ValueError, match="failure_policy_required"):
        resolve_failure_mode(policy=None, failure_reason="unknown")


def test_start_run_preserves_explicit_recipe_policy_pins_on_the_run_value() -> None:
    recipe = RecipeContent.model_validate(
        {
            "recipe_ref": "recipe:industrial-facilities:flour@1",
            "recipe_schema_ref": "schema:construction-recipe@1",
            "input_slots": [{"item_definition_ref": "item:grain@1", "quantity": 2}],
            "tool_refs": [],
            "qualification_refs": [],
            "batch_size": 3,
            "duration_ticks": 4,
            "output_definition_ref": "item:flour@1",
            "quality_policy": {
                "policy_revision_ref": "policy:quality:flour@1",
                "minimum_quality": 0,
                "maximum_quality": 1,
            },
            "wear_policy_ref": "policy:wear:mill@1",
            "failure_policy": {"mode": "loss", "policy_revision_ref": "policy:failure:loss@1"},
        }
    )
    run = ConstructionProductionAuthority.start_run(
        facility=Facility(
            facility_ref="facility:test:mill",
            plot_ref="plot:test:mill",
            facility_kind="mill",
            condition=1.0,
            revision=1,
        ),
        recipe=recipe.to_existing_recipe(),
        run_ref="run:test:policy",
        tick=2,
    )

    assert run.batch_size == 3
    assert run.quality_policy_revision == "policy:quality:flour@1"
    assert run.wear_policy_ref == "policy:wear:mill@1"
    assert run.failure_policy_mode == "loss"


def test_start_run_rejects_when_facility_slot_capacity_is_exhausted() -> None:
    facility = FacilityContent.model_validate(
        {
            "facility_definition_ref": "definition:industrial-facilities-mill@1",
            "facility_schema_ref": "schema:industrial-facilities-facility@1",
            "facility_kind": "mill",
            "slot_capacity": 1,
            "condition_floor": 0.2,
            "maintenance_policy_ref": "policy:maintenance:mill@1",
            "procedural_component_refs": ["component:foundation@1"],
        }
    )
    runtime_facility = facility.to_existing_facility(
        facility_ref="facility:mill:capacity",
        plot_ref="plot:mill:capacity",
        condition=1.0,
        revision=1,
    )
    recipe = RecipeContent.model_validate(
        {
            "recipe_ref": "recipe:mill:capacity@1",
            "recipe_schema_ref": "schema:construction-recipe@1",
            "input_slots": [],
            "tool_refs": [],
            "qualification_refs": [],
            "batch_size": 1,
            "duration_ticks": 2,
            "output_definition_ref": "item:flour@1",
            "quality_policy": {"policy_revision_ref": "policy:quality@1", "minimum_quality": 0, "maximum_quality": 1},
            "wear_policy_ref": "policy:wear@1",
            "failure_policy": {"mode": "terminal", "policy_revision_ref": "policy:failure@1"},
        }
    )
    first = ConstructionProductionAuthority.start_run(
        facility=runtime_facility,
        recipe=recipe.to_existing_recipe(),
        run_ref="run:capacity:1",
        tick=0,
    )
    with pytest.raises(ValueError, match="slot_capacity_exceeded"):
        ConstructionProductionAuthority.start_run(
            facility=runtime_facility,
            recipe=recipe.to_existing_recipe(),
            run_ref="run:capacity:2",
            tick=0,
            active_slot_count=1,
            slot_capacity=facility.slot_capacity,
        )
    assert first.run_ref == "run:capacity:1"


def test_settle_start_run_derives_active_slot_count_from_construction_projection() -> None:
    from app.gameplay.event_store import GameplayEventStore

    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:slot-runtime",
        plot_ref="plot:mill:slot-runtime",
        facility_kind="mill",
        condition=1.0,
        revision=1,
        slot_capacity=1,
    )
    recipe = RecipeContent.model_validate(
        {
            "recipe_ref": "recipe:mill:slot-runtime@1",
            "recipe_schema_ref": "schema:construction-recipe@1",
            "input_slots": [],
            "tool_refs": [],
            "qualification_refs": [],
            "batch_size": 1,
            "duration_ticks": 5,
            "output_definition_ref": "item:flour@1",
            "quality_policy": {"policy_revision_ref": "policy:quality@1", "minimum_quality": 0, "maximum_quality": 1},
            "wear_policy_ref": "policy:wear@1",
            "failure_policy": {"mode": "terminal", "policy_revision_ref": "policy:failure@1"},
        }
    ).to_existing_recipe()
    first = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:slot-runtime:1",
        tick=0,
        command_id="command:slot-runtime:1",
        idempotency_key="idempotency:slot-runtime:1",
        causation_id="causation:slot-runtime:1",
        correlation_id="correlation:slot-runtime:1",
    )
    second = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:slot-runtime:2",
        tick=0,
        command_id="command:slot-runtime:2",
        idempotency_key="idempotency:slot-runtime:2",
        causation_id="causation:slot-runtime:2",
        correlation_id="correlation:slot-runtime:2",
    )

    assert first.committed
    assert not second.committed
    assert second.failure is not None
    assert second.failure.error_code == "slot_capacity_exceeded"


def test_reservation_requirements_require_owner_and_revision_pins() -> None:
    requirements = (
        ReservationRequirementContent(
            reservation_kind="material",
            owner_family_ref="inventory",
            reservation_ref="reservation:grain:1",
            revision=3,
        ),
        ReservationRequirementContent(
            reservation_kind="worker",
            owner_family_ref="organization",
            reservation_ref="reservation:worker:1",
            revision=2,
        ),
    )
    assert validate_reservation_requirements(requirements=requirements, provided_refs=("reservation:grain:1", "reservation:worker:1")) is None

    with pytest.raises(ValueError, match="reservation_requirement_missing"):
        validate_reservation_requirements(requirements=requirements, provided_refs=("reservation:grain:1",))

    with pytest.raises(ValueError, match="reservation_requirement_unexpected"):
        validate_reservation_requirements(
            requirements=requirements,
            provided_refs=("reservation:extra:1", "reservation:grain:1", "reservation:worker:1"),
        )


def test_reservation_requirements_validate_owner_issued_active_revision_evidence() -> None:
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:grain:1",
        revision=3,
    )
    validate_reservation_requirements(
        requirements=(requirement,),
        provided_refs=(requirement.reservation_ref,),
        reservation_evidence={
            requirement.reservation_ref: {
                "owner_family_ref": "inventory",
                "status": "active",
                "revision": 3,
            }
        },
    )


def test_reservation_requirements_reject_stale_or_wrong_owner_evidence() -> None:
    requirement = ReservationRequirementContent(
        reservation_kind="worker",
        owner_family_ref="organization",
        reservation_ref="reservation:worker:1",
        revision=2,
    )
    with pytest.raises(ValueError, match="reservation_requirement_evidence_conflict"):
        validate_reservation_requirements(
            requirements=(requirement,),
            provided_refs=(requirement.reservation_ref,),
            reservation_evidence={
                requirement.reservation_ref: {
                    "owner_family_ref": "inventory",
                    "status": "active",
                    "revision": 2,
                }
            },
        )


def test_start_run_rejects_owner_reservation_evidence_conflict_before_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:reservation-proof",
        plot_ref="plot:mill:reservation-proof",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:reservation-proof@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:grain:proof",
        revision=2,
    )
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:reservation-proof:1",
        tick=0,
        command_id="command:reservation-proof:1",
        idempotency_key="idempotency:reservation-proof:1",
        causation_id="cause:reservation-proof:1",
        correlation_id="corr:reservation-proof:1",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence={
            requirement.reservation_ref: {
                "owner_family_ref": "organization",
                "status": "active",
                "revision": 2,
            }
        },
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_run_reservation_evidence_conflict"
    assert store.read_events() == []


def test_start_run_rejects_forged_owner_reservation_source_event_before_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:reservation-source",
        plot_ref="plot:mill:reservation-source",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:reservation-source@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:grain:source",
        revision=2,
    )
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:reservation-source:1",
        tick=0,
        command_id="command:reservation-source:1",
        idempotency_key="idempotency:reservation-source:1",
        causation_id="cause:reservation-source:1",
        correlation_id="corr:reservation-source:1",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence={
            requirement.reservation_ref: {
                "owner_family_ref": "inventory",
                "status": "active",
                "revision": 2,
                "source_event_id": "event:missing-reservation-source",
            }
        },
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_run_reservation_evidence_source_missing"
    assert store.read_events() == []


def test_start_run_rejects_unbound_reservation_evidence_before_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:reservation-unbound",
        plot_ref="plot:mill:reservation-unbound",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:reservation-unbound@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:reservation-unbound:1",
        tick=0,
        command_id="command:reservation-unbound:1",
        idempotency_key="idempotency:reservation-unbound:1",
        causation_id="cause:reservation-unbound:1",
        correlation_id="corr:reservation-unbound:1",
        reservation_evidence={"reservation:unbound": {"owner_family_ref": "inventory", "status": "active", "revision": 1}},
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_run_reservation_evidence_unbound"
    assert store.read_events() == []


def test_start_run_rejects_consumed_owner_reservation_source_before_append() -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:inventory:organization:mill"
    created = build_atomic_event_batch(
        command_id="reservation-created",
        principal_ref="actor_gameplay.inventory_domain",
        stream_id=source_stream,
        expected_revision=0,
        event_specs=[
            (
                "gameplay.inventory.reservation_created",
                {"reservation_ref": "reservation:grain:consumed", "item_id": "item:grain:1", "quantity": 1},
            )
        ],
        idempotency_key="reservation-created",
        causation_id="cause:reservation-created",
        correlation_id="corr:reservation-created",
    )
    assert store.append_batch(created).committed
    consumed = build_atomic_event_batch(
        command_id="reservation-consumed",
        principal_ref="actor_gameplay.inventory_domain",
        stream_id=source_stream,
        expected_revision=1,
        event_specs=[
            (
                "gameplay.inventory.reservation_consumed",
                {"reservation_ref": "reservation:grain:consumed"},
            )
        ],
        idempotency_key="reservation-consumed",
        causation_id="cause:reservation-consumed",
        correlation_id="corr:reservation-consumed",
    )
    assert store.append_batch(consumed).committed
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:reservation-consumed",
        plot_ref="plot:mill:reservation-consumed",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:reservation-consumed@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:grain:consumed",
        revision=1,
    )
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:reservation-consumed:1",
        tick=0,
        command_id="command:reservation-consumed:1",
        idempotency_key="idempotency:reservation-consumed:1",
        causation_id="cause:reservation-consumed:1",
        correlation_id="corr:reservation-consumed:1",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence={
            requirement.reservation_ref: {
                "owner_family_ref": "inventory",
                "status": "active",
                "revision": 1,
                "source_event_id": created.events[0].event_id,
            }
        },
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_run_reservation_evidence_conflict"


def test_start_run_rejects_consumed_economy_reservation_source_before_append() -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:economy"
    reserved = build_atomic_event_batch(
        command_id="budget-reserved",
        principal_ref="actor_gameplay.economy_domain",
        stream_id=source_stream,
        expected_revision=0,
        event_specs=[
            (
                "gameplay.economy.budget_reserved",
                {
                    "reservation_ref": "reservation:budget:consumed",
                    "account_id": "account:builder",
                    "amount_minor": 10,
                    "currency_ref": "currency:local",
                },
            )
        ],
        idempotency_key="budget-reserved",
        causation_id="cause:budget-reserved",
        correlation_id="corr:budget-reserved",
    )
    assert store.append_batch(reserved).committed
    consumed = build_atomic_event_batch(
        command_id="budget-consumed",
        principal_ref="actor_gameplay.economy_domain",
        stream_id=source_stream,
        expected_revision=1,
        event_specs=[
            (
                "gameplay.economy.public_project_budget_consumed",
                {"source_reservation_event_id": reserved.events[0].event_id},
            )
        ],
        idempotency_key="budget-consumed",
        causation_id="cause:budget-consumed",
        correlation_id="corr:budget-consumed",
    )
    assert store.append_batch(consumed).committed

    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:budget-consumed",
        plot_ref="plot:mill:budget-consumed",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:budget-consumed@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    requirement = ReservationRequirementContent(
        reservation_kind="budget",
        owner_family_ref="economy",
        reservation_ref="reservation:budget:consumed",
        revision=1,
    )
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:budget-consumed:1",
        tick=0,
        command_id="command:budget-consumed:1",
        idempotency_key="idempotency:budget-consumed:1",
        causation_id="cause:budget-consumed:1",
        correlation_id="corr:budget-consumed:1",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence={
            requirement.reservation_ref: {
                "owner_family_ref": "economy",
                "status": "active",
                "revision": 1,
                "source_event_id": reserved.events[0].event_id,
            }
        },
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_run_reservation_evidence_conflict"
    assert store.get_stream_head("gameplay:construction_production:facility:mill:budget-consumed") == 0


def test_replay_rejects_economy_reservation_consumed_after_run_start() -> None:
    store = GameplayEventStore()
    reserved = build_atomic_event_batch(
        command_id="budget-reserved-replay",
        principal_ref="actor_gameplay.economy_domain",
        stream_id="gameplay:economy",
        expected_revision=0,
        event_specs=[
            (
                "gameplay.economy.budget_reserved",
                {
                    "reservation_ref": "reservation:budget:replay",
                    "account_id": "account:builder",
                    "amount_minor": 10,
                    "currency_ref": "currency:local",
                },
            )
        ],
        idempotency_key="budget-reserved-replay",
        causation_id="cause:budget-reserved-replay",
        correlation_id="corr:budget-reserved-replay",
    )
    assert store.append_batch(reserved).committed
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:budget-replay",
        plot_ref="plot:mill:budget-replay",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:budget-replay@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    requirement = ReservationRequirementContent(
        reservation_kind="budget",
        owner_family_ref="economy",
        reservation_ref="reservation:budget:replay",
        revision=1,
    )
    started = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:budget-replay:1",
        tick=0,
        command_id="command:budget-replay:1",
        idempotency_key="idempotency:budget-replay:1",
        causation_id="cause:budget-replay:1",
        correlation_id="corr:budget-replay:1",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence={
            requirement.reservation_ref: {
                "owner_family_ref": "economy",
                "status": "active",
                "revision": 1,
                "source_event_id": reserved.events[0].event_id,
            }
        },
    )
    assert started.committed
    consumed = build_atomic_event_batch(
        command_id="budget-consumed-replay",
        principal_ref="actor_gameplay.economy_domain",
        stream_id="gameplay:economy",
        expected_revision=1,
        event_specs=[
            (
                "gameplay.economy.public_project_budget_consumed",
                {"source_reservation_event_id": reserved.events[0].event_id},
            )
        ],
        idempotency_key="budget-consumed-replay",
        causation_id="cause:budget-consumed-replay",
        correlation_id="corr:budget-consumed-replay",
    )
    assert store.append_batch(consumed).committed
    with pytest.raises(ValueError, match="construction_run_reservation_evidence_source_conflict"):
        authority.projector()


def test_start_run_rejects_unmapped_owner_reservation_source_event_before_append() -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:organization:builder"
    source = build_atomic_event_batch(
        command_id="organization-reservation",
        principal_ref="actor_gameplay.organization_domain",
        stream_id=source_stream,
        expected_revision=0,
        event_specs=[("gameplay.organization.marker_recorded", {"reservation_ref": "reservation:worker:unmapped"})],
        idempotency_key="organization-reservation",
        causation_id="cause:organization-reservation",
        correlation_id="corr:organization-reservation",
    )
    assert store.append_batch(source).committed
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:reservation-unmapped",
        plot_ref="plot:mill:reservation-unmapped",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:reservation-unmapped@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    requirement = ReservationRequirementContent(
        reservation_kind="worker",
        owner_family_ref="organization",
        reservation_ref="reservation:worker:unmapped",
        revision=1,
    )
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:reservation-unmapped:1",
        tick=0,
        command_id="command:reservation-unmapped:1",
        idempotency_key="idempotency:reservation-unmapped:1",
        causation_id="cause:reservation-unmapped:1",
        correlation_id="corr:reservation-unmapped:1",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence={
            requirement.reservation_ref: {
                "owner_family_ref": "organization",
                "status": "active",
                "revision": 1,
                "source_event_id": source.events[0].event_id,
            }
        },
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_run_reservation_evidence_conflict"


def test_start_run_persists_owner_reservation_evidence_for_full_and_tail_replay() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:mill:reservation-proof-ok",
        plot_ref="plot:mill:reservation-proof-ok",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:mill:reservation-proof-ok@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    requirement = ReservationRequirementContent(
        reservation_kind="material",
        owner_family_ref="inventory",
        reservation_ref="reservation:grain:proof-ok",
        revision=4,
    )
    evidence = {
        requirement.reservation_ref: {
            "owner_family_ref": "inventory",
            "status": "active",
            "revision": 4,
        }
    }
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:reservation-proof-ok:1",
        tick=0,
        command_id="command:reservation-proof-ok:1",
        idempotency_key="idempotency:reservation-proof-ok:1",
        causation_id="cause:reservation-proof-ok:1",
        correlation_id="corr:reservation-proof-ok:1",
        reservation_refs=(requirement.reservation_ref,),
        reservation_requirements=(requirement,),
        reservation_evidence=evidence,
    )
    assert result.committed
    event = store.read_events()[-1]
    assert event.payload["reservation_evidence"] == evidence
    assert authority.projector().runs["run:reservation-proof-ok:1"].reservation_evidence == evidence
    assert authority.projector(checkpoint_at=0).runs["run:reservation-proof-ok:1"].reservation_evidence == evidence
    transaction = store.read_transactions()[-1]
    assert transaction.pinned_revisions["reservation:reservation:grain:proof-ok"] == 4


def test_run_started_replay_rejects_reservation_ref_order_and_evidence_key_tamper() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:replay:reservation-shape",
        plot_ref="plot:replay:reservation-shape",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    recipe = Recipe(
        recipe_ref="recipe:replay:reservation-shape@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:local", owner_ref="organization:mill"),
        facility=facility,
        command_id="command:replay:reservation-acquire",
        idempotency_key="idempotency:replay:reservation-acquire",
        causation_id="cause:replay:reservation-acquire",
        correlation_id="corr:replay:reservation-acquire",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:replay:reservation-shape",
        tick=0,
        command_id="command:replay:reservation-start",
        idempotency_key="idempotency:replay:reservation-start",
        causation_id="cause:replay:reservation-start",
        correlation_id="corr:replay:reservation-start",
    ).committed
    start = next(event for event in store.read_events() if event.event_type == "gameplay.construction_production.run_started")
    tampered = start.model_copy(
        update={
            "payload": {
                **start.payload,
                "reservation_refs": ("reservation:z", "reservation:a"),
                "reservation_evidence": {"reservation:z": {"owner_family_ref": "inventory", "status": "active", "revision": 1}},
            }
        },
        deep=True,
    )
    with pytest.raises(ValueError, match="construction_run_reservation_evidence_invalid"):
        authority._projector.rebuild([tampered])


def test_run_started_replay_rejects_facility_stream_or_privacy_tamper() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:replay:run-source",
        plot_ref="plot:replay:run-source",
        facility_kind="mill",
        condition=1.0,
        revision=0,
    )
    recipe = Recipe(
        recipe_ref="recipe:replay:run-source@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    plot = Plot(
        plot_ref=facility.plot_ref,
        jurisdiction_ref="jurisdiction:local",
        owner_ref="organization:mill",
        revision=1,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="command:replay:run-source:acquire",
        idempotency_key="idempotency:replay:run-source:acquire",
        causation_id="cause:replay:run-source:acquire",
        correlation_id="corr:replay:run-source:acquire",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:replay:run-source",
        tick=0,
        command_id="command:replay:run-source:start",
        idempotency_key="idempotency:replay:run-source:start",
        causation_id="cause:replay:run-source:start",
        correlation_id="corr:replay:run-source:start",
    ).committed
    start = next(event for event in store.read_events() if event.event_type == "gameplay.construction_production.run_started")
    wrong_stream = start.model_copy(
        update={
            "stream_id": "gameplay:construction_production:facility:other",
        },
        deep=True,
    )
    with pytest.raises(ValueError, match="production_run_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], wrong_stream])
    private = start.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="production_run_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], private])


def test_facility_acquisition_replay_rejects_stream_privacy_or_identity_tamper() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(
        plot_ref="plot:replay:acquisition-source",
        jurisdiction_ref="jurisdiction:local",
        owner_ref="organization:mill",
        revision=1,
    )
    facility = Facility(
        facility_ref="facility:replay:acquisition-source",
        plot_ref=plot.plot_ref,
        facility_kind="mill",
        condition=1.0,
        revision=0,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="command:replay:acquisition-source",
        idempotency_key="idempotency:replay:acquisition-source",
        causation_id="cause:replay:acquisition-source",
        correlation_id="corr:replay:acquisition-source",
    ).committed
    event = store.read_events()[-1]
    wrong_stream = event.model_copy(
        update={"stream_id": "gameplay:construction_production:facility:other"}, deep=True
    )
    with pytest.raises(ValueError, match="facility_acquisition_source_conflict"):
        authority._projector.rebuild([wrong_stream])
    private = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="facility_acquisition_source_conflict"):
        authority._projector.rebuild([private])


def test_completed_run_records_owner_output_quantity_and_quality_evidence() -> None:
    from app.gameplay.construction_production_runtime import ConstructionProductionAuthority

    recipe = RecipeContent.model_validate(
        {
            "recipe_ref": "recipe:mill:output@1",
            "recipe_schema_ref": "schema:construction-recipe@1",
            "input_slots": [],
            "tool_refs": [],
            "qualification_refs": [],
            "batch_size": 2,
            "duration_ticks": 1,
            "output_definition_ref": "item:flour@1",
            "quality_policy": {"policy_revision_ref": "policy:quality@1", "minimum_quality": 0.2, "maximum_quality": 0.9},
            "wear_policy_ref": "policy:wear@1",
            "failure_policy": {"mode": "terminal", "policy_revision_ref": "policy:failure@1"},
        }
    )
    run = ConstructionProductionAuthority.start_run(
        facility=Facility(
            facility_ref="facility:mill:output",
            plot_ref="plot:mill:output",
            facility_kind="mill",
            condition=1.0,
            revision=1,
        ),
        recipe=recipe.to_existing_recipe(),
        run_ref="run:output:1",
        tick=0,
    )
    completed = ConstructionProductionAuthority.finish_run(
        run,
        tick=1,
        recipe=recipe.to_existing_recipe(),
        output_quantity=4,
        output_quality=0.75,
    )

    assert completed.output_quantity == 4
    assert completed.output_quality == 0.75


def test_construction_recipe_derives_output_quantity_from_batch_size() -> None:
    content = RecipeContent.model_validate(
        {
            "recipe_ref": "recipe:mill:quantity@1",
            "recipe_schema_ref": "schema:construction-recipe@1",
            "input_slots": [],
            "tool_refs": [],
            "qualification_refs": [],
            "batch_size": 3,
            "duration_ticks": 1,
            "output_definition_ref": "item:flour@1",
            "output_quantity": 2,
            "quality_policy": {"policy_revision_ref": "policy:quality@1", "minimum_quality": 0, "maximum_quality": 1},
            "wear_policy_ref": "policy:wear@1",
            "failure_policy": {"mode": "terminal", "policy_revision_ref": "policy:failure@1"},
        }
    )
    assert content.to_existing_recipe().output_quantity == 6


def test_maintenance_obligation_persists_facility_policy_pins_and_replay_rejects_tamper() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(
        plot_ref="plot:maintenance:pins",
        jurisdiction_ref="jurisdiction:local",
        owner_ref="organization:mill",
        revision=1,
    )
    facility = Facility(
        facility_ref="facility:maintenance:pins",
        plot_ref=plot.plot_ref,
        facility_kind="mill",
        condition=1.0,
        revision=1,
        maintenance_policy_ref="policy:maintenance:mill@1",
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="command:maintenance:acquire",
        idempotency_key="idempotency:maintenance:acquire",
        causation_id="cause:maintenance:acquire",
        correlation_id="corr:maintenance:acquire",
    ).committed
    recipe = Recipe(
        recipe_ref="recipe:maintenance:pins@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:maintenance:pins",
        tick=0,
        command_id="command:maintenance:start",
        idempotency_key="idempotency:maintenance:start",
        causation_id="cause:maintenance:start",
        correlation_id="corr:maintenance:start",
    ).committed
    run = authority.projector().runs["run:maintenance:pins"]
    result = authority.settle_maintenance_obligation(
        run,
        obligation_ref="obligation:maintenance:pins",
        command_id="command:maintenance:obligation",
        idempotency_key="idempotency:maintenance:obligation",
        causation_id="cause:maintenance:obligation",
        correlation_id="corr:maintenance:obligation",
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["facility_ref"] == facility.facility_ref
    assert event.payload["project_ref"] == plot.plot_ref
    assert event.payload["facility_revision"] == 1
    assert event.payload["maintenance_policy_ref"] == "policy:maintenance:mill@1"
    tampered = event.model_copy(
        update={"payload": {**event.payload, "project_ref": "plot:other"}}, deep=True
    )
    with pytest.raises(ValueError, match="construction_maintenance_obligation_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_maintenance_obligation_changed_duplicate_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:maintenance:duplicate",
        plot_ref="plot:maintenance:duplicate",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    plot = Plot(
        plot_ref=facility.plot_ref,
        jurisdiction_ref="jurisdiction:local",
        owner_ref="organization:mill",
        revision=1,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="command:maintenance:duplicate:acquire",
        idempotency_key="idempotency:maintenance:duplicate:acquire",
        causation_id="cause:maintenance:duplicate:acquire",
        correlation_id="corr:maintenance:duplicate:acquire",
    ).committed
    recipe = Recipe(
        recipe_ref="recipe:maintenance:duplicate@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:maintenance:duplicate",
        tick=0,
        command_id="command:maintenance:duplicate:start",
        idempotency_key="idempotency:maintenance:duplicate:start",
        causation_id="cause:maintenance:duplicate:start",
        correlation_id="corr:maintenance:duplicate:start",
    ).committed
    run = authority.projector().runs["run:maintenance:duplicate"]
    first = authority.settle_maintenance_obligation(
        run,
        obligation_ref="obligation:maintenance:duplicate:a",
        command_id="command:maintenance:duplicate:obligation:a",
        idempotency_key="idempotency:maintenance:duplicate:obligation",
        causation_id="cause:maintenance:duplicate:obligation",
        correlation_id="corr:maintenance:duplicate:obligation",
    )
    assert first.committed
    before = tuple(store.read_events())
    changed = authority.settle_maintenance_obligation(
        run,
        obligation_ref="obligation:maintenance:duplicate:b",
        command_id="command:maintenance:duplicate:obligation:b",
        idempotency_key="idempotency:maintenance:duplicate:obligation",
        causation_id="cause:maintenance:duplicate:obligation",
        correlation_id="corr:maintenance:duplicate:obligation",
    )
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert tuple(store.read_events()) == before


def test_maintenance_obligation_replay_rejects_missing_obligation_ref_with_stable_error() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:maintenance:missing-ref",
        plot_ref="plot:maintenance:missing-ref",
        facility_kind="mill",
        condition=1.0,
        revision=1,
    )
    plot = Plot(
        plot_ref=facility.plot_ref,
        jurisdiction_ref="jurisdiction:local",
        owner_ref="organization:mill",
        revision=1,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="command:maintenance:missing-ref:acquire",
        idempotency_key="idempotency:maintenance:missing-ref:acquire",
        causation_id="cause:maintenance:missing-ref:acquire",
        correlation_id="corr:maintenance:missing-ref:acquire",
    ).committed
    recipe = Recipe(
        recipe_ref="recipe:maintenance:missing-ref@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:maintenance:missing-ref",
        tick=0,
        command_id="command:maintenance:missing-ref:start",
        idempotency_key="idempotency:maintenance:missing-ref:start",
        causation_id="cause:maintenance:missing-ref:start",
        correlation_id="corr:maintenance:missing-ref:start",
    ).committed
    run = authority.projector().runs["run:maintenance:missing-ref"]
    result = authority.settle_maintenance_obligation(
        run,
        obligation_ref="obligation:maintenance:missing-ref",
        command_id="command:maintenance:missing-ref:obligation",
        idempotency_key="idempotency:maintenance:missing-ref:obligation",
        causation_id="cause:maintenance:missing-ref:obligation",
        correlation_id="corr:maintenance:missing-ref:obligation",
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    tampered = event.model_copy(
        update={"payload": {key: value for key, value in event.payload.items() if key != "obligation_ref"}},
        deep=True,
    )
    with pytest.raises(ValueError, match="construction_maintenance_obligation_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])
    with pytest.raises(ValidationError):
        ProductionQualityPolicyContent.model_validate(
            {"policy_revision_ref": "policy:quality@1", "minimum_quality": 0.8, "maximum_quality": 0.2}
        )
