from __future__ import annotations

import pytest

from app.gameplay.organization_government_social_recipes import (
    OGSRecipeError,
    all_ogs_precompiled_recipes,
    require_ogs_precompiled_recipe,
    validate_ogs_recipe_source,
)


def test_ogs_cross_owner_recipes_are_closed_exact_and_nonwriting() -> None:
    recipes = all_ogs_precompiled_recipes()
    assert len({recipe.recipe_ref for recipe in recipes}) == len(recipes)
    assert all(recipe.source_owner_ref != recipe.target_owner_ref for recipe in recipes)
    assert all(recipe.source_event_type.startswith("gameplay.") for recipe in recipes)
    assert all(recipe.source_revision_fence_ref.startswith("revision:") for recipe in recipes)
    assert require_ogs_precompiled_recipe("recipe:population-explicit-organization-materialization@1").target_family_ref == "organization_lifecycle@1"


def test_ogs_cross_owner_recipe_lookup_fails_closed() -> None:
    with pytest.raises(OGSRecipeError, match="ogs_recipe_unknown"):
        require_ogs_precompiled_recipe("recipe:arbitrary-cross-domain@1")


def test_ogs_recipe_target_admission_rereads_exact_source_owner_event_privacy_and_revision() -> None:
    recipe = validate_ogs_recipe_source(
        recipe_ref="recipe:government-enforcement-obligation@1",
        source_owner_ref="actor_gameplay.government_domain",
        source_event_type="gameplay.government.permit_inspection_case_recorded@1",
        source_privacy_scope="project",
        source_revision=4,
        expected_source_revision=4,
    )
    assert recipe.target_owner_ref == "actor_gameplay.economy_domain"
    with pytest.raises(OGSRecipeError, match="ogs_recipe_source_admission_rejected"):
        validate_ogs_recipe_source(
            recipe_ref="recipe:government-enforcement-obligation@1",
            source_owner_ref="actor_gameplay.government_domain",
            source_event_type="gameplay.government.permit_inspection_case_recorded@1",
            source_privacy_scope="authority_only",
            source_revision=4,
            expected_source_revision=4,
        )
