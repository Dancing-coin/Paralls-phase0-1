from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from app.gameplay.models import GameplayEvent, GameplayFailure, ProjectionCheckpoint, ReplayResult


def _canonical_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class GameplayProjectionReplay:
    def __init__(
        self,
        *,
        projector_id: str,
        projector_version: str,
        projection_schema_version: int = 1,
        supported_event_versions: dict[str, int] | None = None,
    ) -> None:
        self.projector_id = projector_id
        self.projector_version = projector_version
        self.projection_schema_version = projection_schema_version
        self.supported_event_versions = supported_event_versions

    def full_replay(self, events: list[GameplayEvent]) -> ReplayResult:
        return self._replay(events, initial_state={}, initial_vector={}, applied_event_ids=set(), last_global_sequence=0)

    def create_checkpoint(self, events: list[GameplayEvent]) -> ProjectionCheckpoint:
        result = self.full_replay(events)
        if not result.succeeded:
            raise ValueError(result.failure.message if result.failure is not None else "replay failed")
        checkpoint_payload: dict[str, object] = {
            "state": result.state,
            "source_revision_vector": result.source_revision_vector,
            "last_global_sequence": result.last_global_sequence,
            "applied_event_ids": result.applied_event_ids,
        }
        return ProjectionCheckpoint(
            checkpoint_id=f"checkpoint:{self.projector_id}:{result.last_global_sequence}",
            projector_id=self.projector_id,
            projector_version=self.projector_version,
            projection_schema_version=self.projection_schema_version,
            source_revision_vector=result.source_revision_vector,
            last_global_sequence=result.last_global_sequence,
            state=result.state,
            applied_event_ids=result.applied_event_ids,
            projection_hash=_canonical_hash(checkpoint_payload),
        )

    def checkpoint_plus_tail_replay(self, checkpoint: ProjectionCheckpoint, tail_events: list[GameplayEvent]) -> ReplayResult:
        if checkpoint.projector_id != self.projector_id or checkpoint.projector_version != self.projector_version:
            return self._failed("checkpoint_invalid", "checkpoint projector identity does not match", "checkpoint_validation")
        return self._replay(
            tail_events,
            initial_state=checkpoint.state,
            initial_vector=checkpoint.source_revision_vector,
            applied_event_ids=set(checkpoint.applied_event_ids),
            last_global_sequence=checkpoint.last_global_sequence,
        )

    def _replay(
        self,
        events: list[GameplayEvent],
        *,
        initial_state: dict[str, object],
        initial_vector: dict[str, int],
        applied_event_ids: set[str],
        last_global_sequence: int,
    ) -> ReplayResult:
        state = deepcopy(initial_state)
        revision_vector = dict(initial_vector)
        applied_ids = set(applied_event_ids)
        ordered_events = sorted(events, key=lambda event: event.global_sequence)
        for event in ordered_events:
            if event.event_id in applied_ids:
                continue
            supported_version = None if self.supported_event_versions is None else self.supported_event_versions.get(event.event_type)
            if self.supported_event_versions is not None and supported_version != event.schema_version:
                return self._failed(
                    "upcaster_chain_missing",
                    "event version cannot be read by this projector",
                    "event_upcast",
                    stream_id=event.stream_id,
                )
            expected_revision = revision_vector.get(event.stream_id, 0) + 1
            if event.stream_revision != expected_revision:
                return self._failed(
                    "stream_revision_gap",
                    "stream revision gap or out-of-order event detected",
                    "replay_order",
                    expected_revision=expected_revision,
                    actual_revision=event.stream_revision,
                    stream_id=event.stream_id,
                )
            stream_state = dict(state.get(event.stream_id, {})) if isinstance(state.get(event.stream_id, {}), dict) else {}
            stream_state["last_event_id"] = event.event_id
            stream_state["last_event_type"] = event.event_type
            stream_state["last_payload"] = event.payload
            stream_state["event_count"] = int(stream_state.get("event_count", 0)) + 1
            state[event.stream_id] = stream_state
            revision_vector[event.stream_id] = event.stream_revision
            applied_ids.add(event.event_id)
            last_global_sequence = max(last_global_sequence, event.global_sequence)
        hash_payload: dict[str, object] = {
            "state": state,
            "source_revision_vector": revision_vector,
            "last_global_sequence": last_global_sequence,
            "applied_event_ids": sorted(applied_ids),
        }
        return ReplayResult(
            succeeded=True,
            projector_id=self.projector_id,
            projector_version=self.projector_version,
            projection_hash=_canonical_hash(hash_payload),
            state=state,
            source_revision_vector=revision_vector,
            last_global_sequence=last_global_sequence,
            applied_event_ids=sorted(applied_ids),
            applied_event_count=len(applied_ids),
        )

    def _failed(
        self,
        error_code: str,
        message: str,
        failed_stage: str,
        *,
        expected_revision: int | None = None,
        actual_revision: int | None = None,
        stream_id: str | None = None,
    ) -> ReplayResult:
        return ReplayResult(
            succeeded=False,
            projector_id=self.projector_id,
            projector_version=self.projector_version,
            failure=GameplayFailure(
                error_code=error_code,
                message=message,
                failed_stage=failed_stage,
                expected_revision=expected_revision,
                actual_revision=actual_revision,
                stream_id=stream_id,
            ),
        )
