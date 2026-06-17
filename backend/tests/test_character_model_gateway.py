from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.output_validator import CharacterStructuredOutputValidator
from app.character_agent.gateway.prompt_policy import CharacterPromptPolicy


class _RecordingProvider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def complete(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        return self.response


def test_model_gateway_prepares_structured_run_request() -> None:
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
            },
        },
    )

    assert request["task_kind"] == "l2_reasoning"
    assert request["route"]["route_mode"] == "online_default"
    assert request["context"]["actor_id"] == "char_a"
    assert request["policy"]["allow_model_call"] is True
    assert "last_siming_catalyst=watch obj_letter" in str(request["prompt"]["user_instruction"])
    assert "vigilance_level=elevated" in str(request["prompt"]["user_instruction"])
    assert "body_state_hints_count=1" in str(request["prompt"]["user_instruction"])
    assert "recent_world_changes_count=1" in str(request["prompt"]["user_instruction"])
    assert "recent_constraint_results_count=1" in str(request["prompt"]["user_instruction"])
    assert "recent_world_change_sample=moved closer to target" in str(request["prompt"]["user_instruction"])
    assert "recent_constraint_result_sample=target is too far away" in str(request["prompt"]["user_instruction"])
    assert "relational_memory_sample=guarded" in str(request["prompt"]["user_instruction"])


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
    assert request["context"]["control_mode"] == "player_priority_assisted"


def test_model_gateway_runs_task_through_provider_and_validator() -> None:
    provider = _RecordingProvider(
        {
            "interpreted_summary": "char_a may be speaking nearby",
            "interpretation_type": "social_signal",
            "salience_score": 0.82,
            "ambiguity_level": "medium",
            "risk_level": "low",
            "opportunity_level": "medium",
            "attention_target": "char_a",
            "inner_prompt_candidate": "listen before responding",
        }
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


def test_model_gateway_offline_l2_raises_risk_for_active_anomalies() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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
    assert output["ambiguity_level"] == "medium"


def test_model_gateway_offline_l2_treats_body_state_hints_as_body_state_interpretation() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    assert output["ambiguity_level"] == "medium"


def test_model_gateway_offline_l2_raises_risk_for_guarded_relational_memory_about_attention_target() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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

    assert output["risk_level"] == "medium"


def test_model_gateway_offline_l3_prefers_self_protect_for_recent_constraint_results() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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


def test_model_gateway_offline_l3_prefers_self_protect_for_medium_risk_even_without_recent_constraint_history() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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


def test_model_gateway_offline_l3_prefers_speak_public_for_recent_world_changes() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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

    assert output["recommended_intents"][0] == "speak_public"


def test_model_gateway_offline_l3_prefers_speak_public_for_elevated_vigilance() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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

    assert output["recommended_intents"][0] == "speak_public"
    assert output["selected_intent"] == "speak_public"


def test_model_gateway_offline_l3_prefers_speak_public_for_elevated_distraction() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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

    assert output["recommended_intents"][0] == "speak_public"


def test_model_gateway_offline_l3_prefers_self_protect_for_guarded_relational_memory_about_attention_target() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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

    assert output["selected_intent"] == "self_protect"
    assert output["recommended_intents"][0] == "self_protect"


def test_model_gateway_offline_l3_uses_guarded_relational_memory_in_risk_notes() -> None:
    gateway = CharacterModelGateway()

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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

    output = gateway.run_task(
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
        },
    )

    assert "l3_planning" in prompt["system_instruction"]
    assert "candidate_intents" in prompt["required_output_keys"]
    assert output["selected_intent"] == "observe"


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
