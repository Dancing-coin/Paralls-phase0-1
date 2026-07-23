from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.character_agent.gateway.output_validator import CharacterStructuredOutputValidator
from app.character_agent.gateway.prompt_policy import CharacterPromptPolicy
from app.character_agent.gateway.model_router import CharacterModelRouter
from app.config import settings
import pytest


class _RecordingProvider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def complete(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        return self.response


def _complete_l2_output(overrides: dict[str, object] | None = None, **keyword_overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "interpreted_summary": "lamp changed",
        "interpretation_type": "state_change",
        "salience_score": 0.7,
        "ambiguity_level": "low",
        "risk_level": "low",
        "opportunity_level": "medium",
        "attention_target": "env_lamp",
        "inner_prompt_candidate": "watch the lamp",
        "belief_deltas": [],
        "social_deltas": [],
        "higher_order_deltas": [],
        "dynamic_state_delta": {},
        "goal_hints": [],
        "reasoning_trace_summary": "model interpreted lamp change",
    }
    payload.update(overrides or {})
    payload.update(keyword_overrides)
    return payload


def _complete_l3_output(overrides: dict[str, object] | None = None, **keyword_overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_intents": ["observe", "self_protect"],
        "selected_intent": "observe",
        "recommended_intents": ["observe"],
        "risk_notes": [],
        "why_this_now": "lamp changed",
        "role_consistency_hint": "stay observant",
        "active_goal_tags": ["preserve_continuity"],
        "active_goal_frame": {
            "primary_goal": "preserve_continuity",
            "long_term_goal": "preserve_continuity",
            "mid_term_strategy": "hold_position",
            "immediate_goal": "preserve_continuity",
            "supporting_goals": [],
            "blockers": [],
            "goal_sources": ["model"],
            "urgency": "low",
            "dominant_goal_id": "goal_preserve_continuity",
            "preserved_goal_ids": [],
            "suppressed_goal_ids": [],
            "goal_arbitration_summary": "observe without changing world truth",
            "goal_portfolio": [],
        },
        "planning_status": "model",
        "fallback_mode": None,
    }
    payload.update(overrides or {})
    payload.update(keyword_overrides)
    return payload


def _run_local_task(
    gateway: CharacterModelGateway,
    *,
    task_kind: str,
    context: dict[str, object],
) -> dict[str, object]:
    return gateway.run_task(
        task_kind=task_kind,
        context=context,
        route_override="local_only",
    )


def test_model_gateway_prepares_structured_run_request(monkeypatch) -> None:
    monkeypatch.setattr(settings, "character_model_provider_kind", "qwen")
    gateway = CharacterModelGateway()

    request = gateway.prepare_run_request(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_a",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "visible_entities": ["visual_fact/fixed_gaze_on_target"],
                "last_siming_catalyst": "watch obj_letter",
                "vigilance_level": "elevated",
                "body_state_hints": ["interaction_strain:body_state_result/interaction_strain=engaged"],
                "recent_world_changes": ["moved closer to target"],
                "recent_constraint_results": ["target is too far away"],
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [{"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}],
                "higher_order_memories": [
                    {"subject_actor_id": "char_a", "meta_belief": "char_a suspects char_b knows more"}
                ],
            },
            "working_memory_state": {
                "dynamic_state": {"social_pressure": 0.7, "masking_pressure": 0.55},
            },
        },
    )

    assert request["task_kind"] == "l2_reasoning"
    assert request["route"]["route_mode"] == "online_default"
    assert request["route"]["provider_kind"] == "qwen"
    assert request["context"]["actor_id"] == "char_a"
    assert request["policy"]["allow_model_call"] is True
    assert request["policy"]["provider_kind"] == "qwen"
    assert "last_siming_catalyst=watch obj_letter" in str(request["prompt"]["user_instruction"])
    assert "vigilance_level=elevated" in str(request["prompt"]["user_instruction"])
    assert "body_state_hints_count=1" in str(request["prompt"]["user_instruction"])
    assert "recent_world_changes_count=1" in str(request["prompt"]["user_instruction"])
    assert "recent_constraint_results_count=1" in str(request["prompt"]["user_instruction"])
    assert "recent_world_change_sample=moved closer to target" in str(request["prompt"]["user_instruction"])
    assert "recent_constraint_result_sample=target is too far away" in str(request["prompt"]["user_instruction"])
    assert "relational_memory_sample=guarded" in str(request["prompt"]["user_instruction"])
    assert "higher_order_memories_count=1" in str(request["prompt"]["user_instruction"])
    assert "dynamic_state_summary=social_pressure=0.7|masking_pressure=0.55" in str(request["prompt"]["user_instruction"])
    assert "belief_deltas" in request["prompt"]["required_output_keys"]
    assert "higher_order_deltas" in request["prompt"]["required_output_keys"]
    assert "dynamic_state_delta" in request["prompt"]["required_output_keys"]
    assert "goal_hints" in request["prompt"]["required_output_keys"]
    assert "goal_hints" in request["prompt"]["system_instruction"]
    assert "evidence_tags" in request["prompt"]["system_instruction"]


def test_model_router_supports_environment_default_override(monkeypatch) -> None:
    monkeypatch.setenv("CHARACTER_MODEL_ROUTE_OVERRIDE", "local_only")

    route = CharacterModelRouter().resolve_route()

    assert route["route_mode"] == "local_only"
    assert route["provider_kind"] == "local"


def test_model_gateway_allows_route_override_without_changing_context_shape() -> None:
    gateway = CharacterModelGateway()

    request = gateway.prepare_run_request(
        task_kind="dialogue_generation",
        context={
            "actor_id": "char_c",
            "control_mode": "player_priority_assisted",
            "snapshot": {"audible_entities": ["auditory_fact/speaker_active"]},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
        route_override="local_only",
    )

    assert request["route"]["route_mode"] == "local_only"
    assert request["route"]["provider_kind"] == "local"
    assert request["context"]["control_mode"] == "player_priority_assisted"


def test_model_gateway_runs_task_through_provider_and_validator() -> None:
    provider = _RecordingProvider(
        _complete_l2_output({
            "interpreted_summary": "char_a may be speaking nearby",
            "interpretation_type": "social_signal",
            "salience_score": 0.82,
            "ambiguity_level": "medium",
            "risk_level": "low",
            "opportunity_level": "medium",
            "attention_target": "char_a",
            "inner_prompt_candidate": "listen before responding",
        })
    )
    gateway = CharacterModelGateway(provider=provider)

    output = gateway.run_task(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_c",
            "control_mode": "player_priority_assisted",
            "snapshot": {"audible_entities": ["auditory_fact/speaker_active"]},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert provider.requests
    assert provider.requests[0]["prompt"]["system_instruction"]
    assert provider.requests[0]["prompt"]["required_output_keys"]
    assert output["attention_target"] == "char_a"


def test_model_gateway_supports_dialogue_generation_contract() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
        task_kind="dialogue_generation",
        context={
            "actor_id": "char_a",
            "control_mode": "dialogue_service",
            "snapshot": {},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "content": "Where is the letter?",
                "intent_type": "dialogue_submit",
            },
        },
        route_override="local_only",
    )

    assert output["content"] == "I saw something move near the desk."
    assert output["tone"] == "alert"


def test_model_gateway_offline_dialogue_generation_does_not_branch_on_actor_id() -> None:
    gateway = CharacterModelGateway()

    char_b_output = gateway.run_task(
        task_kind="dialogue_generation",
        context={
            "actor_id": "char_b",
            "control_mode": "dialogue_service",
            "snapshot": {},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "content": "Status update.",
                "intent_type": "dialogue_submit",
            },
        },
        route_override="local_only",
    )
    generic_output = gateway.run_task(
        task_kind="dialogue_generation",
        context={
            "actor_id": "char_registry_only",
            "control_mode": "dialogue_service",
            "snapshot": {},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "content": "Status update.",
                "intent_type": "dialogue_submit",
            },
        },
        route_override="local_only",
    )

    assert char_b_output == generic_output


