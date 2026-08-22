from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from threading import RLock

from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.higher_order_memory import (
    CharacterHigherOrderMemoryRecord,
)
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import (
    CharacterObservationMemoryRecord,
)
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
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
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


MemoryRecord = (
    CharacterEventMemoryRecord
    | CharacterObservationMemoryRecord
    | CharacterKnowledgeMemoryRecord
    | CharacterSocialMemoryRecord
    | CharacterHigherOrderMemoryRecord
)


class CharacterGraphMemoryStore:
    POOLS = (
        ("event", "event_memories", CharacterEventMemoryRecord),
        ("observation", "observation_memories", CharacterObservationMemoryRecord),
        ("knowledge", "knowledge_memories", CharacterKnowledgeMemoryRecord),
        ("social", "social_memories", CharacterSocialMemoryRecord),
        ("higher_order", "higher_order_memories", CharacterHigherOrderMemoryRecord),
    )
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
        self._normalizer = CharacterAgentMemoryStore()
        self._source_batches: dict[
            tuple[str, str, str], tuple[dict[str, object], HeavenlyGraphWriteBatch]
        ] = {}

    @property
    def graph(self) -> HeavenlyGraphPort:
        return self._graph

    def write_event(self, event: dict[str, object]) -> None:
        with self._lock:
            actor_id = str(event.get("actor_id", "") or "")
            if not actor_id:
                return
            scope = self._scope_for_actor(actor_id)
            source_event_id = str(event.get("event_id", "") or "")
            source_key = (scope.model_dump_json(), actor_id, source_event_id)
            cached = self._source_batches.get(source_key)
            if cached is not None and cached[0] == event:
                self._graph.write_batch(cached[1])
                return
            already_deposited = bool(source_event_id) and self._has_source_event(
                scope,
                source_event_id,
            )
            self._normalizer.write_event(event)
            if source_event_id and not already_deposited:
                batch = self._deposit_bundle(
                    actor_id,
                    scope,
                    self._normalizer.retrieval_record_bundle(actor_id),
                    source_event_id,
                )
                if batch is not None:
                    self._source_batches[source_key] = (deepcopy(event), batch)

    def _has_source_event(
        self,
        scope: HeavenlyGraphScope,
        source_event_id: str,
    ) -> bool:
        nodes = self._graph.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=self._MAX_TIME,
                node_types=[f"actor_memory:{pool}" for pool, _field, _model in self.POOLS],
                limit=None,
            )
        )
        return any(
            node.provenance.source_ref == source_event_id
            for node in nodes
        )

    def retrieval_record_bundle(
        self,
        actor_id: str,
        *,
        story_branch_id: str | None = None,
        valid_at: int | None = None,
    ) -> CharacterMemoryRecordBundle:
        scope = self._scope_for_actor(actor_id)
        if story_branch_id is not None and story_branch_id != scope.story_branch_id:
            raise ValueError("story branch does not match actor-private scope")
        recall_time = (
            valid_at if valid_at is not None else self._latest_valid_time(scope)
        )
        values: dict[str, list[MemoryRecord]] = {}
        for pool, field, model in self.POOLS:
            nodes = self._graph.query_nodes(
                HeavenlyNodeQuery(
                    scope=scope,
                    valid_at=recall_time,
                    node_types=[f"actor_memory:{pool}"],
                    limit=None,
                )
            )
            records = [
                model.model_validate(node.attributes["record"])
                for node in nodes
                if "record" in node.attributes
            ]
            values[field] = sorted(
                records,
                key=lambda record: (
                    getattr(record, "world_ts", getattr(record, "producer_ts", 0)),
                    record.memory_id,
                ),
            )
        return CharacterMemoryRecordBundle(**values)

    def retrieval_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
        records = self.retrieval_record_bundle(actor_id)
        event_memories = [item.model_dump() for item in records.event_memories]
        observation_memories = [
            item.model_dump() for item in records.observation_memories
        ]
        knowledge_memories = [item.model_dump() for item in records.knowledge_memories]
        social_memories = [item.model_dump() for item in records.social_memories]
        higher_order_memories = [
            item.model_dump() for item in records.higher_order_memories
        ]
        working_memory = self._normalizer.retrieval_bundle(actor_id)["working_memory"]
        return {
            "working_memory": working_memory,
            "event_memories": event_memories,
            "observation_memories": observation_memories,
            "knowledge_memories": knowledge_memories,
            "social_memories": social_memories,
            "higher_order_memories": higher_order_memories,
            "episodic_memories": self._normalizer._legacy_episodic_memories(
                event_memories
            ),
            "relational_memories": self._normalizer._legacy_relational_memories(
                knowledge_memories
            ),
        }

    def working_memory_state(
        self,
        actor_id: str,
        private_snapshot: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | CharacterDynamicState | None = None,
    ) -> CharacterWorkingMemoryState:
        return self._normalizer.working_memory_state(
            actor_id,
            private_snapshot=private_snapshot,
            dynamic_state=dynamic_state,
        )

    def _scope_for_actor(self, actor_id: str) -> HeavenlyGraphScope:
        scope = self._scope_resolver(actor_id)
        if scope.graph_namespace != "actor_private" or scope.owner_actor_id != actor_id:
            raise ValueError("actor-private scope owner must match event actor")
        return scope

    def _deposit_bundle(
        self,
        actor_id: str,
        scope: HeavenlyGraphScope,
        bundle: CharacterMemoryRecordBundle,
        source_event_id: str,
    ) -> HeavenlyGraphWriteBatch | None:
        nodes: list[HeavenlyGraphNode] = []
        relations: list[HeavenlyGraphRelation] = []
        for pool, field, _ in self.POOLS:
            for record in getattr(bundle, field):
                if record.source_event_id != source_event_id:
                    continue
                memory_node = self._memory_node(pool, record, scope)
                nodes.append(memory_node)
                anchor = self._reference_anchor(pool, record, scope)
                if anchor is None:
                    continue
                anchor_node, relation = anchor
                if (
                    self._node_at(
                        scope,
                        anchor_node.node_id,
                        valid_at=relation.validity.valid_from,
                        recorded_at=relation.recorded_at,
                    )
                    is None
                ):
                    nodes.append(anchor_node)
                if (
                    self._relation_at(
                        scope,
                        relation.relation_id,
                        valid_at=relation.validity.valid_from,
                        recorded_at=relation.recorded_at,
                    )
                    is None
                ):
                    relations.append(relation)
        if not nodes and not relations:
            return None
        batch = HeavenlyGraphWriteBatch(
            transaction_id=f"character-memory:{actor_id}:{source_event_id}",
            idempotency_key=f"character-memory:{actor_id}:{source_event_id}",
            scope=scope,
            nodes=nodes,
            relations=relations,
        )
        self._graph.write_batch(batch)
        return batch

    def _memory_node(
        self,
        pool: str,
        record: MemoryRecord,
        scope: HeavenlyGraphScope,
    ) -> HeavenlyGraphNode:
        node_id = f"actor-memory:{pool}:{record.memory_id}"
        prior = self._latest_node(scope, node_id)
        timestamp = self._record_time(record)
        recorded_at = max(
            timestamp,
            prior.recorded_at if prior else 0,
            self._latest_recorded_at(scope),
        )
        return HeavenlyGraphNode(
            node_id=node_id,
            node_type=f"actor_memory:{pool}",
            scope=scope,
            validity=GraphValidity(valid_from=timestamp),
            recorded_at=recorded_at,
            revision=(prior.revision + 1) if prior else 1,
            supersedes_revision=prior.revision if prior else None,
            attributes={"record": record.model_dump(mode="json")},
            provenance=self._provenance(record, actor_id=record.actor_id),
        )

    def _reference_anchor(
        self,
        pool: str,
        record: MemoryRecord,
        scope: HeavenlyGraphScope,
    ) -> tuple[HeavenlyGraphNode, HeavenlyGraphRelation] | None:
        reference = self._record_reference(record)
        if reference is None:
            return None
        kind, reference_id = reference
        timestamp = self._record_time(record)
        anchor_id = f"actor-memory-anchor:{kind}:{reference_id}"
        prior_anchor = self._latest_node(scope, anchor_id)
        anchor_recorded_at = (
            max(
                timestamp,
                prior_anchor.recorded_at if prior_anchor else 0,
                self._latest_recorded_at(scope),
            )
        )
        relation_id = (
            f"actor-memory-relation:{pool}:{record.memory_id}:{kind}:{reference_id}"
        )
        prior_relation = self._latest_relation(scope, relation_id)
        relation_recorded_at = max(
            timestamp,
            anchor_recorded_at,
            prior_relation.recorded_at if prior_relation else 0,
            self._latest_recorded_at(scope),
        )
        anchor = HeavenlyGraphNode(
            node_id=anchor_id,
            node_type=f"actor_memory_anchor:{kind}",
            scope=scope,
            validity=GraphValidity(valid_from=timestamp),
            recorded_at=anchor_recorded_at,
            revision=(prior_anchor.revision + 1) if prior_anchor else 1,
            supersedes_revision=prior_anchor.revision if prior_anchor else None,
            attributes={"reference_id": reference_id},
            provenance=self._provenance(record, actor_id=record.actor_id),
        )
        return anchor, HeavenlyGraphRelation(
            relation_id=relation_id,
            relation_type=f"actor_memory:references_{kind}",
            source_node_id=f"actor-memory:{pool}:{record.memory_id}",
            target_node_id=anchor_id,
            scope=scope,
            validity=GraphValidity(valid_from=timestamp),
            recorded_at=relation_recorded_at,
            revision=(prior_relation.revision + 1) if prior_relation else 1,
            supersedes_revision=prior_relation.revision if prior_relation else None,
            provenance=self._provenance(record, actor_id=record.actor_id),
            attributes={},
        )

    def _record_reference(self, record: MemoryRecord) -> tuple[str, str] | None:
        if isinstance(record, CharacterObservationMemoryRecord):
            reference_id = record.observed_entity_id
        elif isinstance(record, CharacterSocialMemoryRecord):
            return "actor", record.entity_id
        elif isinstance(record, CharacterHigherOrderMemoryRecord):
            return "actor", record.subject_actor_id
        else:
            return None
        if reference_id.startswith(("char_", "actor:")):
            return "actor", reference_id
        if reference_id.startswith(("obj_", "object:")):
            return "object", reference_id
        return None

    def _provenance(self, record: MemoryRecord, *, actor_id: str) -> GraphProvenance:
        source_ref = record.source_event_id or record.memory_id
        return GraphProvenance(
            source_kind="character_memory",
            source_ref=source_ref,
            causation_id=source_ref,
            correlation_id=source_ref,
            producer_system="character_agent",
            actor_id=actor_id,
        )

    def _latest_valid_time(self, scope: HeavenlyGraphScope) -> int:
        nodes = self._graph.query_nodes(
            HeavenlyNodeQuery(scope=scope, valid_at=self._MAX_TIME, limit=None)
        )
        return max((node.validity.valid_from for node in nodes), default=0)

    def _latest_recorded_at(self, scope: HeavenlyGraphScope) -> int:
        nodes = self._graph.query_nodes(
            HeavenlyNodeQuery(scope=scope, valid_at=self._MAX_TIME, limit=None)
        )
        relations = self._graph.query_relations(
            HeavenlyRelationQuery(scope=scope, valid_at=self._MAX_TIME, limit=None)
        )
        return max(
            [entity.recorded_at for entity in [*nodes, *relations]],
            default=0,
        )

    def _latest_node(
        self, scope: HeavenlyGraphScope, node_id: str
    ) -> HeavenlyGraphNode | None:
        return self._graph.get_node(
            node_id=node_id, scope=scope, valid_at=self._MAX_TIME
        )

    def _latest_relation(
        self, scope: HeavenlyGraphScope, relation_id: str
    ) -> HeavenlyGraphRelation | None:
        return self._graph.get_relation(
            relation_id=relation_id, scope=scope, valid_at=self._MAX_TIME
        )

    def _node_at(
        self,
        scope: HeavenlyGraphScope,
        node_id: str,
        *,
        valid_at: int,
        recorded_at: int,
    ) -> HeavenlyGraphNode | None:
        return self._graph.get_node(
            node_id=node_id,
            scope=scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )

    def _relation_at(
        self,
        scope: HeavenlyGraphScope,
        relation_id: str,
        *,
        valid_at: int,
        recorded_at: int,
    ) -> HeavenlyGraphRelation | None:
        return self._graph.get_relation(
            relation_id=relation_id,
            scope=scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )

    def _record_time(self, record: MemoryRecord) -> int:
        return int(getattr(record, "world_ts", getattr(record, "producer_ts", 0)))
