from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.models.character_agent_runtime import CharacterInterpretation
from app.services.character_agent_l3 import CharacterAgentL3Service
from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy


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


class _LocalGateway:
    def __init__(self) -> None:
        self._gateway = CharacterModelGateway()

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.run_task(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )


def _recording_gateway_for_candidates(
    candidates: list[str],
    *,
    selected_intent: str | None = None,
    recommended_intents: list[str] | None = None,
    why_this_now: str = "test planning",
    role_consistency_hint: str = "test contract",
) -> _RecordingGateway:
    selected = selected_intent or (candidates[0] if candidates else "")
    recommended = recommended_intents if recommended_intents is not None else ([selected] if selected != "" else [])
    return _RecordingGateway(
        {
            "candidate_intents": candidates,
            "selected_intent": selected,
            "recommended_intents": recommended,
            "risk_notes": [],
            "why_this_now": why_this_now,
            "role_consistency_hint": role_consistency_hint,
        }
    )


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


def _profile_payload(
    *,
    actor_id: str = "char_b",
    occupation_role: str = "security steward",
    social_openness: float = 0.34,
    privacy_sensitivity: float = 0.71,
    talk_initiative: float = 0.52,
    deception_control: float = 0.91,
    trust_threshold_for_private_talk: float = 0.77,
    value_priorities: list[str] | None = None,
    red_lines: list[str] | None = None,
    forbidden_behaviors: list[str] | None = None,
) -> dict[str, object]:
    return {
        "identity_core": {
            "character_id": actor_id,
            "canonical_name": "Qiao Ren",
            "aliases": ["Ren"],
            "occupation_role": occupation_role,
        },
        "virtue_value_layer": {
            "value_priorities": value_priorities or ["duty", "safety", "clarity"],
            "red_lines": red_lines or ["grant access on vibes alone"],
            "forbidden_behaviors": forbidden_behaviors or ["downplay a proven threat"],
        },
        "conversation_personality_layer": {
            "social_openness": social_openness,
            "privacy_sensitivity": privacy_sensitivity,
            "talk_initiative": talk_initiative,
            "deception_control": deception_control,
            "trust_threshold_for_private_talk": trust_threshold_for_private_talk,
        },
    }


def test_l3_planner_generates_candidate_set_and_filter_results() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
    )

    assert plan["actor_id"] == "char_b"
    assert plan["candidates"] == ["observe", "self_protect"]
    assert plan["filter_results"]
    assert "observe" in plan["candidates"]
    assert any(result["candidate"] == "observe" for result in plan["filter_results"])


def test_l3_planner_selects_intent_from_viable_candidates() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    decision = planner.select_intent(_interpretation())

    assert decision.actor_id == "char_b"
    assert decision.selected_intent in {"observe", "physiology_hint"}
    assert decision.rationale


def test_l3_planner_builds_char_c_suggestion_packet_in_player_priority_mode() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    packet = planner.build_suggestion_packet(
        interpretation=_interpretation(),
        control_mode="player_priority_assisted",
    )

    assert packet["control_mode"] == "player_priority_assisted"
    assert packet["recommended_intents"]
    assert packet["why_this_now"] == "model planning unavailable; continuity floor active"
    assert "urge_vector" in packet
    assert "belief_cues" in packet
    assert "dynamic_pressure" in packet
    assert "reasoning_trace_summary" in packet
    assert "primary_goal" in packet
    assert "long_term_goal" in packet
    assert "supporting_goals" in packet
    assert "blockers" in packet
    assert "goal_sources" in packet
    assert "urgency" in packet
    assert packet["planning_status"] == "continuity_floor"
    assert packet["fallback_mode"] == "continuity_floor"


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


def test_l3_planner_uses_recalled_memory_for_model_and_local_filter() -> None:
    gateway = _recording_gateway_for_candidates(["observe"], selected_intent="observe")
    planner = CharacterAgentL3Service(
        gateway=gateway,
        memory_recall_policy=CharacterMemoryRecallPolicy(pool_limit=1),
    )

    planner.build_intent_plan(
        interpretation=_interpretation(),
        snapshot={"current_focus_target": "obj_letter"},
        current_goal_state={"primary_goal": "understand the letter"},
        memory_bundle={
            "working_memory": [],
            "event_memories": [
                {
                    "memory_id": "event:letter",
                    "actor_id": "char_b",
                    "event_id": "letter",
                    "source_event_id": "letter",
                    "world_ts": 10,
                    "event_type": "character_perceived_event",
                    "summary": "the sealed letter was destroyed",
                    "clarity_score": 0.9,
                    "certainty_score": 0.9,
                    "refs": [],
                },
                {
                    "memory_id": "event:weather",
                    "actor_id": "char_b",
                    "event_id": "weather",
                    "source_event_id": "weather",
                    "world_ts": 99,
                    "event_type": "character_perceived_event",
                    "summary": "the northern rain became heavier",
                    "clarity_score": 1.0,
                    "certainty_score": 1.0,
                    "refs": [],
                },
            ],
        },
        control_mode="agent_full_auto",
    )

    context = gateway.requests[0]["context"]
    assert [entry["memory_id"] for entry in context["memory"]["event_memories"]] == ["event:letter"]
    assert context["memory_recall"]["selected_memory_refs"] == ["event:event:letter"]


def test_l3_planner_consumes_one_shot_recovery_policy_from_runtime_memory() -> None:
    gateway = _recording_gateway_for_candidates(
        ["share_info", "observe"],
        selected_intent="share_info",
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        memory_bundle={
            "working_memory": [
                {
                    "event_type": "character_policy_candidate_event",
                    "producer_ts": 99,
                    "payload": {
                        "candidate_id": "candidate:recovery:1",
                        "status": "candidate_only",
                        "policy_type": "recovery_policy",
                        "failed_intent": "share_info",
                    },
                }
            ]
        },
    )

    assert plan["behavior_policy"]["candidate_id"] == "candidate:recovery:1"
    assert "share_info" not in plan["candidates"]
    assert plan["model_output"]["selected_intent"] == "share_info"


