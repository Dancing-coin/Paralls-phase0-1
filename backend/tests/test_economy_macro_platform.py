from __future__ import annotations

from hashlib import sha256
import json

from app.gameplay.economy_platform_runtime import EconomyPlatformAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _append_population_source(
    store: GameplayEventStore,
    *,
    event_ref: str,
    region_ref: str,
    period_ref: str,
    item_ref: str,
    signal_kind: str,
    quantity: int,
    visibility_policy: str = "public",
    unit_price_minor: int | None = None,
    baseline_unit_price_minor: int | None = None,
) -> str:
    stream_id = f"gameplay:population:{region_ref}"
    payload = {
        "aggregate_ref": event_ref,
        "region_ref": region_ref,
        "period_ref": period_ref,
        "item_ref": item_ref,
        "signal_kind": signal_kind,
        "quantity": quantity,
    }
    if unit_price_minor is not None:
        payload["unit_price_minor"] = unit_price_minor
    if baseline_unit_price_minor is not None:
        payload["baseline_unit_price_minor"] = baseline_unit_price_minor
    batch = build_atomic_event_batch(
        command_id=f"command:{event_ref}",
        principal_ref="actor_gameplay.population_domain",
        stream_id=stream_id,
        expected_revision=store.get_stream_head(stream_id),
        event_specs=(("gameplay.population.aggregate_published@1", payload),),
        idempotency_key=f"idempotency:{event_ref}",
        causation_id=f"cause:{event_ref}",
        correlation_id=f"corr:{event_ref}",
    )
    batch = batch.model_copy(
        update={
            "events": [
                event.model_copy(update={"visibility_policy": visibility_policy}, deep=True)
                for event in batch.events
            ]
        },
        deep=True,
    )
    result = store.append_batch(batch)
    assert result.committed, result.failure
    return result.committed_event_ids[0]


