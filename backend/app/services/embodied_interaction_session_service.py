from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.models.embodied_interaction import (
    InteractionSession,
    InteractionSessionParticipantTerm,
    InteractionSessionSlotAssignment,
    InteractionSessionTerminalObservation,
)
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger


class InteractionSessionCommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    session: InteractionSession | None = None
    append_result: AppendBatchResult | None = None
    error_code: str = ""
    committed_event_ids: list[str] = Field(default_factory=list)


class EmbodiedInteractionSessionService:
    """Backend-authority session lifecycle backed by Gameplay append_batch."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        dispatcher: GameplayOutboxDispatcher | None = None,
        evidence_ledger: EmbodiedEvidenceLedger | None = None,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._evidence_ledger = evidence_ledger or EmbodiedEvidenceLedger()
        self._sessions: dict[str, InteractionSession] = {}
        self._terminal_observations: dict[str, dict[str, InteractionSessionTerminalObservation]] = {}
        self._evidence_source_sequences: dict[str, int] = {}

    def propose(
        self,
        *,
        session_id: str,
        semantic_action: str,
        initiator_ref: str,
        participant_refs: list[str],
        target_refs: list[str],
        authority_preflight_ref: str,
        policy_revision: int,
        scene_revision: int,
        causation_id: str,
        correlation_id: str,
        participant_private_terms: dict[str, dict[str, object]] | None = None,
    ) -> InteractionSessionCommandResult:
        if session_id in self._sessions:
            return self._reject("session_exists")
        if participant_private_terms:
            unknown_private_terms = set(participant_private_terms).difference(participant_refs)
            if unknown_private_terms:
                return self._reject("participant_terms_unknown")
        terms = [
            InteractionSessionParticipantTerm(
                participant_ref=participant_ref,
                slot_id=f"slot:{session_id}:{index + 1}",
                consent_state="accepted" if participant_ref == initiator_ref else "pending",
                response_ref=f"response:{session_id}:{participant_ref}:initiated" if participant_ref == initiator_ref else "",
            )
            for index, participant_ref in enumerate(participant_refs)
        ]
        session = InteractionSession(
            session_id=session_id,
            semantic_action=semantic_action,
            initiator_ref=initiator_ref,
            participant_refs=participant_refs,
            target_refs=target_refs,
            state="awaiting_responses",
            participant_terms=terms,
            authority_preflight_ref=authority_preflight_ref,
            policy_revision=policy_revision,
            scene_revision=scene_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            visibility_policy="session_public_safe",
        )
        return self._commit_transition(
            session=session,
            causation_id=causation_id,
            event_payloads=[
                (
                    "embodied.interaction_session.proposed",
                    {
                        "session_id": session_id,
                        "semantic_action": semantic_action,
                        "state": session.state,
                        "initiator_ref": initiator_ref,
                        "participant_refs": participant_refs,
                        "target_refs": target_refs,
                        "policy_revision": policy_revision,
                        "scene_revision": scene_revision,
                    },
                )
            ],
            idempotency_key=f"interaction_session:{session_id}:propose",
            payload_digest=self._digest({"session_id": session_id, "causation_id": causation_id}),
            evidence_kinds=["session_lifecycle"],
        )

    def accept(
        self,
        *,
        session_id: str,
        participant_ref: str,
        causation_id: str,
        payload_digest: str,
    ) -> InteractionSessionCommandResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._reject("session_unknown")
        if session.state != "awaiting_responses":
            return self._reject("session_not_awaiting_responses", session)
        if participant_ref not in session.participant_refs:
            return self._reject("participant_unknown", session)

        terms = [
            term.model_copy(
                update={
                    "consent_state": "accepted",
                    "response_ref": f"response:{session_id}:{participant_ref}:accepted",
                },
                deep=True,
            )
            if term.participant_ref == participant_ref
            else term
            for term in session.participant_terms
        ]
        if all(term.consent_state == "accepted" for term in terms):
            slot_assignments = self._slot_assignments(session_id, session.participant_refs)
            next_session = session.model_copy(
                update={
                    "state": "authorized",
                    "participant_terms": terms,
                    "slot_assignments": slot_assignments,
                    "reservation_refs": [slot.reservation_ref for slot in slot_assignments],
                    "causation_id": causation_id,
                },
                deep=True,
            )
            payloads = [
                (
                    "embodied.interaction_session.accepted",
                    {
                        "session_id": session_id,
                        "participant_ref": participant_ref,
                        "state": "awaiting_responses",
                    },
                ),
                (
                    "embodied.interaction_session.authorized",
                    {
                        "session_id": session_id,
                        "state": "authorized",
                        "slot_assignments": [slot.model_dump(mode="json") for slot in slot_assignments],
                        "reservation_refs": [slot.reservation_ref for slot in slot_assignments],
                    },
                ),
            ]
            evidence_kinds = ["session_lifecycle", "session_lifecycle"]
        else:
            next_session = session.model_copy(
                update={"participant_terms": terms, "causation_id": causation_id},
                deep=True,
            )
            payloads = [
                (
                    "embodied.interaction_session.accepted",
                    {
                        "session_id": session_id,
                        "participant_ref": participant_ref,
                        "state": next_session.state,
                    },
                )
            ]
            evidence_kinds = ["session_lifecycle"]
        return self._commit_transition(
            session=next_session,
            causation_id=causation_id,
            event_payloads=payloads,
            idempotency_key=f"interaction_session:{session_id}:accept:{participant_ref}",
            payload_digest=payload_digest,
            evidence_kinds=evidence_kinds,
        )

    def reject(
        self,
        *,
        session_id: str,
        participant_ref: str,
        reason_code: str,
        causation_id: str,
        payload_digest: str,
    ) -> InteractionSessionCommandResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._reject("session_unknown")
        if session.state not in {"awaiting_responses", "authorized"}:
            return self._reject("session_not_rejectable", session)
        terms = [
            term.model_copy(
                update={
                    "consent_state": "rejected",
                    "response_ref": f"response:{session_id}:{participant_ref}:rejected",
                },
                deep=True,
            )
            if term.participant_ref == participant_ref
            else term
            for term in session.participant_terms
        ]
        next_session = session.model_copy(
            update={
                "state": "rejected",
                "participant_terms": terms,
                "slot_assignments": self._release_slots(session.slot_assignments),
                "reservation_refs": [],
                "causation_id": causation_id,
            },
            deep=True,
        )
        return self._commit_transition(
            session=next_session,
            causation_id=causation_id,
            event_payloads=[
                (
                    "embodied.interaction_session.rejected",
                    {
                        "session_id": session_id,
                        "participant_ref": participant_ref,
                        "reason_code": reason_code,
                        "state": "rejected",
                    },
                )
            ],
            idempotency_key=f"interaction_session:{session_id}:reject:{participant_ref}",
            payload_digest=payload_digest,
            evidence_kinds=["session_lifecycle"],
        )

    def start_realizing(self, *, session_id: str, causation_id: str) -> InteractionSessionCommandResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._reject("session_unknown")
        if session.state != "authorized":
            return self._reject("session_not_authorized", session)
        next_session = session.model_copy(update={"state": "realizing", "causation_id": causation_id}, deep=True)
        return self._commit_transition(
            session=next_session,
            causation_id=causation_id,
            event_payloads=[
                (
                    "embodied.interaction_session.realizing",
                    {
                        "session_id": session_id,
                        "state": "realizing",
                        "reservation_refs": session.reservation_refs,
                    },
                )
            ],
            idempotency_key=f"interaction_session:{session_id}:realizing",
            payload_digest=self._digest({"session_id": session_id, "causation_id": causation_id}),
            evidence_kinds=["session_lifecycle"],
        )

    def record_terminal_observation(
        self,
        *,
        session_id: str,
        participant_ref: str,
        attempt_ref: str,
        terminal_status: Literal["completed", "refused", "cancelled", "interrupted", "failed"],
        payload_digest: str,
    ) -> InteractionSessionCommandResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._reject("session_unknown")
        if session.state != "realizing":
            return self._reject("session_not_realizing", session)
        if participant_ref not in session.participant_refs:
            return self._reject("participant_unknown", session)
        observation = InteractionSessionTerminalObservation(
            participant_ref=participant_ref,
            attempt_ref=attempt_ref,
            terminal_status=terminal_status,
            payload_digest=payload_digest,
        )
        observations = dict(self._terminal_observations.get(session_id, {}))
        existing = observations.get(participant_ref)
        if existing is not None and existing.payload_digest == payload_digest:
            return InteractionSessionCommandResult(accepted=True, session=session)
        observations[participant_ref] = observation
        attempt_refs = [*session.attempt_refs]
        if attempt_ref not in attempt_refs:
            attempt_refs.append(attempt_ref)

        payloads: list[tuple[str, dict[str, object]]] = [
            (
                "embodied.interaction_session.participant_observed",
                {
                    "session_id": session_id,
                    "participant_ref": participant_ref,
                    "attempt_ref": attempt_ref,
                    "terminal_status": terminal_status,
                },
            )
        ]
        evidence_kinds = ["participant_terminal_observation"]
        next_session = session.model_copy(update={"attempt_refs": attempt_refs}, deep=True)
        if set(observations) == set(session.participant_refs) and all(
            item.terminal_status == "completed" for item in observations.values()
        ):
            next_session = next_session.model_copy(
                update={
                    "state": "committed",
                    "settlement_ref": f"settlement:{session_id}",
                    "slot_assignments": self._release_slots(session.slot_assignments),
                    "reservation_refs": [],
                },
                deep=True,
            )
            payloads.append(
                (
                    "embodied.interaction_session.committed",
                    {
                        "session_id": session_id,
                        "state": "committed",
                        "settlement_ref": next_session.settlement_ref,
                        "attempt_refs": attempt_refs,
                    },
                )
            )
            evidence_kinds.append("settlement")
        result = self._commit_transition(
            session=next_session,
            causation_id=f"observation:{session_id}:{participant_ref}",
            event_payloads=payloads,
            idempotency_key=f"interaction_session:{session_id}:terminal:{participant_ref}",
            payload_digest=payload_digest,
            evidence_kinds=evidence_kinds,
        )
        if result.accepted:
            self._terminal_observations[session_id] = observations
        return result

    def report_target_departure(
        self,
        *,
        session_id: str,
        target_ref: str,
        causation_id: str,
    ) -> InteractionSessionCommandResult:
        return self._interrupt(
            session_id=session_id,
            actor_ref=target_ref,
            reason_code="target_departed",
            causation_id=causation_id,
        )

    def interrupt(
        self,
        *,
        session_id: str,
        actor_ref: str,
        reason_code: str,
        causation_id: str,
    ) -> InteractionSessionCommandResult:
        return self._interrupt(
            session_id=session_id,
            actor_ref=actor_ref,
            reason_code=reason_code,
            causation_id=causation_id,
        )

    def cancel(self, *, session_id: str, participant_ref: str, causation_id: str) -> InteractionSessionCommandResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._reject("session_unknown")
        if session.state in {"committed", "rejected", "cancelled", "interrupted", "expired"}:
            return self._reject("session_terminal", session)
        next_session = session.model_copy(
            update={
                "state": "cancelled",
                "slot_assignments": self._release_slots(session.slot_assignments),
                "reservation_refs": [],
                "causation_id": causation_id,
            },
            deep=True,
        )
        return self._commit_transition(
            session=next_session,
            causation_id=causation_id,
            event_payloads=[
                (
                    "embodied.interaction_session.cancelled",
                    {
                        "session_id": session_id,
                        "participant_ref": participant_ref,
                        "state": "cancelled",
                    },
                )
            ],
            idempotency_key=f"interaction_session:{session_id}:cancel:{participant_ref}",
            payload_digest=self._digest({"session_id": session_id, "participant_ref": participant_ref, "causation_id": causation_id}),
            evidence_kinds=["session_lifecycle"],
        )

    def public_projection(self, session_id: str) -> dict[str, object]:
        session = self._sessions[session_id]
        return {
            "session_id": session.session_id,
            "semantic_action": session.semantic_action,
            "state": session.state,
            "participant_refs": session.participant_refs,
            "target_refs": session.target_refs,
            "safe_phase": session.state,
            "sync_status": session.state,
        }

    def session_state(self, session_id: str) -> str:
        session = self._sessions.get(session_id)
        return session.state if session is not None else ""

    def apply_external_committed_projection(
        self,
        *,
        session_id: str,
        attempt_refs: list[str],
        settlement_ref: str,
        causation_id: str,
    ) -> InteractionSessionCommandResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._reject("session_unknown")
        if session.state != "realizing":
            return self._reject("session_not_realizing", session)
        committed = session.model_copy(
            update={
                "state": "committed",
                "attempt_refs": attempt_refs,
                "settlement_ref": settlement_ref,
                "slot_assignments": self._release_slots(session.slot_assignments),
                "reservation_refs": [],
                "causation_id": causation_id,
            },
            deep=True,
        )
        self._sessions[session_id] = committed
        return InteractionSessionCommandResult(accepted=True, session=committed)

    def _interrupt(
        self,
        *,
        session_id: str,
        actor_ref: str,
        reason_code: str,
        causation_id: str,
    ) -> InteractionSessionCommandResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._reject("session_unknown")
        if session.state in {"committed", "rejected", "cancelled", "interrupted", "expired"}:
            return self._reject("session_terminal", session)
        next_session = session.model_copy(
            update={
                "state": "interrupted",
                "slot_assignments": self._release_slots(session.slot_assignments),
                "reservation_refs": [],
                "causation_id": causation_id,
            },
            deep=True,
        )
        return self._commit_transition(
            session=next_session,
            causation_id=causation_id,
            event_payloads=[
                (
                    "embodied.interaction_session.interrupted",
                    {
                        "session_id": session_id,
                        "actor_ref": actor_ref,
                        "reason_code": reason_code,
                        "state": "interrupted",
                    },
                )
            ],
            idempotency_key=f"interaction_session:{session_id}:interrupt:{actor_ref}:{reason_code}",
            payload_digest=self._digest({"session_id": session_id, "actor_ref": actor_ref, "reason_code": reason_code}),
            evidence_kinds=["session_lifecycle"],
        )

    def _commit_transition(
        self,
        *,
        session: InteractionSession,
        causation_id: str,
        event_payloads: list[tuple[str, dict[str, object]]],
        idempotency_key: str,
        payload_digest: str,
        evidence_kinds: list[str],
    ) -> InteractionSessionCommandResult:
        stream_id = self._stream_id(session.session_id)
        transaction_id = f"tx:{session.session_id}:{self._store.get_stream_head(stream_id) + 1}"
        events = []
        outbox_entries = []
        for index, (event_type, payload) in enumerate(event_payloads, start=1):
            event_id = f"evt:{session.session_id}:{self._event_suffix(event_type)}:{self._store.get_stream_head(stream_id) + index}"
            safe_payload = dict(payload)
            safe_payload.update(
                {
                    "policy_revision": session.policy_revision,
                    "scene_revision": session.scene_revision,
                    "visibility_policy": session.visibility_policy,
                }
            )
            events.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "schema_version": 1,
                    "stream_id": stream_id,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": transaction_id,
                    "command_id": causation_id,
                    "causation_id": causation_id,
                    "correlation_id": session.correlation_id,
                    "visibility_policy": session.visibility_policy,
                    "payload": safe_payload,
                }
            )
            public_outbox_payload = {
                "session_id": session.session_id,
                "semantic_action": session.semantic_action,
                "state": session.state,
                "participant_refs": session.participant_refs,
                "target_refs": session.target_refs,
                "safe_phase": session.state,
                "sync_status": session.state,
                "slot_assignments": [slot.model_dump(mode="json") for slot in session.slot_assignments],
                "reservation_refs": session.reservation_refs,
            }
            if session.settlement_ref is not None:
                public_outbox_payload["settlement_ref"] = session.settlement_ref
            outbox_entries.append(
                {
                    "outbox_id": f"outbox:{event_id}",
                    "transaction_id": transaction_id,
                    "event_id": event_id,
                    "global_sequence": 0,
                    "topic": event_type,
                    "audience": "godot_room",
                    "payload_projection": {
                        "room_id": "room_demo",
                        "scene_id": "scene_demo",
                        "zone_id": "zone_focus",
                        "source": {"layer": "embodied", "system": "interaction_session"},
                        "routing": {
                            "audience_mode": "room",
                            "routing_mode": "event_type",
                            "target_ids": ["godot_mirror", "observatory"],
                        },
                        "priority": "p1",
                        "durability": "replayable",
                        "payload": public_outbox_payload,
                    },
                    "delivery_state": "pending",
                    "attempt_count": 0,
                    "last_error": None,
                }
            )

        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": causation_id,
                "expected_stream_revisions": {stream_id: self._store.get_stream_head(stream_id)},
                "pinned_revisions": {
                    "policy": session.policy_revision,
                    "scene": session.scene_revision,
                },
                "events": events,
                "idempotency_record": {
                    "principal_ref": "embodied_interaction_session",
                    "idempotency_key": idempotency_key,
                    "payload_digest": payload_digest,
                },
                "outbox_entries": outbox_entries,
                "result_digest": self._digest({"session_id": session.session_id, "events": [event[0] for event in event_payloads]}),
                "projection_refresh_hints": [
                    {
                        "projection_id": "embodied_interaction_session",
                        "stream_id": stream_id,
                        "reason": "session_transition",
                    }
                ],
            }
        )
        if not append_result.committed:
            return InteractionSessionCommandResult(
                accepted=False,
                session=self._sessions.get(session.session_id),
                append_result=append_result,
                error_code=append_result.failure.error_code if append_result.failure is not None else "append_batch_failed",
            )
        self._sessions[session.session_id] = session
        for evidence_kind, (_, payload) in zip(evidence_kinds, event_payloads, strict=True):
            self._append_evidence(
                session_id=session.session_id,
                event_kind=evidence_kind,
                payload_digest=self._digest(payload),
                payload=self.public_projection(session.session_id),
            )
        if self._dispatcher is not None:
            self._dispatcher.dispatch_pending()
        return InteractionSessionCommandResult(
            accepted=True,
            session=session,
            append_result=append_result,
            committed_event_ids=append_result.committed_event_ids,
        )

    def _append_evidence(
        self,
        *,
        session_id: str,
        event_kind: str,
        payload_digest: str,
        payload: dict[str, object],
    ) -> None:
        source_sequence = self._evidence_source_sequences.get(session_id, 1)
        result = self._evidence_ledger.append(
            attempt_id=session_id,
            event_kind=event_kind,
            emitter_kind="backend",
            emitter_id="embodied_interaction_session_service",
            emitter_epoch=1,
            source_sequence=source_sequence,
            payload_digest=payload_digest,
            payload=payload,
        )
        if result.accepted:
            self._evidence_source_sequences[session_id] = source_sequence + 1

    @staticmethod
    def _slot_assignments(session_id: str, participant_refs: list[str]) -> list[InteractionSessionSlotAssignment]:
        return [
            InteractionSessionSlotAssignment(
                slot_id=f"slot:{session_id}:{index + 1}",
                participant_ref=participant_ref,
                role="initiator" if index == 0 else "counterparty",
                reservation_ref=f"reservation:{session_id}:{participant_ref}",
            )
            for index, participant_ref in enumerate(participant_refs)
        ]

    @staticmethod
    def _release_slots(slot_assignments: list[InteractionSessionSlotAssignment]) -> list[InteractionSessionSlotAssignment]:
        return [
            slot.model_copy(update={"reservation_state": "released"}, deep=True)
            for slot in slot_assignments
        ]

    @staticmethod
    def _stream_id(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def _event_suffix(event_type: str) -> str:
        return event_type.rsplit(".", maxsplit=1)[-1]

    @staticmethod
    def _digest(payload: dict[str, object]) -> str:
        return "sha256:" + sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()

    @staticmethod
    def _reject(error_code: str, session: InteractionSession | None = None) -> InteractionSessionCommandResult:
        return InteractionSessionCommandResult(accepted=False, session=session, error_code=error_code)
