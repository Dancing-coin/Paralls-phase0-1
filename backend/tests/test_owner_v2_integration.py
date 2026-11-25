from app.gameplay.daily_rhythm_runtime import DailyRhythmRuntime, create_daily_rhythm_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType
from app.models.siming_event import SimingInput
from app.models.siming_heavenly_graph import HeavenlyGraphNode, HeavenlyGraphScope, HeavenlyNodeQuery
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.owner_fact_query_impl import OwnerFactQueryImpl
from app.services.siming_runtime import SimingRuntime


def test_owner_to_heavenly_graph_and_siming_read_pipeline():
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    bus = InMemoryAuthorityEventBus()
    owner = DailyRhythmRuntime(bus, store=store)
    owner.initialize("actor:a")
    owner.publish_state("actor:a", {"fatigue": 0.6}, tick=60, revision=1)
    query = OwnerFactQueryImpl(store, FACT_TYPE_REGISTRY)
    scope = HeavenlyGraphScope(world_id="world:test", session_id="session:test", story_branch_id="branch:main")
    graph = InMemoryHeavenlyGraphAdapter()
    projector = HeavenlyAuthorityEventProjector(graph, query, scope_resolver=lambda _: scope)
    projector.project(bus.list_events()[-1])

    node = graph.query_nodes(HeavenlyNodeQuery(scope=scope, valid_at=60, node_types=["causal_event"]))[0]
    assert node.attributes["owner_ref"] == "daily_rhythm_runtime"
    assert node.attributes["source_revision"] == 1
    assert "committed_payload" not in node.attributes

    runtime = SimingRuntime(owner_fact_query=query)
    event = bus.list_events()[-1]
    observed_event = event.model_copy(update={"event_type": "world_fact_event"})
    runtime.tick([SimingInput(input_type="world_fact_event", source_event=observed_event)])
    fact_types = [FactType.DAILY_RHYTHM_FATIGUE_STATE]
    expected = {FactType.DAILY_RHYTHM_FATIGUE_STATE: {"fatigue": 0.6}}
    assert runtime._state_tree.get_state("actor:a", fact_types) == expected
    assert runtime._global_situation.get_state("actor:a", fact_types) == expected
    assert runtime._narrative_core.get_state("actor:a", fact_types) == expected
