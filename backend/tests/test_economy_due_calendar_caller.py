from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore, DurableGameplayEventStore
from app.gameplay.economy_due_calendar import EconomyDueCalendarRegistry, PopulationEconomyTaxCaller
from app.gameplay.economy_temporal_consumer import EconomyTemporalConsumer
from test_population_economy_random_caller import _setup
from pathlib import Path
import pytest


@pytest.mark.parametrize("field,value", [("due_tick", True), ("due_tick", 60.5),
    ("valid_from_tick", False), ("valid_until_tick", 100.0)])
def test_calendar_rejects_non_integer_world_ticks(field, value):
    entry = dict(calendar_ref="calendar:monthly", period_ref="period:2026-10", due_tick=60,
                 timeline_id="population:world", source_revision="calendar-monthly@1",
                 valid_from_tick=0, valid_until_tick=100)
    entry[field] = value
    with pytest.raises(ValueError, match="economy_due_calendar_entry_invalid"):
        EconomyDueCalendarRegistry.from_entries((entry,))


def test_calendar_rejects_ambiguous_period_source(tmp_path):
    content = (Path(__file__).resolve().parents[2] /
               "assets/gameplay/economy_due_calendar/monthly-2026-10.yaml").read_text()
    (tmp_path / "first.yaml").write_text(content)
    (tmp_path / "second.yaml").write_text(content.replace("due_tick: 60", "due_tick: 61"))
    with pytest.raises(ValueError, match="economy_due_calendar_duplicate"):
        EconomyDueCalendarRegistry.from_directory(tmp_path)


def test_tax_caller_requires_authored_calendar_and_persists_binding(tmp_path):
    store, world, publisher, driver = _setup(tmp_path)
    service = EconomyAuthorityService(store=store)
    assert driver.tick(60).published_cadence_ids
    source = service.record_tax_due(
        command_id="tax:source", organization_ref="org:test", period_ref="period:2026-10",
        assessed_amount_minor=4, policy_revision="policy:commerce@1", policy_digest="sha256:p",
        due_calendar_ref="calendar:monthly", evidence_refs=("evidence:1",), source_digest="sha256:s",
        idempotency_key="tax:source", causation_id="c", correlation_id="r",
    )
    assert source.committed
    source_event = store.read_events()[-1]
    registry = EconomyDueCalendarRegistry.from_entries(({
        "calendar_ref": "calendar:monthly", "period_ref": "period:2026-10", "due_tick": 60,
        "timeline_id": "population:world", "source_revision": "calendar-monthly@1",
        "valid_from_tick": 0, "valid_until_tick": 100,
    },))
    caller = PopulationEconomyTaxCaller(store=store, authority=service, registry=registry,
                                            population_driver=driver)
    result = caller.open(tax_due_event_id=source_event.event_id, command_id="tax:open",
                         idempotency_key="tax:open", causation_id="c", correlation_id="r")
    assert result.committed
    opening = store.read_events()[-1]
    assert opening.payload["due_calendar_ref"] == "calendar:monthly"
    assert opening.payload["calendar_source_revision"] == "calendar-monthly@1"
    assert opening.payload["population_cadence_id"] == "cadence:world:0"
    assert opening.payload["temporal_pins"]["timeline_id"] == "population:world"
    batch = store.get_transaction(opening.transaction_id)
    assert batch is not None
    assert batch.read_stream_revisions["population-cadence:world"] == store.get_stream_head("population-cadence:world")
    assert batch.read_stream_revisions["population-cadence-revocation:world"] == 0
    ids = tuple(result.append_result.committed_event_ids) if hasattr(result, "append_result") else tuple(batch.events[i].event_id for i in range(len(batch.events)))
    path = store.path if hasattr(store, "path") else tmp_path / "random-population.db"
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        restored = EconomyAuthorityService(store=reopened)
        assert restored.tax_obligation_for(obligation_id=opening.payload["obligation_id"]).due_tick == 60
        assert reopened.get_event(opening.event_id).payload == opening.payload
        assert tuple(event.event_id for event in reopened.get_transaction(batch.transaction_id).events) == ids
    finally:
        reopened.close()


