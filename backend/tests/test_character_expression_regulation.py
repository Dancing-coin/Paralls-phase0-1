from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.expression_regulation import ExpressionRegulationFrame, DeviationEpisode
from test_character_execution_contract import _snapshot, _interpretation, _decision, _turn


def test_existing_l4_builds_five_channel_frame_without_guessing_policy():
    executor = CharacterAgentL4Executor()
    decision = _decision()
    snapshot = _snapshot()
    before = deepcopy(snapshot.model_dump())
    contract = executor.build_execution_contract(snapshot=snapshot, interpretation=_interpretation(),
                                                  decision=decision, turn_context=_turn())
    frame = contract.allowed_realization_hints["expression_regulation"]
    assert frame["intent"] == decision.selected_intent
    controls = dict(frame["channel_control"])
    assert set(controls) == {"speech", "face", "body", "social_spatial", "physiology"}
    assert all(value is None for value in controls.values())
    assert frame["rationality_band"] is None
    assert frame["leakage_channels"] == ()
    assert frame["soul_rule_summary"] == ()
    assert snapshot.model_dump() == before
    assert contract.allowed_realization_hints["expression_plan"]["speech_channel"]["dialogue_act"] == decision.selected_intent
    assert contract.allowed_realization_hints["expression_plan"]["social_spatial_channel"]["target_ref"] == ""


def test_expression_frame_keeps_channel_controls_independent_and_blocks_authority_payloads():
    frame = ExpressionRegulationFrame(intent="speak_public", channel_control={"speech": .9, "body": .2},
                                      leakage_channels=("body",))
    assert frame.channel_control["speech"] == .9
    assert frame.channel_control["body"] == .2
    assert ExpressionRegulationFrame.model_validate(frame.model_dump(mode="json")) == frame
    with pytest.raises(TypeError):
        frame.channel_control["speech"] = .1
    for field in ("raw_pose", "authority_result", "world_mutation"):
        with pytest.raises(ValidationError):
            ExpressionRegulationFrame(intent="speak_public", **{field: {"x": 1}})


def test_deviation_episode_records_observation_without_supplying_onset_thresholds():
    episode = DeviationEpisode(onset=10, peak=12, duration=5, recovery=15,
                                channels=("body", "physiology"), source_refs=("event:observed",))
    assert episode.duration == 5
    with pytest.raises(ValidationError):
        episode.recovery = 16
    with pytest.raises(ValidationError):
        DeviationEpisode(onset=10, peak=9, source_refs=("event:observed",))


def test_l4_keeps_explicit_observed_deviation_advisory_and_preserves_intent():
    executor = CharacterAgentL4Executor()
    decision = _decision()
    regulation = ExpressionRegulationFrame(intent=decision.selected_intent,
                                           channel_control={"speech": .9, "body": .2},
                                           leakage_channels=("body",))
    episode = DeviationEpisode(onset=10, peak=12, duration=5, recovery=15,
                               channels=("body",), source_refs=("event:observed",))
    contract = executor.build_execution_contract(snapshot=_snapshot(), interpretation=_interpretation(),
        decision=decision, turn_context=_turn(), expression_regulation=regulation, deviation_episode=episode)
    assert contract.semantic_intent_id == decision.selected_intent
    assert contract.allowed_realization_hints["deviation_episode"]["recovery"] == 15
    assert dict(contract.allowed_realization_hints["expression_regulation"]["channel_control"])["speech"] == .9
    with pytest.raises(ValueError, match="intent"):
        executor.build_execution_contract(snapshot=_snapshot(), interpretation=_interpretation(),
            decision=decision, turn_context=_turn(), expression_regulation=ExpressionRegulationFrame(intent="withdraw"))