def test_l3_planner_passes_bounded_skill_affordance_to_model_without_overriding_selection() -> None:
    gateway = _recording_gateway_for_candidates(["observe"], selected_intent="observe")
    planner = CharacterAgentL3Service(gateway=gateway)

    decision = planner.select_intent(
        _interpretation(),
        skill_affordance_summary={
            "available_action_families": {"observation": {"level": "basic"}},
            "registry": {"must_not": "reach_the_model"},
        },
    )

    context = gateway.requests[0]["context"]
    assert context["skill_affordance_summary"] == {
        "available_action_families": {"observation": {"level": "basic"}}
    }
    assert decision.selected_intent == "observe"


def test_l3_planner_preserves_model_owned_selection_when_candidate_is_locally_valid() -> None:
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["share_info", "ask_probe", "observe"],
            "selected_intent": "share_info",
            "recommended_intents": ["share_info", "ask_probe"],
            "risk_notes": [],
            "why_this_now": "char_a appears open to a controlled disclosure",
            "role_consistency_hint": "speak narrowly",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    decision = planner.select_intent(
        _interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(privacy_sensitivity=0.2, trust_threshold_for_private_talk=0.2),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.95, "suspicion_baseline": 0.05}],
        },
    )

    assert decision.selected_intent == "share_info"
    assert decision.rationale == "char_a appears open to a controlled disclosure"
    assert decision.planning_status == "model"


def test_l3_planner_does_not_append_local_candidates_when_model_candidates_are_present() -> None:
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["share_info"],
            "selected_intent": "share_info",
            "recommended_intents": ["share_info"],
            "risk_notes": [],
            "why_this_now": "controlled disclosure is enough",
            "role_consistency_hint": "stay narrow",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(privacy_sensitivity=0.2, trust_threshold_for_private_talk=0.2),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.95, "suspicion_baseline": 0.05}],
        },
    )

    assert plan["candidates"] == ["share_info"]


def test_l3_planner_uses_model_owned_active_goal_frame_when_present() -> None:
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["ask_probe"],
            "selected_intent": "ask_probe",
            "recommended_intents": ["ask_probe"],
            "risk_notes": [],
            "why_this_now": "probe before committing",
            "role_consistency_hint": "probe softly",
            "active_goal_tags": ["clarify_intent", "preserve_optionality"],
            "active_goal_frame": {
                "primary_goal": "clarify_intent",
                "long_term_goal": "protect_secret",
                "mid_term_strategy": "probe_safely",
                "immediate_goal": "clarify_intent",
                "supporting_goals": ["preserve_optionality"],
                "blockers": ["insufficient_context"],
                "goal_sources": ["model_deliberation"],
                "urgency": "medium",
                "dominant_goal_id": "goal_clarify_intent",
                "preserved_goal_ids": ["goal_preserve_optionality"],
                "suppressed_goal_ids": ["goal_project_confidence"],
                "goal_arbitration_summary": "clarification dominates while optionality stays active",
                "goal_portfolio": [
                    {
                        "goal_id": "goal_clarify_intent",
                        "goal": "clarify_intent",
                        "horizon": "mid",
                        "status": "active",
                        "priority": 0.83,
                        "urgency": "medium",
                        "source": "model_deliberation",
                    },
                    {
                        "goal_id": "goal_preserve_optionality",
                        "goal": "preserve_optionality",
                        "horizon": "mid",
                        "status": "active",
                        "priority": 0.66,
                        "urgency": "low",
                        "source": "model_deliberation",
                    },
                ],
            },
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
    )
    decision = planner.select_intent(
        _interpretation(),
        control_mode="agent_full_auto",
    )

    assert plan["active_goal_tags"] == ["clarify_intent", "preserve_optionality"]
    assert plan["active_goal_frame"]["primary_goal"] == "clarify_intent"
    assert plan["active_goal_frame"]["mid_term_strategy"] == "probe_safely"
    assert plan["active_goal_frame"]["goal_sources"] == ["model_deliberation"]
    assert plan["active_goal_frame"]["dominant_goal_id"] == "goal_clarify_intent"
    assert plan["active_goal_frame"]["preserved_goal_ids"] == ["goal_preserve_optionality"]
    assert plan["active_goal_frame"]["goal_portfolio"][0]["goal"] == "clarify_intent"
    assert decision.primary_goal == "clarify_intent"
    assert decision.mid_term_strategy == "probe_safely"
    assert decision.active_goal_frame is not None
    assert decision.active_goal_frame.dominant_goal_id == "goal_clarify_intent"
    assert decision.active_goal_frame.goal_portfolio[1].goal_id == "goal_preserve_optionality"


def test_l3_planner_injects_current_goal_state_and_history_into_model_context() -> None:
    gateway = _recording_gateway_for_candidates(["ask_probe"])
    planner = CharacterAgentL3Service(gateway=gateway)

    current_goal_state = {
        "actor_id": "char_b",
        "primary_goal": "protect_secret",
        "long_term_goal": "preserve_order",
        "mid_term_strategy": "contain_exposure",
        "immediate_goal": "protect_secret",
        "supporting_goals": ["clarify_intent"],
        "blockers": ["high_masking_pressure"],
        "goal_sources": ["goal_state_store"],
        "urgency": "high",
        "dominant_goal_id": "goal_protect_secret",
        "preserved_goal_ids": ["goal_clarify_intent"],
        "suppressed_goal_ids": ["goal_project_confidence"],
        "goal_arbitration_summary": "safety dominates while clarification remains active",
        "goal_portfolio": [
            {
                "goal_id": "goal_protect_secret",
                "goal": "protect_secret",
                "horizon": "long",
                "status": "active",
                "priority": 0.93,
                "urgency": "high",
                "source": "goal_state_store",
            }
        ],
        "transition_kind": "maintained",
        "transition_reason_tags": ["goal_portfolio_stable"],
    }
    goal_state_history = [
        {
            "actor_id": "char_b",
            "primary_goal": "preserve_optionality",
            "long_term_goal": "preserve_order",
            "mid_term_strategy": "hold_position",
            "immediate_goal": "preserve_optionality",
            "supporting_goals": [],
            "blockers": [],
            "goal_sources": ["goal_state_store"],
            "urgency": "medium",
            "dominant_goal_id": "goal_preserve_optionality",
            "preserved_goal_ids": [],
            "suppressed_goal_ids": [],
            "goal_arbitration_summary": "optionality dominated before the new pressure spike",
            "goal_portfolio": [],
            "transition_kind": "initial",
            "transition_reason_tags": [],
        }
    ]

    planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        current_goal_state=current_goal_state,
        goal_state_history=goal_state_history,
    )

    request = gateway.requests[0]
    assert request["context"]["current_goal_state"]["dominant_goal_id"] == "goal_protect_secret"
    assert request["context"]["current_goal_state"]["goal_portfolio"][0]["goal"] == "protect_secret"
    assert request["context"]["goal_state_history"][0]["transition_kind"] == "initial"


