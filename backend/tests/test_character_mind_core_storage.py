from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.goal_runtime import CharacterGoalStateRecord
from app.character_agent.storage.dynamic_state_store import CharacterDynamicStateStore
from app.character_agent.storage.goal_state_store import CharacterGoalStateStore
from app.character_agent.storage.higher_order_memory_store import CharacterHigherOrderMemoryStore


def test_dynamic_state_store_round_trips_actor_state() -> None:
    store = CharacterDynamicStateStore()

    store.write(
        "char_a",
        {
            "actor_id": "char_a",
            "vigilance_level": 0.7,
            "distraction_level": 0.1,
            "stress_load": 0.4,
            "social_pressure": 0.5,
            "masking_pressure": 0.2,
            "motivation_stack": ["preserve_order"],
        },
    )

    assert store.read("char_a")["vigilance_level"] == 0.7


def test_dynamic_state_store_returns_default_state_for_unknown_actor() -> None:
    store = CharacterDynamicStateStore()

    state = store.read("char_unknown")

    assert state["actor_id"] == "char_unknown"
    assert state["vigilance_level"] == 0.0
    assert state["distraction_level"] == 0.0
    assert state["stress_load"] == 0.0
    assert state["social_pressure"] == 0.0
    assert state["masking_pressure"] == 0.0


def test_dynamic_state_store_merges_partial_updates_without_dropping_existing_fields() -> None:
    store = CharacterDynamicStateStore()
    store.write(
        "char_a",
        {
            "actor_id": "char_a",
            "vigilance_level": 0.7,
            "distraction_level": 0.1,
            "stress_load": 0.4,
            "social_pressure": 0.5,
            "masking_pressure": 0.2,
            "motivation_stack": ["preserve_order"],
        },
    )

    merged = store.merge_delta("char_a", {"social_pressure": 0.8})

    assert merged["vigilance_level"] == 0.7
    assert merged["social_pressure"] == 0.8
    assert merged["motivation_stack"] == ["preserve_order"]


def test_dynamic_state_store_exposes_typed_record_view() -> None:
    store = CharacterDynamicStateStore()
    state = CharacterDynamicState(
        actor_id="char_a",
        vigilance_level=0.7,
        distraction_level=0.1,
        stress_load=0.4,
        social_pressure=0.5,
        masking_pressure=0.2,
        motivation_stack=["preserve_order"],
    )

    store.write("char_a", state.model_dump())

    typed = store.read_record("char_a")

    assert typed is not None
    assert typed.actor_id == "char_a"
    assert typed.vigilance_level == 0.7


def test_higher_order_memory_store_groups_records_by_actor() -> None:
    store = CharacterHigherOrderMemoryStore()

    store.append(
        "char_a",
        {
            "memory_id": "hom:1",
            "actor_id": "char_a",
            "subject_actor_id": "char_b",
            "proposition_key": "obj_letter:is_sensitive",
            "meta_belief": "char_b suspects char_c knows more",
            "confidence": 0.66,
            "source_event_id": "evt:1",
            "producer_ts": 10,
        },
    )

    assert store.recall("char_a")[0]["subject_actor_id"] == "char_b"


def test_goal_state_store_round_trips_active_goal_frame() -> None:
    store = CharacterGoalStateStore()

    store.write(
        "char_a",
        {
            "primary_goal": "protect_secret",
            "long_term_goal": "preserve_order",
            "immediate_goal": "protect_secret",
            "supporting_goals": ["clarify_intent"],
            "blockers": ["high_masking_pressure"],
            "goal_sources": ["dynamic_state", "knowledge_state"],
            "urgency": "high",
        },
    )

    state = store.read("char_a")

    assert state["primary_goal"] == "protect_secret"
    assert state["long_term_goal"] == "preserve_order"
    assert state["urgency"] == "high"


def test_goal_state_store_exposes_previous_state_before_overwrite() -> None:
    store = CharacterGoalStateStore()
    store.write(
        "char_a",
        {
            "primary_goal": "protect_secret",
            "long_term_goal": "preserve_order",
            "immediate_goal": "protect_secret",
            "supporting_goals": ["clarify_intent"],
            "blockers": ["high_masking_pressure"],
            "goal_sources": ["dynamic_state", "knowledge_state"],
            "urgency": "high",
        },
    )

    store.write(
        "char_a",
        {
            "primary_goal": "clarify_intent",
            "long_term_goal": "preserve_order",
            "immediate_goal": "clarify_intent",
            "supporting_goals": ["protect_secret"],
            "blockers": [],
            "goal_sources": ["knowledge_state"],
            "urgency": "medium",
        },
    )
    previous = store.previous("char_a")

    assert previous["primary_goal"] == "protect_secret"
    assert previous["urgency"] == "high"


def test_goal_state_store_keeps_short_history_tail() -> None:
    store = CharacterGoalStateStore()

    store.write("char_a", {"primary_goal": "protect_secret", "urgency": "high"})
    store.write("char_a", {"primary_goal": "clarify_intent", "urgency": "medium"})
    store.write("char_a", {"primary_goal": "stabilize_situation", "urgency": "medium"})

    history = store.history("char_a")

    assert len(history) == 3
    assert history[0]["primary_goal"] == "protect_secret"
    assert history[-1]["primary_goal"] == "stabilize_situation"


def test_goal_state_store_exposes_typed_record_view() -> None:
    store = CharacterGoalStateStore()
    record = CharacterGoalStateRecord(
        actor_id="char_a",
        primary_goal="protect_secret",
        long_term_goal="preserve_order",
        mid_term_strategy="contain_exposure",
        immediate_goal="withhold_until_private",
        supporting_goals=["clarify_intent"],
        blockers=["high_masking_pressure"],
        goal_sources=["dynamic_state", "knowledge_state"],
        urgency="high",
        transition_kind="repairing",
        transition_reason_tags=["strategy_blocked"],
    )

    store.write("char_a", record)

    typed = store.read_record("char_a")

    assert typed is not None
    assert typed.mid_term_strategy == "contain_exposure"
    assert typed.transition_kind == "repairing"
