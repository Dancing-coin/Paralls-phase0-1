from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from threading import RLock

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphReaderContext,
    GraphRevisionVector,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    NodeLookupQuery,
)
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


class CharacterGraphContinuityStore:
    """角色连续性图谱存储：保存可重建状态快照，不接管 runtime owner。"""

    _MAX_TIME = 2**63 - 1

    def __init__(
        self,
        graph: HeavenlyGraphPort,
        *,
        scope_resolver: Callable[[str], HeavenlyGraphScope],
    ) -> None:
        self._graph = graph
        self._scope_resolver = scope_resolver
        self._lock = RLock()

    def write_snapshot(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        snapshot: dict[str, object],
        source_event_ref: str,
    ) -> None:
        with self._lock:
            scope = self._scope_for_actor(actor_id)
            node_id = f"actor-continuity:{actor_id}"
            previous = self._graph.get_node(
                node_id=node_id,
                scope=scope,
                valid_at=self._MAX_TIME,
            )
            if previous is not None and source_event_ref and source_event_ref in previous.semantic_metadata.source_event_refs:
                return
            recorded_at = max(producer_ts, previous.recorded_at if previous else 0)
            revision = previous.revision + 1 if previous else 1
            node = HeavenlyGraphNode(
                node_id=node_id,
                node_type="actor_view",
                scope=scope,
                validity=GraphValidity(valid_from=producer_ts),
                recorded_at=recorded_at,
                revision=revision,
                supersedes_revision=previous.revision if previous else None,
                attributes={
                    "state_kind": "character_continuity",
                    "actor_id": actor_id,
                    "snapshot": deepcopy(snapshot),
                },
                provenance=GraphProvenance(
                    source_kind="runtime_outcome",
                    source_ref=source_event_ref or node_id,
                    causation_id=source_event_ref or node_id,
                    correlation_id=source_event_ref or node_id,
                    producer_system="character_agent_runtime",
                    actor_id=actor_id,
                ),
                semantic_metadata=GraphSemanticMetadata(
                    record_kind="projection",
                    visibility_scope="actor_private",
                    derivation_kind="projection",
                    source_event_refs=(source_event_ref or node_id,),
                    source_revision_vector=GraphRevisionVector(source_revision=revision),
                    policy_revision="policy:character-continuity:v1",
                    scope_digest="scope:actor-private",
                ),
            )
            self._graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id=f"actor-continuity:{actor_id}:{producer_ts}",
                    idempotency_key=f"actor-continuity:{actor_id}:{source_event_ref or producer_ts}",
                    scope=scope,
                    nodes=[node],
                )
            )

    def read_snapshot(
        self,
        actor_id: str,
        *,
        valid_at: int | None = None,
    ) -> dict[str, object] | None:
        scope = self._scope_for_actor(actor_id)
        at = self._MAX_TIME if valid_at is None else valid_at
        result = self._graph.query_semantic(
            NodeLookupQuery(
                context=GraphReaderContext(
                    reader_principal=actor_id,
                    allowed_visibility_scopes=("actor_private",),
                    world_id=scope.world_id,
                    session_id=scope.session_id,
                    story_branch_id=scope.story_branch_id,
                    valid_at=at,
                    policy_revision="policy:character-continuity:v1",
                ),
                scope=scope,
                node_ids=[f"actor-continuity:{actor_id}"],
                node_types=["actor_view"],
                limit=1,
            )
        )
        if not result.nodes:
            return None
        snapshot = result.nodes[0].attributes.get("snapshot")
        return deepcopy(snapshot) if isinstance(snapshot, dict) else None

    def _scope_for_actor(self, actor_id: str) -> HeavenlyGraphScope:
        scope = self._scope_resolver(actor_id)
        if scope.graph_namespace != "actor_private" or scope.owner_actor_id != actor_id:
            raise ValueError("actor-private continuity scope owner must match actor")
        return scope


__all__ = ["CharacterGraphContinuityStore"]
