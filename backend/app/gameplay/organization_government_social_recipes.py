"""Immutable, read-only cross-owner recipe vocabulary for OGS.

Recipes name only approved source evidence and target owner admission family.
They neither issue fragments nor append events; each target owner still rereads
the source event/privacy/revision vector before it writes its own fact.
"""
from __future__ import annotations

from dataclasses import dataclass


class OGSRecipeError(ValueError):
    pass


@dataclass(frozen=True)
class OGSPrecompiledRecipe:
    recipe_ref: str
    source_owner_ref: str
    source_event_type: str
    target_owner_ref: str
    target_family_ref: str
    privacy_scope: str
    source_revision_fence_ref: str


_RECIPES = (
    OGSPrecompiledRecipe(
        "recipe:organization-operating-commitment@1", "actor_gameplay.organization_domain",
        "gameplay.organization.commitment_budget_proposed@1", "actor_gameplay.economy_domain",
        "organization_labor_period@1", "project", "revision:organization-commitment-source@1",
    ),
    OGSPrecompiledRecipe(
        "recipe:government-enforcement-obligation@1", "actor_gameplay.government_domain",
        "gameplay.government.permit_inspection_case_recorded@1", "actor_gameplay.economy_domain",
        "tax_regulation@1", "project", "revision:government-case-source@1",
    ),
    OGSPrecompiledRecipe(
        "recipe:social-conflict-contract-eligibility@1", "authority:p5:social",
        "gameplay.social.norm_conflict_recorded@1", "actor_gameplay.contract_domain",
        "social_contract_eligibility@1", "project", "revision:social-conflict-source@1",
    ),
    OGSPrecompiledRecipe(
        "recipe:population-explicit-organization-materialization@1", "authority:p5:social",
        "gameplay.social.population_signal_recorded@1", "actor_gameplay.organization_domain",
        "organization_lifecycle@1", "public", "revision:population-signal-source@1",
    ),
)


def all_ogs_precompiled_recipes() -> tuple[OGSPrecompiledRecipe, ...]:
    return _RECIPES


def require_ogs_precompiled_recipe(recipe_ref: str) -> OGSPrecompiledRecipe:
    matches = tuple(recipe for recipe in _RECIPES if recipe.recipe_ref == recipe_ref)
    if not matches:
        raise OGSRecipeError("ogs_recipe_unknown")
    if len(matches) != 1:
        raise OGSRecipeError("ogs_recipe_ambiguous")
    return matches[0]


def validate_ogs_recipe_source(
    *, recipe_ref: str, source_owner_ref: str, source_event_type: str,
    source_privacy_scope: str, source_revision: int, expected_source_revision: int,
) -> OGSPrecompiledRecipe:
    """Read-only target-admission gate shared by precompiled recipe consumers.

    This performs no target-owner write.  Economy/Contract/Organization must
    call it before their own separately admitted fragment can append a fact.
    """
    recipe = require_ogs_precompiled_recipe(recipe_ref)
    if (
        recipe.source_owner_ref != source_owner_ref
        or recipe.source_event_type != source_event_type
        or recipe.privacy_scope != source_privacy_scope
        or source_revision != expected_source_revision
        or source_revision < 1
    ):
        raise OGSRecipeError("ogs_recipe_source_admission_rejected")
    return recipe


__all__ = ["OGSPrecompiledRecipe", "OGSRecipeError", "all_ogs_precompiled_recipes", "require_ogs_precompiled_recipe", "validate_ogs_recipe_source"]
