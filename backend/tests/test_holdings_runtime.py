from decimal import Decimal

import pytest

from app.models.fact_type import FACT_TYPE_REGISTRY
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry, gameplay_schema_event_types
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.holdings_event_schema import HOLDINGS_EVENT_TYPES
from app.gameplay.models import GameplayEvent
from app.gameplay.holdings_runtime import (
    HoldingsAuthorityService,
    HoldingsDefinition,
    HoldingsError,
    HoldingsItemDefinition,
    HoldingsProjector,
)

FACT_TYPE = "fact:inventory:store-01:holdings"
ITEM = "item:grain:wheat@1"


def build_service(*, capacity: str = "100", additional_items=()):
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    service = HoldingsAuthorityService(
        store=store,
        definitions={FACT_TYPE: HoldingsDefinition(
            fact_type=FACT_TYPE, capacity=Decimal(capacity),
        )},
        item_definitions={
            ITEM: HoldingsItemDefinition(
                item_ref=ITEM, unit_ref="unit:bushel@1", specification_ref="spec:wheat@1",
            ),
            **{item.item_ref: item for item in additional_items},
        },
    )
    return store, service


def create_lot(store, service, *, quantity: str = "10"):
    result = service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", item_ref=ITEM,
        quantity=Decimal(quantity), container_ref="container:store-01",
        command_id="holdings:create-lot", idempotency_key="create-lot",
        expected_revision=0, causation_id="event:seed", correlation_id="corr:holdings",
    )
    assert result.committed


def test_release_and_partial_settlement_restore_only_unconsumed_quantity():
    store, service = build_service()
    create_lot(store, service)

    reserved = service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("6"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    assert reserved.committed
    projection = service.project(FACT_TYPE)
    assert projection.lots["lot:wheat-01"].quantity == Decimal("4")
    assert projection.lots["lot:wheat-01"].reserved_quantity == Decimal("6")
    assert projection.lots["lot:wheat-01"].available_quantity == Decimal("4")

    released = service.release(
        fact_type=FACT_TYPE, reservation_ref="reservation:r1",
        command_id="holdings:release-1", idempotency_key="release-1",
        expected_revision=2, causation_id="event:seed", correlation_id="corr:holdings",
    )
    assert released.committed
    assert service.project(FACT_TYPE).lots["lot:wheat-01"].available_quantity == Decimal("10")

    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r2",
        amount=Decimal("6"), command_id="holdings:reserve-2", idempotency_key="reserve-2",
        expected_revision=3, causation_id="event:seed", correlation_id="corr:holdings",
    )
    settled = service.settle_reservation(
        fact_type=FACT_TYPE, reservation_ref="reservation:r2", actual=Decimal("4"),
        reason_code="recipe_input", command_id="holdings:settle-2",
        idempotency_key="settle-2", expected_revision=4,
        causation_id="event:seed", correlation_id="corr:holdings",
    )

    assert settled.committed
    lot = service.project(FACT_TYPE).lots["lot:wheat-01"]
    assert lot.quantity == Decimal("6")
    assert lot.reserved_quantity == Decimal("0")
    assert lot.available_quantity == Decimal("6")
    assert service.project(FACT_TYPE).total_quantity == Decimal("6")
    assert [event.event_type for event in store.read_stream(FACT_TYPE)] == [
        "gameplay.holdings.lot_created",
        "gameplay.holdings.reserved",
        "gameplay.holdings.reservation_released",
        "gameplay.holdings.reserved",
        "gameplay.holdings.reservation_settled",
    ]


