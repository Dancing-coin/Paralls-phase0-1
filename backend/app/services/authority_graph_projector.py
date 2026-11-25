from __future__ import annotations

from collections.abc import Callable

from app.contracts.owner_fact_query import OwnerFactQuery
from app.models.authority_event import AuthorityEvent
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType, FactTypeRef
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
    """Project owner facts into the Heavenly Graph without owning their state."""

    def __init__(
        self,
        graph: HeavenlyGraphPort,
        owner_query: OwnerFactQuery,
        *,
        scope_resolver: Callable[[AuthorityEvent], HeavenlyGraphScope],
    ) -> None:
        FACT_TYPE_REGISTRY.validate_event_type_coverage()
        self._graph = graph
        self._owner_query = owner_query
        self._scope_resolver = scope_resolver

    def project(self, event: AuthorityEvent) -> None:
        fact_types = self._extract_fact_types(event)
        if not fact_types:
            return
        projections = self._owner_query.query_facts(
            fact_types,
            source_event_ref=event.event_id,
            audience="siming_internal",
        )
        scope = self._scope_resolver(event)
        for projection in projections:
            self._write_owner_projection(event, scope, projection)

    def _write_owner_projection(self, event, scope, projection) -> None:
        lineage = projection.payload.get("source_ref_lineage", [])
        source_lineage = tuple(ref for ref in lineage if isinstance(ref, str)) if isinstance(lineage, (list, tuple)) else ()
        node = HeavenlyGraphNode(
                node_id=f"authority-projection:{projection.source_event_ref}:{projection.fact_type.value}",
                node_type="causal_event",
                scope=scope,
                validity=GraphValidity(valid_from=projection.captured_at),
                recorded_at=projection.captured_at,
                revision=1,
                attributes={
                    "domain": projection.source_owner,
                    "event_type": projection.event_type,
                    "owner_ref": projection.source_owner,
                    "fact_type": projection.fact_type.value,
                    "source_revision": projection.revision,
                    "source_revision_vector": {projection.source_owner: projection.revision},
                    "source_ref_lineage": list(source_lineage),
                    "correction_target_id": projection.payload.get("correction_target_id", ""),
                    "correction_target_revision": projection.payload.get("correction_target_revision"),
                    "correction_kind": projection.payload.get("correction_kind", ""),
                    "correction_source_refs": list(projection.payload.get("correction_source_refs", [])),
                    "settlement_id": projection.payload.get("settlement_id", ""),
                    "replay_ref": projection.source_event_ref,
                },
                provenance=GraphProvenance(
                    source_kind="siming_projection",
                    source_ref=projection.source_event_ref,
                    causation_id=projection.causation_id or event.causation_id,
                    correlation_id=projection.correlation_id or event.correlation_id,
                    producer_system=projection.source_owner,
                    actor_id=projection.actor_ref,
                    source_ref_lineage=source_lineage,
                ),
                semantic_metadata=GraphSemanticMetadata(
                    record_kind="projection",
                    visibility_scope="siming_internal",
                    derivation_kind="projection",
                    source_event_refs=(projection.source_event_ref,),
                    source_revision_vector=GraphRevisionVector(source_revision=projection.revision),
                    policy_revision="policy:authority-graph:v1",
                    scope_digest="scope:siming-authority",
                ),
        )
        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"authority-graph:{projection.source_event_ref}:{projection.fact_type.value}",
                idempotency_key=f"authority-graph:{projection.source_event_ref}:{projection.fact_type.value}",
                scope=scope,
                nodes=[node],
            )
        )

    @staticmethod
    def _extract_fact_types(event: AuthorityEvent) -> list[FactType | FactTypeRef]:
        declared = event.payload.get("fact_types", ())
        values = declared if isinstance(declared, (list, tuple)) and declared else (event.event_type,)
        result = []
        for value in values:
            if isinstance(value, str):
                fact_type = FACT_TYPE_REGISTRY.from_event_type(value)
                if fact_type is not None:
                    result.append(fact_type)
        return result

    @classmethod
    def _domain_for(cls, event_type: str) -> str | None:
        fact_type = FACT_TYPE_REGISTRY.from_event_type(event_type)
        return FACT_TYPE_REGISTRY.domain_for(fact_type) if fact_type is not None else None


__all__ = ["HeavenlyAuthorityEventProjector"]
