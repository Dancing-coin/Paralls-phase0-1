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
    HeavenlyGraphCheckpointConflict,
    HeavenlyGraphCheckpointNotFound,
    HeavenlyGraphIdempotencyConflict,
    HeavenlyGraphPort,
    HeavenlyGraphReferentialIntegrityError,
    HeavenlyGraphRevisionConflict,
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

    def test_node_refs_are_collision_safe_across_complete_scopes(self) -> None:
        graph = self.make_graph()
        scopes = [
            HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
                room_id=None,
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
                room_id="_",
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:a:b",
                session_id="session:c",
                story_branch_id="branch:main",
                room_id="room:demo",
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:a",
                session_id="b:session:c",
                story_branch_id="branch:main",
                room_id="room:demo",
                scene_id="scene:demo",
            ),
        ]
        node_refs: list[str] = []

        for index, scope in enumerate(scopes):
            node = graph_node(node_id="fact:shared").model_copy(
                update={"scope": scope},
                deep=True,
            )
            result = graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id=f"graph_tx:node-ref:{index}",
                    idempotency_key=f"authority:event:node-ref:{index}",
                    scope=scope,
                    nodes=[node],
                )
            )
            node_refs.append(result.node_refs[0])

        assert all(
            ref.startswith("heavenly_graph_node:") for ref in node_refs
        )
        assert len(set(node_refs)) == len(scopes)

    def test_relation_refs_are_collision_safe_across_complete_scopes(
        self,
    ) -> None:
        graph = self.make_graph()
        scopes = [
            HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
                room_id=None,
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
                room_id="_",
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:a:b",
                session_id="session:c",
                story_branch_id="branch:main",
                room_id="room:demo",
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:a",
                session_id="b:session:c",
                story_branch_id="branch:main",
                room_id="room:demo",
                scene_id="scene:demo",
            ),
        ]
        relation_refs: list[str] = []

        for index, scope in enumerate(scopes):
            source = graph_node(node_id="fact:source").model_copy(
                update={"scope": scope},
                deep=True,
            )
            target = graph_node(node_id="fact:target").model_copy(
                update={"scope": scope},
                deep=True,
            )
            relation = graph_relation(
                relation_id="relation:shared",
                source_node_id=source.node_id,
                target_node_id=target.node_id,
            ).model_copy(update={"scope": scope}, deep=True)
            result = graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id=f"graph_tx:relation-ref:{index}",
                    idempotency_key=(
                        f"authority:event:relation-ref:{index}"
                    ),
                    scope=scope,
                    nodes=[source, target],
                    relations=[relation],
                )
            )
            relation_refs.append(result.relation_refs[0])

        assert all(
            ref.startswith("heavenly_graph_relation:")
            for ref in relation_refs
        )
        assert len(set(relation_refs)) == len(scopes)

    def test_node_revision_rejects_decreasing_recorded_at_atomically(
        self,
    ) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:node-recorded-at:v1",
                idempotency_key="authority:event:node-recorded-at:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        valid_from=0,
                        recorded_at=20,
                    )
                ],
            )
        )

        with pytest.raises(
            HeavenlyGraphRevisionConflict,
            match="recorded_at .* lower than predecessor",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:node-recorded-at:v2",
                    idempotency_key="authority:event:node-recorded-at:v2",
                    scope=scope,
                    nodes=[
                        graph_node(
                            node_id="fact:lamp",
                            state="destroyed",
                            valid_from=0,
                            recorded_at=10,
                            revision=2,
                            supersedes_revision=1,
                        )
                    ],
                )
            )

        current = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=20,
        )
        stored = graph.query_nodes(HeavenlyNodeQuery(scope=scope, valid_at=20))

        assert current is not None and current.revision == 1
        assert [node.revision for node in stored] == [1]

    def test_relation_revision_rejects_decreasing_recorded_at_atomically(
        self,
    ) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:relation-recorded-at:v1",
                idempotency_key="authority:event:relation-recorded-at:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:source",
                        valid_from=0,
                        recorded_at=5,
                    ),
                    graph_node(
                        node_id="fact:target",
                        valid_from=0,
                        recorded_at=5,
                    ),
                ],
                relations=[
                    graph_relation(
                        relation_id="relation:cause",
                        source_node_id="fact:source",
                        target_node_id="fact:target",
                        valid_from=0,
                        recorded_at=20,
                    )
                ],
            )
        )

        with pytest.raises(
            HeavenlyGraphRevisionConflict,
            match="recorded_at .* lower than predecessor",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:relation-recorded-at:v2",
                    idempotency_key="authority:event:relation-recorded-at:v2",
                    scope=scope,
                    relations=[
                        graph_relation(
                            relation_id="relation:cause",
                            source_node_id="fact:source",
                            target_node_id="fact:target",
                            valid_from=0,
                            recorded_at=10,
                            revision=2,
                            supersedes_revision=1,
                        )
                    ],
                )
            )

        current = graph.get_relation(
            relation_id="relation:cause",
            scope=scope,
            valid_at=20,
        )
        stored = graph.query_relations(
            HeavenlyRelationQuery(scope=scope, valid_at=20)
        )

        assert current is not None and current.revision == 1
        assert [relation.revision for relation in stored] == [1]

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

    def test_checkpoint_is_immutable_after_later_writes(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:v1",
                idempotency_key="authority:event:checkpoint:v1",
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
        checkpoint = graph.create_checkpoint(
            checkpoint_id="checkpoint:before-destruction",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:v2",
                idempotency_key="authority:event:checkpoint:v2",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="destroyed",
                        valid_from=0,
                        recorded_at=30,
                        revision=2,
                        supersedes_revision=1,
                        source_ref="authority:event:checkpoint:v2",
                    )
                ],
            )
        )

        snapshot = graph.read_checkpoint(checkpoint.checkpoint_ref)
        current = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=20,
            recorded_at=40,
        )

        assert snapshot.nodes[0].revision == 1
        assert snapshot.nodes[0].attributes["state"] == "dim"
        assert current is not None and current.revision == 2

    def test_checkpoint_creation_is_idempotent_for_same_coordinates(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:idempotent",
                idempotency_key="authority:event:checkpoint:idempotent",
                scope=scope,
                nodes=[graph_node(node_id="fact:lamp")],
            )
        )

        first = graph.create_checkpoint(
            checkpoint_id="checkpoint:stable",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )
        second = graph.create_checkpoint(
            checkpoint_id="checkpoint:stable",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )

        assert first == second

    def test_checkpoint_id_reuse_with_different_coordinates_is_rejected(
        self,
    ) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.create_checkpoint(
            checkpoint_id="checkpoint:conflict",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )

        with pytest.raises(
            HeavenlyGraphCheckpointConflict,
            match="different coordinates",
        ):
            graph.create_checkpoint(
                checkpoint_id="checkpoint:conflict",
                scope=scope,
                valid_at=21,
                recorded_at=20,
            )

    def test_unknown_checkpoint_ref_is_rejected(self) -> None:
        graph = self.make_graph()

        with pytest.raises(
            HeavenlyGraphCheckpointNotFound,
            match="was not found",
        ):
            graph.read_checkpoint("heavenly_graph_checkpoint:missing")

    def test_checkpoint_refs_isolate_collision_prone_complete_scopes(
        self,
    ) -> None:
        graph = self.make_graph()
        scopes = [
            HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
                room_id=None,
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
                room_id="_",
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:a:b",
                session_id="session:c",
                story_branch_id="branch:main",
                room_id="room:demo",
                scene_id="scene:demo",
            ),
            HeavenlyGraphScope(
                world_id="world:a",
                session_id="b:session:c",
                story_branch_id="branch:main",
                room_id="room:demo",
                scene_id="scene:demo",
            ),
        ]
        states = ["none", "underscore", "world-delimiter", "session-delimiter"]
        checkpoint_refs: list[str] = []

        for index, (scope, state) in enumerate(zip(scopes, states, strict=True)):
            node = graph_node(
                node_id="fact:scope-specific",
                state=state,
            ).model_copy(update={"scope": scope}, deep=True)
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id=f"graph_tx:checkpoint:scope:{index}",
                    idempotency_key=f"authority:event:checkpoint:scope:{index}",
                    scope=scope,
                    nodes=[node],
                )
            )
            checkpoint = graph.create_checkpoint(
                checkpoint_id="checkpoint:scope:shared",
                scope=scope,
                valid_at=20,
                recorded_at=20,
            )
            checkpoint_refs.append(checkpoint.checkpoint_ref)

        assert len(set(checkpoint_refs)) == len(scopes)
        for checkpoint_ref, scope, state in zip(
            checkpoint_refs,
            scopes,
            states,
            strict=True,
        ):
            snapshot = graph.read_checkpoint(checkpoint_ref)
            assert snapshot.checkpoint.scope == scope
            assert snapshot.nodes[0].attributes["state"] == state

    def test_checkpoint_captures_all_entities_in_deterministic_order(
        self,
    ) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        node_ids = [f"fact:{index:03d}" for index in range(105)]
        relation_ids = [f"relation:{index:03d}" for index in range(104)]
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:large",
                idempotency_key="authority:event:checkpoint:large",
                scope=scope,
                nodes=[
                    graph_node(node_id=node_id)
                    for node_id in reversed(node_ids)
                ],
                relations=[
                    graph_relation(
                        relation_id=relation_id,
                        source_node_id=node_ids[index],
                        target_node_id=node_ids[index + 1],
                    )
                    for index, relation_id in reversed(
                        list(enumerate(relation_ids))
                    )
                ],
            )
        )

        checkpoint = graph.create_checkpoint(
            checkpoint_id="checkpoint:large",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )
        snapshot = graph.read_checkpoint(checkpoint.checkpoint_ref)

        assert [node.node_id for node in snapshot.nodes] == node_ids
        assert [relation.relation_id for relation in snapshot.relations] == (
            relation_ids
        )

    def test_checkpoint_read_returns_deep_copies(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:deep-copy",
                idempotency_key="authority:event:checkpoint:deep-copy",
                scope=scope,
                nodes=[graph_node(node_id="fact:lamp", state="dim")],
            )
        )
        checkpoint = graph.create_checkpoint(
            checkpoint_id="checkpoint:deep-copy",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )

        first = graph.read_checkpoint(checkpoint.checkpoint_ref)
        first.nodes[0].attributes["state"] = "mutated_by_caller"
        second = graph.read_checkpoint(checkpoint.checkpoint_ref)

        assert second.nodes[0].attributes["state"] == "dim"

    def test_checkpoint_recorded_at_change_is_rejected(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.create_checkpoint(
            checkpoint_id="checkpoint:recorded-at-conflict",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )

        with pytest.raises(
            HeavenlyGraphCheckpointConflict,
            match="different coordinates",
        ):
            graph.create_checkpoint(
                checkpoint_id="checkpoint:recorded-at-conflict",
                scope=scope,
                valid_at=20,
                recorded_at=21,
            )