def test_reserve_beyond_available_is_rejected_without_writes():
    store, service = build_service()
    create_lot(store, service)
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("8"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="holdings_insufficient_available"):
        service.reserve(
            fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r2",
            amount=Decimal("3"), command_id="holdings:reserve-2", idempotency_key="reserve-2",
            expected_revision=2, causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before


def test_settlement_above_reserved_amount_is_rejected_without_writes():
    store, service = build_service()
    create_lot(store, service)
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("4"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="holdings_settlement_exceeds_reservation"):
        service.settle_reservation(
            fact_type=FACT_TYPE, reservation_ref="reservation:r1", actual=Decimal("5"),
            reason_code="recipe_input", command_id="holdings:settle-1",
            idempotency_key="settle-1", expected_revision=2,
            causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before


def test_holdings_events_are_visible_and_registered_in_production_schema_factory():
    registry = create_stormnight_event_schema_registry()

    assert set(HOLDINGS_EVENT_TYPES) <= set(gameplay_schema_event_types())
    for event_type in HOLDINGS_EVENT_TYPES:
        registry.require(event_type, 1)
        fact_type = FACT_TYPE_REGISTRY.from_event_type(event_type)
        assert fact_type is not None
        assert FACT_TYPE_REGISTRY.domain_for(fact_type) == "holdings"


def test_reservation_references_are_unique_across_all_lots_in_the_collection():
    store, service = build_service()
    create_lot(store, service)
    service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-02", item_ref=ITEM,
        quantity=Decimal("5"), container_ref="container:store-01",
        command_id="holdings:create-lot-2", idempotency_key="create-lot-2",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("2"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=2, causation_id="event:seed", correlation_id="corr:holdings",
    )
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="holdings_reservation_duplicate"):
        service.reserve(
            fact_type=FACT_TYPE, lot_ref="lot:wheat-02", reservation_ref="reservation:r1",
            amount=Decimal("2"), command_id="holdings:reserve-2", idempotency_key="reserve-2",
            expected_revision=3, causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before


def test_reserved_quantity_is_a_partition_of_total_stock():
    store, service = build_service()
    create_lot(store, service)
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("6"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )

    projection = service.project(FACT_TYPE)
    lot = projection.lots["lot:wheat-01"]
    assert lot.quantity == Decimal("4")
    assert lot.reserved_quantity == Decimal("6")
    assert lot.available_quantity == Decimal("4")
    assert projection.total_quantity == Decimal("10")


def test_projection_sum_aggregates_by_item_without_mixing_unit_or_specification():
    other_item = "item:grain:barley@1"
    store, service = build_service(additional_items=(HoldingsItemDefinition(
        item_ref=other_item, unit_ref="unit:kilogram@1", specification_ref="spec:barley@1",
    ),))
    create_lot(store, service)
    service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-02", item_ref=ITEM,
        quantity=Decimal("5"), container_ref="container:store-02",
        command_id="holdings:create-lot-2", idempotency_key="create-lot-2",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:barley-01", item_ref=other_item,
        quantity=Decimal("7"), container_ref="container:store-03",
        command_id="holdings:create-lot-3", idempotency_key="create-lot-3",
        expected_revision=2, causation_id="event:seed", correlation_id="corr:holdings",
    )
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("2"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=3, causation_id="event:seed", correlation_id="corr:holdings",
    )

    quantity_sum = service.project(FACT_TYPE).sum_by_item

    assert quantity_sum[ITEM].available_quantity == Decimal("13")
    assert quantity_sum[ITEM].reserved_quantity == Decimal("2")
    assert quantity_sum[ITEM].total_quantity == Decimal("15")
    assert quantity_sum[ITEM].unit_ref == "unit:bushel@1"
    assert quantity_sum[ITEM].specification_ref == "spec:wheat@1"
    assert quantity_sum[other_item].total_quantity == Decimal("7")


def test_transfer_moves_stock_between_existing_lots_without_changing_total():
    store, service = build_service()
    create_lot(store, service)
    service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-02", item_ref=ITEM,
        quantity=Decimal("2"), container_ref="container:store-02",
        command_id="holdings:create-lot-2", idempotency_key="create-lot-2",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )

    result = service.transfer(
        fact_type=FACT_TYPE, source_lot_ref="lot:wheat-01",
        destination_lot_ref="lot:wheat-02", amount=Decimal("3"),
        step_ref="step:transfer-1", command_id="holdings:transfer-1",
        idempotency_key="transfer-1", expected_revision=2,
        causation_id="event:seed", correlation_id="corr:holdings",
    )

    assert result.committed
    projection = service.project(FACT_TYPE)
    assert projection.lots["lot:wheat-01"].quantity == Decimal("7")
    assert projection.lots["lot:wheat-02"].quantity == Decimal("5")
    assert projection.total_quantity == Decimal("12")


