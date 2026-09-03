from pydantic import TypeAdapter

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphReaderContext,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    NodeLookupQuery,
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
            semantic_metadata=GraphSemanticMetadata(
                record_kind=("fact" if provenance.source_kind in {"authority_event", "world_result", "esm_result"} else "projection"),
                visibility_scope="siming_internal",
                derivation_kind=("authority" if provenance.source_kind in {"authority_event", "world_result", "esm_result"} else "projection"),
                source_event_refs=(provenance.source_ref,),
                policy_revision="policy:v1",
                scope_digest="scope:siming-heavenly",
            ),
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
        nodes = self._semantic_nodes(scope=scope, valid_at=valid_at, recorded_at=recorded_at, node_ids=[entry_id], limit=1)
        node = nodes[0] if nodes else None
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
        node = self.get_entry_node(scope=scope, entry_id=entry_id, valid_at=valid_at)
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
        nodes = self._semantic_nodes(scope=scope, valid_at=valid_at, recorded_at=recorded_at, node_types=[f"memory:{domain}"], limit=1000)
        return [
            self._entry_adapter.validate_python(node.attributes)
            for node in sorted(nodes, key=lambda node: node.node_id)
        ]

    def get_entry_node(self, *, scope: HeavenlyGraphScope, entry_id: str, valid_at: int, recorded_at: int | None = None) -> HeavenlyGraphNode | None:
        nodes = self._semantic_nodes(scope=scope, valid_at=valid_at, recorded_at=recorded_at, node_ids=[entry_id], limit=1)
        return nodes[0] if nodes else None

    def _semantic_nodes(self, *, scope: HeavenlyGraphScope, valid_at: int, recorded_at: int | None, node_ids: list[str] | None = None, node_types: list[str] | None = None, limit: int) -> list[HeavenlyGraphNode]:
        query = NodeLookupQuery(
            context=self._reader_context(scope, valid_at, recorded_at),
            scope=scope,
            node_ids=node_ids or [],
            node_types=node_types or [],
            limit=limit,
        )
        semantic_reader = getattr(self._graph, "query_semantic", None)
        if callable(semantic_reader):
            return semantic_reader(query).nodes
        return self._graph.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                node_ids=node_ids or [],
                node_types=node_types or [],
                limit=limit,
            )
        )

    @staticmethod
    def _reader_context(scope: HeavenlyGraphScope, valid_at: int, recorded_at: int | None) -> GraphReaderContext:
        return GraphReaderContext(
            reader_principal="reader:siming",
            allowed_visibility_scopes=("siming_internal", "authority_only", "branch_only"),
            world_id=scope.world_id,
            session_id=scope.session_id,
            story_branch_id=scope.story_branch_id,
            valid_at=valid_at,
            recorded_at=recorded_at,
            policy_revision="policy:v1",
        )

    @staticmethod
    def _require_heavenly_scope(scope: HeavenlyGraphScope) -> None:
        if scope.graph_namespace != "siming_heavenly" or scope.owner_actor_id is not None:
            raise ValueError("Siming memory requires siming_heavenly scope")
