import pytest

from app.character_agent.mind.thought_mode import ThoughtModeDescriptor, ThoughtModeRegistry


def test_registry_accepts_registered_descriptor_and_keeps_background_goal() -> None:
    registry = ThoughtModeRegistry()
    descriptor = ThoughtModeDescriptor(
        mode_id="investigate_pattern",
        activation_conditions=("uncertainty",),
        input_projection=("external_state", "event_inbox"),
        domain="investigation",
        question_schema=("what_changed",),
        allowed_intents=("observe", "ask"),
        priority_bias=0.4,
        resource_horizon="scene",
        information_needs=("target_state",),
        exit_conditions=("evidence_current",),
    )
    registry.register(descriptor)

    assert registry.get("investigate_pattern") == descriptor
    assert registry.project_active(("investigate_pattern", "protect_ally"), background_goals=("protect_ally",)) == (
        descriptor,
    )


def test_registry_rejects_duplicate_or_unknown_mode_without_creating_execution_rules() -> None:
    registry = ThoughtModeRegistry()
    descriptor = ThoughtModeDescriptor(mode_id="social", domain="social")
    registry.register(descriptor)
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(descriptor)
    with pytest.raises(KeyError):
        registry.get("combat")