def test_model_gateway_offline_l2_raises_risk_for_active_anomalies() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_a",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "active_anomalies": ["olfactory_fact/smoke_density_rise"],
                "clarity_score": 0.66,
                "certainty_score": 0.53,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "actor_id": "char_a",
                "percept_channel": "olfactory",
                "perceived_summary": "olfactory_fact/smoke_density_rise",
                "clarity_score": 0.66,
                "certainty_score": 0.53,
            },
        },
    )

    assert output["risk_level"] == "medium"
    assert output["ambiguity_level"] == "high"


def test_model_gateway_offline_l2_treats_body_state_hints_as_body_state_interpretation() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "body_state_hints": ["interaction_strain:body_state_result/interaction_strain=engaged"],
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "actor_id": "char_b",
                "perceived_summary": "body_state_result/interaction_strain=engaged",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
        },
    )

    assert output["interpretation_type"] == "body_state"
    assert output["risk_level"] == "medium"


def test_model_gateway_offline_l2_raises_opportunity_for_recent_world_changes() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "recent_world_changes": ["moved closer to target"],
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "actor_id": "char_b",
                "perceived_summary": "state_change",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
        },
    )

    assert output["opportunity_level"] == "medium"


def test_model_gateway_offline_l2_raises_risk_for_recent_constraint_results() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "recent_constraint_results": ["target is too far away"],
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "actor_id": "char_b",
                "perceived_summary": "visual_fact/fixed_gaze_on_target",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
        },
    )

    assert output["risk_level"] == "medium"


