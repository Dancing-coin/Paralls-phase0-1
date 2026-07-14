from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder


def _dossier_projection() -> dict[str, object]:
    return {
        "actor_id": "char_a",
        "identity": {"canonical_name": "Lin Yue", "self_concept": ["careful_steward"]},
        "embodiment": {"motor_baseline": {"sprint_capacity": "low"}},
        "authority": {"forbidden_actions": ["grant_sealed_access_alone"]},
        "private_truth": {"self_known_secret_count": 1, "projection_mode": "summarized"},
        "relationship_seeds": {
            "candidate_only": True,
            "relationship_seed_count": 1,
            "targets": ["char_b"],
        },
        "capability_seeds": {
            "candidate_only": True,
            "skill_seed_count": 1,
            "skill_ids": ["social.mediation"],
        },
        "source_refs": ["dossier:char_a"],
    }


def test_builder_places_profile_memory_state_goal_and_affordance_cards_in_separate_layers() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={"current_focus_target": "char_b", "visible_entities": ["char_b"]},
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "trait_vector_layer": {"empathy": 0.8, "rationality": 0.7},
            "virtue_value_layer": {"red_lines": ["do_not_falsify_authority_report"]},
        },
        memory_bundle={
            "event_memories": [{"memory_id": "event:old", "summary": "B once saved A"}],
            "knowledge_memories": [
                {
                    "proposition_key": "medicine:urgent",
                    "proposition": "medicine can save a child",
                }
            ],
            "social_memories": [
                {
                    "memory_id": "social:char_a:char_b",
                    "actor_id": "char_a",
                    "entity_id": "char_b",
                    "trust_baseline": 0.8,
                    "suspicion_baseline": 0.2,
                    "intimacy": 0.6,
                    "dependency": 0.3,
                    "unresolved_tension": 0.1,
                    "shared_secret_refs": ["secret:1"],
                    "source_event_id": "event:old",
                    "producer_ts": 12,
                }
            ],
            "higher_order_memories": [{"meta_belief": "B may know A is conflicted"}],
        },
        need_tension_state={"dominant_need": "esteem", "esteem_pressure": 0.4},
        dynamic_state={"stress_load": 0.5, "affect_state": {"concern": 0.7}},
        current_goal_state={"primary_goal": "preserve_order", "goal_portfolio": []},
        goal_state_history=[{"primary_goal": "protect_friend"}],
        unresolved_tensions=[{"summary": "order versus loyalty"}],
        supervision_state={"authorization_level": "none"},
        skill_affordance_summary={
            "available_action_families": {"social_deescalation": {"level": "trained"}}
        },
        action_affordance_summary={"available_actions": ["speak_private"]},
    )

    assert frame.actor_id == "char_a"
    assert frame.trigger.event_id == "event:1"
    assert frame.enduring_truth.cards[0].factor_type == "effective_profile"
    assert frame.memory_evidence.summary["event_memory_count"] == 1
    assert frame.runtime_state.summary["dominant_need"] == "esteem"
    assert frame.affordances.summary["has_skill_affordance"] is True
    assert "profile:char_a" in frame.provenance.source_refs


def test_builder_accepts_dossier_projection_as_shadow_cards() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={},
        memory_bundle={},
        dossier_projection=_dossier_projection(),
    )

    enduring_types = [card.factor_type for card in frame.enduring_truth.cards]
    memory_types = [card.factor_type for card in frame.memory_evidence.cards]
    affordance_types = [card.factor_type for card in frame.affordances.cards]

    assert "identity_context" in enduring_types
    assert "embodiment_context" in enduring_types
    assert "authority_context" in enduring_types
    assert "private_truth_context" in enduring_types
    assert "relationship_seed_context" in memory_types
    assert "capability_seed_affordance" in affordance_types
    capability_card = next(
        card for card in frame.affordances.cards if card.factor_type == "capability_seed_affordance"
    )
    assert capability_card.payload["candidate_only"] is True
    assert "ability_graph" not in capability_card.payload
    assert "dossier:char_a" in frame.provenance.source_refs


def test_builder_exposes_personality_projection_in_shadow_personality_bias_card() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "trait_vector_layer": {
                "courage": 0.64,
                "scheming": 0.31,
                "empathy": 0.82,
                "rationality": 0.74,
                "sociability": 0.58,
            },
            "virtue_value_layer": {"red_lines": ["do_not_falsify_authority_report"]},
            "conversation_personality_layer": {
                "social_openness": 0.57,
                "privacy_sensitivity": 0.63,
                "talk_initiative": 0.48,
                "deception_control": 0.87,
                "trust_threshold_for_private_talk": 0.66,
            },
            "temperament_response_layer": {
                "baseline_temperament": {
                    "dominance": 0.29,
                    "attachment": 0.76,
                    "emotional_reactivity": 0.44,
                    "recovery_speed": 0.58,
                    "impulse_control": 0.83,
                },
                "conflict_style": {
                    "avoidance_tendency": 0.46,
                    "mediation_tendency": 0.88,
                },
                "trust_dynamics": {"forgiveness_threshold": 0.59},
                "expression_bias": {"facial_control": 0.71},
            },
        },
        memory_bundle={},
    )

    effective_profile_card = next(
        card for card in frame.enduring_truth.cards if card.factor_type == "effective_profile"
    )
    personality_card = next(
        card for card in frame.enduring_truth.cards if card.factor_type == "personality_bias"
    )

    projection = personality_card.payload["personality_projection"]
    assert projection["empathic_attunement"] > 0.5
    assert projection["conflict_deescalation_bias"] > 0.5
    assert "empathy" not in projection
    assert effective_profile_card.payload["trait_vector_keys"] == [
        "courage",
        "empathy",
        "rationality",
        "scheming",
        "sociability",
    ]
    assert effective_profile_card.payload["red_lines"] == ["do_not_falsify_authority_report"]


