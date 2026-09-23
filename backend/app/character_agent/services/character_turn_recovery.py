from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Literal

from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.storage.graph_continuity_store import (
    CharacterGraphContinuityStore,
)
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.character_agent.services.character_turn_coordinator import CharacterTurnCoordinator
from app.models.behavior_turn import BEHAVIOR_TURN_STAGE_ORDER


CharacterTurnRecoveryStatus = Literal[
    "resumed", "recovery_required", "already_committed", "no_pending_turn"
]


@dataclass(frozen=True)
class CharacterTurnRecoveryResult:
    status: CharacterTurnRecoveryStatus
    actor_id: str
    turn_id: str | None = None
    reason: str | None = None


class CharacterTurnRecoveryService:
    """Reconcile a persisted actor turn without reissuing authority work."""

    def __init__(
        self,
        *,
        session_store: CharacterAgentSessionStore,
        continuity_store: CharacterGraphContinuityStore,
    ) -> None:
        self._session_store = session_store
        self._continuity_store = continuity_store
        self._coordinator = CharacterTurnCoordinator(session_store)

    def reconcile(self, actor_id: str) -> CharacterTurnRecoveryResult:
        snapshot = self._continuity_store.read_snapshot(actor_id)
        if snapshot is None:
            return self._mark_missing_snapshot(actor_id)
        if not self._snapshot_valid(snapshot):
            return self._mark_missing_snapshot(actor_id, snapshot=snapshot, reason="snapshot_invalid")
        while True:
            snapshot = self._continuity_store.read_snapshot(actor_id) or snapshot
            if not self._snapshot_valid(snapshot):
                return self._mark_missing_snapshot(actor_id, snapshot=snapshot, reason="snapshot_invalid")
            try:
                timeline = self._timeline(snapshot, actor_id)
                contexts = self._pending_contexts(snapshot, actor_id)
            except ValueError as exc:
                reason = "active_turns_invalid" if "active_turns" in str(exc) else "timeline_invalid"
                return self._mark_missing_snapshot(actor_id, snapshot=snapshot, reason=reason)
            if not contexts:
                if not isinstance(snapshot.get("active_turns"), dict):
                    return self._mark_missing_snapshot(actor_id, snapshot=snapshot, reason="active_turns_invalid")
                return CharacterTurnRecoveryResult("no_pending_turn", actor_id)
            for context in contexts:
                if context.lifecycle == "recovery_required":
                    return CharacterTurnRecoveryResult("recovery_required", actor_id, context.turn_id, "recovery_required")
            for candidate in contexts:
                if not self._valid_context_timeline(candidate, timeline):
                    return self._mark_recovery_required(candidate, timeline, "turn_timeline_invalid", snapshot=snapshot)
            awaiting = [item for item in contexts if item.lifecycle == "awaiting_settlement"]
            if not awaiting:
                committed = next((item for item in reversed(contexts) if item.lifecycle == "committed"), None)
                if committed is not None:
                    return CharacterTurnRecoveryResult("already_committed", actor_id, committed.turn_id)
                context = contexts[-1]
                return CharacterTurnRecoveryResult("resumed", actor_id, context.turn_id)
            context = awaiting[0]
            pending = self._pending_execution(snapshot, context)
            if pending is None:
                return self._mark_recovery_required(context, timeline, "pending_execution_invalid", snapshot=snapshot)
            receipt = self._authority_receipt_for(pending, timeline)
            if receipt is None:
                return self._mark_recovery_required(context, timeline, "authority_receipt_missing", snapshot=snapshot)
            result = self._commit_original_turn(context, receipt, snapshot=snapshot, timeline=timeline)
            if result.status != "already_committed":
                return result
            # Reload the complete snapshot/timeline before touching the next pending turn.
            # This prevents a stale active_turns map from overwriting prior commits.

    @staticmethod
    def _snapshot_valid(snapshot: dict[str, object]) -> bool:
        required = CharacterGraphContinuityStore.REQUIRED_SNAPSHOT_FIELDS
        if not required.issubset(snapshot):
            return False
        digest = snapshot.get("snapshot_digest")
        if snapshot.get("schema_version") != 2 or not isinstance(digest, str):
            return False
        if not isinstance(snapshot.get("session_timeline_checkpoint_index"), int):
            return False
        if not isinstance(snapshot.get("graph_source_event_ref"), str):
            return False
        return digest == CharacterTurnRecoveryService._snapshot_digest(snapshot)

    def _timeline(
        self, snapshot: dict[str, object], actor_id: str
    ) -> list[dict[str, object]]:
        checkpoint = snapshot.get("session_timeline", [])
        if not isinstance(checkpoint, list):
            raise ValueError("timeline_invalid")
        local = self._session_store.list_events(actor_id)
        checkpoint = self._validate_timeline_source(checkpoint, actor_id)
        local = self._validate_timeline_source(local, actor_id)
        return self._merge_appended_events(checkpoint, local)

    @staticmethod
    def _validate_timeline_source(source: list[object], actor_id: str) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        seen: set[str] = set()
        for event in source:
            if not isinstance(event, dict):
                raise ValueError("timeline_invalid")
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or not event_id or event_id in seen:
                raise ValueError("timeline_duplicate_conflict" if event_id in seen else "timeline_invalid")
            if event.get("actor_id") != actor_id:
                raise ValueError("timeline_invalid")
            event_index = event.get("event_index")
            if not isinstance(event_index, int) or isinstance(event_index, bool) or event_index < 1:
                raise ValueError("timeline_invalid")
            seen.add(event_id)
            events.append(deepcopy(event))
        return events

    def _pending_contexts(
        self,
        snapshot: dict[str, object],
        actor_id: str,
    ) -> list[CharacterTurnContext]:
        active = snapshot.get("active_turns")
        if not isinstance(active, dict):
            raise ValueError("active_turns_invalid")
        contexts: list[CharacterTurnContext] = []
        for turn_id, raw in active.items():
            if not isinstance(turn_id, str) or not turn_id or not isinstance(raw, dict):
                raise ValueError("active_turns_invalid")
            try:
                context = CharacterTurnContext.model_validate(
                    self._normalize_context_payload(raw)
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("active_turns_invalid") from exc
            if context.actor_id != actor_id or context.turn_id != turn_id:
                raise ValueError("active_turns_invalid")
            contexts.append(context)
        return sorted(
            [item for item in contexts if item.lifecycle in {"awaiting_settlement", "recovery_required", "committed"}],
            key=lambda item: (item.producer_ts, item.turn_id),
        )

    @staticmethod
    def _normalize_context_payload(raw: dict[str, object]) -> dict[str, object]:
        normalized = dict(raw)
        for field in ("stage_refs", "stage_idempotency_keys", "stage_events"):
            value = raw.get(field)
            if not isinstance(value, dict):
                continue
            if any(stage not in BEHAVIOR_TURN_STAGE_ORDER for stage in value):
                raise ValueError("active_turns_invalid")
            normalized[field] = {
                stage: value[stage]
                for stage in BEHAVIOR_TURN_STAGE_ORDER
                if stage in value
            }
        return normalized

    @staticmethod
    def _valid_context_timeline(
        context: CharacterTurnContext, timeline: list[dict[str, object]]
    ) -> bool:
        expected_index = 1
        context_entry: dict[str, object] | None = None
        stages: dict[str, object] = {}
        for event in timeline:
            if event.get("actor_id") != context.actor_id:
                return False
            if event.get("event_index") != expected_index:
                return False
            expected_index += 1
            payload = event.get("payload")
            if not isinstance(payload, dict) or payload.get("turn_id") != context.turn_id:
                continue
            if event.get("event_type") == "character_turn_context_created":
                if context_entry is not None:
                    return False
                context_entry = event
            elif event.get("event_type") == "character_turn_stage_recorded":
                raw_event = payload.get("stage_event")
                if not isinstance(raw_event, dict):
                    return False
                stage = raw_event.get("stage")
                if not isinstance(stage, str) or stage in stages:
                    return False
                stages[stage] = raw_event
        if context_entry is None:
            return False
        raw_context = context_entry.get("payload", {}).get("context")
        if not isinstance(raw_context, dict):
            return False
        try:
            created = CharacterTurnContext.model_validate(raw_context)
        except ValueError:
            return False
        if (
            created.turn_id != context.turn_id
            or created.actor_id != context.actor_id
            or created.source_event_ref != context.source_event_ref
            or created.causation_id != context.causation_id
            or created.correlation_id != context.correlation_id
            or created.input_revision_vector != context.input_revision_vector
            or created.memory_revision_vector != context.memory_revision_vector
            or created.policy_revision != context.policy_revision
            or created.snapshot_revision != context.snapshot_revision
            or created.branch_id != context.branch_id
            or created.valid_at != context.valid_at
            or created.producer_ts != context.producer_ts
        ):
            return False
        return set(stages) == set(context.stage_events) and all(
            stages[stage] == CharacterTurnRecoveryService._json_data(
                event.model_dump(warnings=False)
            )
            for stage, event in context.stage_events.items()
        )

    @staticmethod
    def _json_data(value: object) -> object:
        if isinstance(value, Mapping):
            return {
                str(key): CharacterTurnRecoveryService._json_data(nested)
                for key, nested in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [CharacterTurnRecoveryService._json_data(nested) for nested in value]
        if hasattr(value, "model_dump"):
            return CharacterTurnRecoveryService._json_data(
                value.model_dump(warnings=False)
            )
        return value

    @staticmethod
    def _pending_execution(
        snapshot: dict[str, object], context: CharacterTurnContext
    ) -> dict[str, object] | None:
        pending = snapshot.get("pending_execution", {})
        if not isinstance(pending, dict):
            return None
        raw = pending.get(context.turn_id)
        execution = context.stage_events.get("execution")
        if not isinstance(raw, dict) or execution is None:
            return None
        request_ref = raw.get("authority_request_ref")
        expected_revision = raw.get("expected_revision")
        idempotency_key = raw.get("idempotency_key")
        if (
            not isinstance(request_ref, str)
            or not request_ref
            or not isinstance(expected_revision, int)
            or isinstance(expected_revision, bool)
            or expected_revision < 0
            or idempotency_key != execution.idempotency_key
            or raw.get("receipt_ref") is not None
            or execution.payload.get("authority_request_ref") != request_ref
            or execution.payload.get("expected_revision") != expected_revision
        ):
            return None
        return raw

    @staticmethod
    def _authority_receipt_for(
        pending: dict[str, object], timeline: list[dict[str, object]]
    ) -> dict[str, object] | None:
        exact = {
            "turn_id": pending.get("turn_id"),
            "authority_request_ref": pending.get("authority_request_ref"),
            "expected_revision": pending.get("expected_revision"),
            "idempotency_key": pending.get("idempotency_key"),
        }
        for event in timeline:
            if event.get("event_type") != "character_turn_authority_receipt":
                continue
            receipt = event.get("payload")
            if not isinstance(receipt, dict):
                continue
            if all(receipt.get(key) == value for key, value in exact.items()):
                receipt_ref = receipt.get("receipt_ref")
                if isinstance(receipt_ref, str) and receipt_ref:
                    return receipt
        return None

    def _commit_original_turn(
        self,
        context: CharacterTurnContext,
        receipt: dict[str, object],
        *,
        snapshot: dict[str, object],
        timeline: list[dict[str, object]],
    ) -> CharacterTurnRecoveryResult:
        for stage, payload in (
            ("settlement", receipt),
            ("evaluation", {"receipt_ref": receipt["receipt_ref"], "status": "committed"}),
            ("policy", {"receipt_ref": receipt["receipt_ref"], "status": "committed"}),
        ):
            context = self._coordinator.append_stage(
                context=context,
                stage=stage,
                payload=payload,
                producer_ts=int(receipt.get("producer_ts", 0) or 0),
            )
        self._persist_context_snapshot(snapshot, context, timeline=timeline)
        return CharacterTurnRecoveryResult(
            "already_committed", context.actor_id, context.turn_id
        )

    def _mark_recovery_required(
        self,
        context: CharacterTurnContext,
        timeline: list[dict[str, object]],
        reason: str,
        *,
        snapshot: dict[str, object],
    ) -> CharacterTurnRecoveryResult:
        try:
            updated = context.transition(
                "recovery_required",
                transition_ref=f"recovery:{context.turn_id}",
                idempotency_key=f"recovery:{context.turn_id}:{reason}",
                producer_ts=max((int(event.get("producer_ts", 0) or 0) for event in timeline), default=context.producer_ts),
                payload={"reason": reason},
            )
        except ValueError:
            updated = context
        execution = context.stage_events.get("execution")
        self._session_store.append_event(
            actor_id=context.actor_id,
            event_type="character_turn_lifecycle_transition",
            producer_ts=max(
                (int(event.get("producer_ts", 0) or 0) for event in timeline),
                default=context.producer_ts,
            ),
            expected_revision=self._session_store.event_count(context.actor_id),
            payload={
                "turn_id": context.turn_id,
                "transition": {
                    "from_lifecycle": context.lifecycle,
                    "to_lifecycle": "recovery_required",
                    "transition_ref": f"recovery:{context.turn_id}",
                    "idempotency_key": f"recovery:{context.turn_id}:{reason}",
                    "producer_ts": max((int(event.get("producer_ts", 0) or 0) for event in timeline), default=context.producer_ts),
                    "payload": {"reason": reason},
                },
                "authority_request_ref": (
                    execution.payload.get("authority_request_ref", "")
                    if execution is not None
                    else ""
                ),
                "reason": reason,
            },
        )
        self._persist_context_snapshot(snapshot, updated, timeline=timeline)
        return CharacterTurnRecoveryResult(
            "recovery_required", context.actor_id, context.turn_id, reason
        )

    def _mark_missing_snapshot(self, actor_id: str, *, snapshot: dict[str, object] | None = None, reason: str = "snapshot_missing") -> CharacterTurnRecoveryResult:
        events = self._session_store.list_events(actor_id)
        producer_ts = max(
            (int(event.get("producer_ts", 0) or 0) for event in events),
            default=0,
        )
        audit = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_turn_recovery_required",
            producer_ts=producer_ts,
            expected_revision=self._session_store.event_count(actor_id),
            payload={"reason": reason},
        )
        if audit:
            base = dict(snapshot or {})
            base.setdefault("working_memory", {})
            base.setdefault("dynamic_state", {})
            base.setdefault("need_tension_state", {})
            base.setdefault("supervision_state", {})
            base.setdefault("goal_state", {})
            base.setdefault("goal_state_history", [])
            base.setdefault("continuity_state", {})
            base.setdefault("continuity_revisions", 0)
            base.setdefault("continuity_receipts", {})
            base.setdefault("materialization_receipts", {})
            base.setdefault("pending_seed_candidates", {})
            base.setdefault("seed_projection", {})
            base.setdefault("shared_module_state", {})
            base["schema_version"] = 2
            try:
                base["session_timeline"] = self._timeline(base, actor_id)
            except ValueError:
                base["session_timeline"] = self._reindexed_timeline(
                    self._session_store.list_events(actor_id)
                )
            base["session_timeline_checkpoint_index"] = len(base["session_timeline"])
            base["checkpoint_event_index"] = len(base["session_timeline"])
            base["graph_source_event_ref"] = str(audit["event_id"])
            base["active_turns"] = base.get("active_turns", {}) if isinstance(base.get("active_turns"), dict) else {}
            base["pending_execution"] = base.get("pending_execution", {}) if isinstance(base.get("pending_execution"), dict) else {}
            base["policy_state"] = {"execution_blocked": True, "recovery_reason": reason}
            base["last_committed_turn_id"] = base.get("last_committed_turn_id")
            base.pop("_continuity_source_event_ref", None)
            base["snapshot_digest"] = self._snapshot_digest(base)
            self._continuity_store.write_snapshot(
                actor_id=actor_id,
                producer_ts=int(audit.get("producer_ts", 0) or 0),
                source_event_ref=str(audit["event_id"]),
                snapshot=base,
            )
        return CharacterTurnRecoveryResult("recovery_required", actor_id, reason=reason)

    def _persist_context_snapshot(
        self,
        snapshot: dict[str, object],
        context: CharacterTurnContext,
        *,
        timeline: list[dict[str, object]],
    ) -> None:
        if not snapshot:
            return
        active = dict(snapshot.get("active_turns", {}))
        active[context.turn_id] = self._json_data(context.model_dump(warnings=False))
        updated = dict(snapshot)
        updated["active_turns"] = active
        if context.lifecycle == "committed":
            pending = dict(updated.get("pending_execution", {}))
            pending.pop(context.turn_id, None)
            updated["pending_execution"] = pending
            updated["last_committed_turn_id"] = context.turn_id
        policy = dict(updated.get("policy_state", {}))
        policy["execution_blocked"] = context.lifecycle == "recovery_required"
        updated["policy_state"] = policy
        updated_timeline = self._merge_appended_events(
            timeline, self._session_store.list_events(context.actor_id)
        )
        updated["session_timeline"] = updated_timeline
        updated["checkpoint_event_index"] = len(updated_timeline)
        updated["session_timeline_checkpoint_index"] = len(updated_timeline)
        source = str(updated_timeline[-1]["event_id"])
        updated["graph_source_event_ref"] = source
        updated.pop("_continuity_source_event_ref", None)
        updated["snapshot_digest"] = self._snapshot_digest(updated)
        self._continuity_store.write_snapshot(
            actor_id=context.actor_id,
            producer_ts=max(
                (int(event.get("producer_ts", 0) or 0) for event in updated_timeline),
                default=context.producer_ts,
            ),
            source_event_ref=source,
            snapshot=updated,
        )

    @staticmethod
    def _merge_appended_events(
        timeline: list[dict[str, object]], local_events: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        merged = [deepcopy(event) for event in timeline]
        by_id = {str(event["event_id"]): event for event in merged}
        for event in local_events:
            event_id = str(event.get("event_id", "") or "")
            existing = by_id.get(event_id)
            if existing is not None:
                comparable = dict(existing)
                comparable["event_index"] = event.get("event_index")
                if comparable != event:
                    raise ValueError("timeline_duplicate_conflict")
                continue
            appended = deepcopy(event)
            appended["event_index"] = len(merged) + 1
            merged.append(appended)
            by_id[event_id] = appended
        return merged

    @staticmethod
    def _reindexed_timeline(events: list[dict[str, object]]) -> list[dict[str, object]]:
        return [
            {**deepcopy(event), "event_index": index}
            for index, event in enumerate(events, start=1)
        ]

    @staticmethod
    def _snapshot_digest(snapshot: dict[str, object]) -> str:
        canonical = {
            key: value
            for key, value in snapshot.items()
            if key not in {"snapshot_digest", "_continuity_source_event_ref"}
        }
        return "sha256:" + hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()


__all__ = [
    "CharacterTurnRecoveryResult",
    "CharacterTurnRecoveryService",
    "CharacterTurnRecoveryStatus",
]
