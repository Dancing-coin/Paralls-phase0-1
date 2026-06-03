from app.models.player_input import DialogueSubmit
from app.models.ai_output import DialogueResponse
from app.models.runtime_state import CharacterRuntimeStateDelta, CharacterRuntimeStateSnapshot
from app.models.world_result import ConstraintStateResult
from app.models.siming_output import NarrativeNudge
from fastapi.testclient import TestClient
from app.main import app, reset_runtime_state


def test_player_input_dialogue_submit_shape() -> None:
    event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=123,
        target_actor_id="char_a",
        content="Hello",
    )
    assert event.target_actor_id == "char_a"
    assert event.content == "Hello"


def test_ai_output_dialogue_response_shape() -> None:
    event = DialogueResponse(
        actor_id="char_a",
        room_id="room_demo",
        output_type="dialogue_response",
        causation_id="evt1",
        producer_ts=456,
        target_actor_id="char_c",
        content="Hi there",
        tone="neutral",
        tts_required=True,
    )
    assert event.tts_required is True


def test_world_result_constraint_shape() -> None:
    event = ConstraintStateResult(
        room_id="room_demo",
        source_type="player",
        target_object_id="obj_letter",
        result_type="constraint_state_result",
        causation_id="evt2",
        producer_ts=789,
        constraint_type="distance",
        constraint_summary="too far",
    )
    assert event.constraint_type == "distance"


def test_siming_output_narrative_nudge_shape() -> None:
    event = NarrativeNudge(
        room_id="room_demo",
        output_type="narrative_nudge",
        target_actor_id="char_b",
        causation_id="evt3",
        producer_ts=900,
        nudge_summary="pay attention to the letter",
        nudge_intensity="low",
    )
    assert event.nudge_intensity == "low"


def test_character_runtime_state_snapshot_shape() -> None:
    event = CharacterRuntimeStateSnapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        revision_seq=1,
        producer_ts=123,
        current_focus_target="char_a",
        current_attention_source="focus_state",
        nearby_actor_refs=["char_a", "char_b"],
        nearby_object_refs=["obj_letter"],
        nearby_environment_refs=["env_lamp"],
        conversation_candidate_refs=["cand_char_a_letter"],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        updated_at=124,
    )
    assert event.actor_id == "char_c"
    assert event.conversation_candidate_refs == ["cand_char_a_letter"]


def test_character_runtime_state_delta_shape() -> None:
    event = CharacterRuntimeStateDelta(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        revision_seq=2,
        producer_ts=125,
        changed_fields=["current_focus_target", "conversation_candidate_refs", "nearby_environment_refs"],
        current_focus_target="obj_letter",
        nearby_environment_refs=["env_lamp"],
        conversation_candidate_refs=["cand_letter"],
        updated_at=126,
    )
    assert "current_focus_target" in event.changed_fields
    assert event.current_focus_target == "obj_letter"


def test_websocket_dialogue_submit_emits_ack_and_dialogue_response() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "dialogue_submit",
                    "producer_ts": 123,
                    "target_actor_id": "char_a",
                    "content": "Hello",
                },
            }
        )

        ack = websocket.receive_json()
        response = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "character_service"
    assert response["message_type"] == "dialogue_response"
    assert response["payload"]["actor_id"] == "char_a"


def test_websocket_interact_intent_emits_ack_world_result_environment_shift_and_siming_output() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "interact_intent",
                    "producer_ts": 456,
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                },
            }
        )

        ack = websocket.receive_json()
        world_result = websocket.receive_json()
        environment_result = websocket.receive_json()
        siming_output = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        projection_delta = websocket.receive_json()
        candidate_event = websocket.receive_json()
        runtime_delta = websocket.receive_json()
        candidate_siming_output = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["route"] == "esm_service"
    assert world_result["message_type"] == "world_result"
    assert world_result["payload"]["target_object_id"] == "obj_letter"
    assert environment_result["message_type"] == "world_result"
    assert environment_result["payload"]["result_type"] == "environment_state_result"
    assert environment_result["payload"]["target_environment_id"] == "env_lamp"
    assert environment_result["payload"]["current_state"] == "alerted"
    assert siming_output["message_type"] == "siming_output"
    assert siming_output["payload"]["target_actor_id"] == "char_b"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert projection_delta["message_type"] == "character_runtime_state_delta"
    assert projection_delta["payload"]["current_attention_source"] == "world_result"
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["payload"]["candidate_object_ids"] == ["obj_letter"]
    assert runtime_delta["message_type"] == "character_runtime_state_delta"
    assert runtime_delta["payload"]["conversation_candidate_refs"] == ["cand_obj_letter"]
    assert candidate_siming_output["message_type"] == "siming_output"
    assert candidate_siming_output["payload"]["target_object_id"] == "obj_letter"


def test_websocket_interact_intent_emits_constraint_when_player_is_far() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 455,
                    "move_mode": "locomotion",
                    "target_point": [0.0, 0.0, 20.0],
                },
            }
        )
        websocket.receive_json()

        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "interact_intent",
                    "producer_ts": 456,
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                },
            }
        )

        ack = websocket.receive_json()
        world_result = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["route"] == "esm_service"
    assert world_result["message_type"] == "world_result"
    assert world_result["payload"]["result_type"] == "constraint_state_result"
    assert world_result["payload"]["constraint_type"] == "distance"


def test_websocket_interact_intent_emits_constraint_state_when_actor_is_far() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 455,
                    "move_mode": "locomotion",
                    "target_point": [0.0, 0.0, 16.0],
                },
            }
        )
        move_ack = websocket.receive_json()
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "interact_intent",
                    "producer_ts": 456,
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                },
            }
        )
        interact_ack = websocket.receive_json()
        world_result = websocket.receive_json()

    assert move_ack["message_type"] == "ack"
    assert move_ack["payload"]["route"] == "local_motion"
    assert interact_ack["message_type"] == "ack"
    assert interact_ack["payload"]["route"] == "esm_service"
    assert world_result["message_type"] == "world_result"
    assert world_result["payload"]["result_type"] == "constraint_state_result"
    assert world_result["payload"]["constraint_type"] == "distance"

def test_websocket_focus_target_change_emits_runtime_alignment_messages() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "focus_target_change",
                    "producer_ts": 789,
                    "target_actor_id": "char_a",
                },
            }
        )

        ack = websocket.receive_json()
        focus_state = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        runtime_delta = websocket.receive_json()
        candidate_event = websocket.receive_json()
        candidate_runtime_delta = websocket.receive_json()
        siming_output = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "character_service"
    assert focus_state["message_type"] == "focus_state"
    assert focus_state["payload"]["actor_id"] == "char_c"
    assert focus_state["payload"]["target_actor_id"] == "char_a"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["scene_id"] == "scene_demo"
    assert runtime_delta["message_type"] == "character_runtime_state_delta"
    assert runtime_delta["payload"]["current_focus_target"] == "char_a"
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["payload"]["candidate_actor_ids"] == ["char_a"]
    assert candidate_runtime_delta["message_type"] == "character_runtime_state_delta"
    assert candidate_runtime_delta["payload"]["conversation_candidate_refs"] == ["cand_char_a"]
    assert siming_output["message_type"] == "siming_output"
    assert siming_output["payload"]["target_actor_id"] == "char_a"
