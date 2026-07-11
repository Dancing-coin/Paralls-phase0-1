from typing import Protocol

from app.models.siming_heavenly_graph import (
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
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
