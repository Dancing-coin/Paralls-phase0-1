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
    HeavenlyGraphIdempotencyConflict,
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
        batch = HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:basic",
            idempotency_key="authority:event:basic",
            scope=scope,
            nodes=[node],
        )

        result = graph.write_batch(batch)
        node.attributes["state"] = "mutated_original_node"
        batch.nodes[0].attributes["state"] = "mutated_batch_node"
        loaded = graph.get_node(node_id="fact:lamp", scope=scope, valid_at=20)

        assert result.applied is True
        assert result.replayed is False
        assert loaded is not None
        assert loaded.attributes["state"] == "dim"

        loaded.attributes["state"] = "mutated_by_caller"
        reloaded = graph.get_node(node_id="fact:lamp", scope=scope, valid_at=20)
        assert reloaded is not None
        assert reloaded.attributes["state"] == "dim"

    def test_write_revalidates_mutated_entity_scopes_before_writing(self) -> None:
        graph = self.make_graph()
        main_scope = graph_scope()
        other_scope = graph_scope(branch_id="branch:other")
        source = graph_node(node_id="fact:cause")
        target = graph_node(node_id="fact:effect")
        relation = graph_relation(
            relation_id="relation:cause-effect",
            source_node_id=source.node_id,
            target_node_id=target.node_id,
        )
        batch = HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:mutated-scope",
            idempotency_key="authority:event:mutated-scope",
            scope=main_scope,
            nodes=[source, target],
            relations=[relation],
        )
        target.scope = other_scope

        with pytest.raises(
            HeavenlyGraphReferentialIntegrityError,
            match="every entity must match the batch scope",
        ):
            graph.write_batch(batch)

        assert graph.query_nodes(
            HeavenlyNodeQuery(scope=main_scope, valid_at=20)
        ) == []
        assert graph.query_nodes(
            HeavenlyNodeQuery(scope=other_scope, valid_at=20)
        ) == []
        assert graph.query_relations(
            HeavenlyRelationQuery(scope=main_scope, valid_at=20)
        ) == []

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

    def test_node_query_respects_valid_and_recorded_time(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:node:v1",
                idempotency_key="authority:event:node:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="dim",
                        valid_from=0,
                        recorded_at=10,
                    )
                ],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:node:v2",
                idempotency_key="authority:event:node:v2",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="destroyed",
                        valid_from=50,
                        recorded_at=60,
                        revision=2,
                        supersedes_revision=1,
                        source_ref="authority:event:node:v2",
                    )
                ],
            )
        )

        before_valid_change = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=40,
            recorded_at=100,
        )
        before_recording = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=70,
            recorded_at=59,
        )
        after_recording = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=70,
            recorded_at=60,
        )

        assert before_valid_change is not None
        assert before_valid_change.revision == 1
        assert before_recording is not None
        assert before_recording.revision == 1
        assert after_recording is not None
        assert after_recording.revision == 2

    def test_relation_query_respects_valid_and_recorded_time(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:relation:v1",
                idempotency_key="authority:event:relation:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:cause",
                        valid_from=0,
                        recorded_at=10,
                    ),
                    graph_node(
                        node_id="fact:effect",
                        valid_from=0,
                        recorded_at=10,
                    ),
                ],
                relations=[
                    graph_relation(
                        relation_id="relation:cause",
                        source_node_id="fact:effect",
                        target_node_id="fact:cause",
                        valid_from=0,
                        recorded_at=10,
                    )
                ],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:relation:v2",
                idempotency_key="authority:event:relation:v2",
                scope=scope,
                relations=[
                    graph_relation(
                        relation_id="relation:cause",
                        source_node_id="fact:effect",
                        target_node_id="fact:cause",
                        valid_from=50,
                        recorded_at=60,
                        revision=2,
                        supersedes_revision=1,
                    )
                ],
            )
        )

        before = graph.get_relation(
            relation_id="relation:cause",
            scope=scope,
            valid_at=70,
            recorded_at=59,
        )
        after = graph.get_relation(
            relation_id="relation:cause",
            scope=scope,
            valid_at=70,
            recorded_at=60,
        )

        assert before is not None and before.revision == 1
        assert after is not None and after.revision == 2

    def test_relation_requires_endpoints_effective_at_relation_start(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()

        with pytest.raises(
            HeavenlyGraphReferentialIntegrityError,
            match="missing in batch scope",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:future-endpoint",
                    idempotency_key="authority:event:future-endpoint",
                    scope=scope,
                    nodes=[
                        graph_node(
                            node_id="fact:future",
                            valid_from=50,
                            recorded_at=10,
                        ),
                        graph_node(
                            node_id="fact:present",
                            valid_from=0,
                            recorded_at=10,
                        ),
                    ],
                    relations=[
                        graph_relation(
                            relation_id="relation:too-early",
                            source_node_id="fact:future",
                            target_node_id="fact:present",
                            valid_from=10,
                            recorded_at=12,
                        )
                    ],
                )
            )

    def test_relation_endpoint_can_use_effective_stored_revision(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:endpoints:v1",
                idempotency_key="authority:event:endpoints:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:source",
                        valid_from=0,
                        recorded_at=10,
                    ),
                    graph_node(
                        node_id="fact:target",
                        valid_from=0,
                        recorded_at=10,
                    ),
                ],
            )
        )

        result = graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:endpoints:v2",
                idempotency_key="authority:event:endpoints:v2",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:source",
                        valid_from=50,
                        recorded_at=60,
                        revision=2,
                        supersedes_revision=1,
                    )
                ],
                relations=[
                    graph_relation(
                        relation_id="relation:stored-endpoint",
                        source_node_id="fact:source",
                        target_node_id="fact:target",
                        valid_from=20,
                        recorded_at=30,
                    )
                ],
            )
        )

        loaded = graph.get_relation(
            relation_id="relation:stored-endpoint",
            scope=scope,
            valid_at=20,
            recorded_at=30,
        )

        assert result.applied is True
        assert loaded is not None
        assert loaded.relation_id == "relation:stored-endpoint"

    def test_identical_idempotency_replay_does_not_write_twice(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        batch = HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:idempotent",
            idempotency_key="authority:event:idempotent",
            scope=scope,
            nodes=[graph_node(node_id="fact:lamp")],
        )

        first = graph.write_batch(batch)
        second = graph.write_batch(batch.model_copy(deep=True))
        loaded = graph.query_nodes(
            HeavenlyNodeQuery(scope=scope, valid_at=20)
        )

        assert first.applied is True and first.replayed is False
        assert second.applied is False and second.replayed is True
        assert [node.revision for node in loaded] == [1]

    def test_idempotency_key_reuse_with_different_payload_is_rejected(
        self,
    ) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:original",
                idempotency_key="authority:event:shared",
                scope=scope,
                nodes=[graph_node(node_id="fact:lamp", state="dim")],
            )
        )

        with pytest.raises(
            HeavenlyGraphIdempotencyConflict,
            match="different payload",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:conflict",
                    idempotency_key="authority:event:shared",
                    scope=scope,
                    nodes=[
                        graph_node(
                            node_id="fact:other",
                            state="destroyed",
                        )
                    ],
                )
            )

    def test_invalid_relation_rolls_back_entire_batch(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()

        with pytest.raises(
            HeavenlyGraphReferentialIntegrityError,
            match="missing in batch scope",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:atomic",
                    idempotency_key="authority:event:atomic",
                    scope=scope,
                    nodes=[graph_node(node_id="fact:new")],
                    relations=[
                        graph_relation(
                            relation_id="relation:invalid",
                            source_node_id="fact:new",
                            target_node_id="fact:missing",
                        )
                    ],
                )
            )

        assert graph.get_node(
            node_id="fact:new",
            scope=scope,
            valid_at=20,
        ) is None

    def test_new_revision_does_not_mutate_old_provenance(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:provenance:v1",
                idempotency_key="authority:event:provenance:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        valid_from=0,
                        recorded_at=10,
                        source_ref="authority:event:old",
                    )
                ],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:provenance:v2",
                idempotency_key="authority:event:provenance:v2",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="destroyed",
                        valid_from=50,
                        recorded_at=60,
                        revision=2,
                        supersedes_revision=1,
                        source_ref="authority:event:new",
                    )
                ],
            )
        )

        old = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=20,
            recorded_at=100,
        )
        new = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=70,
            recorded_at=100,
        )

        assert old is not None
        assert old.provenance.source_ref == "authority:event:old"
        assert new is not None
        assert new.provenance.source_ref == "authority:event:new"

    def test_idempotency_keys_are_scoped_by_graph_scope(self) -> None:
        graph = self.make_graph()
        main_scope = graph_scope(branch_id="branch:main")
        other_scope = graph_scope(branch_id="branch:other")

        main = graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:scope:main",
                idempotency_key="authority:event:shared-id",
                scope=main_scope,
                nodes=[graph_node(node_id="fact:lamp", state="dim")],
            )
        )
        other = graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:scope:other",
                idempotency_key="authority:event:shared-id",
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

        assert main.applied is True
        assert other.applied is True
