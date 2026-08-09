from __future__ import annotations

import pytest


def test_organization_and_government_records_keep_external_owner_refs() -> None:
    from app.gameplay.organization_government_runtime import Organization, Permit, RoleAssignment

    organization = Organization(organization_ref="org:bakery", jurisdiction_ref="jurisdiction:demo", owner_character_ref="character:owner")
    permit = Permit(permit_ref="permit:bakery", organization_ref=organization.organization_ref, policy_revision="policy:v1", expires_tick=10, status="active")
    role = RoleAssignment(organization_ref=organization.organization_ref, character_ref="character:owner", role="manager")
    assert permit.status == "active"
    assert role.character_ref.startswith("character:")
    with pytest.raises(ValueError, match="extra|forbid"):
        Organization(organization_ref="org:x", jurisdiction_ref="j", owner_character_ref="character:x", account_balance=3)
