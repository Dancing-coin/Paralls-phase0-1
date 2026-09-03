"""Typed, owner-bound Construction/Production content primitives.

These models validate package content and deterministic grid geometry only. They
do not select an authority, mutate projections, or append events.
"""

from __future__ import annotations

from typing import Literal, Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel
from app.gameplay.patch_runtime import (
    _require_author_canonical,
    _require_platform_ref,
    _validate_platform_content,
)


class _ContentModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def reject_authority_coordinates(cls, value: object) -> object:
        _validate_platform_content(value)
        return value


class GridFootprint(_ContentModel):
    width: int = Field(gt=0)
    depth: int = Field(gt=0)


class ComponentContent(_ContentModel):
    component_ref: str = Field(min_length=1)
    component_kind: str = Field(min_length=1)
    width: int = Field(gt=0)
    depth: int = Field(gt=0)
    offset_x: int = 0
    offset_y: int = 0

    @model_validator(mode="after")
    def validate_reference(self) -> "ComponentContent":
        _require_platform_ref(self.component_ref, prefix="component:")
        return self


class BlueprintContent(_ContentModel):
    blueprint_ref: str = Field(min_length=1)
    facility_definition_ref: str = Field(min_length=1)
    facility_schema_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    footprint: GridFootprint
    allowed_orientations: tuple[int, ...]
    components: tuple[ComponentContent, ...]
    material_requirements: dict[str, int]
    tool_refs: tuple[str, ...]
    qualification_refs: tuple[str, ...]
    duration_ticks: int = Field(gt=0)
    required_permit_ref: str = Field(min_length=1)
    zoning_ref: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "BlueprintContent":
        _require_platform_ref(self.blueprint_ref, prefix="blueprint:")
        _require_platform_ref(self.facility_definition_ref, prefix="definition:")
        _require_platform_ref(self.facility_schema_ref, prefix="schema:")
        _require_platform_ref(self.required_permit_ref, prefix="permit:")
        if self.zoning_ref is not None:
            _require_platform_ref(self.zoning_ref, prefix="zoning:")
        if not self.allowed_orientations or any(value not in {0, 90, 180, 270} for value in self.allowed_orientations):
            raise ValueError("construction_blueprint_orientation_invalid")
        if tuple(self.allowed_orientations) != tuple(sorted(set(self.allowed_orientations))):
            raise ValueError("construction_blueprint_array_not_canonical")
        _require_author_canonical(self.components, identity=lambda value: value.component_ref)
        _require_author_canonical(self.tool_refs, identity=lambda value: value)
        _require_author_canonical(self.qualification_refs, identity=lambda value: value)
        material_keys = tuple(self.material_requirements)
        if material_keys != tuple(sorted(material_keys)):
            raise ValueError("construction_blueprint_array_not_canonical")
        for ref, quantity in self.material_requirements.items():
            _require_platform_ref(ref, prefix="item:")
            if quantity <= 0:
                raise ValueError("construction_blueprint_material_quantity_invalid")
        for ref in self.tool_refs:
            _require_platform_ref(ref, prefix="tool:")
        for ref in self.qualification_refs:
            _require_platform_ref(ref, prefix="qualification:")
        return self

    def to_existing_blueprint(self) -> object:
        """Create the compatible Blueprint value without mutating world state."""
        from app.gameplay.construction_production_runtime import Blueprint

        return Blueprint.model_validate(
            {
                "blueprint_ref": self.blueprint_ref,
                "facility_kind": self.facility_kind,
                "required_permit_ref": self.required_permit_ref,
                "revision": 1,
            }
        )

    @classmethod
    def from_package_definition(cls, definition: object) -> "BlueprintContent":
        source_revision = getattr(definition, "source_package_revision", "")
        typed_content = getattr(definition, "typed_content", None)
        if not source_revision or not isinstance(typed_content, Mapping):
            raise ValueError("construction_blueprint_package_definition_invalid")
        return cls.model_validate(typed_content)


