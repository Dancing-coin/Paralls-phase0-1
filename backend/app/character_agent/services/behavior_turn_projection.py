from __future__ import annotations

from copy import deepcopy
from typing import Callable

from app.character_agent.models.turn_context import CharacterTurnContext
from app.models.behavior_turn import (
    BehaviorTurnRecordRequest,
    BehaviorTurnStageRecord,
    CharacterTurnStageEvent,
)
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphRevisionVector,
    HeavenlyGraphScope,
)
from app.services.behavior_turn_recorder import BehaviorTurnRecorder


class CharacterBehaviorTurnProjection:
    """角色行为回合投影器：映射角色链到共享 typed 回合契约。"""

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
        turn_id = str(settlement_payload.get("turn_id", "") or "")
        if turn_id:
            context = self._context_for_turn(turn_id, timeline)
            if context is not None:
                self.record_context(context, timeline)
                return
        chain = self._legacy_latest_chain(timeline, producer_ts, correlation_id)
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
            BehaviorTurnRecordRequest.from_legacy_projection(
                legacy_reader_ref="legacy:character-behavior-turn-projection:v1",
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

    def record_context(
        self, turn: CharacterTurnContext, timeline: list[dict[str, object]]
    ) -> None:
        """Project the exact canonical stage sequence for one live turn."""
        stage_events = self._canonical_stage_events(turn.turn_id, timeline)
        if not stage_events or tuple(stage_events) != tuple(turn.stage_events.values()):
            return
        source_revision = max(
            (
                int(entry.get("event_index", 0) or 0)
                for entry in timeline
                if entry.get("event_type") == "character_turn_stage_recorded"
                and isinstance(entry.get("payload"), dict)
                and entry["payload"].get("turn_id") == turn.turn_id
            ),
            default=0,
        )
        self._recorder.record(
            BehaviorTurnRecordRequest.from_canonical_stage_events(
                stage_events=tuple(stage_events),
                turn_id=turn.turn_id,
                scope=self._scope_resolver(turn.actor_id),
                valid_at=turn.valid_at,
                recorded_at=stage_events[-1].producer_ts,
                policy_revision=turn.policy_revision,
                source_revision_vector=GraphRevisionVector(source_revision=source_revision),
                scope_digest="scope:actor-private",
                provenance=GraphProvenance(
                    source_kind="runtime_outcome",
                    source_ref=stage_events[-1].stage_ref,
                    causation_id=turn.causation_id,
                    correlation_id=turn.correlation_id,
                    producer_system="character_agent_runtime",
                    actor_id=turn.actor_id,
                ),
                transaction_id=f"canonical-behavior-turn:{turn.turn_id}",
                idempotency_key=(
                    f"canonical-behavior-turn:{turn.turn_id}:"
                    f"{stage_events[-1].idempotency_key}"
                ),
                branch_id=turn.branch_id,
                input_revision_vector=turn.input_revision_vector,
                memory_revision_vector=turn.memory_revision_vector,
                snapshot_revision=turn.snapshot_revision,
            )
        )

    def _legacy_latest_chain(
        self, timeline: list[dict[str, object]], producer_ts: int, correlation_id: str
    ) -> dict[str, dict[str, object]]:
        strict = self._legacy_chain_candidates(
            timeline, producer_ts, correlation_id, require_correlation=True
        )
        result = self._select_legacy_chain(strict)
        if result:
            return result
        # Pre-migration records did not carry the canonical correlation on every
        # producer event; retain the historical timestamp-only reader explicitly.
        return self._select_legacy_chain(
            self._legacy_chain_candidates(
                timeline, producer_ts, correlation_id, require_correlation=False
            )
        )

    def _legacy_chain_candidates(
        self,
        timeline: list[dict[str, object]],
        producer_ts: int,
        correlation_id: str,
        *,
        require_correlation: bool,
    ) -> dict[str, list[dict[str, object]]]:
        candidates: dict[str, list[dict[str, object]]] = {
            event_type: [] for event_type in self._CHAIN_TYPES
        }
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
            if require_correlation and entry_correlation and entry_correlation != correlation_id:
                continue
            candidates[event_type].append(entry)
        return candidates

    def _select_legacy_chain(
        self, candidates: dict[str, list[dict[str, object]]]
    ) -> dict[str, dict[str, object]]:
        candidate_timestamps = {
            int(entry.get("producer_ts", 0) or 0)
            for entries in candidates.values()
            for entry in entries
        }
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
    def _canonical_stage_events(
        turn_id: str, timeline: list[dict[str, object]]
    ) -> list[CharacterTurnStageEvent]:
        events: list[CharacterTurnStageEvent] = []
        for entry in timeline:
            if entry.get("event_type") != "character_turn_stage_recorded":
                continue
            payload = entry.get("payload")
            if not isinstance(payload, dict) or payload.get("turn_id") != turn_id:
                continue
            raw_event = payload.get("stage_event")
            if not isinstance(raw_event, dict):
                return []
            events.append(CharacterTurnStageEvent.model_validate(raw_event))
        return events

    def _context_for_turn(
        self, turn_id: str, timeline: list[dict[str, object]]
    ) -> CharacterTurnContext | None:
        for entry in timeline:
            if entry.get("event_type") != "character_turn_context_created":
                continue
            payload = entry.get("payload")
            if not isinstance(payload, dict) or payload.get("turn_id") != turn_id:
                continue
            raw_context = payload.get("context")
            if isinstance(raw_context, dict):
                return CharacterTurnContext.model_validate(raw_context)
        return None

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