def test_l3_planner_injects_effective_profile_need_tension_and_dynamic_state_into_model_context() -> None:
    gateway = _recording_gateway_for_candidates(["self_protect", "observe"], selected_intent="self_protect")
    planner = CharacterAgentL3Service(gateway=gateway)
    working_memory_state = {
        "recent_perceived_events": [],
        "recent_esm_results": [],
        "recent_siming_catalysts": [],
        "private_snapshot": {"actor_id": "char_b"},
        "dynamic_state": {
            "actor_id": "char_b",
            "stress_load": 0.72,
            "social_pressure": 0.68,
            "masking_pressure": 0.61,
            "motivation_stack": ["preserve_order"],
        },
    }
    effective_profile = {
        **_profile_payload(),
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": 0.9,
                "esteem": 0.45,
            }
        },
    }
    need_tension_state = {
        "actor_id": "char_b",
        "dominant_need": "safety",
        "secondary_need": "esteem",
        "motivation_stack": ["safety", "esteem"],
        "pressure_sources": ["public_dismissal"],
        "safety_pressure": 0.86,
        "esteem_pressure": 0.44,
    }
    dynamic_state = {
        "actor_id": "char_b",
        "stress_load": 0.72,
        "social_pressure": 0.68,
        "masking_pressure": 0.61,
        "motivation_stack": ["preserve_order"],
    }

    planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(),
        effective_profile=effective_profile,
        working_memory_state=working_memory_state,
        need_tension_state=need_tension_state,
        dynamic_state=dynamic_state,
    )

    request = gateway.requests[0]
    assert request["context"]["profile"]["identity_core"]["character_id"] == "char_b"
    assert request["context"]["effective_profile"]["need_hierarchy_layer"]["effective_weights"]["safety"] == 0.9
    assert request["context"]["need_tension_state"]["dominant_need"] == "safety"
    assert request["context"]["dynamic_state"]["stress_load"] == 0.72
    assert request["context"]["working_memory_state"]["dynamic_state"]["social_pressure"] == 0.68


def test_l3_planner_raises_self_protect_over_observe_when_need_pressure_and_dynamic_stress_are_high() -> None:
    planner = CharacterAgentL3Service(
        gateway=_recording_gateway_for_candidates(["observe", "self_protect"], selected_intent="observe")
    )
    interpretation = _interpretation().model_copy(
        update={
            "risk_level": "medium",
            "opportunity_level": "low",
        }
    )

    pressured_plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        effective_profile={
            **_profile_payload(),
            "need_hierarchy_layer": {"effective_weights": {"safety": 0.95}},
        },
        need_tension_state={
            "dominant_need": "safety",
            "secondary_need": "esteem",
            "motivation_stack": ["safety", "esteem"],
            "pressure_sources": ["public_dismissal"],
            "safety_pressure": 0.92,
            "esteem_pressure": 0.35,
        },
        dynamic_state={
            "actor_id": "char_b",
            "stress_load": 0.81,
            "vigilance_level": 0.73,
            "social_pressure": 0.64,
            "masking_pressure": 0.58,
        },
    )
    baseline_plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
    )

    pressured_scores = {
        result["candidate"]: result["gain_loss_score"] for result in pressured_plan["filter_results"]
    }
    baseline_scores = {
        result["candidate"]: result["gain_loss_score"] for result in baseline_plan["filter_results"]
    }

    assert pressured_scores["self_protect"] > pressured_scores["observe"]
    assert pressured_scores["self_protect"] > baseline_scores["self_protect"]
    assert pressured_scores["observe"] < baseline_scores["observe"]


def test_l3_planner_uses_projection_not_raw_overlap_for_deescalation_scoring() -> None:
    planner = CharacterAgentL3Service(
        gateway=_recording_gateway_for_candidates(["defer", "observe"], selected_intent="observe")
    )
    effective_profile = {
        **_profile_payload(),
        "trait_vector_layer": {"empathy": 0.99},
        "temperament_response_layer": {
            "conflict_style": {"mediation_tendency": 0.99},
        },
        "personality_projection": {
            "conflict_deescalation_bias": 0.1,
            "procedural_discipline": 0.5,
            "public_assertion_bias": 0.5,
            "avoidance_bias": 0.5,
        },
    }

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        effective_profile=effective_profile,
    )

    defer = next(result for result in plan["filter_results"] if result["candidate"] == "defer")

    assert defer["gain_loss_score"] == 0.5
    assert all("raw_personality" not in note for note in defer["gain_loss_notes"])


