from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
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
    assert plan["candidates"]
    assert plan["filter_results"]
    assert "observe" in plan["candidates"]
    assert any(result["candidate"] == "observe" for result in plan["filter_results"])


def test_l3_planner_selects_intent_from_viable_candidates() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    decision = planner.select_intent(_interpretation())

    assert decision.actor_id == "char_b"
    assert decision.selected_intent in {"observe", "observe_target", "speak_public", "ask_probe", "share_info"}
    assert decision.rationale


def test_l3_planner_builds_char_c_suggestion_packet_in_player_priority_mode() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    packet = planner.build_suggestion_packet(
        interpretation=_interpretation(),
        control_mode="player_priority_assisted",
    )

    assert packet["control_mode"] == "player_priority_assisted"
    assert packet["recommended_intents"]
    assert packet["why_this_now"] == "char_a may be speaking nearby"
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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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

    assert ask_probe["gain_loss_score"] > share_info["gain_loss_score"]


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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    plan = planner.build_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"recent_world_changes": ["moved closer to target"]},
    )

    assert "observe" in plan["candidates"]
    assert "inspect_object" in plan["candidates"]
    assert "speak_public" in plan["candidates"]


def test_l3_candidate_generation_supports_broad_role_action_space() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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
    assert any(
        result["candidate"] == "self_protect" and result["viability"] in {"viable", "highly_compelling"}
        for result in plan["filter_results"]
    )


def test_l3_planner_prefers_self_protect_when_relational_memory_marks_attention_target_as_guarded() -> None:
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

    assert plan["model_output"]["selected_intent"] == "self_protect"
    assert plan["model_output"]["recommended_intents"][0] == "self_protect"
    assert decision.selected_intent == "physiology_hint"


def test_l3_planner_rejects_share_info_for_private_profile_with_low_social_trust() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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

    assert share_info["persona_passed"] is False
    assert share_info["viability"] == "rejected"
    assert share_info["persona_notes"]
    assert inspect_object["logic_passed"] is False
    assert inspect_object["logic_notes"]


def test_l3_planner_uses_social_memories_as_primary_trust_path_for_share_info() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())
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

    assert low_trust_share_info["persona_passed"] is False
    assert high_trust_share_info["persona_passed"] is True
    assert high_trust_share_info["gain_loss_score"] > low_trust_share_info["gain_loss_score"]


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


def test_l3_planner_target_memory_context_ignores_unstructured_substring_mentions() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    has_context = planner._has_target_memory_context(
        "char_a",
        {
            "working_memory": [],
            "episodic_memories": [{"summary": "heard char_a discussed in passing"}],
            "event_memories": [{"summary": "heard char_a discussed in passing"}],
            "knowledge_memories": [{"proposition": "someone else mentioned char_a in a rumor"}],
            "social_memories": [{"entity_id": "char_b", "notes": "char_a appears in free text only"}],
            "relational_memories": [],
        },
    )

    assert has_context is False


def test_l3_planner_helper_methods_accept_typed_memory_record_bundle() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())
    memory_bundle = CharacterMemoryRecordBundle(
        event_memories=[
            CharacterEventMemoryRecord(
                memory_id="event:char_b:char_a:1",
                actor_id="char_b",
                event_id="evt:char_a:1",
                source_event_id="evt:char_a:1",
                world_ts=1,
                event_type="dialogue",
                summary="char_a spoke nearby",
                clarity_score=0.72,
                certainty_score=0.8,
                refs=["char_a"],
            )
        ],
        observation_memories=[
            CharacterObservationMemoryRecord(
                memory_id="obs:char_b:char_a:1",
                actor_id="char_b",
                source_event_id="evt:char_a:2",
                world_ts=2,
                observed_entity_id="char_a",
                observation_type="posture",
                observation_summary="char_a looked guarded",
                clarity_score=0.76,
                certainty_score=0.81,
                distortion_tags=[],
                refs=[],
            )
        ],
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
                trust_baseline=0.28,
                suspicion_baseline=0.84,
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
    )

    assert planner._has_target_memory_context("char_a", memory_bundle) is True
    assert planner._social_trust_baseline("char_a", memory_bundle) == 0.28
    assert planner._social_suspicion_baseline("char_a", memory_bundle) == 0.84
    assert planner._knowledge_state_for_target("char_a", memory_bundle) == "suspected"
    assert planner._ambient_knowledge_state(memory_bundle) == "suspected"


def test_l3_planner_select_intent_rejects_model_share_info_when_local_profile_filter_blocks_it() -> None:
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

    assert decision.selected_intent == "physiology_hint"


def test_l3_planner_uses_dynamic_state_and_higher_order_memory_in_filtering() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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

    assert share_info["viability"] == "rejected"
    assert ask_probe["gain_loss_score"] > 0.6


def test_l3_planner_prefers_withhold_when_higher_order_memory_signals_target_suspects_hidden_knowledge() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    plan = planner.build_intent_plan(
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

    withhold = next(result for result in plan["filter_results"] if result["candidate"] == "withhold")
    share_info = next(result for result in plan["filter_results"] if result["candidate"] == "share_info")

    assert withhold["gain_loss_score"] > share_info["gain_loss_score"]


def test_l3_goal_activator_biases_defer_and_withhold_under_conflict_pressure() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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

    assert defer["gain_loss_score"] > 0.6
    assert withhold["gain_loss_score"] > share_info["gain_loss_score"]


def test_l3_planner_uses_suspected_knowledge_state_to_raise_probe_value() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

    plan = planner.build_intent_plan(
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

    ask_probe = next(result for result in plan["filter_results"] if result["candidate"] == "ask_probe")
    observe = next(result for result in plan["filter_results"] if result["candidate"] == "observe")

    assert ask_probe["gain_loss_score"] > observe["gain_loss_score"]


def test_l3_planner_uses_disputed_knowledge_state_to_raise_defer_value_and_suppress_public_action() -> None:
    planner = CharacterAgentL3Service(gateway=_LocalGateway())

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

    assert defer["gain_loss_score"] > speak_public["gain_loss_score"]


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


def test_l3_suggestion_packet_prefers_speak_public_for_elevated_vigilance_when_model_selected_intent_is_empty_in_assisted_mode() -> None:
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


def test_l3_suggestion_packet_prefers_speak_public_for_elevated_vigilance_when_model_selected_intent_is_empty_in_full_auto() -> None:
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