def test_model_gateway_offline_l2_raises_opportunity_for_last_siming_catalyst() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "last_siming_catalyst": "watch obj_letter",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "actor_id": "char_b",
                "perceived_summary": "siming_catalyst",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
        },
    )

    assert output["opportunity_level"] == "medium"


def test_model_gateway_offline_l2_raises_opportunity_for_elevated_vigilance_level() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "vigilance_level": "elevated",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "actor_id": "char_b",
                "perceived_summary": "state_change",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
        },
    )

    assert output["opportunity_level"] == "medium"


def test_model_gateway_offline_l2_raises_ambiguity_for_elevated_distraction_level() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_a",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "distraction_level": "elevated",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "actor_id": "char_a",
                "perceived_summary": "state_change",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
        },
    )

    assert output["ambiguity_level"] == "high"


def test_model_gateway_offline_l2_does_not_fabricate_risk_from_guarded_relational_memory_about_attention_target() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {
                "attention_targets": ["char_a"],
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [
                    {"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}
                ],
            },
            "event": {
                "actor_id": "char_b",
                "perceived_summary": "auditory_fact/speaker_active",
                "percept_channel": "auditory",
                "target_actor_id": "char_a",
                "clarity_score": 1.0,
                "certainty_score": 1.0,
            },
        },
    )

    assert output["risk_level"] == "low"


def test_model_gateway_offline_l3_prefers_self_protect_for_recent_constraint_results() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "state_change",
            },
            "snapshot": {"recent_constraint_results": ["target is too far away"]},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["selected_intent"] == "self_protect"
    assert output["recommended_intents"][0] == "self_protect"
    assert output["planning_status"] == "continuity_floor"
    assert output["fallback_mode"] == "local_only_stub"
    assert output["active_goal_frame"]["primary_goal"] == "protect_self"


def test_model_gateway_offline_l3_prefers_self_protect_for_medium_risk_even_without_recent_constraint_history() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "medium",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "state_change",
            },
            "snapshot": {},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["selected_intent"] == "self_protect"
    assert output["recommended_intents"][0] == "self_protect"


def test_model_gateway_offline_l3_keeps_recent_world_changes_on_observe_without_rich_local_tactic() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "state_change",
            },
            "snapshot": {"recent_world_changes": ["moved closer to target"]},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["recommended_intents"][0] == "observe"
    assert output["planning_status"] == "continuity_floor"
    assert output["active_goal_frame"]["primary_goal"] == "preserve_continuity"


