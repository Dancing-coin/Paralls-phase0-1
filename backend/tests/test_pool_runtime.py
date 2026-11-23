from decimal import Decimal

import pytest

from app.gameplay.event_schema_registry import (
    EventSchemaRegistry,
    create_stormnight_event_schema_registry,
    gameplay_schema_event_types,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.pool_event_schema import register_pool_event_schemas
from app.gameplay.pool_runtime import (
    PoolAuthorityService,
    PoolDefinition,
    PoolError,
    PoolProjector,
    PoolThreshold,
    aggregate_pool_values,
)


FACT_TYPE = "fact:character:char-pool:stamina"
PRINCIPAL = "owner:body"


def service_with_pool(*, initial: str = "50"):
    store = GameplayEventStore()
    service = PoolAuthorityService(store=store, owner_ref=PRINCIPAL)
    definition = PoolDefinition(
        fact_type=FACT_TYPE,
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal(initial),
        rate_per_tick=Decimal("-0.5"),
        thresholds=(
            PoolThreshold(
                threshold_ref="exhausted",
                enter_below=Decimal("30"),
                exit_above=Decimal("35"),
            ),
        ),
    )
    service.initialize(
        definition=definition,
        command_id="pool:init",
        idempotency_key="pool:init",
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )
    return store, service, definition


def test_pool_bounds_reservation_and_consume_are_atomic_and_rebuildable():
    store, service, definition = service_with_pool()
    reserved = service.reserve(
        fact_type=FACT_TYPE,
        reservation_ref="reservation:pool:1",
        amount=Decimal("30"),
        holder_ref="character:char-pool",
        purpose_code="action_cost",
        command_id="pool:reserve",
        idempotency_key="pool:reserve",
        expected_revision=1,
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )
    assert reserved.committed

    consumed = service.consume(
        fact_type=FACT_TYPE,
        reservation_ref="reservation:pool:1",
        actual=Decimal("20"),
        reason_code="action_cost",
        command_id="pool:consume",
        idempotency_key="pool:consume",
        expected_revision=2,
        causation_id=reserved.committed_event_ids[0],
        correlation_id="corr:pool",
    )
    assert consumed.committed

    projection = PoolProjector().rebuild(
        store.read_stream(FACT_TYPE), definitions={FACT_TYPE: definition}
    )
    assert projection.value == Decimal("30")
    assert projection.reserved == Decimal("0")
    assert projection.available == Decimal("30")
    assert projection.reservations == {}

    restored = GameplayEventStore.from_snapshot(store.export_snapshot())
    rebuilt = PoolProjector().rebuild(
        restored.read_stream(FACT_TYPE), definitions={FACT_TYPE: definition}
    )
    assert rebuilt == projection


def test_pool_commits_persist_owner_fragment_contract_and_ordered_operations():
    store, service, _ = service_with_pool()
    initialization = store.get_transaction("tx:pool:init")

    assert initialization is not None
    fragment = initialization.owner_fragments[0]
    assert fragment.owner_principal_ref == PRINCIPAL
    assert fragment.source_rule_ref == "pool-runtime:owner-command@1"
    assert fragment.expected_revisions == {FACT_TYPE: 0}
    assert fragment.read_set_revisions == {FACT_TYPE: 0}
    assert fragment.pinned_revisions == {FACT_TYPE: 0}
    assert fragment.event_specs[FACT_TYPE] == (("gameplay.pool.initialized", {
        "fact_type": FACT_TYPE,
        "initial": "50",
        "bound_lower": "0",
        "bound_upper": "100",
    }),)

    adjusted = service.adjust(
        fact_type=FACT_TYPE,
        delta=Decimal("-25"),
        reason_code="damage",
        command_id="pool:adjust-crossing",
        idempotency_key="pool:adjust-crossing",
        expected_revision=1,
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )
    assert adjusted.committed

    transaction = store.get_transaction("tx:pool:adjust-crossing")
    assert transaction is not None
    operation_types = tuple(
        event_type
        for events in transaction.owner_fragments[0].event_specs.values()
        for event_type, _ in events
    )
    assert operation_types == (
        "gameplay.pool.adjusted",
        "gameplay.pool.threshold_crossed",
    )


def test_pool_rejections_leave_event_stream_unchanged():
    store, service, _ = service_with_pool()
    before = store.export_snapshot()

    with pytest.raises(PoolError, match="^pool_upper_bound_exceeded$"):
        service.adjust(
            fact_type=FACT_TYPE,
            delta=Decimal("51"),
            reason_code="heal",
            command_id="pool:overfill",
            idempotency_key="pool:overfill",
            expected_revision=1,
            causation_id="evt:seed",
            correlation_id="corr:pool",
        )
    assert store.export_snapshot() == before

    with pytest.raises(PoolError, match="^pool_insufficient_available$"):
        service.reserve(
            fact_type=FACT_TYPE,
            reservation_ref="reservation:too-large",
            amount=Decimal("51"),
            holder_ref="character:char-pool",
            purpose_code="action_cost",
            command_id="pool:reserve-too-large",
            idempotency_key="pool:reserve-too-large",
            expected_revision=1,
            causation_id="evt:seed",
            correlation_id="corr:pool",
        )
    assert store.export_snapshot() == before

    with pytest.raises(PoolError, match="^pool_lower_bound_exceeded$"):
        service.adjust(
            fact_type=FACT_TYPE,
            delta=Decimal("-51"),
            reason_code="damage",
            command_id="pool:underflow",
            idempotency_key="pool:underflow",
            expected_revision=1,
            causation_id="evt:seed",
            correlation_id="corr:pool",
        )
    assert store.export_snapshot() == before


def test_pool_window_adjustment_rejects_duplicate_and_exact_retry_replays():
    store, service, _ = service_with_pool()
    args = {
        "fact_type": FACT_TYPE,
        "delta": Decimal("-5"),
        "reason_code": "integrate",
        "window_ref": "window:pool:1",
        "command_id": "pool:window:1",
        "idempotency_key": "pool:window:1",
        "expected_revision": 1,
        "causation_id": "evt:seed",
        "correlation_id": "corr:pool",
    }
    first = service.adjust(**args)
    assert first.committed
    assert service.adjust(**args).idempotency_status == "duplicate_replayed"
    before_duplicate_window = store.export_snapshot()

    with pytest.raises(PoolError, match="^pool_window_already_integrated$"):
        service.adjust(
            **(args | {
                "command_id": "pool:window:retry",
                "idempotency_key": "pool:window:retry",
                "expected_revision": 2,
            })
        )
    assert store.export_snapshot() == before_duplicate_window
    assert PoolProjector().rebuild(store.read_stream(FACT_TYPE)).value == Decimal("45")


def test_pool_hysteresis_records_only_enter_and_exit_crossings():
    store, service, definition = service_with_pool(initial="50")
    commands = ((-25, "w1"), (7, "w2"), (-4, "w3"), (5, "w4"), (5, "w5"))
    revision = 1
    for index, (delta, window_ref) in enumerate(commands, start=1):
        result = service.adjust(
            fact_type=FACT_TYPE,
            delta=Decimal(delta),
            reason_code="damage" if delta < 0 else "heal",
            window_ref=f"window:{window_ref}",
            command_id=f"pool:hysteresis:{index}",
            idempotency_key=f"pool:hysteresis:{index}",
            expected_revision=revision,
            causation_id="evt:seed",
            correlation_id="corr:pool",
        )
        assert result.committed
        revision = result.resulting_stream_revisions[FACT_TYPE]

    events = store.read_stream(FACT_TYPE)
    crossings = [event.payload for event in events if event.event_type == "gameplay.pool.threshold_crossed"]
    assert [(event["direction"], event["value"]) for event in crossings] == [
        ("enter", "25"),
        ("exit", "38"),
    ]
    projection = PoolProjector().rebuild(events, definitions={FACT_TYPE: definition})
    assert projection.active_thresholds == frozenset()
    assert projection.value == Decimal("38")


def test_pool_rate_integrates_once_per_window_from_its_definition():
    store, service, definition = service_with_pool()
    args = {
        "fact_type": FACT_TYPE,
        "ticks": 10,
        "window_ref": "window:pool:rate-1",
        "command_id": "pool:integrate:1",
        "idempotency_key": "pool:integrate:1",
        "expected_revision": 1,
        "causation_id": "evt:seed",
        "correlation_id": "corr:pool",
    }
    first = service.integrate(**args)
    assert first.committed
    assert service.integrate(**args).idempotency_status == "duplicate_replayed"
    with pytest.raises(PoolError, match="^pool_window_already_integrated$"):
        service.integrate(**(args | {
            "command_id": "pool:integrate:retry",
            "idempotency_key": "pool:integrate:retry",
            "expected_revision": 2,
        }))
    projection = PoolProjector().rebuild(
        store.read_stream(FACT_TYPE), definitions={FACT_TYPE: definition}
    )
    assert projection.value == Decimal("45")


def test_pool_failed_consume_and_bound_change_write_nothing_then_release_succeeds():
    store, service, definition = service_with_pool()
    reservation = service.reserve(
        fact_type=FACT_TYPE,
        reservation_ref="reservation:release:1",
        amount=Decimal("10"),
        holder_ref="character:char-pool",
        purpose_code="action_cost",
        command_id="pool:reserve-release",
        idempotency_key="pool:reserve-release",
        expected_revision=1,
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )
    assert reservation.committed
    before_reject = store.export_snapshot()

    with pytest.raises(PoolError, match="^pool_consume_exceeds_reservation$"):
        service.consume(
            fact_type=FACT_TYPE,
            reservation_ref="reservation:release:1",
            actual=Decimal("11"),
            reason_code="action_cost",
            command_id="pool:consume-excess",
            idempotency_key="pool:consume-excess",
            expected_revision=2,
            causation_id=reservation.committed_event_ids[0],
            correlation_id="corr:pool",
        )
    assert store.export_snapshot() == before_reject

    with pytest.raises(PoolError, match="^pool_bound_change_invalid$"):
        service.set_bound(
            fact_type=FACT_TYPE,
            new_lower=Decimal("0"),
            new_upper=Decimal("49"),
            authority_ref="authority:pool",
            command_id="pool:bound-invalid",
            idempotency_key="pool:bound-invalid",
            expected_revision=2,
            causation_id="evt:seed",
            correlation_id="corr:pool",
        )
    assert store.export_snapshot() == before_reject

    released = service.release(
        fact_type=FACT_TYPE,
        reservation_ref="reservation:release:1",
        command_id="pool:release",
        idempotency_key="pool:release",
        expected_revision=2,
        causation_id=reservation.committed_event_ids[0],
        correlation_id="corr:pool",
        reason_code="cancelled",
    )
    assert released.committed
    projection = PoolProjector().rebuild(
        store.read_stream(FACT_TYPE), definitions={FACT_TYPE: definition}
    )
    assert projection.reserved == Decimal("0")
    assert projection.available == Decimal("50")


def test_pool_adjust_cannot_reduce_value_below_existing_reservations():
    store, service, definition = service_with_pool()
    reserved = service.reserve(
        fact_type=FACT_TYPE,
        reservation_ref="reservation:pool:invariant",
        amount=Decimal("20"),
        holder_ref="character:char-pool",
        purpose_code="action_cost",
        command_id="pool:reserve-invariant",
        idempotency_key="pool:reserve-invariant",
        expected_revision=1,
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )
    assert reserved.committed
    before = store.export_snapshot()

    with pytest.raises(PoolError, match="^pool_insufficient_available$"):
        service.adjust(
            fact_type=FACT_TYPE,
            delta=Decimal("-31"),
            reason_code="damage",
            command_id="pool:adjust-reservation-conflict",
            idempotency_key="pool:adjust-reservation-conflict",
            expected_revision=2,
            causation_id=reserved.committed_event_ids[0],
            correlation_id="corr:pool",
        )
    assert store.export_snapshot() == before
    assert PoolProjector().rebuild(
        store.read_stream(FACT_TYPE), definitions={FACT_TYPE: definition}
    ).available == Decimal("30")


def test_pool_aggregation_modes_keep_their_declared_semantics():
    values = (("fact:pool:first", Decimal("80")), ("fact:pool:second", Decimal("60")))

    def definition(mode):
        return PoolDefinition(
            fact_type=FACT_TYPE,
            lower=Decimal("0"),
            upper=Decimal("100"),
            initial=Decimal("50"),
            aggregation_mode=mode,
            refold_model_ref="morale_refold@1" if mode == "distribution" else None,
        )

    assert aggregate_pool_values(values, definition=definition("none")) == dict(values)
    assert aggregate_pool_values(values, definition=definition("sum")) == Decimal("140")
    assert aggregate_pool_values(values, definition=definition("ordered")) == values


def test_pool_distribution_recomputes_through_refold_with_frozen_revisions():
    values = (("fact:pool:first", Decimal("12")), ("fact:pool:second", Decimal("8")))
    definition = PoolDefinition(
        fact_type=FACT_TYPE,
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("50"),
        aggregation_mode="distribution",
        refold_model_ref="morale_refold@1",
    )
    calls = []

    def refold(model_ref, members, trigger, input_revision_vector):
        calls.append((model_ref, members, trigger, dict(input_revision_vector)))
        return Decimal("11")

    first = aggregate_pool_values(
        values,
        definition=definition,
        refold=refold,
        trigger="merge",
        input_revision_vector={"fact:pool:first": 3, "fact:pool:second": 5},
    )
    second = aggregate_pool_values(
        values,
        definition=definition,
        refold=refold,
        trigger="merge",
        input_revision_vector={"fact:pool:first": 3, "fact:pool:second": 5},
    )

    assert first == second == Decimal("11")
    assert calls == [
        ("morale_refold@1", values, "merge", {"fact:pool:first": 3, "fact:pool:second": 5}),
        ("morale_refold@1", values, "merge", {"fact:pool:first": 3, "fact:pool:second": 5}),
    ]


def test_pool_distribution_recomputes_after_casualty_with_frozen_revisions():
    values = (("fact:unit:gate-east:morale", Decimal("100")),)
    definition = PoolDefinition(
        fact_type=FACT_TYPE,
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
        aggregation_mode="distribution",
        refold_model_ref="morale_refold@1",
    )
    calls = []

    def refold(model_ref, members, trigger, input_revision_vector):
        calls.append((model_ref, members, trigger, dict(input_revision_vector)))
        return Decimal("75")

    result = aggregate_pool_values(
        values,
        definition=definition,
        refold=refold,
        trigger="casualty",
        input_revision_vector={"fact:unit:gate-east:morale": 2},
    )

    assert result == Decimal("75")
    assert calls == [
        ("morale_refold@1", values, "casualty", {"fact:unit:gate-east:morale": 2}),
    ]


def test_pool_model_adjustment_persists_and_checks_its_input_revision_vector():
    store, service, _ = service_with_pool()
    input_fact_type = "fact:unit:gate-east:morale-input"
    result = service.adjust(
        fact_type=FACT_TYPE,
        delta=Decimal("-5"),
        reason_code="integrate",
        model_ref="morale_refold@1",
        input_revision_vector={input_fact_type: 0},
        command_id="pool:model-adjust",
        idempotency_key="pool:model-adjust",
        expected_revision=1,
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )

    assert result.committed
    transaction = store.get_transaction("tx:pool:model-adjust")
    assert transaction is not None
    fragment = transaction.owner_fragments[0]
    expected_inputs = {FACT_TYPE: 1, input_fact_type: 0}
    assert fragment.read_set_revisions == expected_inputs
    assert fragment.pinned_revisions == expected_inputs
    assert fragment.event_specs[FACT_TYPE][0][1]["model_ref"] == "morale_refold@1"

    before = store.export_snapshot()
    with pytest.raises(PoolError, match="^revision_conflict$"):
        service.adjust(
            fact_type=FACT_TYPE,
            delta=Decimal("-1"),
            reason_code="integrate",
            model_ref="morale_refold@1",
            input_revision_vector={input_fact_type: 1},
            command_id="pool:model-adjust-stale",
            idempotency_key="pool:model-adjust-stale",
            expected_revision=2,
            causation_id="evt:seed",
            correlation_id="corr:pool",
        )
    assert store.export_snapshot() == before


def test_pool_adjustment_can_pin_non_model_aggregation_inputs():
    store, service, _ = service_with_pool()
    input_fact_type = "fact:pool:ammunition:source"

    result = service.adjust(
        fact_type=FACT_TYPE,
        delta=Decimal("5"),
        reason_code="grant",
        input_revision_vector={input_fact_type: 0},
        command_id="pool:sum-adjust",
        idempotency_key="pool:sum-adjust",
        expected_revision=1,
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )

    assert result.committed
    transaction = store.get_transaction("tx:pool:sum-adjust")
    assert transaction is not None
    fragment = transaction.owner_fragments[0]
    assert fragment.read_set_revisions == {FACT_TYPE: 1, input_fact_type: 0}
    assert fragment.pinned_revisions == {FACT_TYPE: 1, input_fact_type: 0}


def test_pool_distribution_rejects_missing_refold_inputs():
    with pytest.raises(PoolError, match="^pool_refold_model_required$"):
        PoolDefinition(
            fact_type=FACT_TYPE,
            lower=Decimal("0"),
            upper=Decimal("100"),
            initial=Decimal("50"),
            aggregation_mode="distribution",
        )


def test_pool_rejects_invalid_aggregation_and_owner_fragment_inputs():
    with pytest.raises(PoolError, match="^pool_aggregation_mode_invalid$"):
        PoolDefinition(
            fact_type=FACT_TYPE,
            lower=Decimal("0"),
            upper=Decimal("100"),
            initial=Decimal("50"),
            aggregation_mode=[],
        )

    with pytest.raises(PoolError, match="^pool_owner_ref_invalid$"):
        PoolAuthorityService(store=GameplayEventStore(), owner_ref=object())

    _, service, _ = service_with_pool()
    with pytest.raises(PoolError, match="^pool_model_revision_vector_invalid$"):
        service.adjust(
            fact_type=FACT_TYPE,
            delta=Decimal("1"),
            reason_code="grant",
            input_revision_vector=[("fact:pool:source", 0)],
            command_id="pool:bad-input-vector",
            idempotency_key="pool:bad-input-vector",
            expected_revision=1,
            causation_id="evt:seed",
            correlation_id="corr:pool",
        )


def test_pool_events_are_visible_to_gameplay_graph_registry():
    event_types = set(gameplay_schema_event_types())
    assert {
        "gameplay.pool.initialized",
        "gameplay.pool.adjusted",
        "gameplay.pool.reserved",
        "gameplay.pool.released",
        "gameplay.pool.consumed",
        "gameplay.pool.bound_changed",
        "gameplay.pool.threshold_crossed",
    } <= event_types

    registry = EventSchemaRegistry()
    register_pool_event_schemas(registry)
    assert {
        (event_type, 1)
        for event_type in event_types
        if event_type.startswith("gameplay.pool.")
    } == {
        ("gameplay.pool.initialized", 1),
        ("gameplay.pool.adjusted", 1),
        ("gameplay.pool.reserved", 1),
        ("gameplay.pool.released", 1),
        ("gameplay.pool.consumed", 1),
        ("gameplay.pool.bound_changed", 1),
        ("gameplay.pool.threshold_crossed", 1),
    }
    for event_type in event_types:
        if event_type.startswith("gameplay.pool."):
            registry.require(event_type, 1)


def test_pool_commit_uses_stormnight_production_event_schema_registry():
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    service = PoolAuthorityService(store=store, owner_ref=PRINCIPAL)
    definition = PoolDefinition(
        fact_type=FACT_TYPE,
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("50"),
    )

    result = service.initialize(
        definition=definition,
        command_id="pool:registered-init",
        idempotency_key="pool:registered-init",
        causation_id="evt:seed",
        correlation_id="corr:pool",
    )

    assert result.committed
    assert [event.event_type for event in store.read_stream(FACT_TYPE)] == [
        "gameplay.pool.initialized",
    ]
