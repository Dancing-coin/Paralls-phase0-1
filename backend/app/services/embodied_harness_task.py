from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.harness_execution import FailureDisposition
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_interaction_session_service import (
    EmbodiedInteractionSessionService,
    InteractionSessionCommandResult,
)
from app.services.harness_execution_trace import HarnessExecutionTraceService
from app.services.harness_capability_store import HarnessCapabilityStore
from app.services.harness_failure_adapters import adapt_failure


class HarnessCapabilityError(ValueError):
    pass


class HarnessCapabilityGate:
    _PHASES = ("inspect", "preflight", "propose", "approve", "commit", "verify")

    def __init__(
        self,
        *,
        store: HarnessCapabilityStore | None = None,
        principal_ref: str = "harness",
        now: int = 1,
    ) -> None:
        self._index = 0
        self._store = store
        self._principal_ref = principal_ref
        self._now = now
        self._attempts: dict[tuple[str, str], int] = {}

    @property
    def current_phase(self) -> str:
        return self._PHASES[self._index]

    def require(self, phase: str) -> None:
        if phase != self.current_phase:
            raise HarnessCapabilityError(
                f"capability phase {phase!r} is not allowed; expected {self.current_phase!r}"
            )

    def consume(
        self,
        phase: str,
        *,
        task_id: str = "",
        correlation_id: str = "",
        policy_revision: str = "",
    ) -> None:
        self.require(phase)
        if self._store is not None:
            key = (task_id, phase)
            attempt = self._attempts.get(key, 0)
            grant_id = f"harness:{task_id}:{phase}:{attempt}"
            try:
                self._store.read(grant_id)
            except ValueError:
                from app.models.harness_execution import CapabilityGrant

                self._store.issue(
                    CapabilityGrant(
                        grant_id=grant_id,
                        principal_ref=self._principal_ref,
                        task_id=task_id,
                        phase=phase,
                        policy_revision=policy_revision,
                        expires_at=self._now + 3600,
                        nonce=f"nonce:{grant_id}",
                    )
                )
            try:
                self._store.consume(
                    grant_id=grant_id,
                    principal_ref=self._principal_ref,
                    task_id=task_id,
                    phase=phase,
                    policy_revision=policy_revision,
                    correlation_id=correlation_id,
                    now=self._now,
                )
            except ValueError as error:
                if "already_consumed" not in str(error):
                    raise HarnessCapabilityError(str(error)) from error
                self._attempts[key] = attempt + 1
                self.consume(
                    phase,
                    task_id=task_id,
                    correlation_id=correlation_id,
                    policy_revision=policy_revision,
                )
        if self._index < len(self._PHASES) - 1:
            self._index += 1

    def restore(self, phase: str) -> None:
        if phase not in self._PHASES:
            raise HarnessCapabilityError(f"unknown capability phase: {phase}")
        self._index = self._PHASES.index(phase)


def map_embodied_failure(error_code: str) -> FailureDisposition:
    return adapt_failure("embodied", error_code)


class EmbodiedHarnessTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    task_id: str = Field(min_length=1)
    phase: Literal["created", "running", "waiting", "recovering", "committed", "failed", "aborted"]
    error_code: str = ""
    failure_kind: str = ""
    authority_event_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class EmbodiedHarnessTaskCoordinator:
    """Harness control/evidence wrapper around the existing embodied authority service."""

    def __init__(
        self,
        *,
        session_service: EmbodiedInteractionSessionService,
        trace: HarnessExecutionTraceService,
        evidence_ledger: EmbodiedEvidenceLedger | None = None,
        capability_store: HarnessCapabilityStore | None = None,
        principal_ref: str = "harness:embodied",
    ) -> None:
        self._session = session_service
        self.trace = trace
        self._evidence = evidence_ledger
        self._capability_store = capability_store
        self._principal_ref = principal_ref
        self.gate = HarnessCapabilityGate(store=capability_store, principal_ref=principal_ref)

    def run_handshake(
        self,
        *,
        session_id: str,
        initiator_ref: str,
        participant_refs: list[str],
        target_refs: list[str],
        policy_revision: int,
        scene_revision: int,
        participant_private_terms: dict[str, dict[str, object]] | None = None,
        semantic_action: str = "handshake",
        authority_preflight_ref: str = "",
        causation_id: str = "",
        correlation_id: str = "",
        complete: bool = True,
    ) -> EmbodiedHarnessTaskResult:
        try:
            existing = self.trace.get_envelope(session_id)
        except ValueError:
            existing = None
        if existing is not None:
            if not self._session.session_state(session_id):
                # A process-local Gameplay store may have been rebuilt after a
                # restart; the old task ledger cannot stand in for missing authority history.
                self.trace.forget(session_id)
                if self._capability_store is not None:
                    self._capability_store.delete_task(session_id)
            else:
                return self.recover(session_id)

        correlation_id = correlation_id or f"corr:{session_id}"
        self.gate = HarnessCapabilityGate(
            store=self._capability_store,
            principal_ref=self._principal_ref,
            now=1,
        )
        self.trace.start(
            task_id=session_id,
            run_id=f"run:{session_id}",
            correlation_id=correlation_id,
            causation_id=causation_id or f"cmd:{session_id}:propose",
            policy_revision=str(policy_revision),
            authority_revision=str(scene_revision),
        )
        self.trace.transition(session_id, "running", producer_ts=1)
        authority_event_ids: list[str] = []

        def authority_metadata(result: InteractionSessionCommandResult) -> dict[str, object]:
            append = result.append_result
            return {
                "authority_event_ids": list(result.committed_event_ids),
                "transaction_id": append.transaction_id if append is not None else "",
                "global_sequence_range": list(append.global_sequence_range) if append is not None and append.global_sequence_range is not None else [],
                "resulting_stream_revisions": dict(append.resulting_stream_revisions) if append is not None else {},
            }

        gate_args = {"task_id": session_id, "correlation_id": correlation_id, "policy_revision": str(policy_revision)}
        self.gate.consume("inspect", **gate_args)
        self.trace.record(session_id, stage="inspect", status="observed", producer_ts=1, metadata={"participant_count": len(participant_refs), "target_refs": target_refs})
        self.gate.consume("preflight", **gate_args)
        self.trace.record(session_id, stage="preflight", status="accepted", producer_ts=1, metadata={"policy_revision": policy_revision, "scene_revision": scene_revision})

        self.gate.consume("propose", **gate_args)
        proposed = self._session.propose(
            session_id=session_id,
            semantic_action=semantic_action,
            initiator_ref=initiator_ref,
            participant_refs=participant_refs,
            target_refs=target_refs,
            authority_preflight_ref=authority_preflight_ref or f"preflight:{session_id}",
            policy_revision=policy_revision,
            scene_revision=scene_revision,
            causation_id=causation_id or f"cmd:{session_id}:propose",
            correlation_id=correlation_id,
            participant_private_terms=participant_private_terms,
        )
        authority_event_ids.extend(proposed.committed_event_ids)
        if not proposed.accepted:
            return self._fail(session_id, proposed.error_code, producer_ts=2, authority_event_ids=authority_event_ids)
        self.trace.record(session_id, stage="propose", status="committed", producer_ts=2, metadata=authority_metadata(proposed))

        self.gate.consume("approve", **gate_args)
        for participant_ref in participant_refs:
            if participant_ref == initiator_ref:
                continue
            accepted = self._session.accept(
                session_id=session_id,
                participant_ref=participant_ref,
                causation_id=f"cmd:{session_id}:accept:{participant_ref}",
                payload_digest=f"digest:accept:{session_id}:{participant_ref}",
            )
            authority_event_ids.extend(accepted.committed_event_ids)
            if not accepted.accepted:
                return self._fail(session_id, accepted.error_code, producer_ts=3, authority_event_ids=authority_event_ids)
        self.trace.record(session_id, stage="approve", status="committed", producer_ts=3, metadata=authority_metadata(accepted))

        self.gate.consume("commit", **gate_args)
        realizing = self._session.start_realizing(
            session_id=session_id,
            causation_id=f"cmd:{session_id}:realize",
        )
        authority_event_ids.extend(realizing.committed_event_ids)
        if not realizing.accepted:
            return self._fail(session_id, realizing.error_code, producer_ts=4, authority_event_ids=authority_event_ids)
        self.trace.record(session_id, stage="commit", status="realizing", producer_ts=4, metadata=authority_metadata(realizing))

        if not complete:
            self.gate.consume("verify", **gate_args)
            envelope = self.trace.transition(session_id, "waiting", producer_ts=5)
            return EmbodiedHarnessTaskResult(
                accepted=True,
                task_id=session_id,
                phase=envelope.phase,
                authority_event_ids=authority_event_ids,
            )

        for participant_ref in participant_refs:
            observation = self._session.record_terminal_observation(
                session_id=session_id,
                participant_ref=participant_ref,
                attempt_ref=f"attempt:{session_id}:{participant_ref}",
                terminal_status="completed",
                payload_digest=f"digest:terminal:{session_id}:{participant_ref}",
            )
            authority_event_ids.extend(observation.committed_event_ids)
            if not observation.accepted:
                return self._fail(session_id, observation.error_code, producer_ts=5, authority_event_ids=authority_event_ids)

        self.gate.consume("verify", **gate_args)
        evidence_refs = self._evidence_refs(session_id)
        self.trace.record(
            session_id,
            stage="verify",
            status="accepted",
            producer_ts=6,
            metadata={"authority_event_ids": authority_event_ids, "evidence_refs": evidence_refs, "evidence_count": len(evidence_refs)},
        )
        envelope = self.trace.transition(
            session_id,
            "committed",
            producer_ts=7,
            metadata={
                "authority_event_ids": authority_event_ids,
                "evidence_refs": evidence_refs,
                "evidence_count": len(evidence_refs),
            },
        )
        return EmbodiedHarnessTaskResult(
            accepted=True,
            task_id=session_id,
            phase=envelope.phase,
            authority_event_ids=authority_event_ids,
            evidence_refs=evidence_refs,
        )

    def recover(self, task_id: str) -> EmbodiedHarnessTaskResult:
        envelope = self.trace.get_envelope(task_id)
        if envelope.phase in {"committed", "aborted"}:
            return EmbodiedHarnessTaskResult(accepted=envelope.phase == "committed", task_id=task_id, phase=envelope.phase)
        if envelope.phase == "waiting":
            self.gate.restore("verify")
            self.trace.record(task_id, stage="recovery", status="ready", producer_ts=8, metadata={"recovery_action": "resume_terminal_observation"})
            return EmbodiedHarnessTaskResult(accepted=True, task_id=task_id, phase="waiting", error_code="recovery_ready")
        self.trace.transition(task_id, "recovering", producer_ts=8)
        return EmbodiedHarnessTaskResult(accepted=False, task_id=task_id, phase="recovering", error_code="recovery_required")

    def record_terminal_observation(
        self,
        *,
        task_id: str,
        participant_ref: str,
        attempt_ref: str,
        terminal_status: str,
        payload_digest: str,
        producer_ts: int,
    ) -> EmbodiedHarnessTaskResult:
        envelope = self.trace.get_envelope(task_id)
        if envelope.phase == "waiting":
            self.gate.restore("verify")
        result = self._session.record_terminal_observation(
            session_id=task_id,
            participant_ref=participant_ref,
            attempt_ref=attempt_ref,
            terminal_status=terminal_status,  # type: ignore[arg-type]
            payload_digest=payload_digest,
        )
        if not result.accepted:
            return self._fail(task_id, result.error_code, producer_ts=producer_ts, authority_event_ids=result.committed_event_ids)
        authority_event_ids = list(result.committed_event_ids)
        if result.session is None or result.session.state != "committed":
            self.trace.record(task_id, stage="terminal_observation", status=terminal_status, producer_ts=producer_ts, metadata={"authority_event_ids": authority_event_ids, "participant_ref": participant_ref, **self._append_metadata(result)})
            return EmbodiedHarnessTaskResult(accepted=True, task_id=task_id, phase="waiting", authority_event_ids=authority_event_ids)
        evidence_refs = self._evidence_refs(task_id)
        self.trace.record(task_id, stage="verify", status="accepted", producer_ts=producer_ts, metadata={"authority_event_ids": authority_event_ids, "evidence_refs": evidence_refs, "evidence_count": len(evidence_refs), **self._append_metadata(result)})
        committed = self.trace.transition(task_id, "committed", producer_ts=producer_ts, metadata={"authority_event_ids": authority_event_ids, "evidence_refs": evidence_refs, "evidence_count": len(evidence_refs), **self._append_metadata(result)})
        return EmbodiedHarnessTaskResult(accepted=True, task_id=task_id, phase=committed.phase, authority_event_ids=authority_event_ids, evidence_refs=evidence_refs)

    def record_godot_projection(
        self,
        task_id: str,
        messages: list[dict[str, object]],
        *,
        producer_ts: int = 0,
    ) -> None:
        safe_refs: list[dict[str, object]] = []
        for message in messages:
            payload = message.get("payload")
            if not isinstance(payload, dict):
                continue
            safe_refs.append(
                {
                    "message_type": str(message.get("message_type", "") or ""),
                    "event_id": str(payload.get("event_id", "") or ""),
                    "transaction_id": str(payload.get("transaction_id", "") or ""),
                    "global_sequence": int(payload.get("global_sequence", 0) or 0),
                    "session_id": str(payload.get("session_id", "") or ""),
                }
            )
        self.trace.record(
            task_id,
            stage="godot_projection",
            status="queued",
            producer_ts=producer_ts,
            metadata={"projection_refs": safe_refs},
        )

    def record_evidence_join(
        self,
        task_id: str,
        *,
        authority_result_ref: str = "",
        gameplay_transaction_id: str = "",
        gameplay_event_ids: list[str] | None = None,
        outbox_delivery_refs: list[str] | None = None,
        godot_receipt_ref: str = "",
        replay_hash: str = "",
        verifier_run_id: str = "",
        producer_ts: int = 0,
    ) -> None:
        self.trace.record(
            task_id,
            stage="evidence_join",
            status="verified",
            producer_ts=producer_ts,
            metadata={
                "authority_result_ref": authority_result_ref,
                "gameplay_transaction_id": gameplay_transaction_id,
                "gameplay_event_ids": list(gameplay_event_ids or []),
                "outbox_delivery_refs": list(outbox_delivery_refs or []),
                "godot_receipt_ref": godot_receipt_ref,
                "replay_hash": replay_hash,
                "verifier_run_id": verifier_run_id,
            },
        )

    def _fail(self, task_id: str, error_code: str, *, producer_ts: int, authority_event_ids: list[str]) -> EmbodiedHarnessTaskResult:
        disposition = map_embodied_failure(error_code)
        envelope = self.trace.transition(task_id, "failed", producer_ts=producer_ts, failure_kind=disposition.kind)  # type: ignore[arg-type]
        return EmbodiedHarnessTaskResult(
            accepted=False,
            task_id=task_id,
            phase=envelope.phase,
            error_code=error_code,
            failure_kind=disposition.kind,
            authority_event_ids=authority_event_ids,
        )

    def _evidence_refs(self, session_id: str) -> list[str]:
        if self._evidence is None:
            return []
        return [
            f"evidence:{event.server_ledger_sequence}"
            for event in self._evidence.events_for_attempt(session_id)
        ]

    @staticmethod
    def _append_metadata(result: InteractionSessionCommandResult) -> dict[str, object]:
        append = result.append_result
        return {
            "transaction_id": append.transaction_id if append is not None else "",
            "global_sequence_range": list(append.global_sequence_range) if append is not None and append.global_sequence_range is not None else [],
            "resulting_stream_revisions": dict(append.resulting_stream_revisions) if append is not None else {},
        }


__all__ = [
    "EmbodiedHarnessTaskCoordinator",
    "EmbodiedHarnessTaskResult",
    "HarnessCapabilityError",
    "HarnessCapabilityGate",
    "map_embodied_failure",
]
