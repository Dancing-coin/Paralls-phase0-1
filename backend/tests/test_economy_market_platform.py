from __future__ import annotations

from app.gameplay.economy_market_platform import (
    ClearingPolicy,
    EconomyMarketAuthority,
    EconomyMarketProjector,
    Order,
    Quote,
)
from app.gameplay.event_store import GameplayEventStore


def _quote(
    *,
    quote_ref: str = "quote:flour:supplier",
    quantity_limit: int = 5,
    version: int = 1,
    side: str = "sell",
) -> Quote:
    return Quote(
        quote_ref=quote_ref,
        issuer_ref="organization:supplier",
        item_ref="item:flour",
        side=side,
        unit_price_minor=7,
        currency_ref="currency:local",
        quantity_limit=quantity_limit,
        valid_from_tick=1,
        valid_until_tick=10,
        policy_revision="policy:market:v1",
        region_ref="region:town",
        version=version,
        status="active",
    )


def _order(
    *,
    order_ref: str,
    principal_ref: str,
    quantity: int,
    created_tick: int,
    quote_ref: str = "quote:flour:supplier",
    side: str = "buy",
) -> Order:
    return Order(
        order_ref=order_ref,
        principal_ref=principal_ref,
        quote_ref=quote_ref,
        side=side,
        quantity=quantity,
        limit_price_minor=7,
        currency_ref="currency:local",
        region_ref="region:town",
        created_tick=created_tick,
        valid_from_tick=1,
        valid_until_tick=10,
        policy_revision="policy:market:v1",
        status="active",
    )


def _policy(*, partial_fill: bool = True, max_matches: int = 10) -> ClearingPolicy:
    return ClearingPolicy(
        policy_ref="policy:market-clear:v1",
        ordering_key="created_tick_order_ref",
        partial_fill=partial_fill,
        max_matches=max_matches,
    )


def _projection_state(projection) -> dict[str, object]:
    return {
        "quotes": {key: value.model_dump(mode="json") for key, value in projection.quotes.items()},
        "orders": {key: value.model_dump(mode="json") for key, value in projection.orders.items()},
        "clearings": {key: value.model_dump(mode="json") for key, value in projection.clearings.items()},
        "source_revision_vector": dict(projection.source_revision_vector),
    }


def test_market_authority_records_quote_order_and_deterministic_clearing() -> None:
    store = GameplayEventStore()
    authority = EconomyMarketAuthority(store=store)

    quote_result = authority.record_quote(
        command_id="market:quote",
        idempotency_key="market:quote",
        quote=_quote(),
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    assert quote_result.committed
    assert not quote_result.zero_write

    first_order = authority.record_order(
        command_id="market:order:a",
        idempotency_key="market:order:a",
        order=_order(
            order_ref="order:bakery:b",
            principal_ref="organization:bakery-b",
            quantity=3,
            created_tick=2,
        ),
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    second_order = authority.record_order(
        command_id="market:order:b",
        idempotency_key="market:order:b",
        order=_order(
            order_ref="order:bakery:a",
            principal_ref="organization:bakery-a",
            quantity=2,
            created_tick=2,
        ),
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    assert first_order.committed and second_order.committed

    clearing = authority.record_clearing(
        command_id="market:clear",
        idempotency_key="market:clear",
        clearing_ref="clearing:town:1",
        quote_refs=("quote:flour:supplier",),
        policy=_policy(),
        tick=2,
        region_ref="region:town",
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )

    assert clearing.committed
    assert not clearing.zero_write
    assert [match.order_ref for match in clearing.clearing.matches] == [
        "order:bakery:a",
        "order:bakery:b",
    ]
    assert [match.quantity for match in clearing.clearing.matches] == [2, 3]

    projection = EconomyMarketProjector().rebuild(store.read_events())
    assert projection.clearings["clearing:town:1"].matches == clearing.clearing.matches


def test_market_authority_duplicate_and_revision_conflict_are_zero_write() -> None:
    store = GameplayEventStore()
    authority = EconomyMarketAuthority(store=store)

    quote = _quote()
    first = authority.record_quote(
        command_id="market:quote",
        idempotency_key="market:quote",
        quote=quote,
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    duplicate = authority.record_quote(
        command_id="market:quote",
        idempotency_key="market:quote",
        quote=quote,
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    stale = authority.record_quote(
        command_id="market:quote:stale",
        idempotency_key="market:quote:stale",
        quote=quote.model_copy(update={"version": 2}),
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )

    assert first.committed and not first.zero_write
    assert duplicate.committed and duplicate.zero_write
    assert duplicate.append_result is not None
    assert duplicate.append_result.idempotency_status == "duplicate_replayed"
    assert not stale.committed
    assert stale.zero_write
    assert stale.error_code == "revision_conflict"
    assert len(store.read_events()) == 1


def test_market_projection_replays_from_checkpoint_tail() -> None:
    store = GameplayEventStore()
    authority = EconomyMarketAuthority(store=store)
    authority.record_quote(
        command_id="market:quote",
        idempotency_key="market:quote",
        quote=_quote(),
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    authority.record_order(
        command_id="market:order:a",
        idempotency_key="market:order:a",
        order=_order(
            order_ref="order:bakery:a",
            principal_ref="organization:bakery-a",
            quantity=2,
            created_tick=1,
        ),
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    authority.record_order(
        command_id="market:order:b",
        idempotency_key="market:order:b",
        order=_order(
            order_ref="order:bakery:b",
            principal_ref="organization:bakery-b",
            quantity=2,
            created_tick=3,
        ),
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )
    authority.record_clearing(
        command_id="market:clear",
        idempotency_key="market:clear",
        clearing_ref="clearing:town:1",
        quote_refs=("quote:flour:supplier",),
        policy=_policy(max_matches=1),
        tick=3,
        region_ref="region:town",
        expected_revision=0,
        causation_id="test",
        correlation_id="test",
    )

    events = store.read_events()
    projector = EconomyMarketProjector()
    full = projector.rebuild(events)
    checkpoint = projector.create_checkpoint(events[:2])
    tail = projector.rebuild(events[2:], checkpoint=checkpoint)

    assert _projection_state(tail) == _projection_state(full)