def test_population_signal_adapter_and_macro_close_are_deterministic_and_checkpoint_safe() -> None:
    from app.gameplay.economy_macro_platform import (
        EconomyMacroPlatformAuthority,
        RegionalMacroPolicy,
    )

    store = GameplayEventStore()
    economy = EconomyPlatformAuthority(store=store)
    macro = EconomyMacroPlatformAuthority(store=store)

    economy.record_currency_issuance(
        command_id="command:issuance:1",
        idempotency_key="idempotency:issuance:1",
        currency_ref="currency:local",
        amount_minor=180,
        issuer_ref="government:district",
        policy_revision="policy:money:local@1",
        expected_revision=0,
        causation_id="cause:issuance:1",
        correlation_id="corr:issuance:1",
    )
    economy.record_currency_issuance(
        command_id="command:issuance:2",
        idempotency_key="idempotency:issuance:2",
        currency_ref="currency:local",
        amount_minor=70,
        issuer_ref="government:district",
        policy_revision="policy:money:local@1",
        expected_revision=1,
        causation_id="cause:issuance:2",
        correlation_id="corr:issuance:2",
    )
    economy.record_fx_fixing(
        command_id="command:fx:1",
        idempotency_key="idempotency:fx:1",
        fixing_ref="fx:district:1",
        base_currency_ref="currency:local",
        quote_currency_ref="currency:grain-credit",
        numerator=3,
        denominator=2,
        policy_revision="policy:fx:district@1",
        expected_revision=0,
        causation_id="cause:fx:1",
        correlation_id="corr:fx:1",
    )

    price_event_id = _append_population_source(
        store,
        event_ref="aggregate:bread-price",
        region_ref="region:district",
        period_ref="period:harvest:1",
        item_ref="item:bread",
        signal_kind="price_index",
        quantity=4,
        unit_price_minor=9,
        baseline_unit_price_minor=8,
    )
    price_signal = macro.append_population_aggregate_signal(
        source_event_id=price_event_id,
        expected_source_revision=1,
        command_id="command:macro:signal:price",
        idempotency_key="idempotency:macro:signal:price",
        causation_id=price_event_id,
        correlation_id="corr:macro:signal",
    )
    assert price_signal.committed, price_signal.failure

    demand_event_id = _append_population_source(
        store,
        event_ref="aggregate:bread-demand",
        region_ref="region:district",
        period_ref="period:harvest:1",
        item_ref="item:bread",
        signal_kind="demand",
        quantity=40,
    )
    demand_signal = macro.append_population_aggregate_signal(
        source_event_id=demand_event_id,
        expected_source_revision=2,
        command_id="command:macro:signal:demand",
        idempotency_key="idempotency:macro:signal:demand",
        causation_id=demand_event_id,
        correlation_id="corr:macro:signal",
    )
    assert demand_signal.committed, demand_signal.failure

    supply_event_id = _append_population_source(
        store,
        event_ref="aggregate:bread-supply",
        region_ref="region:district",
        period_ref="period:harvest:1",
        item_ref="item:bread",
        signal_kind="supply",
        quantity=25,
    )
    supply_signal = macro.append_population_aggregate_signal(
        source_event_id=supply_event_id,
        expected_source_revision=3,
        command_id="command:macro:signal:supply",
        idempotency_key="idempotency:macro:signal:supply",
        causation_id=supply_event_id,
        correlation_id="corr:macro:signal",
    )
    assert supply_signal.committed, supply_signal.failure

    close = macro.close_regional_macro_period(
        policy=RegionalMacroPolicy(
            policy_ref="policy:macro:district@1",
            region_ref="region:district",
            period_ref="period:harvest:1",
            currency_ref="currency:local",
            base_currency_ref="currency:local",
            quote_currency_ref="currency:grain-credit",
            price_index_basket_refs=("item:bread",),
            interest_rate_bps=275,
        ),
        close_ref="macro-close:district:harvest:1",
        command_id="command:macro:close",
        idempotency_key="idempotency:macro:close",
        expected_revision=3,
        causation_id="cause:macro:close",
        correlation_id="corr:macro:close",
    )

    assert close.committed, close.failure
    event = store.get_event(close.committed_event_ids[0])
    assert event.event_type == "gameplay.economy.regional_macro_period_closed@1"
    assert event.payload["cpi_basis_points"] == 11250
    assert event.payload["demand_quantity"] == 40
    assert event.payload["supply_quantity"] == 25
    assert event.payload["money_supply_minor"] == 250
    assert event.payload["interest_rate_bps"] == 275
    assert event.payload["fx_numerator"] == 3
    assert event.payload["fx_denominator"] == 2

    projection = macro.projection()
    checkpoint_projection = macro.projection(checkpoint_at=event.global_sequence - 1)
    assert "signal:aggregate:bread-price" in projection.population_signals
    assert projection == checkpoint_projection
    assert projection.closes["macro-close:district:harvest:1"].signal_event_ids == (
        "event:command:macro:signal:price:1",
        "event:command:macro:signal:demand:1",
        "event:command:macro:signal:supply:1",
    )
    assert macro.replay().projection_hash == macro.replay(checkpoint_at=event.global_sequence - 1).projection_hash


def test_population_signal_adapter_rejects_private_and_stale_sources_without_write() -> None:
    from app.gameplay.economy_macro_platform import EconomyMacroPlatformAuthority

    store = GameplayEventStore()
    macro = EconomyMacroPlatformAuthority(store=store)
    private_event_id = _append_population_source(
        store,
        event_ref="aggregate:private",
        region_ref="region:district",
        period_ref="period:harvest:1",
        item_ref="item:bread",
        signal_kind="demand",
        quantity=12,
        visibility_policy="authority_only",
    )
    before_private = store.export_snapshot()
    private_result = macro.append_population_aggregate_signal(
        source_event_id=private_event_id,
        expected_source_revision=1,
        command_id="command:macro:private",
        idempotency_key="idempotency:macro:private",
        causation_id=private_event_id,
        correlation_id="corr:macro:private",
    )
    assert not private_result.committed
    assert private_result.failure is not None
    assert private_result.failure.error_code == "economy_population_signal_private_source"
    assert store.export_snapshot() == before_private

    stale_event_id = _append_population_source(
        store,
        event_ref="aggregate:stale:1",
        region_ref="region:district",
        period_ref="period:harvest:2",
        item_ref="item:bread",
        signal_kind="supply",
        quantity=11,
    )
    _append_population_source(
        store,
        event_ref="aggregate:stale:2",
        region_ref="region:district",
        period_ref="period:harvest:2",
        item_ref="item:bread",
        signal_kind="demand",
        quantity=13,
    )
    before_stale = store.export_snapshot()
    stale_result = macro.append_population_aggregate_signal(
        source_event_id=stale_event_id,
        expected_source_revision=1,
        command_id="command:macro:stale",
        idempotency_key="idempotency:macro:stale",
        causation_id=stale_event_id,
        correlation_id="corr:macro:stale",
    )
    assert not stale_result.committed
    assert stale_result.failure is not None
    assert stale_result.failure.error_code == "economy_population_signal_stale_source"
    assert store.export_snapshot() == before_stale