def test_tax_caller_rejects_unknown_calendar_without_opening(tmp_path):
    store, world, publisher, driver = _setup(tmp_path)
    service = EconomyAuthorityService(store=store)
    assert driver.tick(60).published_cadence_ids
    source = service.record_tax_due(
        command_id="tax:source", organization_ref="org:test", period_ref="period:2026-10",
        assessed_amount_minor=4, policy_revision="policy:commerce@1", policy_digest="sha256:p",
        due_calendar_ref="calendar:missing", evidence_refs=("evidence:1",), source_digest="sha256:s",
        idempotency_key="tax:source", causation_id="c", correlation_id="r",
    )
    event = store.read_events()[-1]
    caller = PopulationEconomyTaxCaller(store=store, authority=service,
        registry=EconomyDueCalendarRegistry.from_entries(()), population_driver=driver)
    result = caller.open(tax_due_event_id=event.event_id, command_id="tax:open",
                         idempotency_key="tax:open", causation_id="c", correlation_id="r")
    assert not result.committed
    assert result.failure.error_code == "economy_due_calendar_missing"


def test_authored_calendar_package_is_versioned_and_unknown_period_does_not_infer(tmp_path):
    root = Path(__file__).resolve().parents[2] / "assets" / "gameplay" / "economy_due_calendar"
    registry = EconomyDueCalendarRegistry.from_directory(root)
    entry = registry.resolve(calendar_ref="calendar:monthly", period_ref="period:2026-10",
                             timeline_id="population:world", at_tick=60)
    assert entry.source_revision == "calendar-monthly@1"
    assert entry.source_digest.startswith("sha256:")
    try:
        registry.resolve(calendar_ref="calendar:monthly", period_ref="period:2026-11",
                         timeline_id="population:world", at_tick=60)
    except KeyError as exc:
        assert str(exc).strip("'\"") == "economy_due_calendar_missing"
    else:
        raise AssertionError("unknown period was inferred from a calendar name")


def test_changed_calendar_is_rejected_before_owner_append(tmp_path):
    store, world, publisher, driver = _setup(tmp_path)
    service = EconomyAuthorityService(store=store)
    assert driver.tick(60).published_cadence_ids
    assert service.record_tax_due(
        command_id="source", organization_ref="org:test", period_ref="period:2026-10",
        assessed_amount_minor=1, policy_revision="p@1", policy_digest="sha256:p",
        due_calendar_ref="calendar:monthly", evidence_refs=("evidence:1",), source_digest="sha256:s",
        idempotency_key="source", causation_id="c", correlation_id="r",
    ).committed
    event = store.read_events()[-1]
    directory = tmp_path / "calendar"
    directory.mkdir()
    path = directory / "period.yaml"
    content = (Path(__file__).resolve().parents[2] / "assets/gameplay/economy_due_calendar/monthly-2026-10.yaml").read_text()
    path.write_text(content)
    registry = EconomyDueCalendarRegistry.from_directory(directory)
    path.write_text(content.replace("due_tick: 60", "due_tick: 61"))
    caller = PopulationEconomyTaxCaller(store=store, authority=service, registry=registry, population_driver=driver)
    result = caller.open(tax_due_event_id=event.event_id, command_id="open", idempotency_key="open", causation_id="c", correlation_id="r")
    assert not result.committed
    assert result.failure.error_code == "economy_due_calendar_changed"
    assert not any(e.event_type == "gameplay.economy.tax_obligation_opened" for e in store.read_stream("gameplay:economy"))
    store.close()


def test_production_economy_consumer_opens_authored_tax_on_population_cadence(tmp_path):
    store, world, publisher, driver = _setup(tmp_path)
    service = EconomyAuthorityService(store=store)
    assert driver.tick(60).published_cadence_ids
    assert service.record_tax_due(
        command_id="source", organization_ref="org:test", period_ref="period:2026-10",
        assessed_amount_minor=1, policy_revision="p@1", policy_digest="sha256:p",
        due_calendar_ref="calendar:monthly", evidence_refs=("evidence:1",), source_digest="sha256:s",
        idempotency_key="source", causation_id="c", correlation_id="r",
    ).committed
    consumer = EconomyTemporalConsumer(store=store, authority=service)
    driver.require_temporal_authorization = True
    consumer.advance(driver)
    opened = [event for event in store.read_stream("gameplay:economy")
              if event.event_type == "gameplay.economy.tax_obligation_opened"]
    assert len(opened) == 1
    assert opened[0].payload["calendar_source_revision"] == "calendar-monthly@1"
    assert consumer.last_errors == ()
    store.close()
