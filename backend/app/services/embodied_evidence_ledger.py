from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.embodied_interaction import EmbodiedEvidenceEvent, EmbodiedProjectionPolicy


class EmbodiedEvidenceAppendResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    event: EmbodiedEvidenceEvent | None = None
    error_code: str = ""
    idempotent: bool = False


class EmbodiedReplayValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    error_code: str = ""
    event_count: int = 0
    server_ledger_sequences: list[int] = Field(default_factory=list)


class EmbodiedEvidenceLedger:
    _PRIVATE_PAYLOAD_FIELDS = {
        "private_participant_terms",
        "raw_private_memory",
        "vla_prompt_context",
        "unfiltered_vla_context",
        "full_skeletal_artifact",
    }

    def __init__(self) -> None:
        self._events_by_attempt: dict[str, list[EmbodiedEvidenceEvent]] = {}
        self._payloads_by_sequence: dict[int, dict[str, object]] = {}
        self._next_server_sequence = 1
        self._next_source_sequence: dict[tuple[str, str, int], int] = {}
        self._event_by_source: dict[tuple[str, str, int, int], EmbodiedEvidenceEvent] = {}
        self._projection_policy = EmbodiedProjectionPolicy.public_observatory()

    def append(
        self,
        *,
        attempt_id: str,
        event_kind: str,
        emitter_kind: str,
        emitter_id: str,
        emitter_epoch: int,
        source_sequence: int,
        payload_digest: str,
        payload: dict[str, object],
        occurred_at: int = 0,
        recorded_at: int = 0,
        projection_policy_ref: str | None = None,
    ) -> EmbodiedEvidenceAppendResult:
        source_key = (attempt_id, emitter_kind, emitter_epoch)
        event_key = (*source_key, source_sequence)
        existing = self._event_by_source.get(event_key)
        if existing is not None:
            if existing.payload_digest == payload_digest:
                return EmbodiedEvidenceAppendResult(accepted=True, event=existing, idempotent=True)
            return EmbodiedEvidenceAppendResult(accepted=False, error_code="source_sequence_digest_mismatch")

        expected_sequence = self._next_source_sequence.get(source_key, 1)
        if source_sequence != expected_sequence:
            return EmbodiedEvidenceAppendResult(accepted=False, error_code="source_sequence_gap")

        event = EmbodiedEvidenceEvent.model_validate(
            {
                "attempt_id": attempt_id,
                "event_kind": event_kind,
                "emitter_kind": emitter_kind,
                "emitter_id": emitter_id,
                "emitter_epoch": emitter_epoch,
                "source_sequence": source_sequence,
                "server_ledger_sequence": self._next_server_sequence,
                "payload_digest": payload_digest,
                "occurred_at": occurred_at,
                "recorded_at": recorded_at,
                "projection_policy_ref": projection_policy_ref or self._projection_policy.policy_ref,
            }
        )
        self._next_server_sequence += 1
        self._next_source_sequence[source_key] = expected_sequence + 1
        self._event_by_source[event_key] = event
        self._events_by_attempt.setdefault(attempt_id, []).append(event)
        self._payloads_by_sequence[event.server_ledger_sequence] = dict(payload)
        return EmbodiedEvidenceAppendResult(accepted=True, event=event)

    def events_for_attempt(self, attempt_id: str) -> list[EmbodiedEvidenceEvent]:
        return sorted(
            self._events_by_attempt.get(attempt_id, []),
            key=lambda event: event.server_ledger_sequence,
        )

    def validate_replay(self, attempt_id: str) -> EmbodiedReplayValidationResult:
        events = self.events_for_attempt(attempt_id)
        sequences = [event.server_ledger_sequence for event in events]
        if not events:
            return self._replay_reject("missing_request", sequences)
        if sequences != list(range(sequences[0], sequences[0] + len(sequences))):
            return self._replay_reject("server_ledger_sequence_gap", sequences)

        settlement_seen = False
        terminal_seen = False
        required_order = [
            "request_authorized",
            "registry_binding",
            "local_phase",
            "terminal_local_observation",
            "settlement",
        ]
        required_index = 0
        for event in events:
            payload = self._payloads_by_sequence.get(event.server_ledger_sequence, {})
            if self._PRIVATE_PAYLOAD_FIELDS.intersection(payload):
                return self._replay_reject("privacy_ineligible_payload", sequences)
            if event.event_kind == "presentation" and not settlement_seen:
                return self._replay_reject("presentation_before_settlement", sequences)
            if event.event_kind == "settlement":
                if settlement_seen:
                    return self._replay_reject("duplicate_settlement", sequences)
                if not terminal_seen:
                    return self._replay_reject("settlement_before_terminal_observation", sequences)
                settlement_seen = True
            if event.event_kind == "terminal_local_observation":
                terminal_seen = True

            if required_index < len(required_order) and event.event_kind == required_order[required_index]:
                required_index += 1

        if required_index < len(required_order):
            return self._replay_reject(f"missing_{required_order[required_index]}", sequences)
        return EmbodiedReplayValidationResult(
            accepted=True,
            event_count=len(events),
            server_ledger_sequences=sequences,
        )

    def public_projection(self, attempt_id: str, *, extra_payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "attempt_id": attempt_id,
            "events": [
                {
                    "event_kind": event.event_kind,
                    "server_ledger_sequence": event.server_ledger_sequence,
                    "source_sequence": event.source_sequence,
                    "projection_policy_ref": event.projection_policy_ref,
                }
                for event in self.events_for_attempt(attempt_id)
            ],
            "extra_payload": self._projection_policy.project(extra_payload or {}),
        }

    @staticmethod
    def _replay_reject(error_code: str, sequences: list[int]) -> EmbodiedReplayValidationResult:
        return EmbodiedReplayValidationResult(
            accepted=False,
            error_code=error_code,
            event_count=len(sequences),
            server_ledger_sequences=sequences,
        )
