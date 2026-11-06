from __future__ import annotations

import pytest

from app.population_continuity.matter_eligibility import (
    ELIGIBILITY_CHECKS,
    EligibilityEvidence,
    MatterActorSelector,
    MatterEligibility,
)


def _all_evidence(**overrides: bool) -> tuple[EligibilityEvidence, ...]:
    return tuple(
        EligibilityEvidence(
            check=check,
            passed=overrides.get(check, True),
            authority_ref=f"authority:{check}",
        )
        for check in ELIGIBILITY_CHECKS
    )


def test_six_conjunction_terms_are_frozen() -> None:
    assert ELIGIBILITY_CHECKS == (
        "scope_match",
        "role_relevance",
        "location_access",
        "capability_authority",
        "privacy_admission",
        "no_conflicting_lock",
    )


def test_all_six_checks_pass_makes_actor_eligible() -> None:
    result = MatterActorSelector().evaluate(
        actor_ref="character:char_a", matter_ref="matter:supply", evidence=_all_evidence()
    )

    assert result.eligible
    assert result.failed_checks == ()
    assert result.missing_checks == ()


def test_any_single_failed_check_blocks_eligibility() -> None:
    # A conjunction, not a score: one failure is disqualifying.
    for check in ELIGIBILITY_CHECKS:
        result = MatterActorSelector().evaluate(
            actor_ref="character:char_a",
            matter_ref="matter:supply",
            evidence=_all_evidence(**{check: False}),
        )
        assert not result.eligible
        assert result.failed_checks == (check,)


def test_missing_evidence_is_not_permission() -> None:
    # This is the failure mode that silently grants access nobody approved.
    partial = tuple(
        item for item in _all_evidence() if item.check != "privacy_admission"
    )

    result = MatterActorSelector().evaluate(
        actor_ref="character:char_a", matter_ref="matter:supply", evidence=partial
    )

    assert not result.eligible
    assert result.missing_checks == ("privacy_admission",)
    assert "eligibility_evidence_missing" in result.reason_codes


def test_each_evidence_names_its_authority() -> None:
    with pytest.raises(Exception):
        EligibilityEvidence(check="scope_match", passed=True, authority_ref="")


def test_eligibility_cannot_claim_success_with_a_failure() -> None:
    with pytest.raises(ValueError, match="eligible_with_failed_or_missing_check"):
        MatterEligibility(
            actor_ref="character:char_a",
            matter_ref="matter:1",
            eligible=True,
            failed_checks=("scope_match",),
        )


def test_ineligibility_must_state_a_reason() -> None:
    with pytest.raises(ValueError, match="ineligible_without_failure_reason"):
        MatterEligibility(
            actor_ref="character:char_a", matter_ref="matter:1", eligible=False
        )


def test_ranking_drops_ineligible_actors_entirely() -> None:
    selector = MatterActorSelector()
    blocked = selector.evaluate(
        actor_ref="character:blocked",
        matter_ref="matter:1",
        evidence=_all_evidence(no_conflicting_lock=False),
    )
    allowed = selector.evaluate(
        actor_ref="character:allowed", matter_ref="matter:1", evidence=_all_evidence()
    )

    ranked = selector.rank((blocked, allowed))

    # A near-miss must not be presented as a weak candidate.
    assert [item.actor_ref for item in ranked] == ["character:allowed"]


def test_ranking_prefers_higher_matter_urgency() -> None:
    selector = MatterActorSelector()
    low = selector.evaluate(
        actor_ref="character:a", matter_ref="matter:low", evidence=_all_evidence()
    )
    high = selector.evaluate(
        actor_ref="character:b", matter_ref="matter:high", evidence=_all_evidence()
    )

    ranked = selector.rank(
        (low, high), matter_urgency={"matter:low": 0.1, "matter:high": 0.9}
    )

    assert [item.matter_ref for item in ranked] == ["matter:high", "matter:low"]


def test_ranking_uses_fairness_credit_as_tiebreak() -> None:
    selector = MatterActorSelector()
    first = selector.evaluate(
        actor_ref="character:a", matter_ref="matter:1", evidence=_all_evidence()
    )
    second = selector.evaluate(
        actor_ref="character:b", matter_ref="matter:1", evidence=_all_evidence()
    )

    ranked = selector.rank((first, second), fairness_credit={"character:b": 0.8})

    assert [item.actor_ref for item in ranked] == ["character:b", "character:a"]


def test_ranking_is_order_independent() -> None:
    selector = MatterActorSelector()
    a = selector.evaluate(
        actor_ref="character:a", matter_ref="matter:1", evidence=_all_evidence()
    )
    b = selector.evaluate(
        actor_ref="character:b", matter_ref="matter:1", evidence=_all_evidence()
    )

    assert [i.actor_ref for i in selector.rank((a, b))] == [
        i.actor_ref for i in selector.rank((b, a))
    ]


def test_ranking_with_no_eligible_actor_is_empty() -> None:
    selector = MatterActorSelector()
    blocked = selector.evaluate(
        actor_ref="character:a",
        matter_ref="matter:1",
        evidence=_all_evidence(privacy_admission=False),
    )

    assert selector.rank((blocked,)) == ()
