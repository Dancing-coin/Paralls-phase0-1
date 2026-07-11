from abc import ABC, abstractmethod

import pytest

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
)
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphPort,
    HeavenlyGraphReferentialIntegrityError,
)


def graph_scope(*, branch_id: str = "branch:main") -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id=branch_id,
        room_id="room_demo",
        scene_id="scene_demo",
    )


def graph_provenance(*, source_ref: str = "authority:event:1") -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=source_ref,
        causation_id="cause:1",
        correlation_id="corr:1",
        producer_system="system_l6",
        evidence_refs=[source_ref],
    )


def graph_node(
    *,
    node_id: str,
    branch_id: str = "branch:main",
    state: str = "dim",
    valid_from: int = 10,
    valid_to: int | None = None,
    recorded_at: int = 12,
    revision: int = 1,
    supersedes_revision: int | None = None,
    source_ref: str = "authority:event:1",
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type="world_fact",
        scope=graph_scope(branch_id=branch_id),
        validity=GraphValidity(valid_from=valid_from, valid_to=valid_to),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"state": state},
        provenance=graph_provenance(source_ref=source_ref),
    )


def graph_relation(
    *,
    relation_id: str,
    source_node_id: str,
    target_node_id: str,
    branch_id: str = "branch:main",
    valid_from: int = 10,
    recorded_at: int = 12,
    revision: int = 1,
    supersedes_revision: int | None = None,
) -> HeavenlyGraphRelation:
    return HeavenlyGraphRelation(
        relation_id=relation_id,
        relation_type="caused_by",
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        scope=graph_scope(branch_id=branch_id),
        validity=GraphValidity(valid_from=valid_from),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={},
        provenance=graph_provenance(source_ref=f"authority:{relation_id}"),
    )


class HeavenlyGraphContract(ABC):
    @abstractmethod
    def make_graph(self) -> HeavenlyGraphPort:
        raise NotImplementedError

    def test_basic_write_read_returns_deep_copies(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        node = graph_node(node_id="fact:lamp")

        result = graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:basic",
                idempotency_key="authority:event:basic",
                scope=scope,
                nodes=[node],
            )
        )
        loaded = graph.get_node(node_id="fact:lamp", scope=scope, valid_at=20)

        assert result.applied is True
        assert result.replayed is False
        assert loaded is not None
        assert loaded.attributes["state"] == "dim"

        loaded.attributes["state"] = "mutated_by_caller"
        reloaded = graph.get_node(node_id="fact:lamp", scope=scope, valid_at=20)
        assert reloaded is not None
        assert reloaded.attributes["state"] == "dim"

    def test_same_node_id_is_isolated_by_story_branch(self) -> None:
        graph = self.make_graph()
        main_scope = graph_scope(branch_id="branch:main")
        other_scope = graph_scope(branch_id="branch:other")

        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:main",
                idempotency_key="authority:event:main",
                scope=main_scope,
                nodes=[graph_node(node_id="fact:lamp", state="dim")],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:other",
                idempotency_key="authority:event:other",
                scope=other_scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        branch_id="branch:other",
                        state="destroyed",
                    )
                ],
            )
        )

        main = graph.get_node(node_id="fact:lamp", scope=main_scope, valid_at=20)
        other = graph.get_node(node_id="fact:lamp", scope=other_scope, valid_at=20)

        assert main is not None and main.attributes["state"] == "dim"
        assert other is not None and other.attributes["state"] == "destroyed"

    def test_relation_query_is_deterministic(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        nodes = [
            graph_node(node_id="fact:cause"),
            graph_node(node_id="fact:effect"),
        ]
        relations = [
            graph_relation(
                relation_id="relation:z",
                source_node_id="fact:effect",
                target_node_id="fact:cause",
            ),
            graph_relation(
                relation_id="relation:a",
                source_node_id="fact:cause",
                target_node_id="fact:effect",
            ),
        ]

        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:relations",
                idempotency_key="authority:event:relations",
                scope=scope,
                nodes=nodes,
                relations=relations,
            )
        )

        loaded = graph.query_relations(
            HeavenlyRelationQuery(scope=scope, valid_at=20)
        )

        assert [relation.relation_id for relation in loaded] == [
            "relation:a",
            "relation:z",
        ]

    def test_node_query_filters_type_and_limit(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:query",
                idempotency_key="authority:event:query",
                scope=scope,
                nodes=[
                    graph_node(node_id="fact:b"),
                    graph_node(node_id="fact:a"),
                ],
            )
        )

        loaded = graph.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=20,
                node_types=["world_fact"],
                limit=1,
            )
        )

        assert [node.node_id for node in loaded] == ["fact:a"]
