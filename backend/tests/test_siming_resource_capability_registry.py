from app.models.siming_resource_capability import ResourceRealizationRequest
from app.services.siming_resource_capability_registry import ResourceCapabilityRegistry


def realization_request(*, semantic_purpose: str) -> ResourceRealizationRequest:
    return ResourceRealizationRequest(
        node_id="runtime:bridge:1",
        actor_bindings={"speaker": "char_b", "listener": "char_c"},
        target_object_id="obj_letter",
        target_environment_id="env_lamp",
        required_realization_keys=["look_at_target", "focus_attention"],
        camera_pattern="two_actor_confrontation",
        semantic_purpose=semantic_purpose,
        location_state="throne_room:letter_removed",
    )


def test_main_demo_package_covers_private_confrontation() -> None:
    registry = ResourceCapabilityRegistry()

    match = registry.match(
        realization_request(semantic_purpose="private_confrontation"),
        world_ts=100,
    )

    assert match.accepted is True
    assert match.capability is not None
    assert match.capability.asset_bundle == "main_demo_throne_room"


def test_only_exact_recent_signature_receives_fatigue_penalty() -> None:
    registry = ResourceCapabilityRegistry()
    reveal = realization_request(semantic_purpose="evidence_reveal")
    confrontation = realization_request(semantic_purpose="private_confrontation")

    registry.record_realization(reveal, "main_demo_throne_room", world_ts=90)

    assert registry.match(reveal, world_ts=100).fatigue_penalty > 0
    assert registry.match(confrontation, world_ts=100).fatigue_penalty == 0


def test_unavailable_or_cooling_capability_is_not_selected() -> None:
    registry = ResourceCapabilityRegistry()
    request = realization_request(semantic_purpose="private_confrontation")

    registry.set_cooldown("main_demo_throne_room", until=101)

    assert registry.match(request, world_ts=100).accepted is False
