from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from app.models.authority_event import AuthorityEvent
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphRevisionVector,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


class HeavenlyAuthorityEventProjector:
    """Authority 事件图谱投影器：只派生 projection，不拥有领域事实。"""

    DOMAIN_BY_EVENT_PREFIX = {
        "esm_result_event": "esm_world",
        "constraint_state_event": "esm_world",
        "gameplay.inventory.": "inventory",
        "gameplay.ownership.": "ownership",
        "gameplay.economy.": "economy",
        "gameplay.survival.": "survival_body",
        "gameplay.resource.": "resource_scene",
        "gameplay.scene.": "resource_scene",
    }

    def __init__(
        self,
        graph: HeavenlyGraphPort,
        *,
        scope_resolver: Callable[[AuthorityEvent], HeavenlyGraphScope],
    ) -> None:
        self._graph = graph
        self._scope_resolver = scope_resolver

    def project(self, event: AuthorityEvent) -> None:
        scope = self._scope_resolver(event)
        domain = self._domain_for(event.event_type)
        if domain is None:
            return
        payload = deepcopy(event.payload)
        owner_ref = str(payload.get("owner_ref", "") or event.source.system)
        source_vector = payload.get("source_revision_vector", {})
        source_revision = int(event.payload.get("global_sequence", event.producer_ts) or 0)
        if isinstance(source_vector, dict):
            source_revision = max(
                [source_revision, *[int(value) for value in source_vector.values() if isinstance(value, int)]]
            )
        node = HeavenlyGraphNode(
            node_id=f"authority-projection:{event.event_id}",
            node_type="causal_event",
            scope=scope,
            validity=GraphValidity(valid_from=event.producer_ts),
            recorded_at=event.producer_ts,
            revision=1,
            attributes={
                "domain": domain,
                "event_type": event.event_type,
                "owner_ref": owner_ref,
                "source_revision_vector": deepcopy(source_vector) if isinstance(source_vector, dict) else {},
                "source_ref_lineage": list(payload.get("source_ref_lineage", [])) if isinstance(payload.get("source_ref_lineage", []), list) else [],
                "correction_target_id": payload.get("correction_target_id", ""),
                "correction_target_revision": payload.get("correction_target_revision"),
                "correction_kind": payload.get("correction_kind", ""),
                "correction_source_refs": list(payload.get("correction_source_refs", [])) if isinstance(payload.get("correction_source_refs", []), list) else [],
                "settlement_id": payload.get("settlement_id", ""),
                "replay_ref": payload.get("replay_ref", "") or f"global_sequence:{event.payload.get('global_sequence', event.producer_ts)}",
                "committed_payload": payload,
            },
            provenance=GraphProvenance(
                source_kind="authority_event",
                source_ref=event.event_id,
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
                producer_system=event.source.system,
                actor_id=event.source.actor_id,
                source_ref_lineage=tuple(str(ref) for ref in payload.get("source_ref_lineage", []) if isinstance(ref, str)),
            ),
            semantic_metadata=GraphSemanticMetadata(
                record_kind="projection",
                visibility_scope="siming_internal",
                derivation_kind="authority",
                source_event_refs=(event.event_id,),
                source_revision_vector=GraphRevisionVector(source_revision=source_revision),
                policy_revision="policy:authority-graph:v1",
                scope_digest="scope:siming-authority",
            ),
        )
        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"authority-graph:{event.event_id}",
                idempotency_key=f"authority-graph:{event.event_id}",
                scope=scope,
                nodes=[node],
            )
        )

    @classmethod
    def _domain_for(cls, event_type: str) -> str | None:
        if event_type in cls.DOMAIN_BY_EVENT_PREFIX:
            return cls.DOMAIN_BY_EVENT_PREFIX[event_type]
        for prefix, domain in cls.DOMAIN_BY_EVENT_PREFIX.items():
            if event_type.startswith(prefix):
                return domain
        return None


__all__ = ["HeavenlyAuthorityEventProjector"]