def test_model_gateway_offline_l3_keeps_elevated_vigilance_on_observe_without_rich_local_tactic() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "state_change",
            },
            "snapshot": {"vigilance_level": "elevated"},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["recommended_intents"][0] == "observe"
    assert output["selected_intent"] == "observe"


def test_model_gateway_offline_l3_keeps_elevated_distraction_on_observe_without_rich_local_tactic() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "medium",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "",
            },
            "snapshot": {"distraction_level": "elevated"},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["recommended_intents"][0] == "observe"


def test_model_gateway_offline_l3_does_not_turn_guarded_relation_into_rich_local_self_protect_selection() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "char_a may be speaking nearby",
                "interpretation_type": "social_signal",
                "salience_score": 0.84,
                "ambiguity_level": "medium",
                "risk_level": "low",
                "opportunity_level": "medium",
                "attention_target": "char_a",
                "inner_prompt_candidate": "listen before responding",
            },
            "snapshot": {"attention_targets": ["char_a"]},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [
                    {"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}
                ],
            },
        },
    )

    assert output["selected_intent"] == "observe"
    assert output["recommended_intents"][0] == "observe"


def test_model_gateway_offline_l3_uses_guarded_relational_memory_in_risk_notes() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "char_a may be speaking nearby",
                "interpretation_type": "social_signal",
                "salience_score": 0.84,
                "ambiguity_level": "medium",
                "risk_level": "low",
                "opportunity_level": "medium",
                "attention_target": "char_a",
                "inner_prompt_candidate": "listen before responding",
            },
            "snapshot": {"attention_targets": ["char_a"]},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [
                    {"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}
                ],
            },
        },
    )

    assert output["risk_notes"][0] == "guarded relation with char_a"


def test_model_gateway_offline_l3_uses_guarded_relational_memory_in_explanation_when_history_is_absent() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "char_a may be speaking nearby",
                "interpretation_type": "social_signal",
                "salience_score": 0.84,
                "ambiguity_level": "medium",
                "risk_level": "low",
                "opportunity_level": "medium",
                "attention_target": "char_a",
                "inner_prompt_candidate": "",
            },
            "snapshot": {"attention_targets": ["char_a"]},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [
                    {"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}
                ],
            },
        },
    )

    assert output["why_this_now"] == "guarded relation with char_a"
    assert output["role_consistency_hint"] == "guarded relation with char_a"


def test_model_gateway_offline_l3_uses_recent_history_for_risk_notes_and_explanations() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "player_priority_assisted",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "",
            },
            "snapshot": {
                "recent_world_changes": ["moved closer to target"],
                "recent_constraint_results": ["target is too far away"],
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["risk_notes"] == ["target is too far away"]
    assert output["why_this_now"] == "moved closer to target"
    assert output["role_consistency_hint"] == "moved closer to target"


def test_model_gateway_offline_l3_uses_recent_constraint_as_why_this_now_when_no_world_change_exists() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "player_priority_assisted",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "",
            },
            "snapshot": {
                "recent_constraint_results": ["target is too far away"],
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["why_this_now"] == "target is too far away"


def test_model_gateway_offline_l3_uses_recent_constraint_as_role_consistency_hint_when_no_world_change_exists() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "player_priority_assisted",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "",
            },
            "snapshot": {
                "recent_constraint_results": ["target is too far away"],
            },
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["role_consistency_hint"] == "target is too far away"


def test_model_gateway_offline_l3_uses_elevated_vigilance_in_explanation_fallbacks_when_history_is_absent() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "player_priority_assisted",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "",
            },
            "snapshot": {"vigilance_level": "elevated"},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["why_this_now"] == "heightened vigilance"
    assert output["role_consistency_hint"] == "heightened vigilance"


