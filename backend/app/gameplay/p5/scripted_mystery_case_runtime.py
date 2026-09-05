"""Owner-bound case lifecycle and replay projection for Stormnight."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import ProjectionCheckpoint, ReplayResult, StrictGameplayModel
from app.gameplay.p5.scripted_mystery_case_package import StormnightCasePackage, load_stormnight_case_package
from app.gameplay.p5.contracts import canonical_sha256_digest
from app.gameplay.settlement_plan import build_atomic_event_batch


_PRINCIPAL = "authority:p5:scripted-mystery-case"
_PROJECTOR_ID = "projector:p5:scripted-mystery-case"
_PROJECTOR_VERSION = "v1"
_CASE_EVENTS = {
    "case_opened": "gameplay.p5.mystery.case_opened@1",
    "statement_recorded": "gameplay.p5.mystery.statement_recorded@1",
    "accusation_submitted": "gameplay.p5.mystery.accusation_submitted@1",
    "case_outcome_resolved": "gameplay.p5.mystery.case_outcome_resolved@1",
}


def _case_stream(case_ref: str) -> str:
    slug = case_ref.split(":", 1)[-1].split("@", 1)[0]
    return f"gameplay:p5:mystery:{slug}"


class CaseOpenIntent(StrictGameplayModel):
    case_ref: str
    case_revision: str
    expected_stream_revision: int = 0
    command_id: str
    idempotency_key: str
    causation_id: str
    correlation_id: str
    submitted_at: str


class CasePhaseResult(StrictGameplayModel):
    committed: bool
    phase_ref: str
    idempotency_status: str
    error_code: str | None = None
    event_id: str | None = None


class CaseOutcomeResult(StrictGameplayModel):
    committed: bool
    outcome_kind: str
    idempotency_status: str
    error_code: str | None = None
    event_id: str | None = None


class CaseProjection(StrictGameplayModel):
    case_ref: str | None = None
    case_revision: str | None = None
    phase_ref: str | None = None
    opened: bool = False
    committed_clue_refs: tuple[str, ...] = ()
    accusation_refs: tuple[str, ...] = ()
    terminal_outcome: str | None = None
    source_revision_vector: dict[str, int] = {}
    applied_event_ids: tuple[str, ...] = ()
    last_global_sequence: int = 0


@dataclass(frozen=True)
class ScriptedMysteryCaseAuthority:
    store: GameplayEventStore
    package: StormnightCasePackage

    @classmethod
    def create(cls, store: GameplayEventStore, package: StormnightCasePackage | None = None) -> "ScriptedMysteryCaseAuthority":
        resolved = package or load_stormnight_case_package()
        resolved.validate()
        return cls(store=store, package=resolved)

    @property
    def stream_id(self) -> str:
        return _case_stream(self.package.content.case_ref)

    def open_case(self, intent: CaseOpenIntent) -> CasePhaseResult:
        if intent.case_ref != self.package.content.case_ref or intent.case_revision != self.package.content.case_revision:
            return CasePhaseResult(committed=False, phase_ref="", idempotency_status="rejected", error_code="case_identity_mismatch")
        return self._append_phase(intent, phase_ref="phase:stormnight:arrival@1", event_name=_CASE_EVENTS["case_opened"])

    def advance_phase(self, *, command_id: str, idempotency_key: str, phase_ref: str, expected_revision: int, causation_id: str, correlation_id: str) -> CasePhaseResult:
        projection = self.project()
        if not projection.opened:
            return CasePhaseResult(committed=False, phase_ref=phase_ref, idempotency_status="rejected", error_code="case_not_open")
        expected_next = {"phase:stormnight:arrival@1": "phase:stormnight:investigation@1", "phase:stormnight:investigation@1": "phase:stormnight:storm-night@1"}.get(projection.phase_ref or "")
        if expected_next != phase_ref:
            return CasePhaseResult(committed=False, phase_ref=phase_ref, idempotency_status="rejected", error_code="case_phase_order_invalid")
        if self.store.get_stream_head(self.stream_id) != expected_revision:
            return CasePhaseResult(committed=False, phase_ref=phase_ref, idempotency_status="rejected", error_code="case_revision_stale")
        return self._append_phase(
            CaseOpenIntent(case_ref=self.package.content.case_ref, case_revision=self.package.content.case_revision, expected_stream_revision=expected_revision, command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, submitted_at="now"),
            phase_ref=phase_ref,
            event_name=_CASE_EVENTS["case_opened"],
        )

    def resolve_outcome(self, *, command_id: str, idempotency_key: str, outcome_kind: Literal["case_solved", "false_accusation", "culprit_escaped", "investigator_captured"], expected_revision: int, causation_id: str, correlation_id: str) -> CaseOutcomeResult:
        existing = self.store.get_idempotency_record(_PRINCIPAL, idempotency_key)
        if existing is not None:
            receipt = self.store.get_by_idempotency(_PRINCIPAL, idempotency_key)
            return CaseOutcomeResult(committed=True, outcome_kind=outcome_kind, idempotency_status="duplicate_replayed", event_id=receipt.committed_event_ids[0] if receipt and receipt.committed_event_ids else None)
        if self.store.get_stream_head(self.stream_id) != expected_revision:
            return CaseOutcomeResult(committed=False, outcome_kind=outcome_kind, idempotency_status="rejected", error_code="case_revision_stale")
        if outcome_kind not in {item.outcome_kind for item in self.package.content.outcome_definitions}:
            return CaseOutcomeResult(committed=False, outcome_kind=outcome_kind, idempotency_status="rejected", error_code="case_outcome_unknown")
        payload = self._payload(case_ref=self.package.content.case_ref, case_revision=self.package.content.case_revision, phase_ref=self.project().phase_ref, outcome_kind=outcome_kind)
        result = self._append(command_id, idempotency_key, expected_revision, causation_id, correlation_id, _CASE_EVENTS["case_outcome_resolved"], payload)
        if not result.committed:
            return CaseOutcomeResult(committed=False, outcome_kind=outcome_kind, idempotency_status="rejected", error_code=result.failure.error_code if result.failure else "case_append_failed")
        return CaseOutcomeResult(committed=True, outcome_kind=outcome_kind, idempotency_status=result.idempotency_status, event_id=result.committed_event_ids[0] if result.committed_event_ids else None)

    def project(self) -> CaseProjection:
        return self._project_events(self.store.read_events())

    def replay_full(self) -> ReplayResult:
        projection = self._project_events(self.store.read_events())
        return ReplayResult(succeeded=True, projector_id=_PROJECTOR_ID, projector_version=_PROJECTOR_VERSION, projection_hash=canonical_sha256_digest(projection.model_dump(mode="json")), state=projection.model_dump(mode="json"), source_revision_vector=projection.source_revision_vector, last_global_sequence=projection.last_global_sequence, applied_event_ids=list(projection.applied_event_ids), applied_event_count=len(projection.applied_event_ids))

    def create_checkpoint(self, events: list[object]) -> ProjectionCheckpoint:
        projection = self._project_events(events)
        return ProjectionCheckpoint(checkpoint_id="checkpoint:stormnight:case", projector_id=_PROJECTOR_ID, projector_version=_PROJECTOR_VERSION, projection_schema_version=1, source_revision_vector=projection.source_revision_vector, last_global_sequence=projection.last_global_sequence, state=projection.model_dump(mode="json"), applied_event_ids=list(projection.applied_event_ids), projection_hash=canonical_sha256_digest(projection.model_dump(mode="json")))

    def replay_checkpoint_tail(self, checkpoint: ProjectionCheckpoint) -> ReplayResult:
        if checkpoint.projector_id != _PROJECTOR_ID or checkpoint.projector_version != _PROJECTOR_VERSION:
            return ReplayResult(succeeded=False, projector_id=_PROJECTOR_ID, projector_version=_PROJECTOR_VERSION, failure={"error_code": "case_checkpoint_incompatible", "message": "projector mismatch", "failed_stage": "replay"})
        prefix = self.store.read_events(limit=checkpoint.last_global_sequence)
        current = self._project_events(prefix)
        if current.model_dump(mode="json") != checkpoint.state or canonical_sha256_digest(current.model_dump(mode="json")) != checkpoint.projection_hash:
            return ReplayResult(succeeded=False, projector_id=_PROJECTOR_ID, projector_version=_PROJECTOR_VERSION, failure={"error_code": "case_checkpoint_mismatch", "message": "checkpoint does not match prefix", "failed_stage": "replay"})
        tail = self.store.read_events(global_sequence_after=checkpoint.last_global_sequence)
        projection = self._project_events(prefix + tail)
        return ReplayResult(succeeded=True, projector_id=_PROJECTOR_ID, projector_version=_PROJECTOR_VERSION, projection_hash=canonical_sha256_digest(projection.model_dump(mode="json")), state=projection.model_dump(mode="json"), source_revision_vector=projection.source_revision_vector, last_global_sequence=projection.last_global_sequence, applied_event_ids=list(projection.applied_event_ids), applied_event_count=len(projection.applied_event_ids))

    def _append_phase(self, intent: CaseOpenIntent, *, phase_ref: str, event_name: str) -> CasePhaseResult:
        existing = self.store.get_idempotency_record(_PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            receipt = self.store.get_by_idempotency(_PRINCIPAL, intent.idempotency_key)
            return CasePhaseResult(committed=True, phase_ref=phase_ref, idempotency_status="duplicate_replayed", event_id=receipt.committed_event_ids[0] if receipt and receipt.committed_event_ids else None)
        if self.store.get_stream_head(self.stream_id) != intent.expected_stream_revision:
            return CasePhaseResult(committed=False, phase_ref=phase_ref, idempotency_status="rejected", error_code="case_revision_stale")
        payload = self._payload(case_ref=intent.case_ref, case_revision=intent.case_revision, phase_ref=phase_ref)
        result = self._append(intent.command_id, intent.idempotency_key, intent.expected_stream_revision, intent.causation_id, intent.correlation_id, event_name, payload)
        if not result.committed:
            return CasePhaseResult(committed=False, phase_ref=phase_ref, idempotency_status="rejected", error_code=result.failure.error_code if result.failure else "case_append_failed")
        return CasePhaseResult(committed=True, phase_ref=phase_ref, idempotency_status=result.idempotency_status, event_id=result.committed_event_ids[0] if result.committed_event_ids else None)

    def _append(self, command_id: str, idempotency_key: str, expected_revision: int, causation_id: str, correlation_id: str, event_name: str, payload: dict[str, object]):
        batch = build_atomic_event_batch(command_id=command_id, principal_ref=_PRINCIPAL, stream_id=self.stream_id, expected_revision=expected_revision, read_stream_revisions={self.stream_id: expected_revision}, event_specs=((event_name, payload),), idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, pinned_revisions={"package": 1})
        return self.store.append_batch(batch)

    def _payload(self, **values: object) -> dict[str, object]:
        return {"package_revision": self.package.manifest.patch_revision_id, "content_digest": self.package.manifest.content_digest, "declaration_digest": self.package.canonical_declaration_digest, "descriptor_ref": self.package.binding.descriptor_ref, "policy_revision": "policy:scripted-mystery-case@1", "visibility_policy": "project", **values}

    def _project_events(self, events: list[object]) -> CaseProjection:
        case_ref = case_revision = phase_ref = outcome = None
        opened = False
        clues: list[str] = []
        accusations: list[str] = []
        revisions: dict[str, int] = {}
        ids: list[str] = []
        last_sequence = 0
        for event in events:
            if not str(event.event_type).startswith("gameplay.p5.mystery."):
                continue
            payload = dict(event.payload)
            if payload.get("package_revision") != self.package.manifest.patch_revision_id or payload.get("content_digest") != self.package.manifest.content_digest:
                raise ValueError("stormnight_case_provenance_tampered")
            case_ref = str(payload.get("case_ref", case_ref or ""))
            case_revision = str(payload.get("case_revision", case_revision or ""))
            phase_ref = str(payload.get("phase_ref", phase_ref or ""))
            opened = opened or event.event_type == _CASE_EVENTS["case_opened"]
            if event.event_type == _CASE_EVENTS["case_outcome_resolved"]:
                outcome = str(payload.get("outcome_kind", ""))
            revisions[event.stream_id] = event.stream_revision
            ids.append(event.event_id)
            last_sequence = max(last_sequence, event.global_sequence)
        return CaseProjection(case_ref=case_ref, case_revision=case_revision, phase_ref=phase_ref, opened=opened, committed_clue_refs=tuple(clues), accusation_refs=tuple(accusations), terminal_outcome=outcome, source_revision_vector=dict(sorted(revisions.items())), applied_event_ids=tuple(ids), last_global_sequence=last_sequence)


__all__ = ["CaseOpenIntent", "CaseOutcomeResult", "CasePhaseResult", "CaseProjection", "ScriptedMysteryCaseAuthority"]
