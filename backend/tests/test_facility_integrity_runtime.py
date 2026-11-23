from decimal import Decimal

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.pool_runtime import PoolDefinition, PoolError, PoolProjector, PoolThreshold
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority


def _definition() -> PoolDefinition:
    return PoolDefinition(
        fact_type="fact:facility:gate-03:integrity",
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
        thresholds=(PoolThreshold("breach", Decimal("40"), Decimal("45")),),
    )


def test_facility_integrity_owner_commits_damage_and_breach_crossing() -> None:
    store = GameplayEventStore()
    authority = FacilityIntegrityAuthority(store=store, definitions={"gate-03": _definition()})

    initialized = authority.initialize(
        gate_ref="gate-03", command_id="gate:init", idempotency_key="gate:init",
        causation_id="cause:init", correlation_id="corr:gate",
    )
    damaged = authority.apply_delta(
        gate_ref="gate-03", delta=Decimal("-61"), reason_code="damage",
        command_id="gate:damage", idempotency_key="gate:damage", expected_revision=1,
        causation_id="impact:gate", correlation_id="corr:gate",
    )

    assert initialized.committed and damaged.committed
    events = store.read_stream("fact:facility:gate-03:integrity")
    assert [event.event_type for event in events] == [
        "gameplay.pool.initialized",
        "gameplay.pool.adjusted",
        "gameplay.pool.threshold_crossed",
    ]
    assert events[-1].payload == {
        "fact_type": "fact:facility:gate-03:integrity",
        "threshold_ref": "breach",
        "direction": "enter",
        "value": "39",
    }
    assert store.transaction_owns_event(
        transaction_id=events[-1].transaction_id,
        event_id=events[-1].event_id,
        principal_ref="actor_gameplay.construction_production_domain",
    )
    projection = PoolProjector().rebuild(
        events,
        definitions={_definition().fact_type: _definition()},
    )
    assert projection.value == Decimal("39")
    assert projection.active_thresholds == frozenset({"breach"})


def test_facility_integrity_exact_retry_replays_original_commit() -> None:
    store = GameplayEventStore()
    authority = FacilityIntegrityAuthority(store=store, definitions={"gate-03": _definition()})
    authority.initialize(
        gate_ref="gate-03", command_id="gate:init", idempotency_key="gate:init",
        causation_id="cause:init", correlation_id="corr:gate",
    )
    command = {
        "gate_ref": "gate-03", "delta": Decimal("-10"), "reason_code": "damage",
        "idempotency_key": "gate:damage", "expected_revision": 1,
        "causation_id": "impact:gate", "correlation_id": "corr:gate",
    }

    first = authority.apply_delta(command_id="gate:damage", **command)
    retry = authority.apply_delta(command_id="gate:damage", **command)

    assert first.committed and retry.committed
    assert retry.idempotency_status == "duplicate_replayed"
    assert retry.committed_event_ids == first.committed_event_ids
    assert len(store.read_stream("fact:facility:gate-03:integrity")) == 2


def test_facility_integrity_rejects_stale_revision_without_writing() -> None:
    store = GameplayEventStore()
    authority = FacilityIntegrityAuthority(store=store, definitions={"gate-03": _definition()})
    authority.initialize(
        gate_ref="gate-03", command_id="gate:init", idempotency_key="gate:init",
        causation_id="cause:init", correlation_id="corr:gate",
    )

    with pytest.raises(PoolError, match="^revision_conflict$"):
        authority.apply_delta(
            gate_ref="gate-03", delta=Decimal("-10"), reason_code="damage",
            command_id="gate:stale", idempotency_key="gate:stale", expected_revision=0,
            causation_id="impact:gate", correlation_id="corr:gate",
        )

    assert len(store.read_stream("fact:facility:gate-03:integrity")) == 1


def test_facility_integrity_requires_a_breach_threshold() -> None:
    definition = PoolDefinition(
        fact_type="fact:facility:gate-03:integrity",
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
    )

    with pytest.raises(ValueError, match="^facility_integrity_definition_invalid$"):
        FacilityIntegrityAuthority(store=GameplayEventStore(), definitions={"gate-03": definition})
