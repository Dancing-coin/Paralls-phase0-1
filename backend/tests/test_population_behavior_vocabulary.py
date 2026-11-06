from __future__ import annotations

import pytest

from app.population_continuity.batch import PopulationPlanner
from app.population_continuity.decision_surface import PopulationCapabilityCatalog
from app.population_continuity.seed_planner import CharacterSeedPlanner


def test_cycle_behaviors_are_all_registered_in_the_catalog() -> None:
    registered = PopulationCapabilityCatalog.registered_behavior_kinds()

    # A cycle behavior that has no capability descriptor could never reach an
    # owner, so the catalog must cover every one of them.
    assert PopulationPlanner.CYCLE_BEHAVIORS <= registered
    PopulationPlanner.validate_vocabulary()


def test_report_only_catalog_kinds_stay_out_of_the_cycle_vocabulary() -> None:
    # These are registered capabilities, but the cycle must keep rejecting them:
    # tax pressure is report-only and social signals are owner-bound elsewhere.
    for kind in ("tax_pressure", "social_population_signal", "organization_operating_window_due"):
        assert kind in PopulationCapabilityCatalog.registered_behavior_kinds()
        assert kind not in PopulationPlanner.ADMITTED_BEHAVIORS


def test_seed_vocabulary_matches_the_cycle_vocabulary() -> None:
    assert CharacterSeedPlanner.ADMITTED_BEHAVIORS == PopulationPlanner.ADMITTED_BEHAVIORS


def test_activation_behaviors_are_a_subset_of_admitted() -> None:
    assert PopulationPlanner.ACTIVATION_BEHAVIORS <= PopulationPlanner.ADMITTED_BEHAVIORS


def test_vocabulary_validation_rejects_unregistered_cycle_behavior(monkeypatch) -> None:
    monkeypatch.setattr(
        PopulationPlanner, "CYCLE_BEHAVIORS", frozenset({"not_a_registered_kind"})
    )

    with pytest.raises(ValueError, match="population_cycle_behavior_unregistered"):
        PopulationPlanner.validate_vocabulary()


def test_registered_kinds_are_stable_across_policy_revisions() -> None:
    assert PopulationCapabilityCatalog.registered_behavior_kinds(
        "policy:a"
    ) == PopulationCapabilityCatalog.registered_behavior_kinds("policy:b")
