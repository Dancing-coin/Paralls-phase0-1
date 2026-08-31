from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.recipe_production_family import (
    RecipeInputSlot,
    RecipeOutputSlot,
    RecipeProductionContent,
)


def _content(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "facility_definition_ref": "definition:bakery@1",
        "facility_definition_schema_ref": "schema:facility@1",
        "facility_kind": "bakery",
        "recipe_ref": "recipe:bread@1",
        "recipe_schema_ref": "schema:recipe@1",
        "input_slots": [
            {
                "item_definition_ref": "item:flour@1",
                "quantity": 2,
                "unit": "count",
            }
        ],
        "output_slots": [
            {
                "item_definition_ref": "item:bread@1",
                "quantity": 1,
                "unit": "count",
            }
        ],
        "duration_ticks": 1,
        "qualification_refs": ["qualification:baker@1"],
        "policy_revision_ref": "policy:recipe-production@1",
    }
    value.update(overrides)
    return value


def test_recipe_production_content_accepts_typed_bakery_recipe() -> None:
    content = RecipeProductionContent.model_validate(_content())

    assert content.facility_kind == "bakery"
    assert content.input_slots == (
        RecipeInputSlot(item_definition_ref="item:flour@1", quantity=2, unit="count"),
    )
    assert content.output_slots == (
        RecipeOutputSlot(item_definition_ref="item:bread@1", quantity=1, unit="count"),
    )


def test_recipe_production_content_rejects_duplicate_or_unordered_slots() -> None:
    with pytest.raises((ValidationError, ValueError), match="recipe_production"):
        RecipeProductionContent.model_validate(
            _content(
                input_slots=[
                    {"item_definition_ref": "item:sugar@1", "quantity": 1, "unit": "count"},
                    {"item_definition_ref": "item:flour@1", "quantity": 2, "unit": "count"},
                ]
            )
        )


def test_recipe_production_content_rejects_authority_shaped_payload() -> None:
    with pytest.raises((ValidationError, ValueError), match="authority"):
        RecipeProductionContent.model_validate(_content(owner_ref="actor:forged"))


def test_recipe_production_content_rejects_empty_or_multi_output_v1_shape() -> None:
    with pytest.raises((ValidationError, ValueError), match="recipe_production"):
        RecipeProductionContent.model_validate(_content(output_slots=[]))

    with pytest.raises((ValidationError, ValueError), match="recipe_production"):
        RecipeProductionContent.model_validate(
            _content(
                output_slots=[
                    {"item_definition_ref": "item:bread@1", "quantity": 1, "unit": "count"},
                    {"item_definition_ref": "item:crumbs@1", "quantity": 1, "unit": "count"},
                ]
            )
        )


def test_recipe_production_content_rejects_missing_or_invalid_references() -> None:
    with pytest.raises((ValidationError, ValueError), match="recipe_production"):
        RecipeProductionContent.model_validate(_content(recipe_ref="recipe:bread"))

    with pytest.raises((ValidationError, ValueError), match="recipe_production"):
        RecipeProductionContent.model_validate(
            _content(input_slots=[{"item_definition_ref": "definition:flour@1", "quantity": 2, "unit": "count"}])
        )


def test_recipe_production_content_exposes_existing_recipe_fields_without_authority_coordinates() -> None:
    content = RecipeProductionContent.model_validate(_content())

    assert content.as_recipe_fields() == {
        "recipe_ref": "recipe:bread@1",
        "inputs": {"item:flour@1": 2},
        "output_item": "item:bread@1",
        "duration_ticks": 1,
    }

    recipe = content.to_existing_recipe()
    assert recipe.recipe_ref == "recipe:bread@1"
    assert recipe.output_item == "item:bread@1"
