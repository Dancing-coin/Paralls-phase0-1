"""Presence-owned passability decisions for gate Place facts."""
from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Callable, Mapping
from typing import Literal

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayFailure
from app.gameplay.settlement_plan import build_atomic_event_batch


_PRESENCE_PRINCIPAL = "population.presence_authority"
_FACILITY_PRINCIPAL = "actor_gameplay.construction_production_domain"
_PASSABILITY_EVENT = "gameplay.presence.place_passability_changed"
_GATE_REF = re.compile(r"^gate-[a-z0-9-]+$")
PlacePassabilityResolver = Callable[
    [str, GameplayEvent], "PlacePassabilityAssessment | None"
]


@dataclass(frozen=True)
class PlacePassabilityAssessment:
    state: Literal["blocked", "passable"] | None
    assessment_ref: str
    read_stream_revisions: Mapping[str, int]
    source_event_ids: tuple[str, ...]


class PlacePassabilityAuthority:
    """Commit a trusted Presence assessment without deriving it from breach."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        resolver: PlacePassabilityResolver | None = None,
        evidence_event_principals: Mapping[str, str] | None = None,
    ) -> None:
        self.store = store
        self._resolver = resolver
        self._evidence_event_principals = dict(evidence_event_principals or {})

    @staticmethod
    def stream_id(gate_ref: str) -> str:
        return f"place:{gate_ref}:passability"

    def commit_assessment(
        self,
        *,
        gate_ref: str,
        breach_event_id: str,
        expected_revision: int,
    ) -> AppendBatchResult:
        command_id = f"place-passability:{gate_ref}:{breach_event_id}"
        if (
            not isinstance(gate_ref, str)
            or _GATE_REF.fullmatch(gate_ref) is None
            or type(expected_revision) is not int
            or expected_revision < 0
        ):
            return self._reject(command_id, "place_assessment_invalid")
        try:
            breach = self.store.get_event(breach_event_id)
        except KeyError:
            return self._reject(command_id, "place_breach_source_unknown")
        if not self._valid_breach(breach, gate_ref):
            return self._reject(command_id, "place_breach_source_invalid")

        prior = self.store.get_by_idempotency(
            _PRESENCE_PRINCIPAL, command_id
        )
        if prior is not None:
            if self._is_exact_retry(
                prior,
                command_id=command_id,
                gate_ref=gate_ref,
                breach_event_id=breach_event_id,
            ):
                return prior.model_copy(
                    update={"idempotency_status": "duplicate_replayed"}, deep=True
                )
            return self._reject(command_id, "place_assessment_idempotency_key_reused")

        assessment = (
            self._resolver(gate_ref, breach) if self._resolver is not None else None
        )
        if assessment is None:
            return self._reject(command_id, "place_assessment_unknown")
        if not isinstance(assessment, PlacePassabilityAssessment):
            return self._reject(command_id, "place_assessment_invalid")
        if assessment.state is None:
            return self._reject(command_id, "place_assessment_unknown")
        if (
            assessment.state not in {"blocked", "passable"}
            or not isinstance(assessment.assessment_ref, str)
            or not assessment.assessment_ref
            or not isinstance(assessment.read_stream_revisions, Mapping)
            or not assessment.read_stream_revisions
            or any(
                not isinstance(stream_id, str)
                or not stream_id
                or type(revision) is not int
                or revision < 1
                for stream_id, revision in assessment.read_stream_revisions.items()
            )
            or not isinstance(assessment.source_event_ids, tuple)
            or not assessment.source_event_ids
            or len(set(assessment.source_event_ids)) != len(assessment.source_event_ids)
            or breach_event_id not in assessment.source_event_ids
        ):
            return self._reject(command_id, "place_assessment_evidence_invalid")
        if not any(event_id != breach_event_id for event_id in assessment.source_event_ids):
            return self._reject(command_id, "place_assessment_unknown")

        reads = dict(assessment.read_stream_revisions)
        if breach.stream_id not in reads or reads[breach.stream_id] < breach.stream_revision:
            return self._reject(command_id, "place_assessment_evidence_invalid")
        for event_id in assessment.source_event_ids:
            try:
                source = self.store.get_event(event_id)
            except KeyError:
                return self._reject(command_id, "place_assessment_evidence_invalid")
            if source.stream_id not in reads or reads[source.stream_id] < source.stream_revision:
                return self._reject(command_id, "place_assessment_evidence_invalid")
            if source.event_id != breach.event_id and not self._valid_evidence_source(source):
                return self._reject(command_id, "place_assessment_evidence_invalid")

        for stream_id, revision in reads.items():
            if self.store.get_stream_head(stream_id) != revision:
                return self._reject(command_id, "place_assessment_source_stale")
        place_stream = self.stream_id(gate_ref)
        current = self.store.get_stream_head(place_stream)
        if current != expected_revision:
            return self._reject(command_id, "revision_conflict")
        previous = self.state(gate_ref)
        if previous == assessment.state:
            return self._reject(command_id, "place_assessment_unchanged")

        payload = {
            "place_ref": gate_ref,
            "from_state": previous,
            "to_state": assessment.state,
            "assessment_ref": assessment.assessment_ref,
            "source_event_ids": list(assessment.source_event_ids),
            "read_stream_revisions": dict(sorted(reads.items())),
        }
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=_PRESENCE_PRINCIPAL,
            stream_id=place_stream,
            expected_revision=expected_revision,
            event_specs=((_PASSABILITY_EVENT, payload),),
            idempotency_key=command_id,
            causation_id=breach.event_id,
            correlation_id=f"presence:{gate_ref}",
            read_stream_revisions=reads,
            pinned_revisions=reads,
        )
        return self.store.append_batch(batch)

    def state(self, gate_ref: str) -> str:
        events = self.store.read_stream(self.stream_id(gate_ref))
        state = "unknown"
        for event in events:
            if (
                event.event_type != _PASSABILITY_EVENT
                or event.schema_version != 1
                or event.visibility_policy != "project"
                or event.payload.get("place_ref") != gate_ref
                or event.payload.get("from_state") != state
                or event.payload.get("to_state") not in {"blocked", "passable"}
                or not self.store.transaction_owns_event(
                    transaction_id=event.transaction_id,
                    event_id=event.event_id,
                    principal_ref=_PRESENCE_PRINCIPAL,
                )
            ):
                raise ValueError("place_passability_history_invalid")
            state = event.payload["to_state"]
        return state

    def _valid_breach(self, event: GameplayEvent, gate_ref: str) -> bool:
        return (
            event.event_type == "gameplay.pool.threshold_crossed"
            and event.schema_version == 1
            and event.visibility_policy == "authority_only"
            and event.stream_id == f"fact:facility:{gate_ref}:integrity"
            and event.payload.get("fact_type") == event.stream_id
            and event.payload.get("threshold_ref") == "breach"
            and event.payload.get("direction") == "enter"
            and self.store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=_FACILITY_PRINCIPAL,
            )
        )

    def _valid_evidence_source(self, event: GameplayEvent) -> bool:
        principal = self._evidence_event_principals.get(event.event_type)
        return (
            principal is not None
            and event.visibility_policy == "project"
            and self.store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=principal,
            )
        )

    def _is_exact_retry(
        self,
        receipt: AppendBatchResult,
        *,
        command_id: str,
        gate_ref: str,
        breach_event_id: str,
    ) -> bool:
        batch = self.store.get_transaction(receipt.transaction_id)
        if (
            not receipt.committed
            or receipt.command_id != command_id
            or batch is None
            or batch.idempotency_record.principal_ref != _PRESENCE_PRINCIPAL
            or batch.idempotency_record.idempotency_key != command_id
            or len(batch.events) != 1
            or receipt.committed_event_ids != [batch.events[0].event_id]
        ):
            return False
        event = batch.events[0]
        return (
            event.event_type == _PASSABILITY_EVENT
            and event.stream_id == self.stream_id(gate_ref)
            and event.causation_id == breach_event_id
        )

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=code,
                message=code,
                failed_stage="place_passability",
            ),
        )
