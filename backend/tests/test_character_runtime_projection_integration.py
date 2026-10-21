from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.models.character_perceived import CharacterPerceivedEvent


def test_shadow_frame_projects_runtime_self_external_and_event_workspaces() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_self_body_perceived_event(SelfBodyPerceivedEvent(
        actor_id="char_a", body_state_class="fatigue", producer_ts=10,
        room_id="room", scene_id="scene", zone_id="zone",
        perceived_summary="feels tired", source_body_result_id="body:result:1",
    ))
    runtime.ingest_character_perceived_event(CharacterPerceivedEvent(
        actor_id="char_a", percept_channel="visual", producer_ts=11,
        room_id="room", scene_id="scene", zone_id="zone",
        perceived_summary="sees box", source_candidate_event_id="event:box:1",
        subject_ref="box", target_object_id="box",
    ))

    frame = runtime.build_shadow_mind_frame(actor_id="char_a", producer_ts=12)
    workspace = frame["cognition_workspace"]

    assert workspace["self_state"]["source"] == "body:result:1"
    assert workspace["self_state"]["body_state_class"] == "fatigue"
    assert workspace["external_state"][0]["subject_ref"] == "box"
    assert workspace["external_state"][0]["uncertainty"] == "unknown"
    assert any(event["source_ref"] == "event:box:1" for event in workspace["event_inbox"])
