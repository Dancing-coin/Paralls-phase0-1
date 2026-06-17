from app.models.character_agent_runtime import CharacterInterpretation
from app.services.character_agent_l3 import CharacterAgentL3Service


class _RecordingGateway:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        self.requests.append(
            {
                "task_kind": task_kind,
                "context": context,
                "route_override": route_override,
            }
        )
        return self.response


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="char_a may be speaking nearby",
        interpretation_type="social_signal",
        salience_score=0.84,
        ambiguity_level="medium",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="listen before responding",
    )


def test_l3_planner_generates_candidate_set_and_filter_results() -> None:
    planner = CharacterAgentL3Service()

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
    )

    assert plan["actor_id"] == "char_b"
    assert plan["candidates"]
    assert plan["filter_results"]
    assert "observe" in plan["candidates"]
    assert any(result["candidate"] == "observe" for result in plan["filter_results"])


def test_l3_planner_selects_intent_from_viable_candidates() -> None:
    planner = CharacterAgentL3Service()

    decision = planner.select_intent(_interpretation())

    assert decision.actor_id == "char_b"
    assert decision.selected_intent in {"observe", "observe_target", "speak_public", "ask_probe", "share_info"}
    assert decision.rationale


def test_l3_planner_builds_char_c_suggestion_packet_in_player_priority_mode() -> None:
    planner = CharacterAgentL3Service()

    packet = planner.build_suggestion_packet(
        interpretation=_interpretation(),
        control_mode="player_priority_assisted",
    )

    assert packet["control_mode"] == "player_priority_assisted"
    assert packet["recommended_intents"]
    assert packet["why_this_now"] == "char_a may be speaking nearby"
    assert "urge_vector" in packet


def test_l3_planner_uses_model_gateway_for_candidate_generation() -> None:
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["ask_probe", "share_info", "observe"],
            "selected_intent": "ask_probe",
            "recommended_intents": ["ask_probe", "observe"],
            "risk_notes": ["share_info"],
            "why_this_now": "char_a is salient",
            "role_consistency_hint": "stay curious",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
    )
    decision = planner.select_intent(_interpretation())

    assert gateway.requests
    assert gateway.requests[0]["task_kind"] == "l3_planning"
    assert "ask_probe" in plan["candidates"]
    assert decision.selected_intent == "ask_probe"


def test_l3_planner_build_intent_plan_accepts_explicit_snapshot_and_memory_bundle() -> None:
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "char_a is salient",
            "role_consistency_hint": "hold position",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        snapshot={"attention_targets": ["char_a"]},
        memory_bundle={
            "working_memory": [{"event_id": "evt:1"}],
            "episodic_memories": [{"summary": "char_a spoke nearby"}],
            "relational_memories": [{"entity_id": "char_a", "value": "guarded"}],
        },
        working_memory_state={
            "recent_perceived_events": [{"event_type": "character_perceived_event"}],
            "recent_esm_results": [],
            "recent_siming_catalysts": [],
            "private_snapshot": {"actor_id": "char_b"},
        },
    )

    assert gateway.requests
    assert gateway.requests[0]["context"]["snapshot"]["attention_targets"] == ["char_a"]
    assert gateway.requests[0]["context"]["memory"]["episodic_memories"][0]["summary"] == "char_a spoke nearby"
    assert gateway.requests[0]["context"]["working_memory_state"]["private_snapshot"]["actor_id"] == "char_b"


def test_l3_planner_fallback_candidates_expand_for_recent_world_changes_even_without_attention_target() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    planner = CharacterAgentL3Service()

    plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"recent_world_changes": ["moved closer to target"]},
    )

    assert "observe" in plan["candidates"]
    assert "inspect_object" in plan["candidates"]
    assert "speak_public" in plan["candidates"]


def test_l3_planner_fallback_candidates_include_self_protect_for_recent_constraint_results() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    planner = CharacterAgentL3Service()

    plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"recent_constraint_results": ["target is too far away"]},
    )

    assert "self_protect" in plan["candidates"]
    assert any(
        result["candidate"] == "self_protect" and result["viability"] in {"viable", "highly_compelling"}
        for result in plan["filter_results"]
    )


def test_l3_planner_prefers_self_protect_when_relational_memory_marks_attention_target_as_guarded() -> None:
    planner = CharacterAgentL3Service()

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        snapshot={"attention_targets": ["char_a"]},
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "relational_memories": [{"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}],
        },
        control_mode="agent_full_auto",
    )
    decision = planner.select_intent(
        _interpretation(),
        snapshot={"attention_targets": ["char_a"]},
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "relational_memories": [{"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}],
        },
        control_mode="agent_full_auto",
    )

    assert plan["model_output"]["selected_intent"] == "self_protect"
    assert plan["model_output"]["recommended_intents"][0] == "self_protect"
    assert decision.selected_intent == "physiology_hint"


def test_l3_suggestion_packet_uses_recent_constraint_results_as_risk_notes_fallback() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="state_change",
    )
    planner = CharacterAgentL3Service()

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"recent_constraint_results": ["target is too far away"]},
    )

    assert packet["risk_notes"] == ["target is too far away"]