def test_l3_planner_raises_deescalation_candidate_from_personality_projection() -> None:
    planner = CharacterAgentL3Service(
        gateway=_recording_gateway_for_candidates(["defer", "observe"], selected_intent="observe")
    )
    low_projection_plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        effective_profile={
            **_profile_payload(),
            "personality_projection": {
                "conflict_deescalation_bias": 0.5,
                "procedural_discipline": 0.5,
                "public_assertion_bias": 0.5,
                "avoidance_bias": 0.5,
            },
        },
    )
    high_projection_plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        effective_profile={
            **_profile_payload(),
            "personality_projection": {
                "conflict_deescalation_bias": 0.9,
                "procedural_discipline": 0.5,
                "public_assertion_bias": 0.5,
                "avoidance_bias": 0.5,
            },
        },
    )

    low_defer = next(
        result for result in low_projection_plan["filter_results"] if result["candidate"] == "defer"
    )
    high_defer = next(
        result for result in high_projection_plan["filter_results"] if result["candidate"] == "defer"
    )

    assert high_defer["gain_loss_score"] > low_defer["gain_loss_score"]
    assert "personality_projection=conflict_deescalation_bias" in high_defer["gain_loss_notes"]


def test_l3_planner_uses_dominant_need_weight_for_non_safety_pressure() -> None:
    planner = CharacterAgentL3Service(
        gateway=_recording_gateway_for_candidates(["observe", "self_protect"], selected_intent="observe")
    )
    interpretation = _interpretation().model_copy(
        update={
            "risk_level": "medium",
            "opportunity_level": "low",
        }
    )
    need_tension_state = {
        "dominant_need": "esteem",
        "secondary_need": "safety",
        "motivation_stack": ["esteem", "safety"],
        "pressure_sources": ["public_dismissal"],
        "esteem_pressure": 0.9,
        "safety_pressure": 0.2,
    }
    dynamic_state = {
        "actor_id": "char_b",
        "stress_load": 0.4,
        "social_pressure": 0.5,
    }

    high_esteem_plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        effective_profile={
            **_profile_payload(),
            "need_hierarchy_layer": {"effective_weights": {"esteem": 0.95, "safety": 0.05}},
        },
        need_tension_state=need_tension_state,
        dynamic_state=dynamic_state,
    )
    low_esteem_plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        effective_profile={
            **_profile_payload(),
            "need_hierarchy_layer": {"effective_weights": {"esteem": 0.1, "safety": 0.95}},
        },
        need_tension_state=need_tension_state,
        dynamic_state=dynamic_state,
    )

    high_scores = {
        result["candidate"]: result["gain_loss_score"] for result in high_esteem_plan["filter_results"]
    }
    low_scores = {
        result["candidate"]: result["gain_loss_score"] for result in low_esteem_plan["filter_results"]
    }

    assert high_scores["self_protect"] > low_scores["self_protect"]
    assert high_scores["observe"] < low_scores["observe"]


def test_l3_planner_uses_positive_affect_to_bias_approach_without_need_pressure() -> None:
    planner = CharacterAgentL3Service(
        gateway=_recording_gateway_for_candidates(["share_info", "speak_private", "self_protect"], selected_intent="share_info")
    )
    interpretation = _interpretation().model_copy(
        update={
            "attention_target": "char_a",
            "risk_level": "low",
            "opportunity_level": "medium",
        }
    )

    positive_plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        dynamic_state={
            "actor_id": "char_b",
            "affect_state": {
                "trust": 0.8,
                "affection": 0.5,
                "gratitude": 0.4,
                "calm": 0.7,
                "confidence": 0.6,
            },
        },
    )
    baseline_plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
    )

    positive_scores = {
        result["candidate"]: result["gain_loss_score"] for result in positive_plan["filter_results"]
    }
    baseline_scores = {
        result["candidate"]: result["gain_loss_score"] for result in baseline_plan["filter_results"]
    }

    assert positive_scores["share_info"] > baseline_scores["share_info"]
    assert positive_scores["speak_private"] > baseline_scores["speak_private"]
    assert positive_scores["self_protect"] < baseline_scores["self_protect"]


def test_l3_suggestion_packet_surfaces_interpretation_cognition_cues() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())
    interpretation = _interpretation().model_copy(
        update={
            "belief_deltas": [{"proposition_key": "char_a:is_probing", "state": "suspected"}],
            "higher_order_deltas": [{"subject_actor_id": "char_a", "meta_belief": "char_a suspects char_b knows more"}],
            "dynamic_state_delta": {"social_pressure": 0.7, "masking_pressure": 0.55},
            "reasoning_trace_summary": "char_b:probing-read",
        }
    )

    packet = planner.build_suggestion_packet(
        interpretation=interpretation,
        control_mode="player_priority_assisted",
    )

    assert packet["belief_cues"][0] == "char_a:is_probing=suspected"
    assert packet["higher_order_cues"][0] == "char_a suspects char_b knows more"
    assert packet["dynamic_pressure"] == "social_pressure=0.7|masking_pressure=0.55"
    assert packet["reasoning_trace_summary"] == "char_b:probing-read"


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
        profile=_profile_payload(),
        memory_bundle={
            "working_memory": [{"event_id": "evt:1"}],
            "episodic_memories": [{"summary": "char_a spoke nearby"}],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.25, "suspicion_baseline": 0.81}],
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
    assert gateway.requests[0]["context"]["profile"]["conversation_personality_layer"]["privacy_sensitivity"] == 0.71
    assert gateway.requests[0]["context"]["memory"]["social_memories"][0]["entity_id"] == "char_a"
    assert gateway.requests[0]["context"]["memory"]["episodic_memories"][0]["summary"] == "char_a spoke nearby"
    assert gateway.requests[0]["context"]["working_memory_state"]["private_snapshot"]["actor_id"] == "char_b"