def test_builder_summarizes_relationship_as_memory_owned_actor_private_projection() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={},
        memory_bundle={
            "social_memories": [
                {
                    "memory_id": "social:char_a:char_b",
                    "entity_id": "char_b",
                    "trust_baseline": 0.75,
                    "suspicion_baseline": 0.25,
                    "intimacy": 0.5,
                    "dependency": 0.2,
                    "unresolved_tension": 0.4,
                    "shared_secret_refs": [],
                    "source_event_id": "event:old",
                    "producer_ts": 1,
                }
            ]
        },
    )

    relationship_cards = [
        card for card in frame.memory_evidence.cards if card.factor_type == "relationship_context"
    ]

    assert len(relationship_cards) == 1
    assert relationship_cards[0].scope == "actor_private"
    assert relationship_cards[0].payload["target_count"] == 1
    assert relationship_cards[0].payload["top_target"] == "char_b"
    assert "social_memory:char_a:char_b" in relationship_cards[0].source_refs


def test_builder_normalizes_perception_payload_with_focus_target() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={
            "current_focus_target": "char_b",
            "current_attention_source": "focus_state",
            "visible_entities": ["char_b"],
        },
        effective_profile={},
        memory_bundle={},
    )

    perception_cards = [
        card for card in frame.runtime_state.cards if card.factor_type == "perception_context"
    ]

    assert len(perception_cards) == 1
    assert perception_cards[0].payload["focus_target"] == "char_b"
    assert perception_cards[0].payload["current_focus_target"] == "char_b"
    assert perception_cards[0].payload["visible_entities"] == ["char_b"]


def test_builder_copies_nested_inputs_into_stable_frame_snapshot() -> None:
    snapshot = {
        "current_focus_target": "char_b",
        "visible_entities": ["char_b"],
        "sensory": {"certainty": 0.9},
    }
    effective_profile = {
        "identity_core": {"canonical_name": "A"},
        "trait_vector_layer": {"empathy": 0.8},
        "virtue_value_layer": {"red_lines": ["do_not_lie"]},
    }
    memory_bundle = {
        "social_memories": [
            {
                "memory_id": "social:char_a:char_b",
                "entity_id": "char_b",
                "shared_secret_refs": ["secret:1"],
            }
        ]
    }
    dynamic_state = {"stress_load": 0.5, "affect_state": {"concern": 0.7}}
    current_goal_state = {
        "primary_goal": "preserve_order",
        "goal_portfolio": [{"goal_id": "goal:1"}],
    }
    supervision_state = {"authorization_level": "none", "watchers": ["system"]}
    skill_affordance_summary = {
        "available_action_families": {"social_deescalation": {"level": "trained"}}
    }
    action_affordance_summary = {"available_actions": ["speak_private"]}

    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot=snapshot,
        effective_profile=effective_profile,
        memory_bundle=memory_bundle,
        dynamic_state=dynamic_state,
        current_goal_state=current_goal_state,
        supervision_state=supervision_state,
        skill_affordance_summary=skill_affordance_summary,
        action_affordance_summary=action_affordance_summary,
    )

    snapshot["visible_entities"].append("char_c")
    snapshot["sensory"]["certainty"] = 0.1
    effective_profile["identity_core"]["canonical_name"] = "Mutated"
    effective_profile["virtue_value_layer"]["red_lines"].append("do_not_break_cover")
    memory_bundle["social_memories"][0]["shared_secret_refs"].append("secret:2")
    dynamic_state["affect_state"]["concern"] = 0.1
    current_goal_state["goal_portfolio"].append({"goal_id": "goal:2"})
    supervision_state["watchers"].append("operator")
    skill_affordance_summary["available_action_families"]["social_deescalation"]["level"] = (
        "novice"
    )
    action_affordance_summary["available_actions"].append("leave")

    perception_card = next(
        card for card in frame.runtime_state.cards if card.factor_type == "perception_context"
    )
    goal_card = next(card for card in frame.runtime_state.cards if card.factor_type == "goal_context")
    supervision_card = next(
        card for card in frame.runtime_state.cards if card.factor_type == "supervision"
    )
    skill_card = next(card for card in frame.affordances.cards if card.factor_type == "skill_affordance")
    action_card = next(
        card for card in frame.affordances.cards if card.factor_type == "action_affordance"
    )

    assert frame.enduring_truth.cards[0].payload["identity_core"]["canonical_name"] == "A"
    assert frame.enduring_truth.cards[0].payload["red_lines"] == ["do_not_lie"]
    assert perception_card.payload["visible_entities"] == ["char_b"]
    assert perception_card.payload["sensory"]["certainty"] == 0.9
    assert goal_card.payload["current_goal_state"]["goal_portfolio"] == [{"goal_id": "goal:1"}]
    assert supervision_card.payload["watchers"] == ["system"]
    assert skill_card.payload["available_action_families"]["social_deescalation"]["level"] == "trained"
    assert action_card.payload["available_actions"] == ["speak_private"]