def test_macro_close_is_zero_write_on_duplicate_change_and_revision_conflict() -> None:
    from app.gameplay.economy_macro_platform import (
        EconomyMacroPlatformAuthority,
        RegionalMacroPolicy,
    )

    store = GameplayEventStore()
    economy = EconomyPlatformAuthority(store=store)
    macro = EconomyMacroPlatformAuthority(store=store)

    economy.record_currency_issuance(
        command_id="command:issuance:close",
        idempotency_key="idempotency:issuance:close",
        currency_ref="currency:local",
        amount_minor=50,
        issuer_ref="government:district",
        policy_revision="policy:money:local@1",
        expected_revision=0,
        causation_id="cause:issuance:close",
        correlation_id="corr:issuance:close",
    )
    economy.record_fx_fixing(
        command_id="command:fx:close",
        idempotency_key="idempotency:fx:close",
        fixing_ref="fx:district:close",
        base_currency_ref="currency:local",
        quote_currency_ref="currency:grain-credit",
        numerator=5,
        denominator=4,
        policy_revision="policy:fx:district@1",
        expected_revision=0,
        causation_id="cause:fx:close",
        correlation_id="corr:fx:close",
    )
    public_event_id = _append_population_source(
        store,
        event_ref="aggregate:close",
        region_ref="region:district",
        period_ref="period:harvest:3",
        item_ref="item:bread",
        signal_kind="price_index",
        quantity=2,
        unit_price_minor=11,
        baseline_unit_price_minor=10,
    )
    signal = macro.append_population_aggregate_signal(
        source_event_id=public_event_id,
        expected_source_revision=1,
        command_id="command:macro:close:signal",
        idempotency_key="idempotency:macro:close:signal",
        causation_id=public_event_id,
        correlation_id="corr:macro:close:signal",
    )
    assert signal.committed, signal.failure

    policy = RegionalMacroPolicy(
        policy_ref="policy:macro:district@1",
        region_ref="region:district",
        period_ref="period:harvest:3",
        currency_ref="currency:local",
        base_currency_ref="currency:local",
        quote_currency_ref="currency:grain-credit",
        price_index_basket_refs=("item:bread",),
        interest_rate_bps=300,
    )
    first = macro.close_regional_macro_period(
        policy=policy,
        close_ref="macro-close:district:harvest:3",
        command_id="command:macro:close:first",
        idempotency_key="idempotency:macro:close:first",
        expected_revision=1,
        causation_id="cause:macro:close:first",
        correlation_id="corr:macro:close:first",
    )
    assert first.committed, first.failure
    before_duplicate = store.export_snapshot()

    duplicate = macro.close_regional_macro_period(
        policy=policy,
        close_ref="macro-close:district:harvest:3",
        command_id="command:macro:close:duplicate",
        idempotency_key="idempotency:macro:close:first",
        expected_revision=1,
        causation_id="cause:macro:close:first",
        correlation_id="corr:macro:close:first",
    )
    changed = macro.close_regional_macro_period(
        policy=policy.model_copy(update={"interest_rate_bps": 325}),
        close_ref="macro-close:district:harvest:3",
        command_id="command:macro:close:changed",
        idempotency_key="idempotency:macro:close:first",
        expected_revision=1,
        causation_id="cause:macro:close:first",
        correlation_id="corr:macro:close:first",
    )
    revision_conflict = macro.close_regional_macro_period(
        policy=policy,
        close_ref="macro-close:district:harvest:3b",
        command_id="command:macro:close:revision",
        idempotency_key="idempotency:macro:close:revision",
        expected_revision=0,
        causation_id="cause:macro:close:revision",
        correlation_id="corr:macro:close:revision",
    )

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert not revision_conflict.committed
    assert revision_conflict.failure is not None
    assert revision_conflict.failure.error_code == "revision_conflict"
    assert store.export_snapshot() == before_duplicate
