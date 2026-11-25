from pathlib import Path
import pytest

from app.contracts.owner_fact_query import OwnerProjection
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.fact_type import FACT_TYPE_REGISTRY
from app.models.siming_heavenly_graph import GraphReaderContext, HeavenlyGraphScope, HeavenlyNodeQuery, NodeLookupQuery
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.owner_fact_query_impl import OwnerFactQueryImpl
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app import main
from app import config as config_module


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:authority",
        session_id="session:authority",
        story_branch_id="branch:main",
    )


class _FixtureOwnerFactQuery:
    def __init__(self, event: AuthorityEvent, *, owner: str | None = None, revision: int | None = None):
        self.event = event
        self.owner = owner or str(event.payload.get("owner_ref") or event.source.system)
        self.revision = revision

    def query_facts(self, fact_types, *, actor_refs=None, at_revision=None,
                    source_event_ref=None, audience="siming_internal"):
        declared = self.event.payload.get("fact_types", ())
        declared = set(declared) if isinstance(declared, (list, tuple)) and declared else {self.event.event_type}
        actor_ref = self.event.source.actor_id or ""
        revision = self.revision
        if revision is None:
            vector = self.event.payload.get("source_revision_vector", {})
            revision = max(vector.values(), default=0) if isinstance(vector, dict) else 0
        return [
            OwnerProjection(
                fact_type=fact_type,
                actor_ref=actor_ref,
                revision=revision,
                source_owner=self.owner,
                source_event_ref=self.event.event_id,
                event_type=self.event.event_type,
                captured_at=self.event.producer_ts,
                freshness="live",
                payload=dict(self.event.payload),
            )
            for fact_type in fact_types
            if fact_type.value in declared and (actor_refs is None or actor_ref in actor_refs)
        ]

    def get_owner_for_fact_type(self, _fact_type):
        return self.owner

    def subscribe(self, _fact_types, _callback, *, audience="siming_internal"):
        return "fixture-subscription"


def _projector(graph, event: AuthorityEvent, *, owner: str | None = None, revision: int | None = None):
    return HeavenlyAuthorityEventProjector(
        graph,
        _FixtureOwnerFactQuery(event, owner=owner, revision=revision),
        scope_resolver=lambda _event: _scope(),
    )


def _commit_authority_fact(store, event: AuthorityEvent):
    actor_id = event.source.actor_id or "unscoped"
    stream_id = f"owner:{event.source.system}:{actor_id}"
    payload = {**event.payload, "actor_id": actor_id}
    batch = build_atomic_event_batch(
        command_id=event.event_id,
        principal_ref=str(event.payload.get("owner_ref") or event.source.system),
        stream_id=stream_id,
        expected_revision=store.get_stream_head(stream_id),
        event_specs=((event.event_type, payload),),
        idempotency_key=event.event_id,
        causation_id=event.causation_id,
        correlation_id=event.correlation_id,
    )
    result = store.append_batch(batch)
    assert result.committed
    return store.get_event(result.committed_event_ids[0]).event_id


def _event() -> AuthorityEvent:
    return AuthorityEvent(
        event_id="esm_result_event:1",
        event_type="esm_result_event",
        producer_ts=1,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=AuthorityEventSource(layer="L1", system="esm", actor_id="char_b"),
        routing=AuthorityEventRouting(audience_mode="room", routing_mode="event_type", target_ids=["siming"]),
        priority="p1",
        durability="replayable",
        causation_id="cause:1",
        correlation_id="corr:1",
        payload={
            "result_id": "object:1",
            "owner_ref": "esm:world",
            "settlement_id": "settlement:1",
            "replay_ref": "global_sequence:1",
            "source_revision_vector": {"world": 4},
            "state": "open",
        },
    )