def test_transfer_rejects_incompatible_item_specification_without_writes():
    other_item = "item:grain:barley@1"
    store, service = build_service(additional_items=(HoldingsItemDefinition(
        item_ref=other_item, unit_ref="unit:bushel@1", specification_ref="spec:barley@1",
    ),))
    create_lot(store, service)
    service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:barley", item_ref=other_item,
        quantity=Decimal("2"), container_ref="container:store-03",
        command_id="holdings:create-lot-3", idempotency_key="create-lot-3",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="holdings_item_incompatible"):
        service.transfer(
            fact_type=FACT_TYPE, source_lot_ref="lot:wheat-01",
            destination_lot_ref="lot:barley", amount=Decimal("1"),
            step_ref="step:transfer-2", command_id="holdings:transfer-2",
            idempotency_key="transfer-2", expected_revision=2,
            causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before


def test_reserved_transfer_moves_reservation_and_quantity_in_one_event():
    store, service = build_service()
    create_lot(store, service)
    service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-02", item_ref=ITEM,
        quantity=Decimal("10"), container_ref="container:store-02",
        command_id="holdings:create-lot-2", idempotency_key="create-lot-2",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("3"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=2, causation_id="event:seed", correlation_id="corr:holdings",
    )

    result = service.transfer_reservation(
        fact_type=FACT_TYPE, reservation_ref="reservation:r1",
        destination_lot_ref="lot:wheat-02", step_ref="step:transfer-1",
        command_id="holdings:transfer-reservation-1", idempotency_key="transfer-reservation-1",
        expected_revision=3, causation_id="event:seed", correlation_id="corr:holdings",
    )

    projection = service.project(FACT_TYPE)
    assert result.committed
    assert projection.total_quantity == Decimal("20")
    assert projection.lots["lot:wheat-01"].reserved_quantity == Decimal("0")
    assert projection.lots["lot:wheat-02"].reserved_quantity == Decimal("3")
    assert projection.lots["lot:wheat-02"].quantity == Decimal("10")
    assert store.read_stream(FACT_TYPE)[-1].event_type == "gameplay.holdings.reservation_transferred"


def test_split_and_merge_preserve_total_quantity():
    store, service = build_service()
    create_lot(store, service)

    split = service.split(
        fact_type=FACT_TYPE, source_lot_ref="lot:wheat-01",
        result_lot_refs=("lot:wheat-02", "lot:wheat-03"),
        amounts=(Decimal("4"), Decimal("6")), command_id="holdings:split-1",
        idempotency_key="split-1", expected_revision=1,
        causation_id="event:seed", correlation_id="corr:holdings",
    )
    merged = service.merge(
        fact_type=FACT_TYPE, source_lot_refs=("lot:wheat-02", "lot:wheat-03"),
        result_lot_ref="lot:wheat-04", command_id="holdings:merge-1",
        idempotency_key="merge-1", expected_revision=2,
        causation_id="event:seed", correlation_id="corr:holdings",
    )

    projection = service.project(FACT_TYPE)
    assert split.committed and merged.committed
    assert projection.total_quantity == Decimal("10")
    assert projection.lots["lot:wheat-04"].quantity == Decimal("10")
    assert [event.event_type for event in store.read_stream(FACT_TYPE)] == [
        "gameplay.holdings.lot_created",
        "gameplay.holdings.split",
        "gameplay.holdings.merged",
    ]


def test_consumption_and_loss_reduce_stock_without_consuming_reservations():
    store, service = build_service()
    create_lot(store, service)
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("6"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="holdings_insufficient_available"):
        service.consume(
            fact_type=FACT_TYPE, lot_ref="lot:wheat-01", amount=Decimal("5"),
            reason_code="recipe_input", command_id="holdings:consume-rejected",
            idempotency_key="consume-rejected", expected_revision=2,
            causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before
    service.consume(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", amount=Decimal("2"),
        reason_code="recipe_input", command_id="holdings:consume-1",
        idempotency_key="consume-1", expected_revision=2,
        causation_id="event:seed", correlation_id="corr:holdings",
    )
    service.lose(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", amount=Decimal("1"),
        reason_code="spoilage", command_id="holdings:loss-1",
        idempotency_key="loss-1", expected_revision=3,
        causation_id="event:seed", correlation_id="corr:holdings",
    )

    projection = service.project(FACT_TYPE)
    assert projection.total_quantity == Decimal("7")
    assert projection.reserved_quantity == Decimal("6")
    assert projection.available_quantity == Decimal("1")


def test_exact_create_retry_returns_original_receipt_without_another_event():
    store, service = build_service()
    first = service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", item_ref=ITEM,
        quantity=Decimal("10"), container_ref="container:store-01",
        command_id="holdings:create-lot", idempotency_key="create-lot",
        expected_revision=0, causation_id="event:seed", correlation_id="corr:holdings",
    )

    retry = service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", item_ref=ITEM,
        quantity=Decimal("10"), container_ref="container:store-01",
        command_id="holdings:create-lot", idempotency_key="create-lot",
        expected_revision=0, causation_id="event:seed", correlation_id="corr:holdings",
    )

    assert retry.committed
    assert retry.transaction_id == first.transaction_id
    assert retry.command_id == first.command_id
    assert retry.committed_event_ids == first.committed_event_ids
    assert retry.resulting_stream_revisions == first.resulting_stream_revisions
    assert len(store.read_stream(FACT_TYPE)) == 1