def test_model_gateway_offline_l3_uses_elevated_distraction_in_explanation_fallbacks_when_history_is_absent() -> None:
    gateway = CharacterModelGateway()

    output = _run_local_task(
        gateway,
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "player_priority_assisted",
            "interpretation": {
                "actor_id": "char_b",
                "interpreted_summary": "state_change",
                "interpretation_type": "state_change",
                "salience_score": 0.5,
                "ambiguity_level": "low",
                "risk_level": "low",
                "opportunity_level": "low",
                "attention_target": None,
                "inner_prompt_candidate": "",
            },
            "snapshot": {"distraction_level": "elevated"},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
        },
    )

    assert output["why_this_now"] == "uncertain signal"
    assert output["role_consistency_hint"] == "uncertain signal"


def test_model_gateway_preserves_memory_bundle_while_accepting_optional_working_memory_state() -> None:
    gateway = CharacterModelGateway()

    request = gateway.prepare_run_request(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_c",
            "control_mode": "player_priority_assisted",
            "snapshot": {"audible_entities": ["auditory_fact/speaker_active"]},
            "memory": {
                "working_memory": [{"event_id": "evt:2"}],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "working_memory_state": {
                "recent_perceived_events": [{"event_type": "character_perceived_event"}],
                "recent_esm_results": [],
                "recent_siming_catalysts": [],
                "private_snapshot": {"actor_id": "char_c"},
            },
        },
    )

    assert request["context"]["memory"]["working_memory"][0]["event_id"] == "evt:2"
    assert request["context"]["working_memory_state"]["recent_perceived_events"][0]["event_type"] == "character_perceived_event"
    assert "recent_perceived_events_count=1" in str(request["prompt"]["user_instruction"])
    assert "private_snapshot_actor_id=char_c" in str(request["prompt"]["user_instruction"])


def test_model_gateway_accepts_typed_working_memory_state_with_typed_dynamic_state() -> None:
    gateway = CharacterModelGateway()

    request = gateway.prepare_run_request(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_c",
            "control_mode": "player_priority_assisted",
            "snapshot": {"audible_entities": ["auditory_fact/speaker_active"]},
            "memory": {
                "working_memory": [{"event_id": "evt:2"}],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "working_memory_state": CharacterWorkingMemoryState(
                recent_perceived_events=[{"event_type": "character_perceived_event"}],
                recent_esm_results=[],
                recent_siming_catalysts=[],
                private_snapshot={"actor_id": "char_c"},
                dynamic_state=CharacterDynamicState(
                    actor_id="char_c",
                    vigilance_level=0.2,
                    distraction_level=0.1,
                    stress_load=0.4,
                    social_pressure=0.3,
                    masking_pressure=0.2,
                    motivation_stack=["preserve_order"],
                ),
            ),
        },
    )

    assert request["context"]["working_memory_state"]["dynamic_state"]["actor_id"] == "char_c"
    assert request["context"]["working_memory_state"]["dynamic_state"]["motivation_stack"] == ["preserve_order"]
    assert "dynamic_state_summary=vigilance_level=0.2|distraction_level=0.1|stress_load=0.4|social_pressure=0.3|masking_pressure=0.2|actor_id=char_c|affect_valence=0.0|motivation_stack=['preserve_order']|unresolved_conflicts=[]" in str(request["prompt"]["user_instruction"])


def test_prompt_policy_and_output_validator_expose_task_specific_contracts() -> None:
    prompt_policy = CharacterPromptPolicy()
    validator = CharacterStructuredOutputValidator()

    prompt = prompt_policy.build_prompt(
        task_kind="l3_planning",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {"attention_targets": ["char_a"]},
            "memory": {"working_memory": [], "episodic_memories": [], "relational_memories": []},
        },
        route={"route_mode": "online_default", "provider_kind": "online"},
    )
    output = validator.validate(
        task_kind="l3_planning",
        output={
            "selected_intent": "observe",
            "candidate_intents": ["observe", "ask_probe"],
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "char_a is salient",
            "role_consistency_hint": "hold position",
            "active_goal_tags": ["preserve_optionality"],
            "active_goal_frame": {
                "primary_goal": "preserve_optionality",
                "long_term_goal": "preserve_continuity",
                "mid_term_strategy": "hold_position",
                "immediate_goal": "preserve_optionality",
                "supporting_goals": [],
                "blockers": [],
                "goal_sources": ["model_deliberation"],
                "urgency": "low",
            },
        },
    )

    assert "l3_planning" in prompt["system_instruction"]
    assert "candidate_intents" in prompt["required_output_keys"]
    assert "active_goal_tags" in prompt["required_output_keys"]
    assert "active_goal_frame" in prompt["required_output_keys"]
    assert output["selected_intent"] == "observe"
    assert output["active_goal_frame"]["primary_goal"] == "preserve_optionality"