@pytest.mark.parametrize(
    ("event_type", "domain"),
    [
        ("gameplay.inventory.item_moved", "inventory"),
        ("constraint_state_event", "esm_world"),
        ("gameplay.organization.production_work_contribution_accepted", "organization"),
        ("gameplay.ownership.right_transferred", "ownership"),
        ("gameplay.economy.account_credited", "economy"),
        ("gameplay.survival.obligation_settled", "survival_body"),
        ("gameplay.resource.capability_committed", "resource_scene"),
        ("gameplay.scene.result_committed", "resource_scene"),
    ],
)
def test_authority_domain_event_maps_to_typed_projection_domain(
    tmp_path: Path, event_type: str, domain: str
) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / f"{domain}.sqlite3")
    event = _event().model_copy(update={"event_id": f"{event_type}:1", "event_type": event_type})
    projector = _projector(graph, event, owner=domain)
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    bus = InMemoryAuthorityEventBus()
    bus.subscribe("*", projector.project, excluded_event_types=frozenset({"population_cadence_event"}))
    assert projector._domain_for("gameplay.inventory.future_unlisted_event") is None
    assert projector._domain_for("population_cadence_event") == "population"
    bus.publish(event)
    nodes = graph.query_nodes(
        HeavenlyNodeQuery(scope=_scope(), valid_at=1, node_types=["causal_event"])
    )
    graph.close()
    assert len(nodes) == 1
    assert nodes[0].attributes["domain"] == domain


def test_committed_esm_event_is_projected_with_owner_source_and_replay(tmp_path: Path) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "authority.sqlite3")
    event = _event()
    projector = _projector(graph, event)
    projector.project(event)

    result = graph.query_semantic(
        NodeLookupQuery(
            context=GraphReaderContext(
                reader_principal="reader:siming",
                allowed_visibility_scopes=("siming_internal",),
                world_id="world:authority",
                session_id="session:authority",
                story_branch_id="branch:main",
                valid_at=1,
                recorded_at=1,
                policy_revision="policy:authority-graph:v1",
            ),
            scope=_scope(),
            node_types=["causal_event"],
            source_refs=["esm_result_event:1"],
        )
    )
    graph.close()

    assert len(result.nodes) == 1
    node = result.nodes[0]
    assert node.attributes["domain"] == "esm:world"
    assert node.attributes["owner_ref"] == "esm:world"
    assert node.attributes["replay_ref"] == "esm_result_event:1"
    assert node.attributes["source_revision_vector"] == {"esm:world": 4}
    assert "committed_payload" not in node.attributes
    assert node.semantic_metadata.source_event_refs == ("esm_result_event:1",)


@pytest.mark.parametrize("vector, expected", [({"world": 4}, 4), ({}, 0)])
def test_q2_projection_revision_never_uses_clock_or_global_sequence(tmp_path, vector, expected):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "revision.sqlite3")
    try:
        event = _event().model_copy(update={"producer_ts": 9000, "payload": {
            "source_revision_vector": vector, "global_sequence": 8000}})
        projector = _projector(graph, event, revision=expected)
        projector.project(event)
        node = graph.query_nodes(HeavenlyNodeQuery(scope=_scope(), valid_at=9000, node_types=["causal_event"]))[0]
        assert node.semantic_metadata.source_revision_vector.source_revision == expected
        assert node.attributes["source_revision_vector"] == {"esm": expected}
    finally:
        graph.close()


def test_new_fact_type_is_consumed_with_owner_revision(tmp_path):
    from app.gameplay.daily_rhythm_runtime import DailyRhythmRuntime, create_daily_rhythm_event_schema_registry
    from app.gameplay.event_store import GameplayEventStore
    from app.models.fact_type import FactType
    from app.services.authority_event_bus import InMemoryAuthorityEventBus

    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    bus = InMemoryAuthorityEventBus()
    runtime = DailyRhythmRuntime(bus, store=store)
    runtime.initialize("char_b")
    runtime.publish_state("char_b", {"next_due_tick": 43_200}, tick=60, revision=1)
    event = bus.list_events()[-1]
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "new-fact-type.sqlite3")
    projector = HeavenlyAuthorityEventProjector(
        graph,
        OwnerFactQueryImpl(store),
        scope_resolver=lambda _: _scope(),
    )

    projector.project(event)

    node = graph.query_nodes(HeavenlyNodeQuery(scope=_scope(), valid_at=60, node_types=["causal_event"]))[0]
    graph.close()
    assert node.attributes["fact_type"] == FactType.DAILY_RHYTHM_NEXT_DUE_TICK.value
    assert node.attributes["owner_ref"] == "daily_rhythm_runtime"
    assert node.attributes["source_revision"] == 1
    assert node.semantic_metadata.source_revision_vector.source_revision == 1