class FacilityContent(_ContentModel):
    facility_definition_ref: str = Field(min_length=1)
    facility_schema_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    slot_capacity: int = Field(gt=0)
    condition_floor: float = Field(ge=0, le=1)
    maintenance_policy_ref: str = Field(min_length=1)
    procedural_component_refs: tuple[str, ...]

    @model_validator(mode="after")
    def validate_content(self) -> "FacilityContent":
        _require_platform_ref(self.facility_definition_ref, prefix="definition:")
        _require_platform_ref(self.facility_schema_ref, prefix="schema:")
        _require_platform_ref(self.maintenance_policy_ref, prefix="policy:")
        _require_author_canonical(self.procedural_component_refs, identity=lambda value: value)
        for ref in self.procedural_component_refs:
            _require_platform_ref(ref, prefix="component:")
        return self

    def to_existing_facility(
        self,
        *,
        facility_ref: str,
        plot_ref: str,
        condition: float,
        revision: int,
        lifecycle_status: str | None = None,
    ) -> object:
        """Materialize a compatible Facility value from owner/runtime identity."""
        if not facility_ref or not plot_ref:
            raise ValueError("construction_facility_runtime_identity_required")
        if condition < self.condition_floor:
            raise ValueError("construction_facility_condition_below_floor")
        if lifecycle_status not in {None, "active", "decommissioned"}:
            raise ValueError("construction_facility_lifecycle_invalid")
        from app.gameplay.construction_production_runtime import Facility

        return Facility(
            facility_ref=facility_ref,
            plot_ref=plot_ref,
            facility_kind=self.facility_kind,
            facility_definition_ref=self.facility_definition_ref,
            condition=condition,
            revision=revision,
            lifecycle_status=lifecycle_status,
            slot_capacity=self.slot_capacity,
            maintenance_policy_ref=self.maintenance_policy_ref,
        )

    def validate_runtime(self, *, condition: float, active_slot_count: int) -> None:
        if condition < self.condition_floor:
            raise ValueError("construction_facility_condition_below_floor")
        if active_slot_count < 0 or active_slot_count >= self.slot_capacity:
            raise ValueError("construction_facility_slot_capacity_exceeded")

    @classmethod
    def from_package_definition(cls, definition: object) -> "FacilityContent":
        source_revision = getattr(definition, "source_package_revision", "")
        typed_content = getattr(definition, "typed_content", None)
        if not source_revision or not isinstance(typed_content, Mapping):
            raise ValueError("construction_facility_package_definition_invalid")
        content = cls.model_validate(typed_content)
        if content.facility_definition_ref != getattr(definition, "definition_ref", None):
            raise ValueError("construction_facility_definition_identity_mismatch")
        return content


class ProductionQualityPolicyContent(_ContentModel):
    policy_revision_ref: str = Field(min_length=1)
    minimum_quality: float = Field(ge=0, le=1)
    maximum_quality: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> "ProductionQualityPolicyContent":
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        if self.minimum_quality > self.maximum_quality:
            raise ValueError("construction_quality_bounds_invalid")
        return self


class FailurePolicyContent(_ContentModel):
    mode: Literal["release", "loss", "rework", "terminal"]
    policy_revision_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reference(self) -> "FailurePolicyContent":
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        return self


class RecipeInputContent(_ContentModel):
    item_definition_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_reference(self) -> "RecipeInputContent":
        _require_platform_ref(self.item_definition_ref, prefix="item:")
        return self


class ReservationRequirementContent(_ContentModel):
    reservation_kind: Literal["material", "tool", "worker", "budget"]
    owner_family_ref: Literal["inventory", "organization", "economy", "skill"]
    reservation_ref: str = Field(min_length=1)
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_requirement(self) -> "ReservationRequirementContent":
        if not self.reservation_ref.startswith("reservation:"):
            raise ValueError("construction_reservation_ref_invalid")
        return self


def validate_reservation_requirements(
    *,
    requirements: tuple[ReservationRequirementContent, ...],
    provided_refs: tuple[str, ...],
    reservation_evidence: Mapping[str, Mapping[str, object]] | None = None,
) -> None:
    required = tuple(item.reservation_ref for item in requirements)
    if len(set(required)) != len(required):
        raise ValueError("reservation_requirement_duplicate")
    if tuple(sorted(required)) != required:
        raise ValueError("reservation_requirement_not_canonical")
    if tuple(sorted(provided_refs)) != provided_refs:
        raise ValueError("reservation_ref_not_canonical")
    if set(provided_refs) - set(required):
        raise ValueError("reservation_requirement_unexpected")
    missing = set(required) - set(provided_refs)
    if missing:
        raise ValueError("reservation_requirement_missing")
    if reservation_evidence is not None:
        if set(reservation_evidence) - set(required):
            raise ValueError("reservation_requirement_evidence_unexpected")
        for requirement in requirements:
            evidence = reservation_evidence.get(requirement.reservation_ref)
            if evidence is None:
                raise ValueError("reservation_requirement_evidence_missing")
            if (
                evidence.get("owner_family_ref") != requirement.owner_family_ref
                or evidence.get("status") != "active"
                or evidence.get("revision") != requirement.revision
            ):
                raise ValueError("reservation_requirement_evidence_conflict")


def validate_permit_evidence(
    *,
    permit_evidence: Mapping[str, object] | None,
    required_permit_ref: str,
    jurisdiction_ref: str,
    required_zoning_ref: str | None = None,
) -> None:
    if permit_evidence is None:
        raise ValueError("construction_permit_evidence_missing")
    if permit_evidence.get("permit_ref") != required_permit_ref:
        raise ValueError("construction_permit_evidence_conflict")
    if permit_evidence.get("jurisdiction_ref") != jurisdiction_ref:
        raise ValueError("construction_permit_evidence_conflict")
    if required_zoning_ref is not None and permit_evidence.get("zoning_ref") != required_zoning_ref:
        raise ValueError("construction_zoning_evidence_conflict")
    if permit_evidence.get("status") != "active":
        raise ValueError("construction_permit_evidence_inactive")
    revision = permit_evidence.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError("construction_permit_evidence_revision_invalid")


