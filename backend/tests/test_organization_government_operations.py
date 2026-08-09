from __future__ import annotations

import pytest

from app.gameplay.organization_government_runtime import OrganizationAuthority, RoleAssignment
from app.gameplay.event_store import GameplayEventStore


def test_roles_accept_existing_character_records_only() -> None:
    role = RoleAssignment(organization_ref="org:1", character_ref="character:owner", role="manager")
    assert OrganizationAuthority.assign_role(role, existing_character_refs={"character:owner"}) == role
    with pytest.raises(ValueError, match="character_record_required"):
        OrganizationAuthority.assign_role(role.model_copy(update={"character_ref": "npc:synthetic"}), existing_character_refs=set())


def test_settle_role_assignment_appends_organization_event() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    role = RoleAssignment(organization_ref="org:1", character_ref="character:owner", role="manager")
    result = authority.settle_role_assignment(
        role, existing_character_refs={"character:owner"}, command_id="command:organization:role:1",
        idempotency_key="idem:organization:role:1", causation_id="cause:organization:role:1",
        correlation_id="corr:organization:1",
    )
    assert result.committed is True
    assert store.read_events()[-1].event_type == "gameplay.organization.role_assigned"
