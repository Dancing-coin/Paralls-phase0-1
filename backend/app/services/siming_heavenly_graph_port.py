from typing import Protocol

from app.models.siming_heavenly_graph import (
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
    pass


class HeavenlyGraphIdempotencyConflict(HeavenlyGraphError):
    pass


class HeavenlyGraphReferentialIntegrityError(HeavenlyGraphError):
    pass


class HeavenlyGraphCheckpointConflict(HeavenlyGraphError):
    pass


class HeavenlyGraphCheckpointNotFound(HeavenlyGraphError):
    pass


class HeavenlyGraphPort(Protocol):
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