def test_l3_planner_build_intent_plan_accepts_typed_memory_record_bundle() -> None:
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

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        memory_bundle=CharacterMemoryRecordBundle(
            knowledge_memories=[
                CharacterKnowledgeMemoryRecord(
                    memory_id="knowledge:char_b:char_a:is_hiding_something",
                    actor_id="char_b",
                    proposition_key="char_a:is_hiding_something",
                    proposition="char_a may be hiding something",
                    state="suspected",
                    confidence=0.62,
                    source_event_id="evt:1",
                    producer_ts=1,
                )
            ],
            social_memories=[
                CharacterSocialMemoryRecord(
                    memory_id="social:char_b:char_a",
                    actor_id="char_b",
                    entity_id="char_a",
                    trust_baseline=0.25,
                    suspicion_baseline=0.81,
                    intimacy=0.0,
                    dependency=0.0,
                    unresolved_tension=0.2,
                    shared_secret_refs=[],
                    source_event_id="evt:2",
                    producer_ts=2,
                )
            ],
            higher_order_memories=[
                CharacterHigherOrderMemoryRecord(
                    memory_id="higher:char_b:char_a:1",
                    actor_id="char_b",
                    subject_actor_id="char_a",
                    proposition_key="social_probe:knowledge_asymmetry",
                    meta_belief="char_a suspects char_b knows more",
                    confidence=0.72,
                    source_event_id="evt:3",
                    producer_ts=3,
                )
            ],
        ),
    )

    assert plan["filter_results"]
    assert gateway.requests
    assert gateway.requests[0]["context"]["memory"]["knowledge_memories"][0]["proposition_key"] == "char_a:is_hiding_something"


def test_l3_planner_uses_typed_memory_record_bundle_for_core_social_and_higher_order_reasoning() -> None:
    planner = CharacterAgentL3Service(
        gateway=_recording_gateway_for_candidates(
            ["ask_probe", "share_info", "observe"],
            selected_intent="ask_probe",
            recommended_intents=["ask_probe", "observe"],
        )
    )

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        memory_bundle=CharacterMemoryRecordBundle(
            knowledge_memories=[
                CharacterKnowledgeMemoryRecord(
                    memory_id="knowledge:char_b:char_a:is_hiding_something",
                    actor_id="char_b",
                    proposition_key="char_a:is_hiding_something",
                    proposition="char_a may be hiding something",
                    state="suspected",
                    confidence=0.62,
                    source_event_id="evt:1",
                    producer_ts=1,
                )
            ],
            social_memories=[
                CharacterSocialMemoryRecord(
                    memory_id="social:char_b:char_a",
                    actor_id="char_b",
                    entity_id="char_a",
                    trust_baseline=0.25,
                    suspicion_baseline=0.88,
                    intimacy=0.0,
                    dependency=0.0,
                    unresolved_tension=0.2,
                    shared_secret_refs=[],
                    source_event_id="evt:2",
                    producer_ts=2,
                )
            ],
            higher_order_memories=[
                CharacterHigherOrderMemoryRecord(
                    memory_id="higher:char_b:char_a:1",
                    actor_id="char_b",
                    subject_actor_id="char_a",
                    proposition_key="social_probe:knowledge_asymmetry",
                    meta_belief="char_a suspects char_b knows more",
                    confidence=0.72,
                    source_event_id="evt:3",
                    producer_ts=3,
                )
            ],
        ),
    )

    ask_probe = next(result for result in plan["filter_results"] if result["candidate"] == "ask_probe")
    share_info = next(result for result in plan["filter_results"] if result["candidate"] == "share_info")

    assert ask_probe["gain_loss_score"] == share_info["gain_loss_score"]


def test_l3_planner_local_only_candidates_stay_narrow_even_with_recent_world_changes() -> None:
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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"recent_world_changes": ["moved closer to target"]},
    )

    assert plan["candidates"] == ["observe", "self_protect"]


def test_l3_candidate_generation_supports_broad_role_action_space() -> None:
    planner = CharacterAgentL3Service(
        gateway=_recording_gateway_for_candidates(
            [
                "observe",
                "inspect_object",
                "self_protect",
                "pause",
                "defer",
                "withhold",
                "ask_probe",
                "share_info",
                "speak_private",
                "follow_target",
                "seek_private_distance",
                "break_contact",
                "withdraw",
                "approach",
                "speak_public",
            ],
            selected_intent="observe",
        )
    )

    plan = planner.build_intent_plan(
        interpretation=CharacterInterpretation(
            actor_id="char_a",
            interpreted_summary="char_b may be testing whether the letter can be exposed",
            interpretation_type="social_signal",
            salience_score=0.82,
            ambiguity_level="medium",
            risk_level="medium",
            opportunity_level="medium",
            attention_target="char_b",
            inner_prompt_candidate="preserve optionality",
        ),
        control_mode="agent_full_auto",
    )

    assert "withhold" in plan["candidates"]
    assert "seek_private_distance" in plan["candidates"]
    assert "break_contact" in plan["candidates"]
    assert "pause" in plan["candidates"]
    assert "defer" in plan["candidates"]


