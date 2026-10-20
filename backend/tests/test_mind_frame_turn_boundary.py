"""A real MindFrame must survive the original L3 frozen request boundary."""
import json

import pytest

from app.character_agent.models.mind_frame import CharacterMindFrame, MindFrameProvenance
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation


def turn():
    return CharacterTurnContext.begin(
        actor_id="char_a", source_event_ref="perceived:1", producer_ts=10,
        causation_id="cause:1", correlation_id="corr:1", branch_id="branch:main",
        input_revision_vector={"perception": 3}, memory_revision_vector={"memory": 7},
        policy_revision="policy:1", snapshot_revision=3,
    )


def frame():
    return CharacterMindFrame(actor_id="char_a", mind_turn_id="mind_turn:char_a:10",
        producer_ts=10, provenance=MindFrameProvenance(source_refs=["perceived:1", "profile:1"]))


def prepare(value, context):
    return CharacterAgentL3Service().prepare_intent_plan(
        interpretation=CharacterInterpretation(actor_id="char_a", interpreted_summary="visible scene",
            interpretation_type="state_change", salience_score=.5, ambiguity_level="low",
            risk_level="low", opportunity_level="low"),
        control_mode="agent_full_auto", snapshot={}, profile={}, memory_bundle={},
        frame=value, turn_context=context,
    )


def test_actual_frame_is_bound_and_serialized_with_candidate_execution_pins():
    original = frame()
    context = turn()
    prepared = prepare(original, context)
    wire = json.loads(prepared.request_json)
    frozen = wire["context"]["frame"]
    assert frozen["turn_id"] == context.turn_id
    assert frozen["input_revision_vector"] == {"perception": 3}
    assert frozen["memory_revision_vector"] == {"memory": 7}
    assert frozen["frame_digest"]
    assert frozen["source_refs"] == ["perceived:1", "profile:1"]
    assert prepared.candidate_mapping
    for record in prepared.candidate_mapping.values():
        assert record["frame_ref"] == frozen["frame_digest"]
        assert record["revision_pins"]["turn_id"] == context.turn_id
        assert record["execution_contract"]["revision_pins"]["frame_digest"] == frozen["frame_digest"]
    assert not original.turn_id  # preparing does not mutate the diagnostic frame
    restored = CharacterMindFrame.model_validate(frozen)
    restored.validate_turn(context)
    assert restored.bind_to_turn(context).frame_digest == frozen["frame_digest"]


@pytest.mark.parametrize("change", [
    {"actor_id": "char_b"}, {"turn_id": "other:turn"}, {"branch_id": "branch:other"},
    {"input_revision_vector": {"perception": 4}}, {"memory_revision_vector": {"memory": 8}},
    {"policy_revision": "policy:2"}, {"snapshot_revision": 4},
])
def test_existing_frame_cannot_be_rebound_to_changed_turn_pins(change):
    context = turn()
    bound = frame().bind_to_turn(context)
    with pytest.raises(ValueError, match="mind frame"):
        bound.bind_to_turn(context.model_copy(update=change))


def test_l3_rejects_changed_frame_body_even_with_original_turn_pins():
    context = turn()
    bound = frame().bind_to_turn(context)
    body = bound.model_dump(mode="json")
    body["cognition_workspace"]["notes"] = ["changed after freeze"]
    changed = CharacterMindFrame.model_validate(body)
    with pytest.raises(ValueError, match="mind frame.*digest"):
        prepare(changed, context)


def test_l3_rejects_cross_actor_unbound_frame_and_bound_frame_without_context():
    with pytest.raises(ValueError, match="mind frame.*actor"):
        prepare(frame().model_copy(update={"actor_id": "char_b"}), turn())
    with pytest.raises(ValueError, match="mind frame.*turn"):
        prepare(frame().bind_to_turn(turn()), None)


def test_legacy_diagnostic_frame_still_prepares_without_canonical_turn():
    prepared = prepare(frame(), None)
    assert not json.loads(prepared.request_json)["context"]["frame"]["turn_id"]
