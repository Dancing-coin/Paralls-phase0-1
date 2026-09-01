import pytest
from pydantic import ValidationError

from app.population_continuity.models import (
    PopulationCohortMember,
    PopulationCohortReport,
)


def test_cohort_member_accepts_only_the_three_closed_dispositions() -> None:
    member = PopulationCohortMember(
        actor_ref="character:char_a",
        disposition="char_a_supply",
        cost=1,
        source_projection_ref="projection:char_a:w0",
    )
    assert member.disposition == "char_a_supply"


def test_unknown_cohort_disposition_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        PopulationCohortMember(
            actor_ref="character:char_a",
            disposition="free_form_social",
            cost=1,
            source_projection_ref="projection:char_a:w0",
        )


def test_cohort_report_preserves_fixed_actor_order_and_budget() -> None:
    report = PopulationCohortReport(
        cohort_ref="cohort:bakery:W0",
        window="W0",
        member_refs=("character:char_a", "character:char_b", "character:char_c"),
        selected_refs=("character:char_a", "character:char_b", "character:char_c"),
        unprocessed_refs=(),
        budget=3,
        selector_revision="selector:cohort-bakery:v1",
        ruleset_revision="rules:cohort-bakery:v1",
    )
    assert report.member_refs == (
        "character:char_a",
        "character:char_b",
        "character:char_c",
    )
    assert report.budget == 3