def test_changed_create_retry_is_rejected_without_writes():
    store, service = build_service()
    create_lot(store, service)
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="idempotency_key_reused"):
        service.create_lot(
            fact_type=FACT_TYPE, lot_ref="lot:wheat-01", item_ref=ITEM,
            quantity=Decimal("11"), container_ref="container:store-01",
            command_id="holdings:create-lot", idempotency_key="create-lot",
            expected_revision=0, causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before


class MissingEventReceiptStore(GameplayEventStore):
    missing_event_id: str | None = None

    def get_event(self, event_id: str) -> GameplayEvent:
        if event_id == self.missing_event_id:
            raise KeyError(event_id)
        return super().get_event(event_id)


def test_duplicate_retry_rejects_receipt_with_missing_committed_event():
    store = MissingEventReceiptStore(event_schema_registry=create_stormnight_event_schema_registry())
    service = HoldingsAuthorityService(
        store=store,
        definitions={FACT_TYPE: HoldingsDefinition(FACT_TYPE, Decimal("100"))},
        item_definitions={ITEM: HoldingsItemDefinition(
            item_ref=ITEM, unit_ref="unit:bushel@1", specification_ref="spec:wheat@1",
        )},
    )
    first = service.create_lot(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", item_ref=ITEM,
        quantity=Decimal("10"), container_ref="container:store-01",
        command_id="holdings:create-lot", idempotency_key="create-lot",
        expected_revision=0, causation_id="event:seed", correlation_id="corr:holdings",
    )
    store.missing_event_id = first.committed_event_ids[0]
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="holdings_replay_event_missing"):
        service.create_lot(
            fact_type=FACT_TYPE, lot_ref="lot:wheat-01", item_ref=ITEM,
            quantity=Decimal("10"), container_ref="container:store-01",
            command_id="holdings:create-lot", idempotency_key="create-lot",
            expected_revision=0, causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before


def test_capacity_counts_reserved_stock_and_rejects_addition_without_writes():
    store, service = build_service(capacity="10")
    create_lot(store, service)
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("8"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    before = store.read_stream(FACT_TYPE)

    with pytest.raises(HoldingsError, match="holdings_capacity_exceeded"):
        service.create_lot(
            fact_type=FACT_TYPE, lot_ref="lot:wheat-02", item_ref=ITEM,
            quantity=Decimal("1"), container_ref="container:store-01",
            command_id="holdings:create-lot-2", idempotency_key="create-lot-2",
            expected_revision=2, causation_id="event:seed", correlation_id="corr:holdings",
        )

    assert store.read_stream(FACT_TYPE) == before


def test_formal_v1_holdings_events_rebuild_with_quality_kept_out_of_quantity():
    events = [
        GameplayEvent(
            event_id=f"evt:legacy:{index}", event_type=event_type, schema_version=1,
            stream_id=FACT_TYPE, stream_revision=index, global_sequence=index,
            transaction_id=f"tx:legacy:{index}", command_id=f"legacy:{index}",
            causation_id="event:legacy", correlation_id="corr:legacy",
            visibility_policy="authority_only", payload=payload,
        )
        for index, (event_type, payload) in enumerate((
            ("gameplay.holdings.lot_created", {
                "lot_ref": "lot:legacy", "item_ref": ITEM, "quantity": "10.0000",
                "quality": "0.7500", "container_ref": "container:store-01",
            }),
            ("gameplay.holdings.reserved", {
                "lot_ref": "lot:legacy", "reservation_ref": "reservation:legacy",
                "amount": "3.0000",
            }),
            ("gameplay.holdings.consumed", {
                "lot_ref": "lot:legacy", "amount": "2.0000", "reason_code": "recipe_input",
            }),
        ), start=1)
    ]

    projection = HoldingsProjector().rebuild(
        events, definition=HoldingsDefinition(FACT_TYPE, Decimal("100")),
        item_definitions={ITEM: HoldingsItemDefinition(
            item_ref=ITEM, unit_ref="unit:bushel@1", specification_ref="spec:wheat@1",
        )},
    )

    assert projection.source_revision == 3
    assert projection.total_quantity == Decimal("8.0000")
    assert projection.lots["lot:legacy"].quantity == Decimal("5.0000")
    assert projection.lots["lot:legacy"].reserved_quantity == Decimal("3.0000")


def test_rebuilding_the_event_stream_matches_the_live_projection():
    store, service = build_service()
    create_lot(store, service)
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("6"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    service.settle_reservation(
        fact_type=FACT_TYPE, reservation_ref="reservation:r1", actual=Decimal("4"),
        reason_code="recipe_input", command_id="holdings:settle-1",
        idempotency_key="settle-1", expected_revision=2,
        causation_id="event:seed", correlation_id="corr:holdings",
    )

    rebuilt = HoldingsProjector().rebuild(
        store.read_stream(FACT_TYPE), definition=HoldingsDefinition(FACT_TYPE, Decimal("100")),
        item_definitions={ITEM: HoldingsItemDefinition(
            item_ref=ITEM, unit_ref="unit:bushel@1", specification_ref="spec:wheat@1",
        )},
    )

    assert rebuilt == service.project(FACT_TYPE)


def test_rebuilding_after_historical_checkpoint_matches_full_replay():
    store, service = build_service()
    create_lot(store, service)
    service.reserve(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", reservation_ref="reservation:r1",
        amount=Decimal("6"), command_id="holdings:reserve-1", idempotency_key="reserve-1",
        expected_revision=1, causation_id="event:seed", correlation_id="corr:holdings",
    )
    service.consume(
        fact_type=FACT_TYPE, lot_ref="lot:wheat-01", amount=Decimal("2"),
        reason_code="recipe_input", command_id="holdings:consume-1",
        idempotency_key="consume-1", expected_revision=2,
        causation_id="event:seed", correlation_id="corr:holdings",
    )
    events = store.read_stream(FACT_TYPE)
    item_definitions = {ITEM: HoldingsItemDefinition(
        item_ref=ITEM, unit_ref="unit:bushel@1", specification_ref="spec:wheat@1",
    )}

    full_replay = HoldingsProjector().rebuild(
        events, definition=HoldingsDefinition(FACT_TYPE, Decimal("100")),
        item_definitions=item_definitions,
    )
    checkpoint_replay = HoldingsProjector().rebuild(
        events, definition=HoldingsDefinition(FACT_TYPE, Decimal("100")),
        item_definitions=item_definitions, checkpoint_at=events[0].global_sequence,
    )

    assert checkpoint_replay == full_replay


def test_historical_checkpoint_preserves_closed_lots_after_split():
    store, service = build_service()
    create_lot(store, service)
    service.split(
        fact_type=FACT_TYPE, source_lot_ref="lot:wheat-01",
        result_lot_refs=("lot:wheat-02", "lot:wheat-03"),
        amounts=(Decimal("4"), Decimal("6")), command_id="holdings:split-1",
        idempotency_key="split-1", expected_revision=1,
        causation_id="event:seed", correlation_id="corr:holdings",
    )
    events = store.read_stream(FACT_TYPE)

    full_replay = HoldingsProjector().rebuild(
        events, definition=HoldingsDefinition(FACT_TYPE, Decimal("100")),
        item_definitions={ITEM: HoldingsItemDefinition(
            item_ref=ITEM, unit_ref="unit:bushel@1", specification_ref="spec:wheat@1",
        )},
    )
    checkpoint_replay = HoldingsProjector().rebuild(
        events, definition=HoldingsDefinition(FACT_TYPE, Decimal("100")),
        item_definitions={ITEM: HoldingsItemDefinition(
            item_ref=ITEM, unit_ref="unit:bushel@1", specification_ref="spec:wheat@1",
        )},
        checkpoint_at=events[-1].global_sequence,
    )

    assert checkpoint_replay == full_replay
    assert checkpoint_replay.closed_lot_refs == frozenset({"lot:wheat-01"})


def test_negative_checkpoint_is_rejected():
    with pytest.raises(HoldingsError, match="holdings_checkpoint_invalid"):
        HoldingsProjector().rebuild(
            [], definition=HoldingsDefinition(FACT_TYPE), item_definitions={}, checkpoint_at=-1,
        )