def test_application_authority_bus_projects_esm_event_to_shared_graph(tmp_path: Path) -> None:
    previous_path = main.settings.heavenly_graph_path
    main.settings = config_module.Settings(
        heavenly_graph_path=str(tmp_path / "application.sqlite3"),
        siming_heavenly_mode="off",
    )
    main.reset_runtime_state()
    try:
        event = _event()
        stored_event_id = _commit_authority_fact(main.gameplay_event_store, event)
        main.authority_event_bus.publish(event.model_copy(update={"event_id": stored_event_id}))
        result = main.heavenly_graph.query_nodes(
            HeavenlyNodeQuery(
                scope=HeavenlyGraphScope(
                    world_id="world:demo",
                    session_id="session:demo",
                    story_branch_id="branch:main",
                    room_id="room_demo",
                    scene_id="scene_demo",
                ),
                valid_at=100,
                node_types=["causal_event"],
            )
        )
        assert any(node.provenance.source_ref == stored_event_id for node in result)
    finally:
        main.close_runtime_resources()
        main.settings = config_module.Settings(heavenly_graph_path=previous_path)


def test_q2_application_subscribes_registered_gameplay_types_only(tmp_path):
    previous_settings = main.settings
    main.settings = config_module.Settings(heavenly_graph_path=str(tmp_path / "typed-subscription.sqlite3"),
                                          siming_heavenly_mode="off")
    main.reset_runtime_state()
    try:
        stored_event_ids = []
        for event_type in ("gameplay.inventory.item_instantiated@1", "gameplay.inventory.undeclared"):
            event = _event().model_copy(update={"event_id": f"event:{event_type}", "event_type": event_type})
            if FACT_TYPE_REGISTRY.from_event_type(event_type) is not None:
                stored_event_ids.append(_commit_authority_fact(main.gameplay_event_store, event))
                event = event.model_copy(update={"event_id": stored_event_ids[-1]})
            main.authority_event_bus.publish(event)
        nodes = main.heavenly_graph.query_nodes(HeavenlyNodeQuery(
            scope=main.siming_scope_for_event(_event()), valid_at=100, node_types=["causal_event"]))
        assert {node.provenance.source_ref for node in nodes} == set(stored_event_ids)
    finally:
        main.close_runtime_resources()
        main.settings = previous_settings


def test_no_wildcard_authority_graph_subscription(tmp_path):
    previous_settings = main.settings
    main.settings = config_module.Settings(
        heavenly_graph_path=str(tmp_path / "explicit-subscriptions.sqlite3"),
        siming_heavenly_mode="off",
    )
    main.reset_runtime_state()
    try:
        subscriptions = main.authority_event_bus._subscribers
        event_types = {getattr(event_type, "value", event_type) for event_type in subscriptions}
        assert "*" not in event_types
        assert "gameplay.*" not in event_types
        assert all(event_type != "*" and not event_type.endswith(".*") for event_type in event_types)
        import yaml

        manifest = yaml.safe_load(
            (Path(main.__file__).resolve().parents[1] / "assets" / "siming" / "subscriptions.yaml").read_text()
        )
        declared = {item["event_type"] for item in manifest["subscriptions"]}
        registered_gameplay = {
            event_type for event_type in FACT_TYPE_REGISTRY.event_types() if event_type.startswith("gameplay.")
        }
        assert registered_gameplay.issubset(declared)
    finally:
        main.close_runtime_resources()
        main.settings = previous_settings


def test_application_authority_bus_projects_daily_rhythm_owner_facts(tmp_path: Path) -> None:
    previous_path = main.settings.heavenly_graph_path
    main.settings = config_module.Settings(
        heavenly_graph_path=str(tmp_path / "daily-rhythm.sqlite3"),
        siming_heavenly_mode="off",
    )
    main.reset_runtime_state()
    try:
        from app.gameplay.daily_rhythm_runtime import DailyRhythmRuntime

        DailyRhythmRuntime(main.authority_event_bus, store=main.gameplay_event_store).initialize("char_a")
        nodes = main.heavenly_graph.query_nodes(
            HeavenlyNodeQuery(
                scope=HeavenlyGraphScope(
                    world_id="world:demo",
                    session_id="session:demo",
                    story_branch_id="branch:main",
                    room_id="room:population",
                    scene_id="scene:population",
                ),
                valid_at=0,
                node_types=["causal_event"],
            )
        )
        assert {node.attributes["fact_type"] for node in nodes} == {
            "daily_rhythm.fatigue_state",
            "daily_rhythm.need_pressure_state",
            "daily_rhythm.starvation_credit_state",
            "daily_rhythm.activity_phase_state",
            "daily_rhythm.next_due_tick",
            "daily_rhythm.last_update_tick",
        }
        assert all(node.attributes["owner_ref"] == "daily_rhythm_runtime" for node in nodes)
        assert all(node.attributes["source_revision"] == 0 for node in nodes)
    finally:
        main.close_runtime_resources()
        main.settings = config_module.Settings(heavenly_graph_path=previous_path)