class RecipeContent(_ContentModel):
    recipe_ref: str = Field(min_length=1)
    recipe_schema_ref: str = Field(min_length=1)
    input_slots: tuple[RecipeInputContent, ...]
    tool_refs: tuple[str, ...]
    qualification_refs: tuple[str, ...]
    batch_size: int = Field(gt=0)
    duration_ticks: int = Field(gt=0)
    output_definition_ref: str = Field(min_length=1)
    output_quantity: int = Field(default=1, gt=0)
    quality_policy: ProductionQualityPolicyContent
    wear_policy_ref: str = Field(min_length=1)
    failure_policy: FailurePolicyContent

    @model_validator(mode="after")
    def validate_content(self) -> "RecipeContent":
        _require_platform_ref(self.recipe_ref, prefix="recipe:")
        _require_platform_ref(self.recipe_schema_ref, prefix="schema:")
        _require_platform_ref(self.output_definition_ref, prefix="item:")
        _require_platform_ref(self.wear_policy_ref, prefix="policy:")
        _require_author_canonical(self.input_slots, identity=lambda value: value.item_definition_ref)
        _require_author_canonical(self.tool_refs, identity=lambda value: value)
        _require_author_canonical(self.qualification_refs, identity=lambda value: value)
        for ref in self.tool_refs:
            _require_platform_ref(ref, prefix="tool:")
        for ref in self.qualification_refs:
            _require_platform_ref(ref, prefix="qualification:")
        return self

    def to_existing_recipe(self) -> object:
        """Create the compatible runtime value without writing a fact."""
        from app.gameplay.construction_production_runtime import Recipe

        fields: dict[str, object] = {
                "recipe_ref": self.recipe_ref,
                "inputs": {slot.item_definition_ref: slot.quantity for slot in self.input_slots},
                "output_item": self.output_definition_ref,
                "duration_ticks": self.duration_ticks,
                "batch_size": self.batch_size,
                "quality_policy_revision": self.quality_policy.policy_revision_ref,
                "wear_policy_ref": self.wear_policy_ref,
                "failure_policy_mode": self.failure_policy.mode,
        }
        if self.recipe_schema_ref == "schema:construction-recipe@1":
            fields["output_quantity"] = self.output_quantity * self.batch_size
        return Recipe.model_validate(fields)

    @classmethod
    def from_package_definition(cls, definition: object) -> "RecipeContent":
        source_revision = getattr(definition, "source_package_revision", "")
        typed_content = getattr(definition, "typed_content", None)
        if not source_revision or not isinstance(typed_content, Mapping):
            raise ValueError("construction_recipe_package_definition_invalid")
        return cls.model_validate(typed_content)


def occupied_grid_cells(
    *, anchor: tuple[int, int], components: tuple[ComponentContent, ...], orientation: int
) -> frozenset[tuple[int, int]]:
    """Return deterministic occupied cells for a discrete orientation."""
    if orientation not in {0, 90, 180, 270}:
        raise ValueError("construction_grid_orientation_invalid")
    cells: set[tuple[int, int]] = set()
    for component in components:
        for x in range(component.width):
            for y in range(component.depth):
                local_x = component.offset_x + x
                local_y = component.offset_y + y
                if orientation == 0:
                    rotated = (local_x, local_y)
                elif orientation == 90:
                    rotated = (-local_y, local_x)
                elif orientation == 180:
                    rotated = (-local_x, -local_y)
                else:
                    rotated = (local_y, -local_x)
                cells.add((anchor[0] + rotated[0], anchor[1] + rotated[1]))
    return frozenset(cells)


def grid_placement_conflict(
    *,
    anchor: tuple[int, int],
    components: tuple[ComponentContent, ...],
    orientation: int,
    occupied_cells: frozenset[tuple[int, int]],
) -> bool:
    """Return whether a placement overlaps already committed occupancy."""
    return bool(
        occupied_grid_cells(anchor=anchor, components=components, orientation=orientation)
        & occupied_cells
    )


def resolve_failure_mode(*, policy: FailurePolicyContent | None, failure_reason: str) -> str:
    """Resolve an explicitly declared failure mode; never select a default."""
    if policy is None:
        raise ValueError("construction_failure_policy_required")
    if not failure_reason:
        raise ValueError("construction_failure_reason_required")
    return policy.mode


__all__ = [
    "BlueprintContent",
    "ComponentContent",
    "FailurePolicyContent",
    "FacilityContent",
    "GridFootprint",
    "ProductionQualityPolicyContent",
    "RecipeContent",
    "RecipeInputContent",
    "ReservationRequirementContent",
    "validate_reservation_requirements",
    "validate_permit_evidence",
    "occupied_grid_cells",
    "grid_placement_conflict",
    "resolve_failure_mode",
]
