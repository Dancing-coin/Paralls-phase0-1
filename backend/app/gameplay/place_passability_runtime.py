"""Presence-owned passability decisions for gate Place facts."""
from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Callable, Mapping
from typing import Literal

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayFailure
from app.gameplay.owner_runtime_base import replay_duplicate
from app.gameplay.place_event_schema import PLACE_ASSESSMENT_CONFIRMED_EVENT
from app.gameplay.settlement_plan import build_atomic_event_batch, build_multi_stream_atomic_event_batch
from app.gameplay.siege_physical_input_runtime import (
    PRESENCE_ASSESSMENT_INPUT_EVENT_V2,
    PresenceAssessmentReceipt,
    PresenceAssessmentReceiptV2,
    SiegePhysicalInputAuthority,
)


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

        record = self.store.get_idempotency_record(
            _PRESENCE_PRINCIPAL, command_id
        )
        if record is not None:
            try:
                replay = replay_duplicate(
                    self.store,
                    principal=_PRESENCE_PRINCIPAL,
                    idempotency_key=command_id,
                    payload_digest=record.payload_digest,
                    error_factory=ValueError,
                    missing_result_code="presence_replay_missing_result",
                    transaction_mismatch_code="presence_replay_transaction_mismatch",
                    event_count_mismatch_code="presence_replay_event_count_mismatch",
                    event_missing_code="presence_replay_event_missing",
                    expected_event_types=(_PASSABILITY_EVENT,),
                    expected_command_id=command_id,
                )
            except ValueError as error:
                return self._reject(command_id, str(error))
            if replay is not None:
                event = self.store.get_event(replay.committed_event_ids[0])
                if (
                    event.stream_id == self.stream_id(gate_ref)
                    and event.causation_id == breach_event_id
                ):
                    return replay
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

    def commit_signed_assessment(
        self,
        *,
        input_authority: SiegePhysicalInputAuthority,
        authority_ref: str,
        receipt_id: str,
        resolver_plan: Mapping[str, object] | None = None,
    ) -> AppendBatchResult:
        input_event = input_authority.presence_assessment_event(
            authority_ref=authority_ref,
            receipt_id=receipt_id,
        )
        if input_event is None:
            return self._reject(receipt_id, "place_assessment_input_unknown")
        if input_authority.store() is not self.store:
            return self._reject(receipt_id, "place_assessment_input_store_mismatch")
        if input_event.event_type == PRESENCE_ASSESSMENT_INPUT_EVENT_V2:
            receipt_v2 = PresenceAssessmentReceiptV2.model_validate(input_event.payload["receipt"])
            return self._commit_impact_assessment(receipt_v2, input_event, resolver_plan)
        receipt = PresenceAssessmentReceipt.model_validate(input_event.payload["receipt"])
        assessment = PlacePassabilityAssessment(
            state=receipt.state,
            assessment_ref=receipt.assessment_ref,
            read_stream_revisions={
                **receipt.source_stream_revisions,
                input_event.stream_id: input_event.stream_revision,
            },
            source_event_ids=(*receipt.source_event_ids, input_event.event_id),
        )
        authority = PlacePassabilityAuthority(
            store=self.store,
            resolver=lambda _gate_ref, _breach: assessment,
            evidence_event_principals={
                **self._evidence_event_principals,
                "gameplay.facility.gate_impact_input_received":
                    "authority:siege:physical-input",
                "gameplay.presence.assessment_input_received":
                    "authority:siege:physical-input",
            },
        )
        return authority.commit_assessment(
            gate_ref=receipt.gate_ref,
            breach_event_id=receipt.breach_event_id,
            expected_revision=self.store.get_stream_head(self.stream_id(receipt.gate_ref)),
        )

    def _commit_impact_assessment(
        self,
        receipt: PresenceAssessmentReceiptV2,
        input_event: GameplayEvent,
        resolver_plan: Mapping[str, object] | None,
    ) -> AppendBatchResult:
        command_id = f"place-impact-assessment:{receipt.impact_event_id}"
        idempotency_record = self.store.get_idempotency_record(
            _PRESENCE_PRINCIPAL, command_id
        )
        if idempotency_record is not None:
            try:
                prior = replay_duplicate(
                    self.store,
                    principal=_PRESENCE_PRINCIPAL,
                    idempotency_key=command_id,
                    payload_digest=idempotency_record.payload_digest,
                    error_factory=ValueError,
                    missing_result_code="presence_replay_missing_result",
                    transaction_mismatch_code="presence_replay_transaction_mismatch",
                    event_count_mismatch_code="presence_replay_event_count_mismatch",
                    event_missing_code="presence_replay_event_missing",
                    expected_command_id=command_id,
                )
            except ValueError as error:
                return self._reject(command_id, str(error))
            if prior is not None:
                event = self.store.get_event(prior.committed_event_ids[0])
                valid_state_change = (
                    event.event_type == _PASSABILITY_EVENT
                    and event.stream_id == self.stream_id(receipt.gate_ref)
                )
                valid_confirmation = (
                    event.event_type == PLACE_ASSESSMENT_CONFIRMED_EVENT
                    and event.stream_id
                    == f"{self.stream_id(receipt.gate_ref)}:assessments"
                )
                if event.payload.get("source_event_ids") != [
                    receipt.impact_event_id, input_event.event_id
                ]:
                    return self._reject(command_id, "place_impact_already_assessed")
                if valid_state_change or valid_confirmation:
                    return prior
                return self._reject(command_id, "presence_replay_transaction_mismatch")

        expected_sources = (receipt.impact_event_id, input_event.event_id)
        if (
            not isinstance(resolver_plan, Mapping)
            or set(resolver_plan) != {"state", "source_event_ids"}
            or resolver_plan.get("state") != receipt.state
            or resolver_plan.get("source_event_ids") != expected_sources
        ):
            return self._reject(command_id, "place_assessment_resolver_output_invalid")

        impact_event = self.store.get_event(receipt.impact_event_id)
        place_stream = self.stream_id(receipt.gate_ref)
        reads = {
            **receipt.expected_layer_revisions,
            impact_event.stream_id: impact_event.stream_revision,
            place_stream: receipt.expected_place_revision,
            input_event.stream_id: input_event.stream_revision,
        }
        if any(self.store.get_stream_head(stream) != revision for stream, revision in reads.items()):
            return self._reject(command_id, "place_assessment_source_stale")
        previous = self.state(receipt.gate_ref)
        payload = {
            "place_ref": receipt.gate_ref,
            "from_state": previous,
            "to_state": receipt.state,
            "assessment_ref": receipt.assessment_ref,
            "source_event_ids": [receipt.impact_event_id, input_event.event_id],
            "read_stream_revisions": dict(sorted(reads.items())),
        }
        if previous == receipt.state:
            stream = f"{place_stream}:assessments"
            return self.store.append_batch(build_multi_stream_atomic_event_batch(
                command_id=command_id,
                principal_ref=_PRESENCE_PRINCIPAL,
                expected_revisions={stream: self.store.get_stream_head(stream)},
                event_specs={stream: ((PLACE_ASSESSMENT_CONFIRMED_EVENT, payload),)},
                idempotency_key=command_id,
                causation_id=receipt.impact_event_id,
                correlation_id=f"presence:{receipt.gate_ref}",
                read_stream_revisions=reads,
                pinned_revisions=reads,
                event_visibility_policies={stream: ("authority_only",)},
            ))
        return self.store.append_batch(build_atomic_event_batch(
            command_id=command_id,
            principal_ref=_PRESENCE_PRINCIPAL,
            stream_id=place_stream,
            expected_revision=receipt.expected_place_revision,
            event_specs=((_PASSABILITY_EVENT, payload),),
            idempotency_key=command_id,
            causation_id=receipt.impact_event_id,
            correlation_id=f"presence:{receipt.gate_ref}",
            read_stream_revisions=reads,
            pinned_revisions=reads,
        ))

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
            and event.visibility_policy in {"project", "authority_only"}
            and self.store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=principal,
            )
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
