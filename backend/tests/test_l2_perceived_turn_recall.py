import json

import pytest

from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.services.character_semantic_recall import CharacterSemanticRecallService
from app.models.character_perceived import CharacterPerceivedEvent


def _prepare(turn_actor="char_b", memory_actor="char_b"):
    turn = CharacterTurnContext.begin(
        turn_actor, "evt:perceived", 10, causation_id="cause", correlation_id="corr",
        input_revision_vector={}, memory_revision_vector={"node_revision": 2},
        policy_revision="policy:v1", snapshot_revision=1,
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b", room_id="room", scene_id="scene", zone_id="zone",
        producer_ts=10, updated_at=10,
    )
    event = CharacterPerceivedEvent(
        actor_id="char_b", percept_channel="visual", producer_ts=10,
        room_id="room", scene_id="scene", zone_id="zone",
        perceived_summary="A door is open", source_candidate_event_id="evt:perceived",
    )
    return CharacterAgentL2Service(
        semantic_recall_service=CharacterSemanticRecallService(),
    ).prepare_perceived_event(
        snapshot, event, turn_context=turn,
        memory_bundle={"event_memories": [{
            "memory_id": "door-opened:1", "actor_id": memory_actor,
            "world_ts": 1, "source_ref": "evt:door",
        }]},
    )


def test_perceived_event_freezes_actor_private_semantic_cards():
    request = json.loads(_prepare())
    cards = request["context"]["semantic_cards"]
    assert [card["ref"] for card in cards] == ["event:door-opened:1"]
    assert cards[0]["source_refs"] == ["evt:door"]
    assert request["context"]["semantic_recall"]["revision_vector"]["node_revision"] == 2


def test_perceived_event_rejects_foreign_turn_before_gateway_preparation():
    with pytest.raises(ValueError, match="canonical turn context"):
        _prepare(turn_actor="char_a")


def test_perceived_event_rejects_foreign_private_memory_before_gateway_preparation():
    with pytest.raises(ValueError, match="actor scope"):
        _prepare(memory_actor="char_a")
