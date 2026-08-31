"""Closed, package-declared recipe production content contract.

This module validates content slots only. It does not select an owner, create
an event, append a batch, or interpret a recipe as committed world truth.
"""

from __future__ import annotations

from typing import Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.patch_runtime import PackageDefinition, _require_author_canonical, _require_platform_ref, _validate_platform_content
from app.gameplay.models import StrictGameplayModel


RECIPE_PRODUCTION_FAMILY = "recipe_production@1"
RECIPE_PRODUCTION_OUTCOME_FAMILY_REF = "outcome:recipe-production@1"


class _RecipeSlot(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_definition_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_reference(self) -> "_RecipeSlot":
        _require_platform_ref(self.item_definition_ref, prefix="item:", error="recipe_production_item_ref_invalid")
        return self


class RecipeInputSlot(_RecipeSlot):
    """One declared input item and quantity for a recipe."""


class RecipeOutputSlot(_RecipeSlot):
    """One declared output item and quantity for a recipe."""


class RecipeProductionContent(StrictGameplayModel):
    """Strict package content for the closed single-output production family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facility_definition_ref: str = Field(min_length=1)
    facility_definition_schema_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    recipe_ref: str = Field(min_length=1)
    recipe_schema_ref: str = Field(min_length=1)
    input_slots: tuple[RecipeInputSlot, ...] = ()
    output_slots: tuple[RecipeOutputSlot, ...]
    duration_ticks: int = Field(gt=0)
    qualification_refs: tuple[str, ...] = ()
    policy_revision_ref: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _reject_authority_shaped_content(cls, value: object) -> object:
        _validate_platform_content(value)
        return value

    @model_validator(mode="after")
    def _validate_content(self) -> "RecipeProductionContent":
        _require_platform_ref(self.facility_definition_ref, prefix="definition:", error="recipe_production_definition_ref_invalid")
        _require_platform_ref(
            self.facility_definition_schema_ref,
            prefix="schema:",
            error="recipe_production_schema_ref_invalid",
        )
        _require_platform_ref(self.recipe_ref, prefix="recipe:", error="recipe_production_recipe_ref_invalid")
        _require_platform_ref(self.recipe_schema_ref, prefix="schema:", error="recipe_production_schema_ref_invalid")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:", error="recipe_production_policy_ref_invalid")

        try:
            _require_author_canonical(self.input_slots, identity=lambda slot: slot.item_definition_ref)
            _require_author_canonical(self.output_slots, identity=lambda slot: slot.item_definition_ref)
            _require_author_canonical(self.qualification_refs, identity=lambda value: value)
        except ValueError as error:
            raise ValueError("recipe_production_array_not_canonical") from error
        if not self.output_slots:
            raise ValueError("recipe_production_output_required")
        if len(self.output_slots) != 1:
            raise ValueError("recipe_production_single_output_required")
        for reference in self.qualification_refs:
            _require_platform_ref(reference, prefix="qualification:", error="recipe_production_qualification_ref_invalid")
        return self

    @classmethod
    def from_package_definition(cls, definition: PackageDefinition) -> "RecipeProductionContent":
        """Validate one package definition's content without admitting it."""
        if definition.source_package_revision == "":
            raise ValueError("recipe_production_package_revision_missing")
        return cls.model_validate(definition.typed_content)

    def as_recipe_fields(self) -> Mapping[str, object]:
        """Return fields compatible with the existing Construction Recipe model."""
        output = self.output_slots[0]
        return {
            "recipe_ref": self.recipe_ref,
            "inputs": {slot.item_definition_ref: slot.quantity for slot in self.input_slots},
            "output_item": output.item_definition_ref,
            "duration_ticks": self.duration_ticks,
        }

    def to_existing_recipe(self) -> object:
        """Build the existing Construction ``Recipe`` value without writing facts."""
        from app.gameplay.construction_production_runtime import Recipe

        return Recipe.model_validate(self.as_recipe_fields())


class RecipeProductionStartIntent(StrictGameplayModel):
    """Caller intent; authority coordinates are resolved by Construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facility_ref: str = Field(min_length=1)
    recipe_ref: str = Field(min_length=1)
    run_ref: str = Field(min_length=1)
    tick: int = Field(ge=0)
    expected_facility_revision: int = Field(ge=0)
    expected_stream_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


__all__ = [
    "RECIPE_PRODUCTION_FAMILY",
    "RECIPE_PRODUCTION_OUTCOME_FAMILY_REF",
    "RecipeInputSlot",
    "RecipeOutputSlot",
    "RecipeProductionContent",
    "RecipeProductionStartIntent",
]
