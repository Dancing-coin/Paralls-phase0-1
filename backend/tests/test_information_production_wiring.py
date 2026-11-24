from decimal import Decimal
import hashlib
import hmac
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.information_runtime import SiegeReportPublicationReceipt
from app.gameplay.m6_5_siege_runtime import DEFAULT_MORALE_DEFINITIONS, build_m6_5_siege_runtime
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority, SocialDeliveryWindow
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.gameplay.rule_pack_validator import load_pack
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.models.fact_type import FACT_TYPE_REGISTRY
from app.models.siming_heavenly_graph import HeavenlyNodeQuery


REPORT_FACT_TYPE = "fact:information:siege:report"
REPORT_EVENT_TYPE = "gameplay.information.siege_report_published@1"
INFORMATION_EVENT_TYPE = "gameplay.information.knowledge_updated@1"
RECIPIENT = "character:defender-1"
SIGNER = "authority:fixture-report-producer"
SIGNING_FIXTURE = "fixture-key" * 4
PUBLICATION_PATH = "/api/v2/siege/information/report-publication-input"


def _store_with_delivery(
    source_fact_type=REPORT_FACT_TYPE,
    *,
    source_principal="authority:information:report-publisher",
    source_recipient=RECIPIENT,
):
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source_stream = "gameplay:reports:east-gate"
    source_batch = build_atomic_event_batch(
        command_id="siege-report:source",
        principal_ref=source_principal,
        stream_id=source_stream,
        expected_revision=0,
        event_specs=((REPORT_EVENT_TYPE, {"fact_type": source_fact_type, "report_ref": "report:east-gate", "recipient_ref": source_recipient}),),
        idempotency_key="siege-report:source",
        causation_id="siege:dispatch",
        correlation_id="siege:east-gate",
    )
    source_batch = source_batch.model_copy(update={
        "events": [source_batch.events[0].model_copy(update={"visibility_policy": f"actor:{RECIPIENT}"}, deep=True)],
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

    registry.require(REPORT_EVENT_TYPE, 1)
    registry.require(INFORMATION_EVENT_TYPE, 1)
    registry.require("gameplay.social.delivery_recorded@2", 2)
    assert FACT_TYPE_REGISTRY.from_event_type(REPORT_EVENT_TYPE).domain == "information"
    assert INFORMATION_EVENT_TYPE in FACT_TYPE_REGISTRY.event_types()


def test_information_pack_declares_recipient_private_report_before_knowledge():
    pack = load_pack(
        Path(__file__).resolve().parents[2] / "packs" / "county_siege_information",
        handlers={},
        owner_domains={"Information": "information"},
        command_fact_outputs={
            "information.update_knowledge": {"fact:information:siege:report_knowledge"},
        },
    )

    report = pack.registry.facts[REPORT_FACT_TYPE]
    knowledge = pack.registry.facts["fact:information:siege:report_knowledge"]
    assert report.owner_ref == "Information"
    assert report.visibility["class"] == "private"
    assert tuple(report.visibility["learnable_by"]) == ("recipient_of(subject)",)
    assert report.resolution_order < knowledge.resolution_order
    assert tuple(pack.registry.machines[report.state_set_ref]["terminal_states"]) == ("published",)
    assert pack.command_catalog["information.publish_siege_report"]["requires_authority"]


def test_production_l5_updates_knowledge_from_committed_information_report():
    store, transaction = _store_with_delivery()
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        world_tick_provider=lambda: 16,
    )

    results = runtime.after_transaction_dispatched(transaction)

    assert len(results) == 1
    assert results[0].committed
    events = store.read_events(event_type=INFORMATION_EVENT_TYPE)
    assert len(events) == 1
    assert events[0].visibility_policy == f"actor:{RECIPIENT}"
    assert events[0].payload["report_ref"] == transaction.events[0].payload["source_event_id"]


@pytest.mark.parametrize(("principal", "recipient"), [
    ("authority:other", RECIPIENT),
    ("authority:information:report-publisher", "character:other"),
])
def test_lookalike_report_source_does_not_trigger_information_write(principal, recipient):
    store, transaction = _store_with_delivery(
        source_principal=principal,
        source_recipient=recipient,
    )
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        world_tick_provider=lambda: 16,
    )

    assert runtime.after_transaction_dispatched(transaction) == ()
    assert store.read_events(event_type=INFORMATION_EVENT_TYPE) == []


def test_delivery_of_a_non_siege_fact_does_not_trigger_information_write():
    store, transaction = _store_with_delivery(source_fact_type="fact:government:notice")
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
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


