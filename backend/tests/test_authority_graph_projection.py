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
