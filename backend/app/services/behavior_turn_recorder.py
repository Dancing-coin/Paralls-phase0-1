from __future__ import annotations

from app.models.behavior_turn import (
    BEHAVIOR_TURN_STAGE_ORDER,
    BehaviorTurnRecordRequest,
    BehaviorTurnStageRecord,
)
from app.models.siming_heavenly_graph import (
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
)
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


class BehaviorTurnRecorder:
    """行为回合记录器：将 owner 产生的阶段投影为可审计图谱回合。"""

    def __init__(self, graph: HeavenlyGraphPort) -> None:
        self._graph = graph

    def record(self, request: BehaviorTurnRecordRequest) -> HeavenlyGraphWriteResult:
        self._validate_stage_order(request.stages)
        anchor_id = f"behavior-turn:{request.turn_id}"
        metadata = GraphSemanticMetadata(
            record_kind="projection",
            visibility_scope=(
                "actor_private"
                if request.scope.graph_namespace == "actor_private"
                else "siming_internal"
            ),
            derivation_kind="projection",
            source_event_refs=self._source_refs(request),
            source_revision_vector=request.source_revision_vector,
            policy_revision=request.policy_revision,
            scope_digest=request.scope_digest,
        )
        anchor = HeavenlyGraphNode(
            node_id=anchor_id,
            node_type="behavior_turn",
            scope=request.scope,
            validity=GraphValidity(valid_from=request.valid_at),
            recorded_at=request.recorded_at,
            revision=1,
            attributes={
                "entity_kind": "turn",
                "turn_id": request.turn_id,
                "actor_id": request.provenance.actor_id,
                "correlation_id": request.provenance.correlation_id,
            },
            provenance=request.provenance,
            semantic_metadata=metadata,
        )
        nodes = [anchor]
        relations: list[HeavenlyGraphRelation] = []
        for index, stage in enumerate(request.stages):
            stage_node_id = self._stage_node_id(request.turn_id, index, stage)
            stage_metadata = metadata.model_copy(
                update={"source_event_refs": stage.source_refs}
            )
            nodes.append(
                HeavenlyGraphNode(
                    node_id=stage_node_id,
                    node_type="behavior_turn",
                    scope=request.scope,
                    validity=GraphValidity(valid_from=request.valid_at),
                    recorded_at=request.recorded_at,
                    revision=1,
                    attributes={
                        "entity_kind": "stage",
                        "turn_id": request.turn_id,
                        "actor_id": request.provenance.actor_id,
                        "correlation_id": request.provenance.correlation_id,
                        "stage": stage.stage,
                        "outcome": stage.outcome,
                        "payload": stage.payload,
                    },
                    provenance=request.provenance,
                    semantic_metadata=stage_metadata,
                )
            )
            relations.append(
                HeavenlyGraphRelation(
                    relation_id=(
                        f"behavior-turn:{request.turn_id}:part:{index:02d}-{stage.stage}"
                    ),
                    relation_type="part_of_turn",
                    source_node_id=stage_node_id,
                    target_node_id=anchor_id,
                    scope=request.scope,
                    validity=GraphValidity(valid_from=request.valid_at),
                    recorded_at=request.recorded_at,
                    revision=1,
                    attributes={
                        "turn_id": request.turn_id,
                        "actor_id": request.provenance.actor_id,
                        "correlation_id": request.provenance.correlation_id,
                        "stage": stage.stage,
                    },
                    provenance=request.provenance,
                    semantic_metadata=stage_metadata,
                )
            )
        return self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=request.transaction_id,
                idempotency_key=request.idempotency_key,
                scope=request.scope,
                nodes=nodes,
                relations=relations,
            )
        )

    @staticmethod
    def _validate_stage_order(stages: tuple[BehaviorTurnStageRecord, ...]) -> None:
        actual = tuple(stage.stage for stage in stages)
        expected = BEHAVIOR_TURN_STAGE_ORDER[: len(actual)]
        if actual != expected:
            raise ValueError("behavior turn stages must follow contiguous canonical order")

    @staticmethod
    def _stage_node_id(
        turn_id: str, index: int, stage: BehaviorTurnStageRecord
    ) -> str:
        return f"behavior-turn:{turn_id}:stage:{index:02d}-{stage.stage}"

    @staticmethod
    def _source_refs(request: BehaviorTurnRecordRequest) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                ref for stage in request.stages for ref in stage.source_refs
            )
        )


__all__ = ["BehaviorTurnRecorder"]
