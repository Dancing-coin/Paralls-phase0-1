import pytest

from app.config import Settings
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.m6_5_siege_runtime import DEFAULT_MORALE_DEFINITIONS, build_m6_5_siege_runtime
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority, SocialDeliveryWindow
from app.gameplay.pool_runtime import PoolDefinition
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.models.fact_type import FACT_TYPE_REGISTRY


REPORT_FACT_TYPE = "fact:information:siege:report"
REPORT_EVENT_TYPE = "gameplay.social.knowledge_observed"
INFORMATION_EVENT_TYPE = "gameplay.information.knowledge_updated@1"
RECIPIENT = "character:defender-1"


def _store_with_delivery(source_fact_type=REPORT_FACT_TYPE):
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source_stream = "gameplay:reports:east-gate"
    source_batch = build_atomic_event_batch(
        command_id="siege-report:source",
        principal_ref="authority:p5:social",
        stream_id=source_stream,
        expected_revision=0,
        event_specs=((REPORT_EVENT_TYPE, {"fact_type": source_fact_type, "report_ref": "report:east-gate"}),),
        idempotency_key="siege-report:source",
        causation_id="siege:dispatch",
        correlation_id="siege:east-gate",
    )
    source_batch = source_batch.model_copy(update={
        "events": [source_batch.events[0].model_copy(update={"visibility_policy": "public"}, deep=True)],
    }, deep=True)
    source_result = store.append_batch(source_batch)
    assert source_result.committed
    source_event = store.get_event(source_result.committed_event_ids[0])
    delivery_result = SocialDeliveryAuthority(store=store).record_delivery(
        delivery_ref="delivery:east-gate:defender-1",
        source_stream_id=source_stream,
        source_revision=source_event.stream_revision,
        source_event_id=source_event.event_id,
        recipient_ref=RECIPIENT,
        window=SocialDeliveryWindow(10, 30, None),
        world_now=15,
        command_id="delivery:east-gate:defender-1",
        idempotency_key="delivery:east-gate:defender-1",
        causation_id=source_event.event_id,
        correlation_id="siege:east-gate",
    )
    assert delivery_result.committed
    transaction = store.get_transaction(delivery_result.append_result.transaction_id)
    return store, transaction


def test_stormnight_factory_registers_information_output_and_delivery_input():
    registry = create_stormnight_event_schema_registry()

    registry.require(INFORMATION_EVENT_TYPE, 1)
    registry.require("gameplay.social.delivery_recorded@2", 2)
    assert INFORMATION_EVENT_TYPE in FACT_TYPE_REGISTRY.event_types()


def test_production_l5_updates_knowledge_only_for_configured_siege_report_sources():
    store, transaction = _store_with_delivery()
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        information_report_source_event_types={REPORT_EVENT_TYPE},
        world_tick_provider=lambda: 16,
    )

    results = runtime.after_transaction_dispatched(transaction)

    assert len(results) == 1
    assert results[0].committed
    events = store.read_events(event_type=INFORMATION_EVENT_TYPE)
    assert len(events) == 1
    assert events[0].visibility_policy == f"actor:{RECIPIENT}"
    assert events[0].payload["report_ref"] == transaction.events[0].payload["source_event_id"]


def test_unconfigured_report_source_does_not_trigger_information_write():
    store, transaction = _store_with_delivery()
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        information_report_source_event_types=set(),
        world_tick_provider=lambda: 16,
    )

    assert runtime.after_transaction_dispatched(transaction) == ()
    assert store.read_events(event_type=INFORMATION_EVENT_TYPE) == []


def test_delivery_of_a_non_siege_fact_does_not_trigger_information_write():
    store, transaction = _store_with_delivery(source_fact_type="fact:government:notice")
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        information_report_source_event_types={REPORT_EVENT_TYPE},
        world_tick_provider=lambda: 16,
    )

    assert runtime.after_transaction_dispatched(transaction) == ()
    assert store.read_events(event_type=INFORMATION_EVENT_TYPE) == []


def test_information_reaction_waits_for_authoritative_world_tick_and_retries():
    store, transaction = _store_with_delivery()
    world_tick = None
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        information_report_source_event_types={REPORT_EVENT_TYPE},
        world_tick_provider=lambda: world_tick,
    )

    dispatcher = GameplayOutboxDispatcher(
        store=store,
        bus=InMemoryAuthorityEventBus(),
        after_transaction_dispatched=runtime.after_transaction_dispatched,
    )
    first = dispatcher.dispatch_pending()
    assert first.failed_count == 0
    assert store.read_events(event_type=INFORMATION_EVENT_TYPE) == []
    assert len(store.list_pending_projection_refresh()) == 1

    world_tick = 16
    dispatcher.dispatch_pending()
    assert len(store.read_events(event_type=INFORMATION_EVENT_TYPE)) == 1
    assert store.list_pending_projection_refresh() == []


def test_information_source_configuration_rejects_unknown_or_duplicate_event_types():
    assert Settings().siege_information_report_event_types == []
    assert Settings(siege_information_report_event_types=[REPORT_EVENT_TYPE]).siege_information_report_event_types == [REPORT_EVENT_TYPE]
    with pytest.raises(ValueError, match="siege_information_report_event_types_invalid"):
        Settings(siege_information_report_event_types=["not-an-event"])
    with pytest.raises(ValueError, match="siege_information_report_event_types_invalid"):
        Settings(siege_information_report_event_types=[REPORT_EVENT_TYPE, REPORT_EVENT_TYPE])
