import json

from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.models.mind_frame import CharacterMindFrame
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot


def _frame() -> CharacterMindFrame:
    turn = CharacterTurnContext.begin(
        actor_id="char_a", source_event_ref="event:1", producer_ts=1,
        causation_id="cause:1", correlation_id="corr:1",
        input_revision_vector={"l1": 1}, memory_revision_vector={"memory": 1},
        policy_revision="policy:1", snapshot_revision=1, branch_id="branch:main",
    )
    return CharacterMindFrameBuilder().build_frame(
        actor_id="char_a", producer_ts=1, turn_context=turn,
        snapshot={}, memory_bundle={},
    )


def test_l2_prepared_request_carries_frozen_mind_frame() -> None:
    frame = _frame()
    request = CharacterAgentL2Service().prepare_reasoning_request(
        snapshot=CharacterPrivateWorldSnapshot(
            actor_id="char_a", room_id="room", scene_id="scene", zone_id="zone",
            producer_ts=1, updated_at=1,
        ),
        event=CharacterPerceivedEvent(
            actor_id="char_a", percept_channel="visual", producer_ts=1,
            room_id="room", scene_id="scene", zone_id="zone",
            perceived_summary="box", source_candidate_event_id="event:box",
        ),
        frame=frame,
    )
    encoded = request["context"]["frame"]
    assert encoded is frame
    assert encoded.frame_digest == frame.frame_digest


def test_l3_prepared_request_carries_frozen_mind_frame() -> None:
    frame = _frame()
    prepared = CharacterAgentL3Service().prepare_intent_plan(
        interpretation=CharacterInterpretation(
            actor_id="char_a", interpreted_summary="observe", interpretation_type="state_change",
            salience_score=0.5, ambiguity_level="low", risk_level="low", opportunity_level="low",
        ),
        control_mode="agent_full_auto", snapshot={}, profile={}, memory_bundle={}, frame=frame,
    )
    request = json.loads(prepared.request_json)
    assert request["context"]["frame"]["frame_digest"] == frame.frame_digest
    assert request["context"]["frame"]["turn_id"] == frame.turn_id
