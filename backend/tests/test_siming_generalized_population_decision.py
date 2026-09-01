from app.population_continuity.vertical import GeneralizedPopulationDecisionFixture


def test_multiple_valid_selections_are_accepted_without_authority_bypass() -> None:
    fixture = GeneralizedPopulationDecisionFixture.create()
    owner_first = fixture.run_scenario("competing_candidates")
    player_first = fixture.run_scenario("player_proximity")
    assert owner_first["status"] == "accepted"
    assert player_first["status"] == "accepted"
    assert owner_first["selected"] != player_first["selected"]
    assert owner_first["owner_refs"] == ["character:char_a"]
    assert player_first["owner_refs"] == []


def test_all_adversarial_scenarios_are_zero_write() -> None:
    fixture = GeneralizedPopulationDecisionFixture.create()
    for name in ("stale_receipt", "owner_rejection", "budget_exhaustion"):
        result = fixture.run_scenario(name)
        assert result["zero_write"] is True


def test_fixed_input_replays_identically_and_fixture_is_not_generic_contract() -> None:
    fixture = GeneralizedPopulationDecisionFixture.create()
    first = fixture.run_scenario("competing_candidates")
    replay = fixture.replay_scenario("competing_candidates")
    assert first["decision_digest"] == replay["decision_digest"]
    assert first["uses_actor_specific_fixture"] is False