def test_prompt_policy_uses_personality_projection_as_primary_personality_surface() -> None:
    prompt_policy = CharacterPromptPolicy()

    prompt = prompt_policy.build_prompt(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_a",
            "control_mode": "agent_full_auto",
            "profile": {
                "identity_core": {
                    "character_id": "char_a",
                    "canonical_name": "Lin Yue",
                    "occupation_role": "archive attendant",
                },
                "trait_vector_layer": {"empathy": 0.82, "rationality": 0.74},
                "personality_projection": {
                    "conflict_deescalation_bias": 0.82,
                    "procedural_discipline": 0.79,
                },
            },
            "snapshot": {},
            "memory": {"working_memory": [], "episodic_memories": [], "relational_memories": []},
        },
        route={"route_mode": "online_default", "provider_kind": "online"},
    )

    user_instruction = str(prompt["user_instruction"])
    summary_segments = user_instruction.split("; ")

    assert any(segment.startswith("personality_projection=") for segment in summary_segments)
    assert any(segment.startswith("legacy_traits=") for segment in summary_segments)
    assert not any(segment.startswith("traits=") for segment in summary_segments)


def test_prompt_policy_includes_supervision_and_unresolved_tensions_in_user_instruction() -> None:
    prompt_policy = CharacterPromptPolicy()

    prompt = prompt_policy.build_prompt(
        task_kind="l2_reasoning",
        context={
            "actor_id": "char_a",
            "control_mode": "agent_full_auto",
            "snapshot": {"attention_targets": ["obj_letter"], "last_siming_catalyst": "watch obj_letter"},
            "memory": {"working_memory": [], "episodic_memories": [], "relational_memories": []},
            "event": {"actor_id": "char_a", "event_type": "background_reappraisal", "perceived_summary": "obj_letter remains unresolved"},
            "supervision_state": {
                "current_level": "medium",
                "source": "strategy_authorized",
                "last_reason_summary": "safety-first review window",
                "active_constraints": {
                    "background_mode": "quiet",
                    "allow_background_loop": True,
                    "caution_bias": "high",
                    "pressure_theme": "room_instability",
                    "attention_theme": ["safety_watch"],
                    "blocked_goal_classes": ["conflict_escalation"],
                    "preferred_goal_classes": ["safety", "observation"],
                    "allow_proactive_initiation": False,
                    "allow_proactive_tendency_generation": False,
                },
            },
            "unresolved_tensions": [
                {
                    "tension_id": "char_a:constraint_result:obj_letter",
                    "category": "constraint_result",
                    "summary": "obj_letter remains locked",
                }
            ],
        },
        route={"route_mode": "online_default", "provider_kind": "online"},
    )

    user_instruction = str(prompt["user_instruction"])

    assert "supervision_state=" in user_instruction
    assert "level=medium" in user_instruction
    assert "blocked_goal_classes=conflict_escalation" in user_instruction
    assert "unresolved_tensions=count=1" in user_instruction


