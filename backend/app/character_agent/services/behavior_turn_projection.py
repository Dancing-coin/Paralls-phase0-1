from __future__ import annotations

from copy import deepcopy
from typing import Callable

from app.models.behavior_turn import BehaviorTurnRecordRequest, BehaviorTurnStageRecord
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphRevisionVector,
    HeavenlyGraphScope,
)
from app.services.behavior_turn_recorder import BehaviorTurnRecorder


class CharacterBehaviorTurnProjection:
    """Maps one completed character-owned chain to the shared turn contract."""

    _CHAIN_TYPES = (
        "l2_reasoning_request",
        "character_interpretation_event",
        "goal_state_event",
        "character_agent_execution_request",
    )

    def __init__(
        self,
        *,
        recorder: BehaviorTurnRecorder,
        scope_resolver: Callable[[str], HeavenlyGraphScope],
    ) -> None:
        self._recorder = recorder
        self._scope_resolver = scope_resolver

    def record(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        settlement_event: dict[str, object],
        evaluation: dict[str, object],
        timeline: list[dict[str, object]],
    ) -> None:
        settlement_payload = settlement_event.get("payload", {})
        if not isinstance(settlement_payload, dict):
            return
        correlation_id = str(
            settlement_payload.get("correlation_id", "")
            or settlement_event.get("event_id", "")
        )
        chain = self._latest_chain(timeline, producer_ts, correlation_id)
        if any(event_type not in chain for event_type in self._CHAIN_TYPES):
            return
        causation_id = str(
            settlement_payload.get("causation_id", "") or correlation_id
        )
        result_ref = str(
            settlement_payload.get("result_id", "")
            or settlement_event.get("event_id", "")
        )
        policy_revision = str(
            settlement_payload.get("policy_revision", "")
            or "policy:character-runtime:v1"
        )
        policy_payload = evaluation.get("candidate_policy")
        if not isinstance(policy_payload, dict):
            policy_payload = {"status": "unchanged"}
        reasoning = chain["l2_reasoning_request"]
        interpretation = chain["character_interpretation_event"]
        goal = chain["goal_state_event"]
        execution = chain["character_agent_execution_request"]
        stage_events = (
            ("context", reasoning, "recorded"),
            ("interpretation", interpretation, "recorded"),
            ("goal", goal, "recorded"),
            (
                "intent",
                {
                    **goal,
                    "payload": {
                        "selected_intent": self._intent_from_payload(goal),
                        "source_goal_event_id": str(goal.get("event_id", "")),
                    },
                },
                "recorded",
            ),
            ("execution", execution, "recorded"),
            (
                "settlement",
                settlement_event,
                self._settlement_outcome(settlement_payload),
            ),
        )
        stages = [
            BehaviorTurnStageRecord(
                stage=stage,
                outcome=outcome,
                source_refs=(str(entry.get("event_id", "")),),
                payload=self._payload(entry),
            )
            for stage, entry, outcome in stage_events
        ]
        stages.extend(
            (
                BehaviorTurnStageRecord(
                    stage="evaluation",
                    outcome=self._evaluation_outcome(evaluation),
                    source_refs=self._evaluation_source_refs(evaluation),
                    payload=evaluation,
                ),
                BehaviorTurnStageRecord(
                    stage="policy",
                    outcome=(
                        "recorded"
                        if policy_payload.get("status") == "candidate_only"
                        else "skipped"
                    ),
                    source_refs=self._policy_source_refs(
                        evaluation, settlement_event
                    ),
                    payload=policy_payload,
                ),
            )
        )
        authority_event_ref = str(settlement_payload.get("authority_event_ref", ""))
        has_authority_result = bool(
            authority_event_ref and settlement_payload.get("authority_owner_ref")
        )
        self._recorder.record(
            BehaviorTurnRecordRequest(
                turn_id=str(settlement_payload.get("turn_id", "") or correlation_id),
                scope=self._scope_resolver(actor_id),
                valid_at=producer_ts,
                recorded_at=producer_ts,
                policy_revision=policy_revision,
                source_revision_vector=GraphRevisionVector(
                    source_revision=int(settlement_event.get("event_index", 0) or 0),
                    policy_revision=1,
                ),
                scope_digest="scope:actor-private",
                provenance=GraphProvenance(
                    source_kind=("authority_event" if has_authority_result else "runtime_outcome"),
                    source_ref=authority_event_ref or result_ref,
                    causation_id=causation_id,
                    correlation_id=correlation_id,
                    producer_system="character_agent_runtime",
                    actor_id=actor_id,
                    evidence_refs=list(self._evaluation_source_refs(evaluation)),
                ),
                transaction_id=f"behavior-turn:{actor_id}:{correlation_id}",
                idempotency_key=f"behavior-turn:{actor_id}:{result_ref}",
                stages=tuple(stages),
            )
        )

    def _latest_chain(
        self, timeline: list[dict[str, object]], producer_ts: int, correlation_id: str
    ) -> dict[str, dict[str, object]]:
        candidates: dict[str, list[dict[str, object]]] = {
            event_type: [] for event_type in self._CHAIN_TYPES
        }
        candidate_timestamps: set[int] = set()
        for entry in timeline:
            if int(entry.get("producer_ts", 0) or 0) > producer_ts:
                continue
            event_type = str(entry.get("event_type", "") or "")
            if event_type not in candidates:
                continue
            payload = entry.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}
            entry_correlation = str(
                payload.get("correlation_id", "")
                or payload.get("causation_id", "")
                or ""
            )
            if entry_correlation and entry_correlation != correlation_id:
                continue
            candidates[event_type].append(entry)
            candidate_timestamps.add(int(entry.get("producer_ts", 0) or 0))
        common_timestamps = {
            timestamp
            for timestamp in candidate_timestamps
            if all(
                any(
                    int(entry.get("producer_ts", 0) or 0) == timestamp
                    for entry in entries
                )
                for entries in candidates.values()
            )
        }
        if not common_timestamps:
            return {}
        anchor_ts = max(common_timestamps)
        chain: dict[str, dict[str, object]] = {}
        for event_type, entries in candidates.items():
            matching = [
                entry
                for entry in entries
                if int(entry.get("producer_ts", 0) or 0) == anchor_ts
            ]
            if len(matching) != 1:
                return {}
            chain[event_type] = matching[0]
        return chain

    @staticmethod
    def _intent_from_payload(entry: dict[str, object]) -> str:
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            return ""
        return str(
            payload.get("selected_intent", "")
            or payload.get("dominant_goal_id", "")
            or ""
        )

    @staticmethod
    def _policy_source_refs(
        evaluation: dict[str, object], settlement_event: dict[str, object]
    ) -> tuple[str, ...]:
        candidate_event_id = str(evaluation.get("policy_candidate_event_id", ""))
        if candidate_event_id:
            return (candidate_event_id,)
        return (str(settlement_event.get("event_id", "")),)

    @staticmethod
    def _settlement_outcome(payload: dict[str, object]) -> str:
        status = str(
            payload.get("settlement_status", "")
            or payload.get("resolution_status", "")
        )
        if status in {"accepted", "applied", "observed"} and payload.get(
            "authority_event_ref"
        ) and payload.get("authority_owner_ref"):
            return "committed"
        if status in {"accepted", "applied", "observed"}:
            return "accepted"
        if status in {"rejected", "blocked", "denied"}:
            return "rejected"
        return "failed"

    @staticmethod
    def _evaluation_outcome(evaluation: dict[str, object]) -> str:
        score = float(evaluation.get("behavior_score", 0.5) or 0.5)
        if score >= 0.75:
            return "accepted"
        if score <= 0.25:
            return "failed"
        return "recorded"

    @staticmethod
    def _evaluation_source_refs(evaluation: dict[str, object]) -> tuple[str, ...]:
        refs = evaluation.get("source_refs", [])
        if not isinstance(refs, list):
            return ()
        return tuple(str(ref) for ref in refs if str(ref))

    @staticmethod
    def _payload(entry: dict[str, object]) -> dict[str, object]:
        payload = entry.get("payload", {})
        return deepcopy(payload) if isinstance(payload, dict) else {}


__all__ = ["CharacterBehaviorTurnProjection"]
