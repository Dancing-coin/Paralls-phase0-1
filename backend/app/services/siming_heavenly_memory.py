from pydantic import TypeAdapter

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
)
from app.models.siming_heavenly_memory import SimingHeavenlyMemoryEntry
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


class SimingHeavenlyMemoryService:
    def __init__(self, graph: HeavenlyGraphPort) -> None:
        self._graph = graph
        self._entry_adapter = TypeAdapter(SimingHeavenlyMemoryEntry)

    def write_entry(
        self,
        *,
        scope: HeavenlyGraphScope,
        entry: SimingHeavenlyMemoryEntry,
        validity: GraphValidity,
        recorded_at: int,
        revision: int,
        supersedes_revision: int | None,
        provenance: GraphProvenance,
        transaction_id: str,
        idempotency_key: str,
    ) -> HeavenlyGraphWriteResult:
        self._require_heavenly_scope(scope)
        node = HeavenlyGraphNode(
            node_id=entry.entry_id,
            node_type=f"memory:{entry.domain}",
            scope=scope,
            validity=validity,
            recorded_at=recorded_at,
            revision=revision,
            supersedes_revision=supersedes_revision,
            attributes=entry.model_dump(mode="json"),
            provenance=provenance,
        )
        batch = HeavenlyGraphWriteBatch(
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
            scope=scope,
            nodes=[node],
        )
        return self._graph.write_batch(batch)

    def get_entry(
        self,
        *,
        scope: HeavenlyGraphScope,
        entry_id: str,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> SimingHeavenlyMemoryEntry | None:
        self._require_heavenly_scope(scope)
        node = self._graph.get_node(
            node_id=entry_id,
            scope=scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )
        if node is None or not node.node_type.startswith("memory:"):
            return None
        return self._entry_adapter.validate_python(node.attributes)

    def entry_revision(
        self,
        *,
        scope: HeavenlyGraphScope,
        entry_id: str,
        valid_at: int,
    ) -> int | None:
        self._require_heavenly_scope(scope)
        node = self._graph.get_node(
            node_id=entry_id,
            scope=scope,
            valid_at=valid_at,
        )
        return None if node is None else node.revision

    def list_domain(
        self,
        scope: HeavenlyGraphScope,
        domain: str,
        *,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> list[SimingHeavenlyMemoryEntry]:
        self._require_heavenly_scope(scope)
        nodes = self._graph.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                node_types=[f"memory:{domain}"],
                limit=None,
            )
        )
        return [
            self._entry_adapter.validate_python(node.attributes)
            for node in sorted(nodes, key=lambda node: node.node_id)
        ]

    @staticmethod
    def _require_heavenly_scope(scope: HeavenlyGraphScope) -> None:
        if scope.graph_namespace != "siming_heavenly" or scope.owner_actor_id is not None:
            raise ValueError("Siming memory requires siming_heavenly scope")