def test_l3_build_intent_plan_exposes_active_goal_tags() -> None:
    planner = CharacterAgentL3Service(
        gateway=_RecordingGateway(
            {
                "candidate_intents": ["self_protect", "observe", "ask_probe"],
                "selected_intent": "self_protect",
                "recommended_intents": ["self_protect"],
                "risk_notes": [],
                "why_this_now": "pressure remains elevated",
                "role_consistency_hint": "stay guarded",
                "active_goal_tags": ["protect_secret", "protect_self", "clarify_intent"],
                "active_goal_frame": {
                    "primary_goal": "protect_secret",
                    "long_term_goal": "preserve_order",
                    "mid_term_strategy": "contain_exposure",
                    "immediate_goal": "protect_secret",
                    "supporting_goals": ["protect_self", "clarify_intent"],
                    "blockers": ["high_masking_pressure"],
                    "goal_sources": ["dynamic_state", "knowledge_state", "profile_values", "l2_goal_hint:social_signal"],
                    "urgency": "high",
                },
            }
        )
    )

    plan = planner.build_intent_plan(
        interpretation=_interpretation().model_copy(
            update={
                "ambiguity_level": "medium",
                "risk_level": "medium",
                "goal_hints": [
                    {"goal": "protect_secret", "source": "social_signal", "strength": 0.85},
                    {"goal": "clarify_intent", "source": "knowledge_state", "strength": 0.7},
                ],
            }
        ),
        control_mode="agent_full_auto",
        profile=_profile_payload(value_priorities=["clarity", "safety"]),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "knowledge_memories": [
                {
                    "proposition_key": "char_a:is_hiding_something",
                    "proposition": "char_a may be hiding something",
                    "state": "suspected",
                    "confidence": 0.62,
                }
            ],
        },
        working_memory_state={
            "dynamic_state": {
                "masking_pressure": 0.75,
                "motivation_stack": ["preserve_order"],
            }
        },
    )

    assert "protect_secret" in plan["active_goal_tags"]
    assert "protect_self" in plan["active_goal_tags"]
    assert "clarify_intent" in plan["active_goal_tags"]
    assert plan["active_goal_frame"]["primary_goal"] == "protect_secret"
    assert plan["active_goal_frame"]["long_term_goal"] == "preserve_order"
    assert plan["active_goal_frame"]["immediate_goal"] == "protect_secret"
    assert "protect_self" in plan["active_goal_frame"]["supporting_goals"]
    assert "clarify_intent" in plan["active_goal_frame"]["supporting_goals"]
    assert plan["active_goal_frame"]["urgency"] == "high"
    assert plan["active_goal_frame"]["mid_term_strategy"] == "contain_exposure"
    assert "high_masking_pressure" in plan["active_goal_frame"]["blockers"]
    assert "dynamic_state" in plan["active_goal_frame"]["goal_sources"]
    assert "knowledge_state" in plan["active_goal_frame"]["goal_sources"]
    assert "profile_values" in plan["active_goal_frame"]["goal_sources"]
    assert "l2_goal_hint:social_signal" in plan["active_goal_frame"]["goal_sources"]


def test_l3_goal_frame_prioritizes_stronger_l2_goal_hint_over_default_priority_order() -> None:
    planner = CharacterAgentL3Service(
        gateway=_RecordingGateway(
            {
                "candidate_intents": ["ask_probe", "observe"],
                "selected_intent": "ask_probe",
                "recommended_intents": ["ask_probe"],
                "risk_notes": [],
                "why_this_now": "clarity matters more than concealment here",
                "role_consistency_hint": "probe softly",
                "active_goal_frame": {
                    "primary_goal": "clarify_intent",
                    "long_term_goal": "preserve_order",
                    "mid_term_strategy": "probe_safely",
                    "immediate_goal": "clarify_intent",
                    "supporting_goals": [],
                    "blockers": [],
                    "goal_sources": ["l2_goal_hint:social_signal"],
                    "urgency": "medium",
                },
            }
        )
    )

    plan = planner.build_intent_plan(
        interpretation=_interpretation().model_copy(
            update={
                "goal_hints": [
                    {"goal": "clarify_intent", "source": "social_signal", "strength": 0.95},
                    {"goal": "protect_secret", "source": "social_signal", "strength": 0.55},
                ],
                "ambiguity_level": "medium",
                "risk_level": "medium",
            }
        ),
        control_mode="agent_full_auto",
        profile=_profile_payload(value_priorities=["clarity", "safety"]),
        memory_bundle={"working_memory": [], "episodic_memories": [], "knowledge_memories": []},
        working_memory_state={
            "dynamic_state": {
                "masking_pressure": 0.75,
                "motivation_stack": ["preserve_order"],
            }
        },
    )

    assert plan["active_goal_frame"]["primary_goal"] == "clarify_intent"


def test_l3_select_intent_carries_typed_active_goal_frame_on_decision() -> None:
    planner = CharacterAgentL3Service(
        gateway=_RecordingGateway(
            {
                "candidate_intents": ["self_protect", "observe"],
                "selected_intent": "self_protect",
                "recommended_intents": ["self_protect"],
                "risk_notes": [],
                "why_this_now": "contain exposure before speaking",
                "role_consistency_hint": "stay guarded",
                "active_goal_frame": {
                    "primary_goal": "protect_secret",
                    "long_term_goal": "preserve_order",
                    "mid_term_strategy": "contain_exposure",
                    "immediate_goal": "protect_secret",
                    "supporting_goals": [],
                    "blockers": ["high_masking_pressure"],
                    "goal_sources": ["l2_goal_hint:social_signal"],
                    "urgency": "high",
                },
            }
        )
    )

    decision = planner.select_intent(
        _interpretation().model_copy(
            update={
                "goal_hints": [
                    {"goal": "protect_secret", "source": "social_signal", "strength": 0.85},
                ],
                "ambiguity_level": "medium",
                "risk_level": "medium",
            }
        ),
        control_mode="agent_full_auto",
        profile=_profile_payload(value_priorities=["clarity", "safety"]),
        memory_bundle={
            "working_memory": [],
            "knowledge_memories": [
                {
                    "proposition_key": "char_a:is_hiding_something",
                    "proposition": "char_a may be hiding something",
                    "state": "suspected",
                    "confidence": 0.62,
                }
            ],
        },
        working_memory_state={
            "dynamic_state": {
                "masking_pressure": 0.75,
                "motivation_stack": ["preserve_order"],
            }
        },
    )

    assert decision.active_goal_frame is not None
    assert decision.active_goal_frame.primary_goal == decision.primary_goal
    assert decision.active_goal_frame.mid_term_strategy == "contain_exposure"


def test_l3_normalize_interpretation_coerces_dict_deltas_into_typed_models(recwarn) -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())
    interpretation = _interpretation().model_copy(
        update={
            "belief_deltas": [{"proposition_key": "char_a:is_probing", "state": "suspected"}],
            "social_deltas": [{"entity_id": "char_a", "suspicion_baseline": 0.8}],
            "higher_order_deltas": [{"subject_actor_id": "char_a", "meta_belief": "char_a suspects char_b knows more"}],
        }
    )

    normalized = planner._normalize_interpretation(interpretation)  # type: ignore[attr-defined]

    assert isinstance(normalized.belief_deltas[0], CharacterBeliefDelta)
    assert isinstance(normalized.social_deltas[0], CharacterSocialDelta)
    assert isinstance(normalized.higher_order_deltas[0], CharacterHigherOrderDelta)
    assert len(recwarn) == 0


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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"recent_constraint_results": ["target is too far away"]},
    )

    assert "self_protect" in plan["candidates"]
    assert any(result["candidate"] == "self_protect" for result in plan["filter_results"])


