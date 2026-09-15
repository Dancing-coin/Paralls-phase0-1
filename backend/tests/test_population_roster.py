from __future__ import annotations

import json

import pytest

from app.population_continuity.roster import load_population_roster


SAMPLE_ACTOR_IDS = load_population_roster().actor_ids


def test_population_roster_has_twelve_residents_with_three_full_agent_profiles() -> None:
    assert len(SAMPLE_ACTOR_IDS) == 12
    assert SAMPLE_ACTOR_IDS[:3] == ("char_a", "char_b", "char_c")
    assert len(set(SAMPLE_ACTOR_IDS)) == 12


def test_configured_roster_is_not_limited_to_the_sample_population(tmp_path, monkeypatch):
    from app.population_continuity.roster import load_population_roster

    actors = [f"story-resident-{index}@1" for index in range(17)]
    source = tmp_path / "roster.json"
    source.write_text(json.dumps({"actor_ids": actors}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert load_population_roster(source).actor_ids == tuple(actors)
    assert len(load_population_roster("backend/assets/population/default_roster.json").actor_ids) == 12


@pytest.mark.parametrize("actors", [[], ["one", "one"], [""], [" one"],
                                   ["character:one"], ["../one"], ["a/b"], [12],
                                   ["Alice", "alice"], ["actor_privateer"],
                                   ["my_private"], ["treebranch"]])
def test_invalid_population_roster_is_rejected(actors):
    from app.population_continuity.roster import PopulationRoster

    with pytest.raises(ValueError):
        PopulationRoster(actor_ids=actors)


def test_bad_roster_file_does_not_fall_back_to_sample(tmp_path):
    from app.population_continuity.roster import load_population_roster

    with pytest.raises(FileNotFoundError):
        load_population_roster(tmp_path / "missing.json")
    source = tmp_path / "draft.json"
    source.write_text('{"status":"draft","actor_ids":["one"]}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_population_roster(source)


def test_versioned_script_actor_references_keep_the_scope_boundary():
    from app.services.siming_population_capability import PopulationSimulationCapability

    admitted = PopulationSimulationCapability._payload_scope_admitted
    assert admitted("character:guardian@1", actor_ref="character:guardian@1")
    assert not admitted("character:guardian@2", actor_ref="character:guardian@1")
    assert not admitted("character:heir@1", actor_ref="character:guardian@1")
