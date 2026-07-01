from app.models.player_input import DialogueSubmit, FocusTargetChange, InteractIntent, MoveIntent
from app.services.session_input_router import SessionInputRouter
from app.services.session_runtime import SessionRuntime


def test_session_input_router_routes_dialogue_event() -> None:
    runtime = SessionInputRouter()
    event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=1,
        target_actor_id="char_a",
        content="Hello",
    )
    result = runtime.accept_player_input(event)
    assert result["accepted"] is True
    assert result["route"] == "character_service"


def test_session_input_router_routes_interaction_event() -> None:
    runtime = SessionInputRouter()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=2,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = runtime.accept_player_input(event)
    assert result["accepted"] is True
    assert result["route"] == "esm_service"


def test_session_input_router_routes_move_event() -> None:
    runtime = SessionInputRouter()
    event = MoveIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="move_intent",
        producer_ts=3,
        move_mode="locomotion",
        target_point=(1.0, 0.0, 2.0),
    )
    result = runtime.accept_player_input(event)
    assert result["accepted"] is True
    assert result["route"] == "local_motion"
    assert runtime.get_actor_position("char_c") == (1.0, 0.0, 2.0)


def test_session_input_router_routes_focus_target_change_event() -> None:
    runtime = SessionInputRouter()
    event = FocusTargetChange(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="focus_target_change",
        producer_ts=4,
        target_actor_id="char_a",
    )
    result = runtime.accept_player_input(event)
    assert result["accepted"] is True
    assert result["route"] == "character_service"


def test_legacy_session_runtime_import_remains_compatible() -> None:
    assert SessionRuntime is SessionInputRouter
