from app.world_runtime.fact_registry import WorldFactRegistry


def test_world_fact_registry_classifies_core_fact_families() -> None:
    registry = WorldFactRegistry()

    assert registry.route_for_family("visual_fact") == "visual"
    assert registry.route_for_family("auditory_fact") == "auditory"
    assert registry.route_for_family("spatial_access_fact") == "spatial_access"


def test_world_fact_registry_preserves_existing_authority_ack_routes() -> None:
    registry = WorldFactRegistry()

    assert registry.route_for_family("role_state_fact") == "authority_role_state_fact"
    assert registry.route_for_family("physiology_state_fact") == "authority_physiology_fact"
    assert registry.route_for_family("tactile_fact") == "authority_tactile_fact"


def test_world_fact_registry_marks_unknown_family_explicitly() -> None:
    registry = WorldFactRegistry()

    assert registry.route_for_family("mystery_family") == "unknown"
