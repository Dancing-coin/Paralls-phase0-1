from app.character_agent.gateway.context_builder import CharacterContextBuilder


def test_context_builder_combines_snapshot_memory_and_control_mode() -> None:
    builder = CharacterContextBuilder()

    context = builder.build_context(
        actor_id="char_c",
        snapshot={
            "visible_entities": ["visual_fact/fixed_gaze_on_target"],
            "clarity_score": 1.0,
        },
        memory_bundle={
            "working_memory": [{"event_id": "evt:1"}],
            "episodic_memories": [{"summary": "char_a spoke nearby"}],
            "relational_memories": [{"entity_id": "char_a", "value": "guarded"}],
        },
        control_mode="player_priority_assisted",
    )

    assert context["actor_id"] == "char_c"
    assert context["control_mode"] == "player_priority_assisted"
    assert context["snapshot"]["visible_entities"] == ["visual_fact/fixed_gaze_on_target"]
    assert context["memory"]["working_memory"][0]["event_id"] == "evt:1"
    assert context["memory"]["episodic_memories"][0]["summary"] == "char_a spoke nearby"
    assert context["memory"]["relational_memories"][0]["entity_id"] == "char_a"


def test_context_builder_can_include_optional_working_memory_state_without_breaking_existing_memory_bundle() -> None:
    builder = CharacterContextBuilder()

    context = builder.build_context(
        actor_id="char_c",
        snapshot={"audible_entities": ["auditory_fact/speaker_active"]},
        memory_bundle={
            "working_memory": [{"event_id": "evt:2"}],
            "episodic_memories": [],
            "relational_memories": [],
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
    assert context["working_memory_state"]["recent_perceived_events"][0]["event_type"] == "character_perceived_event"
    assert context["working_memory_state"]["private_snapshot"]["actor_id"] == "char_c"
