from types import SimpleNamespace

import pytest

from app.gameplay.ecology_temporal_consumer import EcologyTemporalConsumer
from test_infra_ecology_drought_state_obligation import _apply, _seed_process, REGION_REF, STREAM
from app.gameplay.economy_temporal_consumer import EconomyTemporalConsumer
from test_economy_temporal_replay_application import _open_temporal_obligation


@pytest.mark.parametrize("consumer_domain", ["ecology", "economy"])
def test_each_consumer_budget_excludes_other_domain_due_obligations(consumer_domain):
    store, authority, source_id, source_revision = _seed_process()
    assert _apply(authority, expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_id, source_event_revision=source_revision,
        due_tick=6 if consumer_domain == "ecology" else 0).committed
    economy = EconomyTemporalConsumer(store=store)
    ecology = EcologyTemporalConsumer(store=store, authority=authority)
    _open_temporal_obligation(SimpleNamespace(gameplay_event_store=store,
        economy_temporal_consumer=economy,
        _population_runtime_driver=SimpleNamespace(current_tick=0 if consumer_domain == "ecology" else 6)))
    driver = SimpleNamespace(current_tick=6, catch_up_limit=1,
        world_runtime=SimpleNamespace(is_paused=lambda: False))
    consumer = ecology if consumer_domain == "ecology" else economy
    other_prefix = "gameplay.economy." if consumer_domain == "ecology" else "gameplay.ecology."
    before = [event for event in store.read_events() if event.event_type.startswith(other_prefix)]
    consumer.advance(driver)
    assert consumer.last_errors == ()
    assert len(consumer.last_results) == 1 and consumer.last_results[0].committed
    assert [event for event in store.read_events() if event.event_type.startswith(other_prefix)] == before


def test_ecology_temporal_consumer_uses_confirmed_population_tick_and_existing_owner():
    store, authority, source_event_id, source_event_revision = _seed_process()
    assert _apply(
        authority,
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed
    before = len(store.read_events())
    driver = SimpleNamespace(
        current_tick=6,
        catch_up_limit=1,
        world_runtime=SimpleNamespace(is_paused=lambda: False),
    )

    consumer = EcologyTemporalConsumer(store=store, authority=authority)
    consumer.advance(driver)

    assert len(store.read_events()) == before + 2
    assert consumer.last_errors == ()
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.drought_state_expired",
        "gameplay.ecology.drought_state_obligation_settled",
    ]


def test_ecology_temporal_consumer_rejects_after_close_without_writing():
    store, authority, _source_event_id, _source_event_revision = _seed_process()
    consumer = EcologyTemporalConsumer(store=store, authority=authority)
    consumer.close()
    try:
        consumer.advance(SimpleNamespace(current_tick=6, catch_up_limit=1, world_runtime=SimpleNamespace(is_paused=lambda: False)))
    except RuntimeError as exc:
        assert str(exc) == "ecology_consumer_closed"
    else:
        raise AssertionError("closed Ecology consumer accepted advancement")
