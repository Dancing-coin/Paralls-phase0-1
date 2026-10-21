import pytest

from app.models.raw_fact import RawFactEvent
from app.services.candidate_percept_service import compile_candidate_percepts
from app.services.per_character_percept_filter import filter_candidate_for_actor
from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service


def _fact(**signal_changes):
    signal = dict(type="opening_created", source="char_a", observation="window observed",
                  confidence="medium", target="char_b", expires_at=20)
    signal.update(signal_changes)
    return RawFactEvent.model_validate(dict(
        fact_family="auditory_fact", fact_type="speaker_active", producer_ts=10,
        room_id="room_demo", scene_id="scene_demo", zone_id="zone_demo",
        source={"system": "character_actor", "actor_id": "char_a"}, targets={"actor_id": "char_b"},
        observability={"auditory": True}, acoustics={"reachability": "audible"},
        coordination_signal=signal,
    ))


def test_sender_signal_passes_existing_fact_candidate_filter_and_receiver_l1():
    fact = _fact()
    candidate, = compile_candidate_percepts(fact)
    perceived = filter_candidate_for_actor(candidate, actor_id="char_b", context={"now_ts": 10})
    assert perceived is not None
    snapshot = CharacterAgentL1Service().apply_character_perceived_event(perceived)
    assert snapshot.local_coordination_signals[0]["source"] == "char_a"
    assert snapshot.local_coordination_signals[0]["observation"] == "window observed"
    assert perceived.fact_claim is None
    assert "world_fact" not in snapshot.local_coordination_signals[0]
    assert filter_candidate_for_actor(candidate, actor_id="char_c") is None


@pytest.mark.parametrize("with_signal", [False, True])
def test_fact_serialization_omits_absent_signal_and_preserves_present_signal(with_signal):
    import json
    from app.models.visual_fact import VisualFactEvent

    fact = _fact()
    if not with_signal:
        fact.coordination_signal = None
    for event in (fact, VisualFactEvent.model_validate(fact.model_dump())):
        for payload in (event.model_dump(), json.loads(event.model_dump_json())):
            assert ("coordination_signal" in payload) is with_signal
            if with_signal:
                assert payload["coordination_signal"]["source"] == "char_a"


@pytest.mark.parametrize("cause", ["inaudible", "out_of_range", "expired", "source_mismatch"])
def test_signal_rejected_before_receiver_l1(cause):
    fact = _fact(source="char_c") if cause == "source_mismatch" else _fact()
    if cause == "inaudible":
        fact.observability.auditory = False
    elif cause == "out_of_range":
        fact.acoustics.reachability = "out_of_range"
    candidate, = compile_candidate_percepts(fact)
    perceived = filter_candidate_for_actor(candidate, actor_id="char_b", context={"now_ts": 20 if cause == "expired" else 10})
    assert perceived is None


def test_short_contract_is_optional_local_proposal_and_requires_current_preconditions():
    contract = dict(goal="observe window", participants=["char_a", "char_b"],
                    responsibilities=[["char_a", "signal"], ["char_b", "observe"]],
                    expires_at=18, failure_conditions=["window_closed"], exit_conditions=["withdraw"],
                    context_revision="world@1")
    fact = _fact(contract=contract)
    candidate, = compile_candidate_percepts(fact)
    context = {"now_ts": 10, "context_revision": "world@1", "participant_state": "accepted"}
    accepted = filter_candidate_for_actor(candidate, actor_id="char_b", context=context)
    assert accepted is not None
    assert accepted.coordination_signal.contract.goal == "observe window"
    for changed in ({"context_revision": "world@2"}, {"participant_state": "rejected"},
                    {"participant_state": "withdrawn"}, {"now_ts": 18}):
        assert filter_candidate_for_actor(candidate, actor_id="char_b", context=context | changed) is None


def test_signal_requires_trusted_current_time_and_never_copies_private_memory_fields():
    from pydantic import ValidationError

    candidate, = compile_candidate_percepts(_fact())
    assert filter_candidate_for_actor(candidate, actor_id="char_b", context={}) is None
    with pytest.raises(ValidationError):
        _fact(private_memory={"secret": "sender only"})
