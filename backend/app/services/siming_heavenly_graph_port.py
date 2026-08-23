from typing import Protocol

from app.models.siming_heavenly_graph import (
    GraphBranchDiffQuery,
    GraphBranchDiffResult,
    GraphBranchForkRequest,
    GraphBranchLifecycleRequest,
    GraphCorrectionRequest,
    HeavenlyGraphQueryResult,
    HeavenlyGraphSemanticQuery,
    HeavenlyGraphCheckpointRef,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphSnapshot,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
    HeavenlySubgraphDirection,
    HeavenlySubgraphResult,
)


class HeavenlyGraphError(RuntimeError):
    pass


class HeavenlyGraphRevisionConflict(HeavenlyGraphError):
    def __init__(
        self,
        message: str,
        *,
        expected_revision_vector: object | None = None,
        current_revision_vector: object | None = None,
        affected_refs: list[str] | tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.expected_revision_vector = expected_revision_vector
        self.current_revision_vector = current_revision_vector
        self.affected_refs = tuple(affected_refs)


class HeavenlyGraphIdempotencyConflict(HeavenlyGraphError):
    pass


class HeavenlyGraphReferentialIntegrityError(HeavenlyGraphError):
    pass


class HeavenlyGraphCheckpointConflict(HeavenlyGraphError):
    pass


class HeavenlyGraphCheckpointNotFound(HeavenlyGraphError):
    pass


class HeavenlyGraphPort(Protocol):
    def fork_branch(
        self, request: GraphBranchForkRequest
    ) -> HeavenlyGraphWriteResult:
        raise NotImplementedError

    def diff_branches(
        self, query: GraphBranchDiffQuery
    ) -> GraphBranchDiffResult:
        raise NotImplementedError

    def lifecycle_branch(
        self, request: GraphBranchLifecycleRequest
    ) -> HeavenlyGraphWriteResult:
        raise NotImplementedError

    def correct(
        self,
        request: GraphCorrectionRequest,
    ) -> HeavenlyGraphWriteResult:
        raise NotImplementedError

    def query_semantic(
        self,
        query: HeavenlyGraphSemanticQuery,
    ) -> HeavenlyGraphQueryResult:
        raise NotImplementedError

    def has_idempotency_key(
        self,
        *,
        scope: HeavenlyGraphScope,
        idempotency_key: str,
    ) -> bool:
        raise NotImplementedError

    def write_batch(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> HeavenlyGraphWriteResult:
        raise NotImplementedError

    def get_node(
        self,
        *,
        node_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphNode | None:
        raise NotImplementedError

    def get_relation(
        self,
        *,
        relation_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphRelation | None:
        raise NotImplementedError

    def query_nodes(
        self,
        query: HeavenlyNodeQuery,
    ) -> list[HeavenlyGraphNode]:
        raise NotImplementedError

    def query_relations(
        self,
        query: HeavenlyRelationQuery,
    ) -> list[HeavenlyGraphRelation]:
        raise NotImplementedError

    def query_subgraph(
        self,
        *,
        scope: HeavenlyGraphScope,
        seed_node_ids: list[str],
        relation_types: list[str],
        direction: HeavenlySubgraphDirection,
        max_depth: int,
        valid_at: int,
        recorded_at: int | None,
        node_limit: int,
        relation_limit: int,
    ) -> HeavenlySubgraphResult:
        raise NotImplementedError

    def create_checkpoint(
        self,
        *,
        checkpoint_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int,
    ) -> HeavenlyGraphCheckpointRef:
        raise NotImplementedError

    def read_checkpoint(
        self,
        checkpoint_ref: str,
    ) -> HeavenlyGraphSnapshot:
        raise NotImplementedError

    def replay_from_checkpoint(
        self,
        checkpoint_ref: str,
        tail_batches: list[HeavenlyGraphWriteBatch],
    ) -> HeavenlyGraphSnapshot:
        raise NotImplementedError
