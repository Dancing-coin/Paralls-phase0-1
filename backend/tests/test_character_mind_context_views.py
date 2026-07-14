from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.view_builder import LayerContextViewBuilder
from app.character_agent.models.mind_frame import CognitionWorkspace


def _dossier_projection() -> dict[str, object]:
    return {
        "actor_id": "char_a",
        "identity": {"canonical_name": "Lin Yue", "self_concept": ["careful_steward"]},
        "embodiment": {
            "motor_baseline": {"sprint_capacity": "low"},
            "realization_hints": {"motion_style_tags": ["contained"]},
        },
        "authority": {
            "responsibilities": ["maintain_archive_order"],
            "forbidden_actions": ["grant_sealed_access_alone"],
        },
        "private_truth": {
            "self_known_secret_count": 1,
            "visible_truth_ids": ["secret:char_a:omission_fear"],
            "projection_mode": "summarized",
        },
        "relationship_seeds": {
            "candidate_only": True,
            "relationship_seed_count": 1,
            "targets": ["char_b"],
        },
        "capability_seeds": {
            "candidate_only": True,
            "skill_seed_count": 1,
            "skill_ids": ["social.mediation"],
            "constraint_count": 2,
        },
        "source_refs": ["dossier:char_a"],
    }


def _frame():
    return CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={"current_focus_target": "char_b", "visible_entities": ["char_b"]},
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "virtue_value_layer": {"red_lines": ["do_not_falsify_authority_report"]},
        },
        memory_bundle={
            "event_memories": [{"memory_id": "event:old", "summary": "B once saved A"}],
            "social_memories": [
                {
                    "memory_id": "social:char_a:char_b",
                    "entity_id": "char_b",
                    "trust_baseline": 0.8,
                    "suspicion_baseline": 0.2,
                    "intimacy": 0.6,
                    "dependency": 0.3,
                    "unresolved_tension": 0.1,
                    "shared_secret_refs": [],
                    "source_event_id": "event:old",
                    "producer_ts": 12,
                }
            ],
        },
        need_tension_state={"dominant_need": "esteem", "esteem_pressure": 0.4},
        dynamic_state={"stress_load": 0.5},
        current_goal_state={"primary_goal": "preserve_order"},
        unresolved_tensions=[{"summary": "order versus loyalty"}],
        supervision_state={"authorization_level": "none"},
        skill_affordance_summary={
            "available_action_families": {"social_deescalation": {"level": "trained"}}
        },
        action_affordance_summary={"available_actions": ["speak_private"]},
    )


def test_l2_view_contains_interpretation_inputs_but_not_affordance_registry() -> None:
    view = LayerContextViewBuilder().build_l2_view(_frame())

    assert view.actor_id == "char_a"
    assert view.perception_context["focus_target"] == "char_b"
    assert view.relationship_context_summary["top_target"] == "char_b"
    assert view.need_pressure_summary["dominant_need"] == "esteem"
    assert "available_action_families" not in view.model_dump()


def test_l3_view_contains_workspace_goals_state_and_affordance_summaries() -> None:
    workspace = CognitionWorkspace(
        active_conflicts=["order_vs_loyalty"],
        hard_constraints=["cannot_falsify_authority_report"],
    )

    view = LayerContextViewBuilder().build_l3_view(
        _frame(),
        interpretation_summary={"risk_level": "medium"},
        workspace=workspace,
    )

    assert view.interpretation_summary["risk_level"] == "medium"
    assert view.cognition_workspace.active_conflicts == ["order_vs_loyalty"]
    assert view.goal_context_summary["primary_goal"] == "preserve_order"
    assert (
        view.skill_affordance_summary["available_action_families"]["social_deescalation"]["level"]
        == "trained"
    )
    assert "registry" not in view.skill_affordance_summary
    assert "skills" not in view.skill_affordance_summary
    assert "actions" not in view.skill_affordance_summary
    assert "bindings" not in view.skill_affordance_summary
    assert view.hard_constraints == ["cannot_falsify_authority_report"]


def test_l2_view_mutation_does_not_mutate_frame_payloads_or_summaries() -> None:
    frame = _frame()
    view = LayerContextViewBuilder().build_l2_view(frame)

    view.perception_context["visible_entities"].append("char_c")
    view.effective_profile_summary["red_lines"].append("protect_secret")
    view.memory_activation_summary["event_memory_count"] = 99

    assert frame.runtime_state.cards[0].payload["visible_entities"] == ["char_b"]
    assert frame.enduring_truth.cards[0].payload["red_lines"] == [
        "do_not_falsify_authority_report"
    ]
    assert frame.memory_evidence.summary["event_memory_count"] == 1


