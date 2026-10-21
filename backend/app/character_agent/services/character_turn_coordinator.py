from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Callable

from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.models.mind_frame import CharacterMindFrame
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.models.behavior_turn import BehaviorTurnStage, CharacterTurnStageEvent


class CharacterTurnCoordinator:
    """Append canonical actor-private turn records through one session stream."""

    def __init__(self, session_store: CharacterAgentSessionStore,
                 project_event: Callable[[dict[str, object]], None] | None = None) -> None:
        self._session_store = session_store
        self._project_event = project_event

    def begin_or_replay(
        self,
        *,
        actor_id: str,
        source_event_ref: str,
        producer_ts: int,
        causation_id: str,
        correlation_id: str,
        input_revision_vector: dict[str, int],
        memory_revision_vector: dict[str, int],
        policy_revision: str,
        snapshot_revision: int,
        branch_id: str | None = None,
    ) -> CharacterTurnContext:
        candidate = CharacterTurnContext.begin(
            actor_id=actor_id,
            source_event_ref=source_event_ref,
            producer_ts=producer_ts,
            causation_id=causation_id,
            correlation_id=correlation_id,
            input_revision_vector=input_revision_vector,
            memory_revision_vector=memory_revision_vector,
            policy_revision=policy_revision,
            snapshot_revision=snapshot_revision,
            branch_id=branch_id,
        )
        existing = self._load_context(actor_id, candidate.turn_id)
        if existing is not None:
            if self._creation_identity(existing) != self._creation_identity(candidate):
                raise ValueError("character_turn_context_replay_mismatch")
            return existing
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_turn_context_created",
            producer_ts=producer_ts,
            expected_revision=self._session_store.event_count(actor_id),
            payload={
                "turn_id": candidate.turn_id,
                "source_event_ref": candidate.source_event_ref,
                "context": self._json_data(candidate.model_dump(warnings=False)),
            },
        )
        if self._project_event is not None:
            self._project_event(stored)
        return candidate

    def append_stage(
        self,
        *,
        context: CharacterTurnContext,
        stage: BehaviorTurnStage,
        payload: Mapping[str, object],
        producer_ts: int,
    ) -> CharacterTurnContext:
        canonical_payload = self._canonical_payload(payload)
        digest = self._payload_digest(canonical_payload)
        stage_ref = f"stage:{context.turn_id}:{stage}:{digest}"
        idempotency_key = f"{context.turn_id}:{stage}:{digest}"
        advanced, stage_event = context.stage_event(
            stage,
            stage_ref=stage_ref,
            idempotency_key=idempotency_key,
            producer_ts=producer_ts,
            payload=canonical_payload,
        )
        existing = context.stage_events.get(stage)
        if existing is not None:
            if existing != stage_event:
                raise ValueError("character_turn_stage_replay_mismatch")
            return context
        stored = self._session_store.append_event(
            actor_id=context.actor_id,
            event_type="character_turn_stage_recorded",
            producer_ts=producer_ts,
            expected_revision=self._session_store.event_count(context.actor_id),
            payload={
                "turn_id": context.turn_id,
                "stage": stage,
                "stage_event": self._json_data(stage_event.model_dump(warnings=False)),
            },
        )
        if self._project_event is not None:
            self._project_event(stored)
        return advanced

    def mark_awaiting_settlement(
        self,
        *,
        context: CharacterTurnContext,
        execution_ref: str,
        authority_request_ref: str,
        expected_revision: int | None = None,
        producer_ts: int,
    ) -> CharacterTurnContext:
        return self.append_stage(
            context=context,
            stage="execution",
            payload={
                "execution_ref": execution_ref,
                "authority_request_ref": authority_request_ref,
                "expected_revision": expected_revision if expected_revision is not None else context.snapshot_revision,
            },
            producer_ts=producer_ts,
        )

    def freeze_frame(self, *, context: CharacterTurnContext, frame: CharacterMindFrame) -> CharacterMindFrame:
        if frame.actor_id != context.actor_id:
            raise ValueError("mind frame actor mismatch")
        return frame.bind_to_turn(context)

    def _load_context(
        self, actor_id: str, turn_id: str
    ) -> CharacterTurnContext | None:
        context: CharacterTurnContext | None = None
        stage_entries: list[dict[str, object]] = []
        for entry in self._session_store.list_events(actor_id):
            payload = entry.get("payload")
            if not isinstance(payload, dict) or payload.get("turn_id") != turn_id:
                continue
            event_type = str(entry.get("event_type", ""))
            if event_type == "character_turn_context_created":
                raw_context = payload.get("context")
                if not isinstance(raw_context, dict):
                    raise ValueError("character_turn_context_invalid")
                parsed = CharacterTurnContext.model_validate(raw_context)
                if context is not None and context != parsed:
                    raise ValueError("character_turn_context_conflict")
                context = parsed
            elif event_type == "character_turn_stage_recorded":
                stage_entries.append(entry)
        if context is None:
            return None
        for entry in stage_entries:
            payload = entry["payload"]
            assert isinstance(payload, dict)
            raw_event = payload.get("stage_event")
            if not isinstance(raw_event, dict):
                raise ValueError("character_turn_stage_invalid")
            stage_event = CharacterTurnStageEvent.model_validate(raw_event)
            stage_payload = self._json_data(stage_event.payload)
            if not isinstance(stage_payload, dict):
                raise ValueError("character_turn_stage_invalid")
            updated, rebuilt = context.stage_event(
                stage_event.stage,
                stage_ref=stage_event.stage_ref,
                idempotency_key=stage_event.idempotency_key,
                producer_ts=stage_event.producer_ts,
                outcome=stage_event.outcome,
                payload=stage_payload,
            )
            if rebuilt != stage_event:
                raise ValueError("character_turn_stage_conflict")
            context = updated
        return context

    @staticmethod
    def _canonical_payload(payload: Mapping[str, object]) -> dict[str, Any]:
        raw = json.dumps(
            CharacterTurnCoordinator._json_data(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("character_turn_stage_payload_invalid")
        return decoded

    @classmethod
    def _payload_digest(cls, payload: Mapping[str, object]) -> str:
        return hashlib.sha256(cls._canonical_bytes(payload)).hexdigest()

    @staticmethod
    def _canonical_bytes(value: object) -> bytes:
        return json.dumps(
            CharacterTurnCoordinator._json_data(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _json_data(value: object) -> object:
        if isinstance(value, Mapping):
            return {
                str(key): CharacterTurnCoordinator._json_data(nested)
                for key, nested in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [CharacterTurnCoordinator._json_data(nested) for nested in value]
        return value

    @classmethod
    def _creation_identity(cls, context: CharacterTurnContext) -> bytes:
        return cls._canonical_bytes(
            {
                "turn_id": context.turn_id,
                "actor_id": context.actor_id,
                "source_event_ref": context.source_event_ref,
                "causation_id": context.causation_id,
                "correlation_id": context.correlation_id,
                "input_revision_vector": context.input_revision_vector,
                "memory_revision_vector": context.memory_revision_vector,
                "policy_revision": context.policy_revision,
                "snapshot_revision": context.snapshot_revision,
                "branch_id": context.branch_id,
                "valid_at": context.valid_at,
                "producer_ts": context.producer_ts,
            }
        )


__all__ = ["CharacterTurnCoordinator"]
