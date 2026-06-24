from app.character_agent.models.knowledge_state import KnowledgeState


def test_knowledge_state_exposes_full_stage2_state_set() -> None:
    assert KnowledgeState.NOTICED.value == "noticed"
    assert KnowledgeState.HIGH_CONFIDENCE_BELIEVED.value == "high_confidence_believed"
    assert [state.value for state in KnowledgeState] == [
        "noticed",
        "suspected",
        "tentatively_believed",
        "believed",
        "high_confidence_believed",
        "disputed",
        "abandoned",
    ]
