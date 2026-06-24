from app.character_agent.gateway.context_builder import CharacterContextBuilder


def test_context_builder_combines_snapshot_memory_and_control_mode() -> None:
    builder = CharacterContextBuilder()

    context = builder.build_context(
        actor_id="char_a",
        snapshot={
            "visible_entities": ["visual_fact/fixed_gaze_on_target"],
            "clarity_score": 1.0,
        },
        profile={
            "identity_core": {
                "character_id": "char_a",
                "canonical_name": "Lin Yue",
                "aliases": [],
                "occupation_role": "mediator",
            }
        },
        memory_bundle={
            "working_memory": [{"event_id": "evt:1"}],
            "event_memories": [{"summary": "char_a spoke nearby"}],
            "observation_memories": [{"observation_summary": "char_a spoke nearby"}],
            "knowledge_memories": [{"proposition_key": "social:char_a:trust_level", "proposition": "char_a:trust_level=guarded"}],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.25}],
        },
        control_mode="player_priority_assisted",
    )

    assert context["actor_id"] == "char_a"
    assert context["control_mode"] == "player_priority_assisted"
    assert context["profile"]["identity_core"]["character_id"] == "char_a"
    assert context["profile"]["identity_core"]["canonical_name"] == "Lin Yue"
    assert context["profile"]["identity_core"]["occupation_role"] == "mediator"
    assert context["snapshot"]["visible_entities"] == ["visual_fact/fixed_gaze_on_target"]
    assert context["memory"]["working_memory"][0]["event_id"] == "evt:1"
    assert context["memory"]["event_memories"][0]["summary"] == "char_a spoke nearby"
    assert context["memory"]["observation_memories"][0]["observation_summary"] == "char_a spoke nearby"
    assert context["memory"]["knowledge_memories"][0]["proposition_key"] == "social:char_a:trust_level"
    assert context["memory"]["social_memories"][0]["entity_id"] == "char_a"


def test_context_builder_can_include_optional_working_memory_state_while_normalizing_legacy_memory_aliases() -> None:
    builder = CharacterContextBuilder()

    context = builder.build_context(
        actor_id="char_c",
        snapshot={"audible_entities": ["auditory_fact/speaker_active"]},
        memory_bundle={
            "working_memory": [{"event_id": "evt:2"}],
            "episodic_memories": [{"summary": "char_b spoke nearby"}],
            "relational_memories": [{"entity_id": "char_b", "belief_type": "trust_level", "value": "guarded"}],
        },
        control_mode="player_priority_assisted",
        working_memory_state={
            "recent_perceived_events": [{"event_type": "character_perceived_event"}],
            "recent_esm_results": [],
            "recent_siming_catalysts": [],
            "private_snapshot": {"actor_id": "char_c"},
        },
    )

    assert context["memory"]["working_memory"][0]["event_id"] == "evt:2"
    assert context["memory"]["event_memories"][0]["summary"] == "char_b spoke nearby"
    assert context["memory"]["knowledge_memories"][0]["proposition_key"] == "social:char_b:trust_level"
    assert context["working_memory_state"]["recent_perceived_events"][0]["event_type"] == "character_perceived_event"
    assert context["working_memory_state"]["private_snapshot"]["actor_id"] == "char_c"