def test_l3_suggestion_packet_uses_guarded_relational_memory_as_risk_notes_fallback() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="char_a may be speaking nearby",
        interpretation_type="social_signal",
        salience_score=0.84,
        ambiguity_level="medium",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="listen before responding",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["self_protect", "observe"],
            "selected_intent": "self_protect",
            "recommended_intents": ["self_protect", "observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"attention_targets": ["char_a"]},
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "relational_memories": [{"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}],
        },
    )

    assert packet["risk_notes"][0] == "guarded relation with char_a"


def test_l3_suggestion_packet_uses_recent_constraint_result_to_prefer_self_protect_when_model_recommendations_are_empty() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="state_change",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": [],
            "selected_intent": "",
            "recommended_intents": [],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"recent_constraint_results": ["target is too far away"]},
    )

    assert packet["recommended_intents"][0] == "self_protect"


def test_l3_suggestion_packet_uses_recent_world_change_as_why_this_now_fallback() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="state_change",
    )
    planner = CharacterAgentL3Service()

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"recent_world_changes": ["moved closer to target"]},
    )

    assert packet["why_this_now"] == "moved closer to target"


def test_l3_suggestion_packet_uses_guarded_relational_memory_as_explanation_when_history_is_absent() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="char_a may be speaking nearby",
        interpretation_type="social_signal",
        salience_score=0.84,
        ambiguity_level="medium",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["self_protect", "observe"],
            "selected_intent": "self_protect",
            "recommended_intents": ["self_protect", "observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"attention_targets": ["char_a"]},
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "relational_memories": [{"entity_id": "char_a", "belief_type": "trust_level", "value": "guarded"}],
        },
    )

    assert packet["why_this_now"] == "guarded relation with char_a"
    assert packet["role_consistency_hint"] == "guarded relation with char_a"


def test_l3_suggestion_packet_uses_elevated_vigilance_as_why_this_now_when_history_is_absent() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="state_change",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "hold position",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"vigilance_level": "elevated"},
    )

    assert packet["why_this_now"] == "heightened vigilance"


def test_l3_suggestion_packet_uses_elevated_vigilance_as_role_consistency_hint_when_history_and_prompt_are_absent() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"vigilance_level": "elevated"},
    )

    assert packet["role_consistency_hint"] == "heightened vigilance"


def test_l3_suggestion_packet_uses_elevated_distraction_as_explanation_fallback_when_history_is_absent() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"distraction_level": "elevated"},
    )

    assert packet["why_this_now"] == "uncertain signal"
    assert packet["role_consistency_hint"] == "uncertain signal"


def test_l3_suggestion_packet_prefers_speak_public_when_recent_world_change_exists_and_model_recommendations_are_empty() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="state_change",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": [],
            "selected_intent": "",
            "recommended_intents": [],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"recent_world_changes": ["moved closer to target"]},
    )

    assert packet["recommended_intents"][0] == "speak_public"


def test_l3_suggestion_packet_uses_recent_constraint_as_why_this_now_fallback_when_no_world_change_exists() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="state_change",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "hold position",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"recent_constraint_results": ["target is too far away"]},
    )

    assert packet["why_this_now"] == "target is too far away"


def test_l3_suggestion_packet_uses_recent_world_change_as_role_consistency_hint_fallback() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"recent_world_changes": ["moved closer to target"]},
    )

    assert packet["role_consistency_hint"] == "moved closer to target"


def test_l3_suggestion_packet_uses_recent_constraint_as_role_consistency_hint_fallback_when_no_world_change_exists() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"recent_constraint_results": ["target is too far away"]},
    )

    assert packet["role_consistency_hint"] == "target is too far away"


def test_l3_suggestion_packet_prefers_speak_public_for_elevated_vigilance_when_model_recommendations_are_empty() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": [],
            "selected_intent": "",
            "recommended_intents": [],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"vigilance_level": "elevated"},
    )

    assert packet["recommended_intents"][0] == "speak_public"
    assert packet["why_this_now"] == "heightened vigilance"
    assert packet["role_consistency_hint"] == "heightened vigilance"


def test_l3_suggestion_packet_prefers_speak_public_for_elevated_vigilance_when_model_selected_intent_is_empty() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": [],
            "selected_intent": "",
            "recommended_intents": [],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
        snapshot={"vigilance_level": "elevated"},
    )

    assert packet["recommended_intents"][0] == "speak_public"


def test_l3_suggestion_packet_prefers_speak_public_for_elevated_vigilance_when_model_selected_intent_is_empty() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="state_change",
        interpretation_type="state_change",
        salience_score=0.5,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target=None,
        inner_prompt_candidate="",
    )
    gateway = _RecordingGateway(
        {
            "candidate_intents": [],
            "selected_intent": "",
            "recommended_intents": [],
            "risk_notes": [],
            "why_this_now": "",
            "role_consistency_hint": "",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"vigilance_level": "elevated"},
    )

    assert packet["recommended_intents"][0] == "speak_public"