def test_l2_view_can_see_shadow_personality_projection_without_raw_duplicate_fields() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "trait_vector_layer": {"empathy": 0.8, "scheming": 0.3},
            "conversation_personality_layer": {"social_openness": 0.57},
            "temperament_response_layer": {
                "conflict_style": {"mediation_tendency": 0.88},
            },
        },
        memory_bundle={},
    )

    view = LayerContextViewBuilder().build_l2_view(frame)
    personality_summary = view.personality_bias_summary
    projection = personality_summary["personality_projection"]
    projection["conflict_deescalation_bias"] = 0.0

    frame_personality_card = next(
        card for card in frame.enduring_truth.cards if card.factor_type == "personality_bias"
    )

    assert "conflict_deescalation_bias" in personality_summary["personality_projection"]
    assert "empathy" not in personality_summary["personality_projection"]
    assert (
        frame_personality_card.payload["personality_projection"]["conflict_deescalation_bias"]
        != 0.0
    )


def test_l2_view_includes_visibility_filtered_dossier_context_summary() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={},
        memory_bundle={},
        dossier_projection=_dossier_projection(),
    )

    view = LayerContextViewBuilder().build_l2_view(frame)
    summary = view.dossier_context_summary
    summary["identity"]["canonical_name"] = "Mutated"

    identity_card = next(
        card for card in frame.enduring_truth.cards if card.factor_type == "identity_context"
    )

    assert summary["identity"]["canonical_name"] == "Mutated"
    assert identity_card.payload["canonical_name"] == "Lin Yue"
    assert summary["embodiment"]["motor_baseline"]["sprint_capacity"] == "low"
    assert summary["authority"]["forbidden_actions"] == ["grant_sealed_access_alone"]
    assert summary["private_truth"]["self_known_secret_count"] == 1
    assert "character_profile" not in view.model_dump()
    assert "fears one omission" not in str(view.model_dump())


def test_l3_view_mutation_does_not_mutate_frame_payloads() -> None:
    frame = _frame()
    view = LayerContextViewBuilder().build_l3_view(
        frame,
        interpretation_summary={"risk_level": "medium"},
        workspace=CognitionWorkspace(),
    )

    view.skill_affordance_summary["available_action_families"]["social_deescalation"][
        "level"
    ] = "expert"
    view.action_affordance_summary["available_actions"].append("leave_scene")

    assert (
        frame.affordances.cards[0].payload["available_action_families"]["social_deescalation"][
            "level"
        ]
        == "trained"
    )
    assert frame.affordances.cards[1].payload["available_actions"] == ["speak_private"]


def test_l3_view_is_immune_to_caller_owned_input_mutation() -> None:
    interpretation_summary = {
        "risk_level": "medium",
        "signals": [{"kind": "hesitation", "weight": 0.5}],
    }
    workspace = CognitionWorkspace(
        active_conflicts=["order_vs_loyalty"],
        hard_constraints=["cannot_falsify_authority_report"],
    )
    view = LayerContextViewBuilder().build_l3_view(
        _frame(),
        interpretation_summary=interpretation_summary,
        workspace=workspace,
    )

    view.interpretation_summary["risk_level"] = "low"
    view.interpretation_summary["signals"][0]["weight"] = 0.1
    view.cognition_workspace.active_conflicts.append("protect_reputation")
    view.cognition_workspace.hard_constraints.append("do_not_escalate")

    assert interpretation_summary == {
        "risk_level": "medium",
        "signals": [{"kind": "hesitation", "weight": 0.5}],
    }
    assert workspace.active_conflicts == ["order_vs_loyalty"]
    assert workspace.hard_constraints == ["cannot_falsify_authority_report"]


def test_l3_view_includes_dossier_planning_summaries_only() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={},
        memory_bundle={},
        dossier_projection=_dossier_projection(),
    )

    view = LayerContextViewBuilder().build_l3_view(
        frame,
        interpretation_summary={},
        workspace=CognitionWorkspace(),
    )

    summary = view.dossier_planning_summary
    assert summary["authority"]["forbidden_actions"] == ["grant_sealed_access_alone"]
    assert summary["relationship_seed_context"]["candidate_only"] is True
    assert summary["capability_seed_affordance"]["skill_seed_count"] == 1
    assert "ability_graph" not in summary
    assert "character_profile" not in view.model_dump()
    assert "fears one omission" not in str(view.model_dump())


