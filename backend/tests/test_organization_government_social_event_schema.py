from __future__ import annotations

from app.gameplay.event_schema_registry import (
    EventSchemaRegistry,
    register_organization_government_social_platform_event_schemas,
)


def test_ogs_event_schema_bundle_is_idempotent_and_registers_only_closed_portfolio() -> None:
    registry = EventSchemaRegistry()
    register_organization_government_social_platform_event_schemas(registry)
    register_organization_government_social_platform_event_schemas(registry)

    snapshot = registry.export_snapshot()
    event_types = {item["event_type"] for item in snapshot["registrations"]}
    assert "gameplay.organization.lifecycle_transitioned@1" in event_types
    assert "gameplay.government.policy_lifecycle_recorded@1" in event_types
    assert "gameplay.social.identity_relationship_recorded@1" in event_types
    assert "gameplay.social.population_signal_recorded@1" in event_types
    assert "gameplay.organization.arbitrary_transition@1" not in event_types
