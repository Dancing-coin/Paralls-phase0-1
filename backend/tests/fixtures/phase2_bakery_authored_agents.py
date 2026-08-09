from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.organization_government_runtime import Organization, RoleAssignment


def authored_bakery_fixture() -> dict[str, object]:
    registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[3] / "assets" / "characters" / "profiles")
    actors = {f"character:{actor}": registry.get(actor) for actor in ("char_a", "char_b", "char_c")}
    organization = Organization(organization_ref="org:bakery-authored", jurisdiction_ref="jurisdiction:demo", owner_character_ref="character:char_a")
    assignments = (
        RoleAssignment(assignment_ref="assignment:operator", organization_ref=organization.organization_ref, character_ref="character:char_a", role="operator", permitted_role_ref="operator"),
        RoleAssignment(assignment_ref="assignment:baker", organization_ref=organization.organization_ref, character_ref="character:char_b", role="baker/production", permitted_role_ref="baker/production"),
        RoleAssignment(assignment_ref="assignment:counter", organization_ref=organization.organization_ref, character_ref="character:char_c", role="counter/procurement", permitted_role_ref="counter/procurement"),
    )
    return {"registry": registry, "actors": actors, "organization": organization, "assignments": assignments, "scenario": BakeryReferenceScenario.default()}