def test_l4_view_is_small_and_execution_focused() -> None:
    view = LayerContextViewBuilder().build_l4_view(
        _frame(),
        selected_intent="speak_private",
        selected_skill_path={"binding_id": "persuasion_to_speak_private"},
        target_refs={"actor": "char_b"},
    )

    assert view.selected_intent == "speak_private"
    assert view.selected_skill_path["binding_id"] == "persuasion_to_speak_private"
    assert view.target_refs == {"actor": "char_b"}
    assert "memory_activation_summary" not in view.model_dump()


def test_l4_view_is_immune_to_caller_owned_input_mutation() -> None:
    selected_skill_path = {
        "binding_id": "persuasion_to_speak_private",
        "steps": [{"kind": "speak", "style": "private"}],
    }
    target_refs = {"actor": "char_b"}
    view = LayerContextViewBuilder().build_l4_view(
        _frame(),
        selected_intent="speak_private",
        selected_skill_path=selected_skill_path,
        target_refs=target_refs,
    )

    selected_skill_path["steps"][0]["style"] = "public"
    selected_skill_path["binding_id"] = "mutated"
    target_refs["actor"] = "char_c"

    assert view.selected_skill_path == {
        "binding_id": "persuasion_to_speak_private",
        "steps": [{"kind": "speak", "style": "private"}],
    }
    assert view.target_refs == {"actor": "char_b"}


def test_l4_view_includes_action_relevant_dossier_execution_constraints() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={},
        memory_bundle={},
        dossier_projection=_dossier_projection(),
    )

    view = LayerContextViewBuilder().build_l4_view(
        frame,
        selected_intent="speak_private",
    )

    constraints = view.dossier_execution_constraints
    assert constraints["embodiment"]["motor_baseline"]["sprint_capacity"] == "low"
    assert constraints["authority"]["forbidden_actions"] == ["grant_sealed_access_alone"]
    assert "private_truth" not in constraints
    assert "relationship_seed_context" not in constraints
    assert "character_profile" not in view.model_dump()


def test_writeback_view_wraps_existing_outputs_without_persisting_them() -> None:
    view = LayerContextViewBuilder().build_writeback_view(
        _frame(),
        l2_deltas={"belief_deltas": [{"proposition_key": "b_motive"}]},
        l3_decision={"selected_intent": "speak_private"},
        l4_execution_proposal={"action_request_bundle": {"requested_actions": []}},
        settlement_result={"outcome_band": "partial"},
        evidence_refs=["event:1"],
    )

    assert view.l2_deltas["belief_deltas"][0]["proposition_key"] == "b_motive"
    assert view.settlement_result["outcome_band"] == "partial"


def test_writeback_view_is_immune_to_caller_owned_input_mutation() -> None:
    l2_deltas = {"belief_deltas": [{"proposition_key": "b_motive"}]}
    l3_decision = {"selected_intent": "speak_private", "reasons": ["privacy"]}
    l4_execution_proposal = {"action_request_bundle": {"requested_actions": ["speak"]}}
    settlement_result = {"outcome_band": "partial", "details": {"applied": True}}
    dialogue_or_action_outcome = {"events": [{"event_id": "event:2"}]}
    evidence_refs = ["event:1"]
    view = LayerContextViewBuilder().build_writeback_view(
        _frame(),
        l2_deltas=l2_deltas,
        l3_decision=l3_decision,
        l4_execution_proposal=l4_execution_proposal,
        settlement_result=settlement_result,
        dialogue_or_action_outcome=dialogue_or_action_outcome,
        evidence_refs=evidence_refs,
    )

    l2_deltas["belief_deltas"][0]["proposition_key"] = "mutated"
    l3_decision["reasons"].append("urgency")
    l4_execution_proposal["action_request_bundle"]["requested_actions"].append("leave")
    settlement_result["details"]["applied"] = False
    dialogue_or_action_outcome["events"][0]["event_id"] = "event:mutated"
    evidence_refs.append("event:2")

    assert view.l2_deltas == {"belief_deltas": [{"proposition_key": "b_motive"}]}
    assert view.l3_decision == {
        "selected_intent": "speak_private",
        "reasons": ["privacy"],
    }
    assert view.l4_execution_proposal == {
        "action_request_bundle": {"requested_actions": ["speak"]}
    }
    assert view.settlement_result == {
        "outcome_band": "partial",
        "details": {"applied": True},
    }
    assert view.dialogue_or_action_outcome == {"events": [{"event_id": "event:2"}]}
    assert view.evidence_refs == ["event:1"]
