from app.gameplay.daily_rhythm_runtime import DailyRhythmRuntime, create_daily_rhythm_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.owner_fact_query_impl import OwnerFactQueryImpl


def make_query():
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    bus = InMemoryAuthorityEventBus()
    runtime = DailyRhythmRuntime(bus, store=store)
    query = OwnerFactQueryImpl(store, FACT_TYPE_REGISTRY, event_bus=bus)
    return store, bus, runtime, query


def test_query_single_fact_type():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")

    results = query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE])

    assert [(item.actor_ref, item.payload["fatigue"]) for item in results] == [("actor:a", 0.2)]


def test_unregistered_fact_type_is_an_explicit_error():
    _store, _bus, _runtime, query = make_query()
    from app.models.fact_type import FactTypeRef

    try:
        query.query_facts([FactTypeRef("daily_rhythm.future_field", "daily_rhythm")])
    except ValueError as error:
        assert str(error) == "owner_fact_type_unregistered:daily_rhythm.future_field"
    else:
        raise AssertionError("unregistered fact type was silently ignored")


def test_query_multiple_fact_types():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")

    results = query.query_facts([
        FactType.DAILY_RHYTHM_FATIGUE_STATE,
        FactType.DAILY_RHYTHM_NEXT_DUE_TICK,
    ])

    assert {item.fact_type for item in results} == {
        FactType.DAILY_RHYTHM_FATIGUE_STATE,
        FactType.DAILY_RHYTHM_NEXT_DUE_TICK,
    }


def test_query_with_actor_filter():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")
    runtime.initialize("actor:b")

    results = query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE], actor_refs=["actor:b"])

    assert [item.actor_ref for item in results] == ["actor:b"]


def test_query_at_revision():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.7}, tick=10, revision=1)

    result = query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE], at_revision=0)

    assert result[0].payload["fatigue"] == 0.2
    assert result[0].revision == 0


def test_query_by_source_event_uses_its_own_revision():
    store, _, runtime, query = make_query()
    runtime.initialize("actor:a")
    first = store.read_events()[0]
    runtime.publish_state("actor:a", {"fatigue": 0.7}, tick=10, revision=1)

    result = query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE], source_event_ref=first.event_id)

    assert [(item.source_event_ref, item.revision, item.payload) for item in result] == [
        (first.event_id, 0, {"fatigue": 0.2})
    ]


def test_audience_filtering():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")

    assert query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE], audience="public") == []
    assert query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE], audience="siming_internal")


def test_get_owner_for_fact_type():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")

    assert query.get_owner_for_fact_type(FactType.DAILY_RHYTHM_FATIGUE_STATE) == "daily_rhythm_runtime"


def test_get_owner_uses_the_committed_source_transaction():
    store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.6}, tick=60, revision=1)

    assert query.get_owner_for_fact_type(FactType.DAILY_RHYTHM_FATIGUE_STATE) == "daily_rhythm_runtime"


def test_owner_conflict_is_explicit():
    store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")
    stream_id = "daily-rhythm:actor:a"
    from app.gameplay.settlement_plan import build_atomic_event_batch

    batch = build_atomic_event_batch(
        command_id="shadow-fact",
        principal_ref="second_owner",
        stream_id=stream_id,
        expected_revision=store.get_stream_head(stream_id),
        event_specs=(("daily_rhythm.state_updated", {
            "actor_id": "actor:a",
            "state": {"fatigue": 0.9},
            "fact_types": [FactType.DAILY_RHYTHM_FATIGUE_STATE.value],
            "revision": 1,
            "tick": 1,
        }),),
        idempotency_key="shadow-fact",
        causation_id="shadow-fact",
        correlation_id="shadow-fact",
    )
    assert store.append_batch(batch).committed

    try:
        query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE], actor_refs=["actor:a"])
    except ValueError as error:
        assert str(error) == "owner_fact_owner_conflict:daily_rhythm.fatigue_state:actor:a"
    else:
        raise AssertionError("multiple owners were silently merged")


def test_subscribe_callback():
    _store, bus, runtime, query = make_query()
    received = []
    query.subscribe([FactType.DAILY_RHYTHM_FATIGUE_STATE], received.append)
    runtime.initialize("actor:a")

    assert len(received) == 1
    assert received[0].payload["fatigue"] == 0.2


def test_projection_includes_source_owner():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")

    assert query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE])[0].source_owner == "daily_rhythm_runtime"


def test_projection_includes_source_revision():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.5}, tick=10, revision=1)

    result = query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE])[0]

    assert result.revision == 1


def test_freshness_calculation():
    _store, _bus, runtime, query = make_query()
    runtime.initialize("actor:a")

    result = query.query_facts([FactType.DAILY_RHYTHM_FATIGUE_STATE])[0]

    assert result.freshness == "live"
    assert result.captured_at == 0
