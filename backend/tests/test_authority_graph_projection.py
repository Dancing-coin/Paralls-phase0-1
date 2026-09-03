from pathlib import Path
import pytest

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_heavenly_graph import GraphReaderContext, HeavenlyGraphScope, HeavenlyNodeQuery, NodeLookupQuery
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app import main
from app import config as config_module


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:authority",
        session_id="session:authority",
        story_branch_id="branch:main",
    )


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
    projector = HeavenlyAuthorityEventProjector(graph, scope_resolver=lambda _event: _scope())
    event = _event().model_copy(update={"event_id": f"{event_type}:1", "event_type": event_type})
    projector.project(event)
    nodes = graph.query_nodes(
        HeavenlyNodeQuery(scope=_scope(), valid_at=1, node_types=["causal_event"])
    )
    graph.close()
    assert len(nodes) == 1
    assert nodes[0].attributes["domain"] == domain


def test_committed_esm_event_is_projected_with_owner_source_and_replay(tmp_path: Path) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "authority.sqlite3")
    projector = HeavenlyAuthorityEventProjector(graph, scope_resolver=lambda _event: _scope())
    projector.project(_event())

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
    assert node.attributes["domain"] == "esm_world"
    assert node.attributes["owner_ref"] == "esm:world"
    assert node.attributes["replay_ref"] == "global_sequence:1"
    assert node.attributes["source_revision_vector"] == {"world": 4}
    assert node.semantic_metadata.source_event_refs == ("esm_result_event:1",)


def test_application_authority_bus_projects_esm_event_to_shared_graph(tmp_path: Path) -> None:
    previous_path = main.settings.heavenly_graph_path
    main.settings = config_module.Settings(
        heavenly_graph_path=str(tmp_path / "application.sqlite3"),
        siming_heavenly_mode="off",
    )
    main.reset_runtime_state()
    try:
        main.authority_event_bus.publish(_event())
        result = main.heavenly_graph.query_nodes(
            HeavenlyNodeQuery(
                scope=HeavenlyGraphScope(
                    world_id="world:demo",
                    session_id="session:demo",
                    story_branch_id="branch:main",
                ),
                valid_at=1,
                node_types=["causal_event"],
            )
        )
        assert any(node.provenance.source_ref == "esm_result_event:1" for node in result)
    finally:
        main.close_runtime_resources()
        main.settings = config_module.Settings(heavenly_graph_path=previous_path)


def test_authority_correction_projection_retains_correction_lineage(tmp_path: Path) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "authority-correction.sqlite3")
    projector = HeavenlyAuthorityEventProjector(graph, scope_resolver=lambda _event: _scope())
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
    main.reset_runtime_state()
    try:
        for index, (event_id, event_type, _domain) in enumerate(events, start=1):
            main.authority_event_bus.publish(
                _event().model_copy(
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
            )
        nodes = main.heavenly_graph.query_nodes(
            HeavenlyNodeQuery(
                scope=HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main"),
                valid_at=10,
                node_types=["causal_event"],
                limit=None,
            )
        )
        projected = {node.provenance.source_ref: node for node in nodes}
        assert len(projected) >= len(events)
        for event_id, _event_type, domain in events:
            node = projected[event_id]
            assert node.attributes["domain"] == domain
            assert node.attributes["owner_ref"].startswith("owner:")
            assert node.attributes["replay_ref"].startswith("replay:")
            assert node.attributes["source_revision_vector"]
    finally:
        main.close_runtime_resources()
        main.settings = config_module.Settings(heavenly_graph_path=previous_path)
