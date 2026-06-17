from app.character_agent.planning.triple_filter import CharacterTripleFilter


def test_triple_filter_maps_candidates_into_auditable_viability_levels() -> None:
    engine = CharacterTripleFilter()

    result = engine.evaluate_candidate(
        candidate="observe",
        persona_ok=True,
        logic_ok=True,
        gain_loss_score=0.8,
    )

    assert result["candidate"] == "observe"
    assert result["persona_passed"] is True
    assert result["logic_passed"] is True
    assert result["gain_loss_score"] == 0.8
    assert result["viability"] == "highly_compelling"


def test_triple_filter_rejects_persona_or_logic_failures() -> None:
    engine = CharacterTripleFilter()

    persona_fail = engine.evaluate_candidate(
        candidate="lie",
        persona_ok=False,
        logic_ok=True,
        gain_loss_score=0.9,
    )
    logic_fail = engine.evaluate_candidate(
        candidate="inspect_object",
        persona_ok=True,
        logic_ok=False,
        gain_loss_score=0.6,
    )

    assert persona_fail["viability"] == "rejected"
    assert logic_fail["viability"] == "rejected"
