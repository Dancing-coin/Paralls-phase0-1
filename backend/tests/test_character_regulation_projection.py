from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder


def test_mind_frame_derives_private_regulation_without_inventing_mental_resources():
    dynamic = {"actor_id": "char_a", "distraction_level": 0.3,
               "tension_state": {"masking_pressure": 0.8, "stress_load": 0.2},
               "affect_state": {"fear": 0.7}, "unresolved_conflicts": ["goal:1"]}
    before = deepcopy(dynamic)
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a", producer_ts=10, snapshot={"clarity_score": 0.6, "producer_ts": 9},
        dynamic_state=dynamic,
    )
    cards = [card for card in frame.runtime_state.cards if card.factor_type == "mental_regulation"]
    assert len(cards) == 1
    card = cards[0]
    assert card.scope == "actor_private"
    assert card.payload["clarity"] == 0.6
    assert card.payload["masking_load"] == 0.8
    assert card.payload["inhibitory_control"] is None
    assert card.payload["rationality_band"] is None
    assert card.payload["mental_resource_summary"] == []
    assert "regulation_policy_unregistered" in card.risk_notes
    assert dynamic == before
    assert card.payload["source_revisions"]


def test_regulation_projection_is_immutable_and_does_not_silently_supply_thresholds():
    from app.character_agent.mind.regulation_projection import project_mental_regulation

    projection = project_mental_regulation(actor_id="char_a", snapshot={}, dynamic_state={})
    assert projection.clarity is None
    assert projection.rationality_band is None
    with pytest.raises(ValidationError):
        projection.clarity = 1.0


def test_regulation_projection_rejects_other_actor_dynamic_state():
    with pytest.raises(ValueError, match="actor"):
        CharacterMindFrameBuilder().build_frame(
            actor_id="char_a", producer_ts=10, dynamic_state={"actor_id": "char_b"},
        )
