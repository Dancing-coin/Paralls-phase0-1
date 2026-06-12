from app.models.character_agent_runtime import CharacterGoalCommand, CharacterIntentFrame


def test_character_goal_command_is_backend_actor_contract() -> None:
    command = CharacterGoalCommand(
        actor_id="char_a",
        command_type="approach",
        target_object_id="obj_letter",
        ttl_ms=1000,
        causation_id="cg:1",
        correlation_id="cg:1",
    )

    assert command.command_type == "approach"
    assert command.target_object_id == "obj_letter"


def test_character_intent_frame_is_local_execution_shape() -> None:
    frame = CharacterIntentFrame(
        actor_id="char_a",
        controller_source="agent",
        move_local=[0.0, 1.0],
        gait="walk",
        action="observe",
        ttl_ms=1000,
        causation_id="ci:1",
        correlation_id="ci:1",
    )

    assert frame.controller_source == "agent"
    assert frame.gait == "walk"