def test_output_validator_enforces_typed_l2_delta_constraints() -> None:
    validator = CharacterStructuredOutputValidator()

    normalized = validator.validate(
        task_kind="l2_reasoning",
        output=_complete_l2_output({
            "interpreted_summary": "char_b is probing",
            "interpretation_type": "social_signal",
            "salience_score": 0.8,
            "ambiguity_level": "medium",
            "risk_level": "medium",
            "opportunity_level": "low",
            "belief_deltas": [{"proposition_key": "char_b:is_probing", "state": "suspected", "confidence": 0.72}],
            "social_deltas": [{"entity_id": "char_b", "suspicion_baseline": 0.8}],
            "higher_order_deltas": [{"subject_actor_id": "char_b", "meta_belief": "char_b suspects char_c knows more", "confidence": 0.66}],
            "dynamic_state_delta": {"social_pressure": 0.7, "masking_pressure": 0.55},
            "goal_hints": [{"goal": "protect_secret", "source": "social_signal", "strength": 0.85, "evidence_tags": ["guarded_attention"]}],
            "reasoning_trace_summary": "char_a:probing-read",
        }),
    )

    assert normalized["dynamic_state_delta"]["social_pressure"] == 0.7
    assert normalized["goal_hints"][0]["evidence_tags"] == ["guarded_attention"]

    try:
        validator.validate(
            task_kind="l2_reasoning",
            output=_complete_l2_output({
                "interpreted_summary": "char_b is probing",
                "interpretation_type": "social_signal",
                "salience_score": 0.8,
                "ambiguity_level": "medium",
                "risk_level": "medium",
                "opportunity_level": "low",
                "dynamic_state_delta": {"social_pressure": 1.7},
                "goal_hints": [{"goal": "protect_secret", "source": "social_signal", "strength": 1.5}],
            }),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid typed l2 delta payload to be rejected")


def test_output_validator_rejects_empty_dialogue_content() -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError, match="content must not be empty"):
        validator.validate(
            task_kind="dialogue_generation",
            output={"content": "", "tone": "neutral"},
        )


def test_output_validator_rejects_l2_salience_out_of_range() -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError, match="salience_score"):
        validator.validate(
            task_kind="l2_reasoning",
            output=_complete_l2_output(salience_score=1.5),
        )


def test_output_validator_rejects_l3_selected_intent_outside_candidates() -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError, match="selected_intent"):
        validator.validate(
            task_kind="l3_planning",
            output=_complete_l3_output(candidate_intents=["observe"], selected_intent="share_info"),
        )


def test_prompt_policy_user_instruction_stays_bounded_for_large_context() -> None:
    prompt_policy = CharacterPromptPolicy()
    large_text = "auditory_fact/speaker_active|" * 4000

    prompt = prompt_policy.build_prompt(
        task_kind="l3_planning",
        context={
            "actor_id": "char_c",
            "control_mode": "player_priority_assisted",
            "snapshot": {
                "visible_entities": [large_text],
                "audible_entities": [large_text],
                "attention_targets": ["char_a"],
                "last_siming_catalyst": large_text,
                "vigilance_level": "elevated",
                "body_state_hints": [large_text] * 8,
                "recent_world_changes": [large_text] * 8,
                "recent_constraint_results": [large_text] * 8,
            },
            "memory": {
                "working_memory": [{"summary": large_text}] * 8,
                "episodic_memories": [{"summary": large_text}] * 8,
                "relational_memories": [{"summary": large_text}] * 8,
            },
            "working_memory_state": {
                "recent_perceived_events": [{"event_type": large_text}] * 8,
                "recent_esm_results": [{"event_type": large_text}] * 8,
                "recent_siming_catalysts": [{"event_type": large_text}] * 8,
                "private_snapshot": {"actor_id": "char_c"},
            },
            "event": {
                "perceived_summary": large_text,
                "source_candidate_event_id": "auditory_fact:4000:char_c",
            },
        },
        route={"route_mode": "online_default", "provider_kind": "online"},
    )

    user_instruction = str(prompt["user_instruction"])
    assert len(user_instruction) < 8000
    assert "visible_entities_count=" in user_instruction
    assert "working_memory_count=" in user_instruction
    assert "recent_perceived_events_count=" in user_instruction
    assert "last_siming_catalyst=" in user_instruction
    assert "vigilance_level=" in user_instruction
    assert "body_state_hints_count=" in user_instruction
    assert "recent_world_changes_count=" in user_instruction
    assert "recent_constraint_results_count=" in user_instruction
    assert "recent_world_change_sample=" in user_instruction
    assert "recent_constraint_result_sample=" in user_instruction
    assert "event_summary=" in user_instruction