def test_l3_planner_no_longer_gets_local_self_protect_selection_from_guarded_relational_memory() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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

    assert plan["model_output"]["selected_intent"] == "observe"
    assert plan["model_output"]["recommended_intents"][0] == "observe"
    assert decision.selected_intent == "observe"


def test_l3_planner_no_longer_rejects_share_info_from_local_private_profile_and_low_trust() -> None:
    planner = CharacterAgentL3Service(gateway=_recording_gateway_for_candidates(["share_info", "inspect_object", "observe"], selected_intent="share_info"))

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(privacy_sensitivity=0.84, trust_threshold_for_private_talk=0.82),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.25, "suspicion_baseline": 0.88}],
        },
    )

    share_info = next(result for result in plan["filter_results"] if result["candidate"] == "share_info")
    inspect_object = next(result for result in plan["filter_results"] if result["candidate"] == "inspect_object")

    assert share_info["persona_passed"] is True
    assert share_info["viability"] in {"weakly_viable", "viable", "highly_compelling"}
    assert inspect_object["logic_passed"] is False
    assert inspect_object["logic_notes"]


def test_l3_planner_no_longer_uses_social_trust_to_change_share_info_local_persona_result() -> None:
    planner = CharacterAgentL3Service(gateway=_recording_gateway_for_candidates(["share_info", "observe"], selected_intent="share_info"))
    profile = _profile_payload(privacy_sensitivity=0.84, trust_threshold_for_private_talk=0.82)

    low_trust_plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=profile,
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.25, "suspicion_baseline": 0.88}],
        },
    )
    high_trust_plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=profile,
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.93, "suspicion_baseline": 0.1}],
        },
    )

    low_trust_share_info = next(result for result in low_trust_plan["filter_results"] if result["candidate"] == "share_info")
    high_trust_share_info = next(result for result in high_trust_plan["filter_results"] if result["candidate"] == "share_info")

    assert low_trust_share_info["persona_passed"] is True
    assert high_trust_share_info["persona_passed"] is True
    assert high_trust_share_info["gain_loss_score"] == low_trust_share_info["gain_loss_score"]


def test_l3_planner_logic_uses_same_profile_guard_threshold_as_other_filters() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    logic_ok, logic_notes = planner._evaluate_logic(
        "self_protect",
        CharacterInterpretation(
            actor_id="char_b",
            interpreted_summary="char_a is hard to read",
            interpretation_type="state_change",
            salience_score=0.6,
            ambiguity_level="low",
            risk_level="low",
            opportunity_level="low",
            attention_target="char_a",
            inner_prompt_candidate="",
        ),
        snapshot={},
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.45, "suspicion_baseline": 0.1}],
        },
        profile=_profile_payload(trust_threshold_for_private_talk=0.82),
        control_mode="agent_full_auto",
    )

    assert logic_ok is True
    assert logic_notes == []


def test_l3_planner_select_intent_no_longer_rejects_model_share_info_from_local_profile_filter() -> None:
    gateway = _RecordingGateway(
        {
            "candidate_intents": ["share_info", "self_protect", "observe"],
            "selected_intent": "share_info",
            "recommended_intents": ["share_info", "self_protect"],
            "risk_notes": [],
            "why_this_now": "char_a is salient",
            "role_consistency_hint": "stay guarded",
        }
    )
    planner = CharacterAgentL3Service(gateway=gateway)

    decision = planner.select_intent(
        _interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(privacy_sensitivity=0.84, trust_threshold_for_private_talk=0.82),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.25, "suspicion_baseline": 0.88}],
        },
    )

    assert decision.selected_intent == "share_info"


def test_l3_planner_no_longer_rejects_share_info_from_dynamic_state_and_higher_order_alone() -> None:
    planner = CharacterAgentL3Service(gateway=_recording_gateway_for_candidates(["share_info", "ask_probe", "observe"], selected_intent="observe"))

    plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(privacy_sensitivity=0.84, trust_threshold_for_private_talk=0.82),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.93, "suspicion_baseline": 0.1}],
            "higher_order_memories": [
                {
                    "subject_actor_id": "char_a",
                    "proposition_key": "obj_letter:is_sensitive",
                    "meta_belief": "char_a suspects char_b knows more",
                    "confidence": 0.66,
                }
            ],
        },
        working_memory_state={
            "dynamic_state": {
                "masking_pressure": 0.85,
            }
        },
    )

    share_info = next(result for result in plan["filter_results"] if result["candidate"] == "share_info")
    ask_probe = next(result for result in plan["filter_results"] if result["candidate"] == "ask_probe")

    assert share_info["viability"] in {"weakly_viable", "viable", "highly_compelling"}
    assert ask_probe["gain_loss_score"] == 0.5


def test_l3_planner_no_longer_raises_withhold_value_from_higher_order_suspicion() -> None:
    planner = CharacterAgentL3Service(gateway=_recording_gateway_for_candidates(["withhold", "share_info", "observe"], selected_intent="observe"))

    plan_with_higher_order = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(privacy_sensitivity=0.55, trust_threshold_for_private_talk=0.5),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.93, "suspicion_baseline": 0.1}],
            "higher_order_memories": [
                {
                    "subject_actor_id": "char_a",
                    "proposition_key": "social_probe:knowledge_asymmetry",
                    "meta_belief": "char_a suspects char_b knows more",
                    "confidence": 0.72,
                }
            ],
        },
        working_memory_state={
            "dynamic_state": {
                "masking_pressure": 0.35,
            }
        },
    )
    baseline_plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        profile=_profile_payload(privacy_sensitivity=0.55, trust_threshold_for_private_talk=0.5),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.93, "suspicion_baseline": 0.1}],
        },
        working_memory_state={
            "dynamic_state": {
                "masking_pressure": 0.35,
            }
        },
    )

    withhold_with_higher_order = next(
        result for result in plan_with_higher_order["filter_results"] if result["candidate"] == "withhold"
    )
    withhold_baseline = next(
        result for result in baseline_plan["filter_results"] if result["candidate"] == "withhold"
    )

    assert withhold_with_higher_order["gain_loss_score"] == withhold_baseline["gain_loss_score"]


