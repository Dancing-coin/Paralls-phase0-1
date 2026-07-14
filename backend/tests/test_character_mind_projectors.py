from app.character_agent.mind.projectors import (
    AffectiveBodyStateProjector,
    DossierProjectionProjector,
    EffectiveProfileProjector,
    GoalContextProjector,
    MemoryActivationProjector,
    NeedPressureProjector,
    RelationshipContextProjector,
    SupervisionProjector,
    UnresolvedTensionProjector,
)
from app.character_agent.models.mind_frame import MentalFactorProjectionCard


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
        "source_refs": ["dossier:char_a", "dossier_layer:identity_profile:1"],
    }


def test_effective_profile_projector_emits_enduring_truth_cards() -> None:
    cards = EffectiveProfileProjector().project(
        actor_id="char_a",
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "virtue_value_layer": {"red_lines": ["do_not_falsify_authority_report"]},
            "trait_vector_layer": {"openness": 0.4},
            "conversation_personality_layer": {"tone": "formal"},
            "temperament_response_layer": {"threat_response": "controlled"},
        },
    )

    assert [card.factor_type for card in cards] == [
        "effective_profile",
        "authored_constraint",
        "personality_bias",
    ]
    assert all(card.layer == "enduring_truth" for card in cards)
    assert cards[0].source_refs == ["profile:char_a"]
    assert cards[1].source_refs == ["profile:char_a:virtue_value_layer"]
    assert cards[1].payload == {"red_lines": ["do_not_falsify_authority_report"]}
    assert cards[2].source_refs == ["profile:char_a:personality_layers"]
    assert cards[2].confidence == 0.9
    assert cards[2].payload["conversation_personality_layer"] == {"tone": "formal"}
    assert cards[2].payload["temperament_response_layer"] == {"threat_response": "controlled"}
    projection = cards[2].payload["personality_projection"]
    assert projection["conflict_deescalation_bias"] == 0.5
    assert "empathy" not in projection


def test_memory_projectors_keep_memory_and_relationship_context_memory_owned() -> None:
    memory_bundle = {
        "event_memories": [{"memory_id": "event:1", "summary": "B once saved A"}],
        "knowledge_memories": [{"memory_id": "knowledge:1", "proposition": "B is a medic"}],
        "higher_order_memories": [
            {
                "memory_id": "higher:1",
                "subject_actor_id": "char_b",
                "proposition_key": "b_motive",
                "meta_belief": "B may be protecting a child",
            }
        ],
        "social_memories": [
            {
                "memory_id": "social:char_a:char_b",
                "entity_id": "char_b",
                "trust_baseline": 0.8,
                "suspicion_baseline": 0.2,
            }
        ],
    }

    memory_cards = MemoryActivationProjector().project(memory_bundle)
    relationship_cards = RelationshipContextProjector().project(
        actor_id="char_a",
        social_memories=memory_bundle["social_memories"],
    )
    expected_memory_refs = [
        "memory:event:1",
        "memory:knowledge:1",
        "memory:higher:1",
    ]

    assert [card.factor_type for card in memory_cards] == [
        "memory_activation",
        "cognitive_anchor",
        "knowledge_context",
        "higher_order_belief",
    ]
    assert all(card.layer == "memory_evidence" for card in memory_cards)
    assert memory_cards[0].source_refs == expected_memory_refs
    assert memory_cards[1].confidence == 0.75
    assert memory_cards[1].payload == {"active_anchors": ["B once saved A"]}
    assert memory_cards[1].source_refs == expected_memory_refs
    assert memory_cards[2].confidence == 0.75
    assert memory_cards[2].payload == {"knowledge_memory_count": 1}
    assert memory_cards[2].source_refs == ["knowledge_memory:knowledge:1"]
    assert memory_cards[3].confidence == 0.75
    assert memory_cards[3].payload == {"higher_order_memory_count": 1}
    assert memory_cards[3].source_refs == ["higher_order_memory:higher:1"]
    assert relationship_cards[0].factor_type == "relationship_context"
    assert relationship_cards[0].layer == "memory_evidence"
    assert relationship_cards[0].source_refs == ["social_memory:char_a:char_b"]


def test_runtime_state_projectors_emit_need_affect_goal_tension_and_supervision_cards() -> None:
    cards: list[MentalFactorProjectionCard] = []
    cards.extend(NeedPressureProjector().project({"dominant_need": "esteem", "esteem_pressure": 0.4}))
    cards.extend(AffectiveBodyStateProjector().project({"stress_load": 0.6, "affect_valence": -0.2}))
    cards.extend(
        GoalContextProjector().project(
            current_goal_state={"primary_goal": "verify_emergency"},
            goal_state_history=[{"primary_goal": "preserve_order"}],
        )
    )
    cards.extend(UnresolvedTensionProjector().project([{"summary": "order versus loyalty"}]))
    cards.extend(SupervisionProjector().project({"authorization_level": "none"}))

    assert [card.factor_type for card in cards] == [
        "need_pressure",
        "affective_body_state",
        "goal_context",
        "unresolved_tension",
        "supervision",
    ]
    assert all(card.layer == "runtime_state" for card in cards)
    assert cards[2].payload["goal_state_history_count"] == 1


def test_runtime_state_projectors_use_empty_source_refs_for_empty_need_affect_and_goal_inputs() -> None:
    need_card = NeedPressureProjector().project({})[0]
    affect_card = AffectiveBodyStateProjector().project({})[0]
    goal_card = GoalContextProjector().project(current_goal_state={}, goal_state_history=[])[0]

    assert need_card.payload == {}
    assert need_card.source_refs == []
    assert affect_card.payload == {}
    assert affect_card.source_refs == []
    assert goal_card.payload == {
        "current_goal_state": {},
        "goal_state_history_count": 0,
    }
    assert goal_card.source_refs == []


def test_dossier_projection_projector_emits_shadow_cards_without_raw_graphs() -> None:
    projector = DossierProjectionProjector()

    enduring_cards = projector.project_enduring_truth(_dossier_projection())
    memory_cards = projector.project_memory_evidence(_dossier_projection())
    affordance_cards = projector.project_affordances(_dossier_projection())

    assert [card.factor_type for card in enduring_cards] == [
        "identity_context",
        "embodiment_context",
        "authority_context",
        "private_truth_context",
    ]
    assert all(card.layer == "enduring_truth" for card in enduring_cards)
    assert memory_cards[0].factor_type == "relationship_seed_context"
    assert memory_cards[0].payload["candidate_only"] is True
    assert "not_live_relationship_truth" in memory_cards[0].risk_notes
    assert affordance_cards[0].factor_type == "capability_seed_affordance"
    assert affordance_cards[0].payload["candidate_only"] is True
    assert "ability_graph" not in affordance_cards[0].payload
    assert "skill_evaluation" not in affordance_cards[0].payload
