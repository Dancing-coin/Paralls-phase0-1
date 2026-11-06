from __future__ import annotations

import pytest

from app.population_continuity.driver_arbitration import (
    MECHANISM_DIMENSIONS,
    DriverArbitrator,
    DriverClaim,
    DriverDecision,
)


def _claim(**updates: object) -> DriverClaim:
    values: dict[str, object] = {
        "subject_ref": "character:char_a",
        "dimension": "continuity",
        "driver_ref": "driver:b0_batch",
        "window_start": 100,
        "window_end": 200,
        "scope_ref": "world:bakery",
    }
    values.update(updates)
    return DriverClaim(**values)


def test_four_mechanism_dimensions_are_declared() -> None:
    assert MECHANISM_DIMENSIONS == ("continuity", "local_event", "propagation", "resource")


def test_first_claim_is_granted() -> None:
    decision = DriverArbitrator().request(_claim())

    assert decision.granted
    assert decision.conflicting_driver_ref == ""


def test_second_driver_on_same_window_is_refused() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim())

    decision = arbitrator.request(_claim(driver_ref="driver:b3_agent"))

    assert not decision.granted
    assert decision.conflicting_driver_ref == "driver:b0_batch"
    assert decision.reason == "driver_conflict"


def test_same_driver_refreshing_its_own_claim_is_granted() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim())

    # An idempotent retry must not fight itself.
    decision = arbitrator.request(_claim())

    assert decision.granted


def test_different_dimension_does_not_conflict() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim())

    decision = arbitrator.request(_claim(dimension="resource", driver_ref="driver:inventory"))

    assert decision.granted


def test_different_subject_does_not_conflict() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim())

    decision = arbitrator.request(_claim(subject_ref="character:char_b", driver_ref="driver:other"))

    assert decision.granted


def test_different_scope_does_not_conflict() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim())

    # A branch or another world must not collide on the same ids.
    decision = arbitrator.request(_claim(scope_ref="branch:preview", driver_ref="driver:preview"))

    assert decision.granted


def test_adjacent_windows_do_not_overlap() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim(window_start=100, window_end=200))

    decision = arbitrator.request(
        _claim(window_start=200, window_end=300, driver_ref="driver:next")
    )

    # Half-open intervals: [100,200) and [200,300) are disjoint.
    assert decision.granted


def test_overlapping_partial_window_is_refused() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim(window_start=100, window_end=200))

    decision = arbitrator.request(
        _claim(window_start=150, window_end=250, driver_ref="driver:late")
    )

    assert not decision.granted


def test_release_allows_another_driver_to_take_over() -> None:
    arbitrator = DriverArbitrator()
    claim = _claim()
    arbitrator.request(claim)

    assert arbitrator.release(claim)
    assert arbitrator.request(_claim(driver_ref="driver:b3_agent")).granted


def test_release_of_unheld_claim_reports_false() -> None:
    assert DriverArbitrator().release(_claim()) is False


def test_release_driver_drops_every_claim_it_held() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim())
    arbitrator.request(_claim(dimension="resource"))

    released = arbitrator.release_driver("driver:b0_batch")

    assert released == 2
    assert arbitrator.active_claims() == ()


def test_subject_can_be_advanced_by_only_one_driver_per_dimension() -> None:
    arbitrator = DriverArbitrator()
    arbitrator.request(_claim())
    arbitrator.request(_claim(dimension="resource", driver_ref="driver:inventory"))
    arbitrator.request(_claim(dimension="propagation", driver_ref="driver:spread"))

    drivers = arbitrator.drivers_for("character:char_a")

    # Several dimensions may be driven, but no dimension has two drivers.
    assert drivers == {"driver:b0_batch", "driver:inventory", "driver:spread"}
    assert len(arbitrator.claims_for("character:char_a")) == 3


def test_invalid_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="claim_window_invalid"):
        _claim(window_start=200, window_end=200)


def test_granted_decision_cannot_name_a_conflict() -> None:
    with pytest.raises(ValueError, match="granted_claim_names_a_conflict"):
        DriverDecision(
            granted=True, claim=_claim(), conflicting_driver_ref="driver:other"
        )


def test_refusal_must_state_a_reason() -> None:
    with pytest.raises(ValueError, match="refused_claim_without_reason"):
        DriverDecision(granted=False, claim=_claim())


def test_population_capability_claims_before_settling() -> None:
    from app.services.siming_population_capability import PopulationSimulationCapability

    arbitrator = DriverArbitrator()
    capability = PopulationSimulationCapability(driver_arbitrator=arbitrator)

    granted = capability._claim_driver(
        subject_ref="character:char_a",
        dimension="resource",
        window_start=100,
        window_end=200,
        scope_ref="world:bakery",
    )

    assert granted
    assert arbitrator.drivers_for("character:char_a") == {"driver:population_capability"}
    # An idempotent retry from the same driver is not a second driver.
    assert capability._claim_driver(
        subject_ref="character:char_a",
        dimension="resource",
        window_start=100,
        window_end=200,
        scope_ref="world:bakery",
    )


def test_claim_is_refused_when_another_driver_already_holds_the_window() -> None:
    from app.services.siming_population_capability import PopulationSimulationCapability

    arbitrator = DriverArbitrator()
    arbitrator.request(
        _claim(
            subject_ref="character:char_a",
            dimension="resource",
            driver_ref="driver:b3_agent",
            window_start=100,
            window_end=200,
            scope_ref="world:bakery",
        )
    )
    capability = PopulationSimulationCapability(driver_arbitrator=arbitrator)

    assert not capability._claim_driver(
        subject_ref="character:char_a",
        dimension="resource",
        window_start=100,
        window_end=200,
        scope_ref="world:bakery",
    )


def test_capability_without_arbitrator_keeps_previous_behaviour() -> None:
    from app.services.siming_population_capability import PopulationSimulationCapability

    capability = PopulationSimulationCapability()

    # Callers that have not opted in must not silently lose settlements.
    assert capability._claim_driver(
        subject_ref="character:char_a",
        dimension="resource",
        window_start=100,
        window_end=200,
        scope_ref="world:bakery",
    )