def test_l3_goal_activator_biases_defer_and_withhold_under_conflict_pressure() -> None:
    planner = CharacterAgentL3Service(gateway=_recording_gateway_for_candidates(["defer", "withhold", "share_info", "observe"], selected_intent="observe"))

    plan = planner.build_intent_plan(
        interpretation=_interpretation().model_copy(
            update={
                "attention_target": "char_a",
                "ambiguity_level": "medium",
                "risk_level": "medium",
                "opportunity_level": "medium",
            }
        ),
        control_mode="agent_full_auto",
        profile=_profile_payload(value_priorities=["clarity", "safety"]),
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "knowledge_memories": [
                {
                    "proposition_key": "char_a:is_hiding_something",
                    "proposition": "char_a may be hiding something",
                    "state": "suspected",
                    "confidence": 0.62,
                }
            ],
            "higher_order_memories": [
                {
                    "subject_actor_id": "char_a",
                    "proposition_key": "social_probe:knowledge_asymmetry",
                    "meta_belief": "char_a suspects char_b knows more",
                    "confidence": 0.72,
                }
            ],
        },
        working_memory_state={
            "dynamic_state": {
                "masking_pressure": 0.78,
                "stress_load": 0.7,
                "motivation_stack": ["preserve_order"],
            }
        },
    )

    defer = next(result for result in plan["filter_results"] if result["candidate"] == "defer")
    withhold = next(result for result in plan["filter_results"] if result["candidate"] == "withhold")
    share_info = next(result for result in plan["filter_results"] if result["candidate"] == "share_info")

    assert defer["gain_loss_score"] == 0.5
    assert withhold["gain_loss_score"] == share_info["gain_loss_score"]


def test_l3_planner_no_longer_raises_probe_value_from_suspected_knowledge_state() -> None:
    planner = CharacterAgentL3Service(gateway=_recording_gateway_for_candidates(["ask_probe", "observe"], selected_intent="observe"))

    plan_with_knowledge = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "knowledge_memories": [
                {
                    "proposition_key": "char_a:is_hiding_something",
                    "proposition": "char_a may be hiding something",
                    "state": "suspected",
                    "confidence": 0.62,
                }
            ],
                "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.55, "suspicion_baseline": 0.2}],
            },
        )
    baseline_plan = planner.build_intent_plan(
        interpretation=_interpretation(),
        control_mode="agent_full_auto",
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.55, "suspicion_baseline": 0.2}],
        },
    )

    ask_probe_with_knowledge = next(
        result for result in plan_with_knowledge["filter_results"] if result["candidate"] == "ask_probe"
    )
    ask_probe_baseline = next(
        result for result in baseline_plan["filter_results"] if result["candidate"] == "ask_probe"
    )

    assert ask_probe_with_knowledge["gain_loss_score"] == ask_probe_baseline["gain_loss_score"]


def test_l3_planner_uses_disputed_knowledge_state_to_raise_defer_value_and_suppress_public_action() -> None:
    planner = CharacterAgentL3Service(gateway=_recording_gateway_for_candidates(["defer", "speak_public", "observe"], selected_intent="observe"))

    plan = planner.build_intent_plan(
        interpretation=_interpretation().model_copy(
            update={
                "attention_target": None,
                "opportunity_level": "medium",
                "ambiguity_level": "medium",
            }
        ),
        control_mode="agent_full_auto",
        snapshot={"recent_world_changes": ["env_lamp changed from stable to alerted"]},
        memory_bundle={
            "working_memory": [],
            "episodic_memories": [],
            "knowledge_memories": [
                {
                    "proposition_key": "env_lamp:state_change",
                    "proposition": "env_lamp may have changed state",
                    "state": "disputed",
                    "confidence": 0.41,
                }
            ],
        },
    )

    defer = next(result for result in plan["filter_results"] if result["candidate"] == "defer")
    speak_public = next(result for result in plan["filter_results"] if result["candidate"] == "speak_public")

    assert defer["gain_loss_score"] == speak_public["gain_loss_score"]


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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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


def test_l3_suggestion_packet_enters_continuity_floor_when_recent_world_change_exists_and_model_recommendations_are_empty() -> None:
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

    assert packet["recommended_intents"][0] == "stay_silent"
    assert packet["planning_status"] == "continuity_floor"
    assert packet["fallback_mode"] == "continuity_floor"


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


def test_l3_suggestion_packet_enters_continuity_floor_for_elevated_vigilance_when_model_recommendations_are_empty() -> None:
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

    assert packet["recommended_intents"][0] == "stay_silent"
    assert packet["planning_status"] == "continuity_floor"
    assert packet["fallback_mode"] == "continuity_floor"
    assert packet["why_this_now"] == "heightened vigilance"
    assert packet["role_consistency_hint"] == "heightened vigilance"


def test_l3_suggestion_packet_enters_continuity_floor_for_elevated_vigilance_when_model_selected_intent_is_empty_in_assisted_mode() -> None:
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

    assert packet["recommended_intents"][0] == "stay_silent"
    assert packet["planning_status"] == "continuity_floor"


def test_l3_suggestion_packet_enters_continuity_floor_for_elevated_vigilance_when_model_selected_intent_is_empty_in_full_auto() -> None:
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

    assert packet["recommended_intents"][0] == "stay_silent"
    assert packet["planning_status"] == "continuity_floor"
