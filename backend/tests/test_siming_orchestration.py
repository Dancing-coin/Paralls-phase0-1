from __future__ import annotations

import pytest

from app.services.siming_orchestration import (
    AUDITORS,
    AUDITOR_FOR_DIMENSION,
    BUDGET_OVERRUN_ACTION,
    DEFAULT_BUDGETS,
    PATH_FALLBACK_LADDER,
    PRESSURE_DOWNSAMPLED_AUDITORS,
    RUNTIME_PRIORITIES,
    SimingBudgetProfile,
    is_priority_scheduled,
    next_permitted_path,
    retained_priorities,
    select_runtime_mode,
)


def test_five_priority_levels_are_frozen() -> None:
    assert RUNTIME_PRIORITIES == ("P0", "P1", "P2", "P3", "P4")


def test_standard_mode_keeps_every_priority() -> None:
    assert retained_priorities("standard") == frozenset(RUNTIME_PRIORITIES)


def test_survival_mode_keeps_only_the_main_judge_chain() -> None:
    # The contract forbids shedding P0/P1 even under extreme congestion.
    assert retained_priorities("survival") == frozenset({"P0", "P1"})
    assert is_priority_scheduled("P0", "survival")
    assert is_priority_scheduled("P1", "survival")
    assert not is_priority_scheduled("P3", "survival")
    assert not is_priority_scheduled("P4", "survival")


def test_pressure_mode_sheds_enhancement_before_survival_does() -> None:
    assert is_priority_scheduled("P3", "pressure")
    assert not is_priority_scheduled("P4", "pressure")
    assert retained_priorities("survival") < retained_priorities("pressure")


def test_unknown_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown_runtime_mode"):
        retained_priorities("turbo")


def test_degradation_ladder_ends_at_no_action() -> None:
    assert PATH_FALLBACK_LADDER[-1] == "no_action"
    assert next_permitted_path("environment_change_path") == "visual_fact_path"
    assert next_permitted_path("character_input_path") == "no_action"


def test_no_action_is_the_floor() -> None:
    assert next_permitted_path("no_action") == "no_action"


def test_unknown_path_degrades_to_no_action_not_to_a_stronger_path() -> None:
    # An unrecognised path must never climb the ladder toward more force.
    assert next_permitted_path("made_up_path") == "no_action"


def test_five_auditors_are_independent() -> None:
    assert len(AUDITORS) == 5
    # Conversation access must not be folded into participation.
    assert "conversation_access_auditor" in AUDITORS
    assert AUDITOR_FOR_DIMENSION["conversation_access_fairness"] == "conversation_access_auditor"
    assert AUDITOR_FOR_DIMENSION["participation_distribution"] == "participation_auditor"


def test_every_fairness_dimension_maps_to_a_declared_auditor() -> None:
    assert set(AUDITOR_FOR_DIMENSION.values()) == set(AUDITORS)
    assert len(AUDITOR_FOR_DIMENSION) == 5


def test_only_suspicion_may_be_downsampled_under_pressure() -> None:
    assert PRESSURE_DOWNSAMPLED_AUDITORS == frozenset({"suspicion_auditor"})
    assert PRESSURE_DOWNSAMPLED_AUDITORS < set(AUDITORS)


def test_seven_budget_names_are_frozen() -> None:
    assert set(DEFAULT_BUDGETS) == {
        "tick_interval_ms",
        "max_event_window_age_ms",
        "auditor_fanout_budget_ms",
        "decision_budget_ms",
        "dispatch_deadline_ms",
        "ack_timeout_ms",
        "audit_persist_budget_ms",
    }
    assert len(DEFAULT_BUDGETS) == 7


def test_budget_defaults_match_the_frozen_contract() -> None:
    assert DEFAULT_BUDGETS["tick_interval_ms"] == 1000
    assert DEFAULT_BUDGETS["max_event_window_age_ms"] == 3000
    assert DEFAULT_BUDGETS["auditor_fanout_budget_ms"] == 300
    assert DEFAULT_BUDGETS["decision_budget_ms"] == 200
    assert DEFAULT_BUDGETS["dispatch_deadline_ms"] == 500
    assert DEFAULT_BUDGETS["ack_timeout_ms"] == 5000
    assert DEFAULT_BUDGETS["audit_persist_budget_ms"] == 1000


def test_every_budget_has_a_declared_overrun_action() -> None:
    # An overrun without a declared reaction invites a later reader to guess.
    assert set(BUDGET_OVERRUN_ACTION) == set(DEFAULT_BUDGETS)


def test_budget_profile_defaults_match_the_dict() -> None:
    assert SimingBudgetProfile.default().as_dict() == DEFAULT_BUDGETS


def test_budget_profile_keeps_names_but_allows_value_override() -> None:
    tightened = SimingBudgetProfile(tick_interval_ms=250)

    assert tightened.tick_interval_ms == 250
    assert tightened.as_dict()["ack_timeout_ms"] == 5000
    assert set(tightened.as_dict()) == set(DEFAULT_BUDGETS)


def test_negative_budget_is_rejected() -> None:
    with pytest.raises(Exception):
        SimingBudgetProfile(decision_budget_ms=-1)


def test_mode_selection_orders_survival_above_pressure() -> None:
    assert select_runtime_mode(queued_events=0, pressure_threshold=10, survival_threshold=50) == "standard"
    assert select_runtime_mode(queued_events=10, pressure_threshold=10, survival_threshold=50) == "pressure"
    assert select_runtime_mode(queued_events=50, pressure_threshold=10, survival_threshold=50) == "survival"


def test_mode_selection_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError, match="survival_threshold_below_pressure_threshold"):
        select_runtime_mode(queued_events=0, pressure_threshold=50, survival_threshold=10)
