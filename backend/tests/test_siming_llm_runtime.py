from app.models.authority_event import AuthorityEvent
from app.models.siming_event import InterventionCandidate, SimingInput
from app.services.siming_llm_provider import (
    FakeSimingLlmCandidateProvider,
    SimingLlmProviderInvalidOutput,
)
from app.services.siming_runtime import SimingRuntime


def make_visual_fact_event(**payload_overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": "visual_fact:300:char_c:light_level_drop",
        "event_type": "visual_fact_event",
        "producer_ts": 300,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "payload": {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            "target_environment_id": "env_lamp",
        },
    }
    payload["payload"].update(payload_overrides)  # type: ignore[index, union-attr]
    return AuthorityEvent.model_validate(payload)


def make_candidate(**overrides: object) -> InterventionCandidate:
    payload = {
        "candidate_id": "cand:llm:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300:char_c:light_level_drop",
        "correlation_id": "visual_fact:300",
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "target_environment_id": "env_lamp",
        "established_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "explanation": "Reveal the established light drop.",
        "confidence": 0.7,
        "source": "llm",
    }
    payload.update(overrides)
    return InterventionCandidate.model_validate(payload)


class InvalidOutputProvider:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def generate_candidates(
        self,
        *,
        snapshot: object,
        recent_events: list[AuthorityEvent],
        recent_audit: list[object],
    ) -> list[InterventionCandidate]:
        raise self._exc


def test_runtime_invokes_llm_provider_inside_tick_and_emits_canonical_outputs() -> None:
    runtime = SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([make_candidate()]))
    event = make_visual_fact_event()

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=event)])

    output_types = [output.output_type for output in result.outputs]
    assert "fairness_snapshot" in output_types
    assert "intervention_candidate" in output_types
    assert "intervention_decision" in output_types
    dispatches = [output for output in result.outputs if output.output_type == "dispatch_intent"]
    assert dispatches
    assert dispatches[0].selected_path == "visual_fact_path"
    assert dispatches[0].intervention_band == "fact_reveal"
    assert result.audit_records[0].status == "recorded"


def test_runtime_rejects_unsafe_llm_candidate_and_records_no_action() -> None:
    runtime = SimingRuntime(
        llm_provider=FakeSimingLlmCandidateProvider(
            [make_candidate(established_fact_ids=["visual_fact:unknown"])]
        )
    )

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert any(audit.status == "policy_rejected" for audit in result.audit_records)
    assert any(output.output_type == "no_action" for output in result.outputs)


def test_runtime_falls_back_when_llm_provider_times_out() -> None:
    runtime = SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([], timeout=True))

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert any(audit.status == "llm_timeout" for audit in result.audit_records)
    assert any(output.output_type == "no_action" for output in result.outputs)


def test_runtime_uses_first_accepted_candidate_after_rejecting_earlier_candidate() -> None:
    runtime = SimingRuntime(
        llm_provider=FakeSimingLlmCandidateProvider(
            [
                make_candidate(
                    candidate_id="cand:llm:rejected",
                    established_fact_ids=["visual_fact:unknown"],
                    target_environment_id=None,
                ),
                make_candidate(
                    candidate_id="cand:llm:accepted",
                    target_actor_id="char_b",
                    target_environment_id=None,
                    explanation="Second candidate is executable.",
                ),
            ]
        )
    )

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert any(audit.status == "policy_rejected" for audit in result.audit_records)
    dispatches = [output for output in result.outputs if output.output_type == "dispatch_intent"]
    assert dispatches
    assert dispatches[0].selected_path == "character_input_path"
    assert dispatches[0].payload["target_actor_id"] == "char_b"
    assert dispatches[0].payload["presentation_hint"] == "Second candidate is executable."
    decisions = [output for output in result.outputs if output.output_type == "intervention_decision"]
    assert decisions
    assert decisions[0].payload["candidate_id"] == "cand:llm:accepted"
    assert result.audit_records[-1].status == "recorded"


def test_runtime_records_no_action_when_provider_returns_invalid_output_error() -> None:
    runtime = SimingRuntime(
        llm_provider=InvalidOutputProvider(SimingLlmProviderInvalidOutput("bad candidate envelope"))
    )

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert any(audit.status == "llm_invalid_output" for audit in result.audit_records)
    assert any(output.output_type == "no_action" for output in result.outputs)


def test_runtime_records_no_action_when_provider_raises_value_error() -> None:
    runtime = SimingRuntime(llm_provider=InvalidOutputProvider(ValueError("provider returned bad shape")))

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert any(audit.status == "llm_invalid_output" for audit in result.audit_records)
    assert any(output.output_type == "no_action" for output in result.outputs)
