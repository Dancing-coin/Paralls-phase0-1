from __future__ import annotations

from app.population_continuity.roster import POPULATION_ACTOR_IDS


def test_population_roster_has_twelve_residents_with_three_full_agent_profiles() -> None:
    assert len(POPULATION_ACTOR_IDS) == 12
    assert POPULATION_ACTOR_IDS[:3] == ("char_a", "char_b", "char_c")
    assert len(set(POPULATION_ACTOR_IDS)) == 12