def _signed_facility_report(store):
    gate_ref = "gate-03"
    integrity = FacilityIntegrityAuthority(
        store=store,
        definitions={gate_ref: PoolDefinition(
            fact_type=FacilityIntegrityAuthority.fact_type_for(gate_ref),
            lower=Decimal("0"),
            upper=Decimal("100"),
            initial=Decimal("100"),
            thresholds=(PoolThreshold("breach", Decimal("40"), Decimal("45")),),
        )},
    )
    initialized = integrity.initialize(
        gate_ref=gate_ref, command_id="facility:report-init", idempotency_key="facility:report-init",
        causation_id="siege:setup", correlation_id="siege:east-gate",
    )
    assert initialized.committed
    breach = integrity.apply_delta(
        gate_ref=gate_ref, delta=Decimal("-65"), reason_code="damage", expected_revision=1,
        command_id="facility:report-breach", idempotency_key="facility:report-breach",
        causation_id=initialized.committed_event_ids[0], correlation_id="siege:east-gate",
    )
    assert breach.committed
    source = store.get_event(breach.committed_event_ids[-1])
    assert source.event_type == "gameplay.pool.threshold_crossed"
    unsigned = SiegeReportPublicationReceipt(
        authority_ref=SIGNER, receipt_id="receipt:east-gate", report_ref="report:east-gate:breach",
        recipient_ref=RECIPIENT, summary="The east gate is breached.",
        source_event_id=source.event_id, source_stream_id=source.stream_id,
        source_revision=source.stream_revision, effective_from=10, effective_to=20,
        signature="0" * 64,
    )
    signature = hmac.new(
        SIGNING_FIXTURE.encode(), unsigned.canonical_bytes(), hashlib.sha256,
    ).hexdigest()
    return unsigned.model_copy(update={"signature": signature})


def test_report_publication_http_commits_private_report_and_knowledge(monkeypatch, tmp_path):
    from app import main

    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "graph.sqlite"))
    monkeypatch.setattr(main.settings, "siege_information_report_authority_secrets", {SIGNER: SIGNING_FIXTURE})
    world_tick = 15
    monkeypatch.setattr(main, "_session_world_clock_tick", lambda: world_tick)
    main.reset_runtime_state(restore_gameplay=True)
    try:
        store = main.gameplay_event_store
        receipt = _signed_facility_report(store)
        published = []
        for event_type in (REPORT_EVENT_TYPE, INFORMATION_EVENT_TYPE):
            main.authority_event_bus.subscribe(event_type, published.append)
        private = []
        main.authority_event_bus.subscribe(REPORT_EVENT_TYPE, private.append, consumer_id=RECIPIENT)
        main.authority_event_bus.subscribe(
            REPORT_EVENT_TYPE, lambda _event: pytest.fail("report reached another actor"),
            consumer_id="character:other",
        )
        client = TestClient(main.component_app)

        response = client.post(PUBLICATION_PATH, json=receipt.model_dump(mode="json"))

        assert response.status_code == 200
        body = response.json()
        assert body["committed"]
        report, = store.read_events(event_type=REPORT_EVENT_TYPE)
        knowledge, = store.read_events(event_type=INFORMATION_EVENT_TYPE)
        assert knowledge.payload["report_ref"] == report.event_id
        assert report.payload["source_event_id"] == receipt.source_event_id
        assert report.visibility_policy == knowledge.visibility_policy == f"actor:{RECIPIENT}"
        assert [event.routing.audience_mode for event in published] == [f"actor:{RECIPIENT}"] * 2
        assert private == [published[0]]
        nodes = main.heavenly_graph.query_nodes(HeavenlyNodeQuery(
            scope=main.siming_scope_for_event(published[0]), valid_at=100,
            node_types=["causal_event"],
        ))
        assert {node.attributes["event_type"] for node in nodes} >= {
            REPORT_EVENT_TYPE, INFORMATION_EVENT_TYPE,
        }
        delivery = SocialDeliveryAuthority(store=store)
        assert len(delivery.view_for(recipient_ref=RECIPIENT, world_now=15).deliveries) == 1
        assert not delivery.view_for(recipient_ref="character:other", world_now=15).deliveries

        world_tick = 25
        main.reset_runtime_state(restore_gameplay=True)
        repeat = client.post(PUBLICATION_PATH, json=receipt.model_dump(mode="json")).json()

        assert repeat["committed"]
        assert repeat["error_code"] == "duplicate_replayed"
        for key in ("report", "delivery"):
            assert repeat[key]["committed_event_ids"] == body[key]["committed_event_ids"]
        reopened = main.gameplay_event_store
        assert reopened.read_events(event_type=REPORT_EVENT_TYPE) == [report]
        assert reopened.read_events(event_type=INFORMATION_EVENT_TYPE) == [knowledge]
    finally:
        with monkeypatch.context() as patch:
            patch.setattr(main.settings, "heavenly_graph_path", ":memory:")
            main.reset_runtime_state()


@pytest.mark.parametrize("configured", [False, True])
def test_report_publication_http_rejects_unsigned_requests_without_writes(monkeypatch, configured):
    from app import main

    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    receipt = _signed_facility_report(store)
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        information_report_authority_secrets={SIGNER: SIGNING_FIXTURE} if configured else {},
        world_tick_provider=lambda: 15,
    )
    monkeypatch.setattr(main, "m6_5_siege_runtime", runtime)
    monkeypatch.setattr(main, "runtime_execution", None)
    before = store.export_snapshot()
    payload = receipt.model_dump(mode="json")
    if configured:
        payload["recipient_ref"] = "character:other"

    response = TestClient(main.component_app).post(PUBLICATION_PATH, json=payload)

    assert response.status_code == 200
    assert response.json()["error_code"] == "information_report_signature_invalid"
    assert store.export_snapshot() == before


def test_report_publication_http_validation_omits_receipt_contents(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "m6_5_siege_runtime", object())
    response = TestClient(main.component_app).post(
        PUBLICATION_PATH, json={"summary": "Fixture private report", "signature": "malformed"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"error_code": "information_report_receipt_invalid"}}