def test_authority_correction_projection_retains_correction_lineage(tmp_path: Path) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "authority-correction.sqlite3")
    event = _event().model_copy(
        update={
            "event_id": "esm_result_event:correction:2",
            "producer_ts": 2,
            "payload": {
                **_event().payload,
                "correction_target_id": "esm_result_event:1",
                "correction_target_revision": 1,
                "correction_kind": "corrected",
                "correction_source_refs": ["authority:correction:2"],
                "source_ref_lineage": ["esm_result_event:1"],
            },
        }
    )
    projector = _projector(graph, event)
    projector.project(event)
    node = graph.query_nodes(
        HeavenlyNodeQuery(scope=_scope(), valid_at=2, node_types=["causal_event"])
    )[0]
    graph.close()

    assert node.attributes["correction_target_id"] == "esm_result_event:1"
    assert node.attributes["correction_kind"] == "corrected"
    assert node.attributes["correction_source_refs"] == ["authority:correction:2"]
    assert node.provenance.source_ref_lineage == ["esm_result_event:1"]


def test_application_bus_projects_all_authority_domains_to_shared_graph(tmp_path: Path) -> None:
    previous_path = main.settings.heavenly_graph_path
    main.settings = config_module.Settings(
        heavenly_graph_path=str(tmp_path / "authority-all-domains.sqlite3"),
        siming_heavenly_mode="off",
    )
    events = [
        ("esm_result_event:all", "esm_result_event", "esm_world"),
        ("gameplay.inventory.item_moved:all", "gameplay.inventory.item_moved", "inventory"),
        ("gameplay.ownership.right_transferred:all", "gameplay.ownership.right_transferred", "ownership"),
        ("gameplay.economy.account_credited:all", "gameplay.economy.account_credited", "economy"),
        ("gameplay.survival.body_changed:all", "gameplay.survival.body_changed", "survival_body"),
        ("gameplay.resource.capability_committed:all", "gameplay.resource.capability_committed", "resource_scene"),
        ("gameplay.scene.result_committed:all", "gameplay.scene.result_committed", "resource_scene"),
    ]
    stored_event_ids = []
    main.reset_runtime_state()
    try:
        for index, (event_id, event_type, _domain) in enumerate(events, start=1):
            event = _event().model_copy(
                    update={
                        "event_id": event_id,
                        "event_type": event_type,
                        "producer_ts": index,
                        "payload": {
                            **_event().payload,
                            "owner_ref": f"owner:{event_type}",
                            "replay_ref": f"replay:{index}",
                            "source_revision_vector": {"domain": index},
                        },
                    }
                )
            stored_event_ids.append(_commit_authority_fact(main.gameplay_event_store, event))
            main.authority_event_bus.publish(event.model_copy(update={"event_id": stored_event_ids[-1]}))
        nodes = main.heavenly_graph.query_nodes(
            HeavenlyNodeQuery(
                scope=HeavenlyGraphScope(
                    world_id="world:demo",
                    session_id="session:demo",
                    story_branch_id="branch:main",
                    room_id="room_demo",
                    scene_id="scene_demo",
                ),
                valid_at=100,
                node_types=["causal_event"],
                limit=None,
            )
        )
        projected = {node.provenance.source_ref: node for node in nodes}
        assert len(projected) >= len(events)
        for (_event_id, event_type, _domain), stored_event_id in zip(events, stored_event_ids, strict=True):
            node = projected[stored_event_id]
            assert node.attributes["domain"] == f"owner:{event_type}"
            assert node.attributes["owner_ref"].startswith("owner:")
            assert node.attributes["replay_ref"] == stored_event_id
            assert node.attributes["source_revision_vector"]
    finally:
        main.close_runtime_resources()
        main.settings = config_module.Settings(heavenly_graph_path=previous_path)
