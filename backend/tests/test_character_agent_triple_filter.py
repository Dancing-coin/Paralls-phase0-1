from app.character_agent.planning.triple_filter import CharacterTripleFilter


def test_triple_filter_maps_candidates_into_auditable_viability_levels() -> None:
    engine = CharacterTripleFilter()

    result = engine.evaluate_candidate(
        candidate="observe",
        persona_ok=True,
        logic_ok=True,
        gain_loss_score=0.8,
        persona_notes=["fits duty-first stance"],
        logic_notes=["attention target is present"],
        gain_loss_notes=["low exposure cost"],
    )

    assert result["candidate"] == "observe"
    assert result["persona_passed"] is True
    assert result["logic_passed"] is True
    assert result["gain_loss_score"] == 0.8
    assert result["persona_notes"] == ["fits duty-first stance"]
    assert result["logic_notes"] == ["attention target is present"]
    assert result["gain_loss_notes"] == ["low exposure cost"]
    assert result["viability"] == "highly_compelling"


def test_triple_filter_rejects_persona_or_logic_failures() -> None:
    engine = CharacterTripleFilter()

    persona_fail = engine.evaluate_candidate(
        candidate="lie",
        persona_ok=False,
        logic_ok=True,
        gain_loss_score=0.9,
        persona_notes=["forbidden by profile"],
        logic_notes=[],
        gain_loss_notes=[],
    )
    logic_fail = engine.evaluate_candidate(
        candidate="inspect_object",
        persona_ok=True,
        logic_ok=False,
        gain_loss_score=0.6,
        persona_notes=[],
        logic_notes=["no inspectable object in focus"],
        gain_loss_notes=[],
    )

    assert persona_fail["viability"] == "rejected"
    assert persona_fail["persona_notes"] == ["forbidden by profile"]
    assert logic_fail["viability"] == "rejected"
    assert logic_fail["logic_notes"] == ["no inspectable object in focus"]
