import pytest

from app.character_agent.models.action_execution_state import ActionExecutionState
from app.character_agent.models.external_percept_snapshot import ExternalPerceptSnapshot
from app.character_agent.models.self_state_snapshot import SelfStateSnapshot
from app.character_agent.mind.self_state_normalizer import SelfStateNormalizer
from app.models.self_body_perceived import SelfBodyPerceivedEvent


def test_self_state_keeps_source_capture_revision_and_quality_explicit() -> None:
    state = SelfStateSnapshot(
        actor_id="char_a",
        source="body:result:1",
        captured_at=10,
        producer_ts=11,
        revision="body@2",
        freshness="stale",
        visibility="actor_private",
        uncertainty="unknown",
        body_state_class="injured",
        combat_influences={"mobility": "reduced"},
    )
    assert state.freshness == "stale"
    assert state.uncertainty == "unknown"
    assert state.combat_influences["mobility"] == "reduced"
    with pytest.raises(TypeError):
        state.combat_influences["mobility"] = "normal"


def test_external_percept_can_be_conflicting_without_selecting_a_truth() -> None:
    percept = ExternalPerceptSnapshot(
        actor_id="char_a",
        subject_ref="box",
        source="l1:fact:1",
        captured_at=20,
        producer_ts=21,
        revision="l1@4",
        freshness="current",
        visibility="actor_private",
        uncertainty="conflicting",
        summary="clear and blocked evidence both exist",
        conflict_refs=("conflict:box:1",),
    )
    assert percept.uncertainty == "conflicting"
    assert percept.conflict_refs == ("conflict:box:1",)


def test_action_execution_state_separates_intent_request_execution_and_result() -> None:
    state = ActionExecutionState(
        actor_id="char_a",
        source="turn:char_a:1",
        captured_at=30,
        producer_ts=31,
        revision="turn@1",
        freshness="current",
        visibility="actor_private",
        uncertainty="unknown",
        intent_ref="intent:observe",
        request_ref="request:observe:1",
        execution_ref=None,
        result_ref=None,
        status="requested",
    )
    assert state.intent_ref and state.request_ref
    assert state.execution_ref is None and state.result_ref is None


def test_self_state_normalizer_keeps_body_event_quality_unknown_without_owner_revision() -> None:
    event = SelfBodyPerceivedEvent(
        actor_id="char_a", body_state_class="fatigue", producer_ts=11,
        room_id="room", scene_id="scene", zone_id="zone",
        perceived_summary="feels tired", source_body_result_id="body:result:1",
    )

    snapshot = SelfStateNormalizer().from_body_event(event)

    assert snapshot.source == "body:result:1"
    assert snapshot.captured_at == 11
    assert snapshot.producer_ts == 11
    assert snapshot.revision == "body:result:1"
    assert snapshot.freshness == "unknown"
    assert snapshot.uncertainty == "unknown"
