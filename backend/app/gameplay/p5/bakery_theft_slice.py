from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import ReplayResult
from app.gameplay.p5.contracts import P5ResolutionResult, P5RevisionVector, canonical_sha256_digest
from app.gameplay.p5.investigation_conflict import (
    InvestigationConflictAuthority,
    InvestigationConflictAuthorityResult,
)
from app.gameplay.p5.quest_evidence import QuestEvidenceAuthority, QuestEvidenceAuthorityResult
from app.gameplay.p5.registry import P5PolicyRegistry
from app.gameplay.p5.social_knowledge import SocialFactAuthority, SocialFactAuthorityResult
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalMode


_PROJECTOR_ID = "projector:p5:bakery-theft-slice"
_PROJECTOR_VERSION = "v1"
_SLICED_REJECTED = "rejected_zero_write"


def _is_visible(visibility: str, recipient_ref: str) -> bool:
    if visibility == "public":
        return True
    if visibility == "authority_only":
        return recipient_ref.startswith("authority:")
    return visibility == f"actor:{recipient_ref}"


@dataclass(frozen=True)
class BakeryTheftInvestigationSliceResult:
    resolution: P5ResolutionResult
    social_result: SocialFactAuthorityResult
    quest_result: QuestEvidenceAuthorityResult
    conflict_result: InvestigationConflictAuthorityResult
    survival_mode: SurvivalMode


class BakeryTheftInvestigationSlice:
    def __init__(
        self,
        *,
        social_registry: P5PolicyRegistry,
        quest_registry: P5PolicyRegistry,
        conflict_registry: P5PolicyRegistry,
        store: GameplayEventStore,
    ) -> None:
        self._social_registry = social_registry
        self._quest_registry = quest_registry
        self._conflict_registry = conflict_registry
        self._store = store

    def resolve(
        self,
        *,
        social_command: GameplayCommandEnvelope,
        social_request,
        quest_command: GameplayCommandEnvelope,
        quest_request,
        conflict_command: GameplayCommandEnvelope,
        conflict_request,
        owner_fragments=(),
        reward_fragments=(),
        survival_mode: SurvivalMode,
        now: str,
    ) -> BakeryTheftInvestigationSliceResult:
        if survival_mode not in {SurvivalMode.DISABLED, SurvivalMode.NARRATIVE}:
            return self._rejected_result(
                failure_code="p5_survival_mode_unsupported",
                survival_mode=survival_mode,
            )

        hidden_failure = self._validate_hidden_clue_visibility(social_command=social_command)
        if hidden_failure is not None:
            return self._rejected_result(failure_code=hidden_failure, survival_mode=survival_mode)

        preview = self._resolve_components(
            store=self._clone_store(),
            social_command=social_command,
            social_request=social_request,
            quest_command=quest_command,
            quest_request=quest_request,
            conflict_command=conflict_command,
            conflict_request=conflict_request,
            owner_fragments=owner_fragments,
            reward_fragments=reward_fragments,
            now=now,
        )
        if self._is_rejected(preview):
            return self._rejected_result(
                failure_code=self._first_failure_code_from_results(preview),
                survival_mode=survival_mode,
            )

        # Component authorities retain their own SettlementPlan -> append_batch()
        # boundary.  Restore this single event store if a later component rejects
        # so the composed investigation remains all-or-nothing.
        before_actual = self._store.export_snapshot()
        before_write_ready = self._store.write_ready
        actual = self._resolve_components(
            store=self._store,
            social_command=social_command,
            social_request=social_request,
            quest_command=quest_command,
            quest_request=quest_request,
            conflict_command=conflict_command,
            conflict_request=conflict_request,
            owner_fragments=owner_fragments,
            reward_fragments=reward_fragments,
            now=now,
        )
        if self._is_rejected(actual):
            self._restore_store_snapshot(before_actual, write_ready=before_write_ready)
            return self._rejected_result(
                failure_code=self._first_failure_code_from_results(actual),
                survival_mode=survival_mode,
            )

        social_result, quest_result, conflict_result = actual
        resolution = self._summarize_resolution(
            social_result=social_result,
            quest_result=quest_result,
            conflict_result=conflict_result,
        )
        return BakeryTheftInvestigationSliceResult(
            resolution=resolution,
            social_result=social_result,
            quest_result=quest_result,
            conflict_result=conflict_result,
            survival_mode=survival_mode,
        )

    def view_for(self, *, recipient_ref: str, now: str) -> dict[str, object]:
        social_view = asdict(self._make_social_authority(self._store).view_for(recipient_ref=recipient_ref, now=now))
        quest_view = self._quest_view(recipient_ref=recipient_ref, now=now)
        conflict_view = self._make_conflict_authority(self._store).view_for(recipient_ref=recipient_ref, now=now)
        view = {
            "social": social_view,
            "quest": quest_view,
            "conflict": conflict_view,
        }
        view["source_revision_vector"] = self._combined_source_revision_vector(
            social_view=social_view,
            quest_view=quest_view,
            conflict_view=conflict_view,
        )
        view["projection_hash"] = canonical_sha256_digest(view)
        return view

    def replay_full(self, *, now: str) -> ReplayResult:
        state = self._projection_state(now=now, recipient_ref="authority:auditor")
        return ReplayResult(
            succeeded=True,
            projector_id=_PROJECTOR_ID,
            projector_version=_PROJECTOR_VERSION,
            projection_hash=canonical_sha256_digest(state),
            state=state,
            source_revision_vector=dict(state["source_revision_vector"]),
            last_global_sequence=self._last_global_sequence(),
            applied_event_ids=self._applied_event_ids(),
            applied_event_count=len(self._applied_event_ids()),
        )

    def replay_checkpoint_tail(self, *, checkpoint, now: str) -> ReplayResult:
        if checkpoint.projector_id != _PROJECTOR_ID or checkpoint.projector_version != _PROJECTOR_VERSION:
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint projector mismatch")
        if checkpoint.projection_schema_version != 1:
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint schema version mismatch")
        current = self.replay_full(now=now)
        if checkpoint.last_global_sequence > current.last_global_sequence:
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint is ahead of the event log")
        prefix_store = self._prefix_store_for_checkpoint(checkpoint=checkpoint)
        if prefix_store is None:
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint is not an event-log prefix")

        prefix_replay = self._slice_for_store(prefix_store).replay_full(now=now)
        if (
            checkpoint.state != prefix_replay.state
            or checkpoint.projection_hash != prefix_replay.projection_hash
            or checkpoint.source_revision_vector != prefix_replay.source_revision_vector
            or checkpoint.applied_event_ids != prefix_replay.applied_event_ids
        ):
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint state does not match its event-log prefix")

        for batch in self._store.read_transactions():
            if not batch.events or batch.events[-1].global_sequence <= checkpoint.last_global_sequence:
                continue
            appended = prefix_store.append_batch(batch)
            if not appended.committed:
                return self._failed_replay("p5_checkpoint_tail_failed", "tail batch could not be replayed")
        return self._slice_for_store(prefix_store).replay_full(now=now)

    def _resolve_components(
        self,
        *,
        store: GameplayEventStore,
        social_command: GameplayCommandEnvelope,
        social_request,
        quest_command: GameplayCommandEnvelope,
        quest_request,
        conflict_command: GameplayCommandEnvelope,
        conflict_request,
        owner_fragments,
        reward_fragments,
        now: str,
    ) -> tuple[SocialFactAuthorityResult, QuestEvidenceAuthorityResult, InvestigationConflictAuthorityResult]:
        social_authority = self._make_social_authority(store)
        quest_authority = self._make_quest_authority(store)
        social_command = self._namespaced_command(social_command, suffix="social")
        quest_command = self._namespaced_command(quest_command, suffix="quest")
        conflict_command = self._namespaced_command(conflict_command, suffix="conflict")
        social_duplicate = store.get_idempotency_record("authority:p5:social", social_command.idempotency_key) is not None

        social_result = social_authority.resolve(command=social_command, request=social_request, now=now)
        social_result = self._normalize_social_duplicate_result(social_result=social_result, duplicate=social_duplicate)
        quest_result = quest_authority.resolve(
            command=quest_command,
            request=quest_request,
            reward_fragments=reward_fragments,
            now=now,
        )
        conflict_command, conflict_request = self._align_conflict_inputs(
            store=store,
            conflict_command=conflict_command,
            conflict_request=conflict_request,
        )
        owner_fragments = self._align_owner_fragments(
            store=store,
            owner_fragments=owner_fragments,
            conflict_command=conflict_command,
        )
        conflict_result = self._resolve_conflict_component(
            store=store,
            conflict_command=conflict_command,
            conflict_request=conflict_request,
            owner_fragments=owner_fragments,
            now=now,
        )
        return social_result, quest_result, conflict_result

    def _validate_hidden_clue_visibility(self, *, social_command: GameplayCommandEnvelope) -> str | None:
        knowledge_fact = social_command.payload.get("knowledge_fact")
        if not isinstance(knowledge_fact, dict):
            return None
        fact_ref = str(knowledge_fact.get("fact_ref", ""))
        if not fact_ref.startswith("fact:clue:"):
            return None
        if str(knowledge_fact.get("visibility", "")) == "public":
            return "p5_hidden_clue_visibility_invalid"
        return None

    def _first_failure_code_from_results(
        self,
        results: tuple[SocialFactAuthorityResult, QuestEvidenceAuthorityResult, InvestigationConflictAuthorityResult],
    ) -> str:
        social_result, quest_result, conflict_result = results
        for result in (social_result, quest_result, conflict_result):
            if result.resolution.result_kind == _SLICED_REJECTED:
                return str(result.resolution.failure_code or "append_batch_failed")
        return "append_batch_failed"

    @staticmethod
    def _is_rejected(
        results: tuple[SocialFactAuthorityResult, QuestEvidenceAuthorityResult, InvestigationConflictAuthorityResult],
    ) -> bool:
        return any(result.resolution.result_kind == _SLICED_REJECTED for result in results)

    def _summarize_resolution(
        self,
        *,
        social_result: SocialFactAuthorityResult,
        quest_result: QuestEvidenceAuthorityResult,
        conflict_result: InvestigationConflictAuthorityResult,
    ) -> P5ResolutionResult:
        committed_event_refs = (
            tuple(social_result.resolution.committed_event_refs)
            + tuple(quest_result.resolution.committed_event_refs)
            + tuple(conflict_result.resolution.committed_event_refs)
        )
        result_kind = (
            "committed_adverse_outcome"
            if conflict_result.resolution.result_kind == "committed_adverse_outcome"
            else "committed_success"
        )
        return P5ResolutionResult(
            result_kind=result_kind,
            registry_ref=self._social_registry.registry_ref,
            registry_revision=self._social_registry.registry_revision,
            registry_digest=self._social_registry.registry_digest,
            committed_event_refs=committed_event_refs,
        )

    def _rejected_result(self, *, failure_code: str, survival_mode: SurvivalMode) -> BakeryTheftInvestigationSliceResult:
        social_result = self._rejected_social_result(failure_code=failure_code)
        quest_result = self._rejected_quest_result(failure_code=failure_code)
        conflict_result = self._rejected_conflict_result(failure_code=failure_code)
        return BakeryTheftInvestigationSliceResult(
            resolution=P5ResolutionResult(
                result_kind=_SLICED_REJECTED,
                registry_ref=self._social_registry.registry_ref,
                registry_revision=self._social_registry.registry_revision,
                registry_digest=self._social_registry.registry_digest,
                committed_event_refs=(),
                failure_code=failure_code,
            ),
            social_result=social_result,
            quest_result=quest_result,
            conflict_result=conflict_result,
            survival_mode=survival_mode,
        )

    def _rejected_social_result(self, *, failure_code: str) -> SocialFactAuthorityResult:
        return SocialFactAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind=_SLICED_REJECTED,
                registry_ref=self._social_registry.registry_ref,
                registry_revision=self._social_registry.registry_revision,
                registry_digest=self._social_registry.registry_digest,
                committed_event_refs=(),
                failure_code=failure_code,
            ),
            receipt=None,
            settlement_plan=None,
        )

    def _rejected_quest_result(self, *, failure_code: str) -> QuestEvidenceAuthorityResult:
        return QuestEvidenceAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind=_SLICED_REJECTED,
                registry_ref=self._quest_registry.registry_ref,
                registry_revision=self._quest_registry.registry_revision,
                registry_digest=self._quest_registry.registry_digest,
                committed_event_refs=(),
                failure_code=failure_code,
            ),
            receipt=None,
            settlement_plan=None,
        )

    def _rejected_conflict_result(self, *, failure_code: str) -> InvestigationConflictAuthorityResult:
        return InvestigationConflictAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind=_SLICED_REJECTED,
                registry_ref=self._conflict_registry.registry_ref,
                registry_revision=self._conflict_registry.registry_revision,
                registry_digest=self._conflict_registry.registry_digest,
                committed_event_refs=(),
                failure_code=failure_code,
            ),
            receipt=None,
            settlement_plan=None,
        )

    def _align_conflict_inputs(
        self,
        *,
        store: GameplayEventStore,
        conflict_command: GameplayCommandEnvelope,
        conflict_request,
    ) -> tuple[GameplayCommandEnvelope, object]:
        expected_revisions = dict(conflict_command.expected_revisions)
        read_set_revisions = dict(conflict_command.read_set_revisions)
        request_expected = self._vector_entries(conflict_request.expected_revisions)
        request_read = self._vector_entries(conflict_request.read_set_revisions)
        read_only_streams = (set(read_set_revisions) | set(request_read)) - (set(expected_revisions) | set(request_expected))
        for stream_ref in read_only_streams:
            head = store.get_stream_head(stream_ref)
            if stream_ref in read_set_revisions:
                read_set_revisions[stream_ref] = head
            if stream_ref in request_read:
                request_read[stream_ref] = head
        return (
            conflict_command.model_copy(update={"expected_revisions": expected_revisions, "read_set_revisions": read_set_revisions}, deep=True),
            conflict_request.model_copy(
                update={
                    "expected_revisions": P5RevisionVector(entries=request_expected),
                    "read_set_revisions": P5RevisionVector(entries=request_read),
                },
                deep=True,
            ),
        )

    def _align_owner_fragments(
        self,
        *,
        store: GameplayEventStore,
        owner_fragments,
        conflict_command: GameplayCommandEnvelope,
    ):
        adjusted = []
        write_streams = set(conflict_command.expected_revisions)
        for fragment in owner_fragments:
            read_set_revisions = dict(fragment.read_set_revisions)
            for stream_ref in set(read_set_revisions) - write_streams:
                read_set_revisions[stream_ref] = store.get_stream_head(stream_ref)
            adjusted.append(fragment.model_copy(update={"read_set_revisions": read_set_revisions}, deep=True))
        return tuple(adjusted)

    @staticmethod
    def _vector_entries(value: object) -> dict[str, int]:
        if hasattr(value, "entries"):
            return dict(getattr(value, "entries"))
        if isinstance(value, dict) and "entries" in value:
            return dict(value["entries"])
        if isinstance(value, dict):
            return dict(value)
        return {}

    def _clone_store(self) -> GameplayEventStore:
        return GameplayEventStore.from_snapshot(self._store.export_snapshot())

    def _restore_store_snapshot(self, snapshot: dict[str, Any], *, write_ready: bool) -> None:
        restored = GameplayEventStore.from_snapshot(snapshot)
        self._store.__dict__.update(restored.__dict__)
        self._store.set_write_readiness(write_ready)

    def _slice_for_store(self, store: GameplayEventStore) -> "BakeryTheftInvestigationSlice":
        return BakeryTheftInvestigationSlice(
            social_registry=self._social_registry,
            quest_registry=self._quest_registry,
            conflict_registry=self._conflict_registry,
            store=store,
        )

    def _prefix_store_for_checkpoint(self, *, checkpoint) -> GameplayEventStore | None:
        snapshot = self._store.export_snapshot()
        prefix_events = [
            event
            for event in snapshot["events"]
            if int(event["global_sequence"]) <= checkpoint.last_global_sequence
        ]
        if len(prefix_events) != checkpoint.last_global_sequence:
            return None
        prefix_event_ids = {event["event_id"] for event in prefix_events}
        prefix_transactions = [
            batch
            for batch in snapshot["transactions"]
            if all(int(event["global_sequence"]) <= checkpoint.last_global_sequence for event in batch["events"])
        ]
        transaction_event_ids = {
            event["event_id"]
            for batch in prefix_transactions
            for event in batch["events"]
        }
        if transaction_event_ids != prefix_event_ids:
            return None
        transaction_ids = {batch["transaction_id"] for batch in prefix_transactions}
        prefix_snapshot = dict(snapshot)
        prefix_snapshot["events"] = prefix_events
        prefix_snapshot["transactions"] = prefix_transactions
        prefix_snapshot["transaction_results"] = [
            result
            for result in snapshot["transaction_results"]
            if result["transaction_id"] in transaction_ids
        ]
        prefix_snapshot["idempotency"] = [
            entry
            for entry in snapshot["idempotency"]
            if entry["result"]["transaction_id"] in transaction_ids
        ]
        prefix_snapshot["outbox"] = [entry for entry in snapshot["outbox"] if entry["event_id"] in prefix_event_ids]
        prefix_snapshot["projection_checkpoints"] = []
        try:
            return GameplayEventStore.from_snapshot(prefix_snapshot)
        except Exception:
            return None

    @staticmethod
    def _namespaced_command(command: GameplayCommandEnvelope, *, suffix: str) -> GameplayCommandEnvelope:
        command_id = command.command_id if command.command_id.endswith(f":{suffix}") else f"{command.command_id}:{suffix}"
        transaction_id = command.transaction_id or f"tx:{command.command_id}"
        if not transaction_id.endswith(f":{suffix}"):
            transaction_id = f"{transaction_id}:{suffix}"
        return command.model_copy(
            update={
                "command_id": command_id,
                "transaction_id": transaction_id,
            },
            deep=True,
        )

    @staticmethod
    def _normalize_social_duplicate_result(
        *,
        social_result: SocialFactAuthorityResult,
        duplicate: bool,
    ) -> SocialFactAuthorityResult:
        if not duplicate or social_result.receipt is None:
            return social_result
        return SocialFactAuthorityResult(
            resolution=social_result.resolution,
            receipt=social_result.receipt.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
            settlement_plan=social_result.settlement_plan,
        )

    def _make_social_authority(self, store: GameplayEventStore) -> SocialFactAuthority:
        return SocialFactAuthority(registry=self._social_registry, store=store)

    def _make_quest_authority(self, store: GameplayEventStore) -> QuestEvidenceAuthority:
        return QuestEvidenceAuthority(registry=self._quest_registry, store=store)

    def _make_conflict_authority(self, store: GameplayEventStore) -> InvestigationConflictAuthority:
        return InvestigationConflictAuthority(registry=self._conflict_registry, store=store)

    def _resolve_conflict_component(
        self,
        *,
        store: GameplayEventStore,
        conflict_command: GameplayCommandEnvelope,
        conflict_request,
        owner_fragments,
        now: str,
    ) -> InvestigationConflictAuthorityResult:
        preview_store = GameplayEventStore.from_snapshot(store.export_snapshot())
        preview_result = self._make_conflict_authority(preview_store).resolve(
            command=conflict_command,
            request=conflict_request,
            owner_fragments=owner_fragments,
            now=now,
        )
        receipt = preview_result.receipt
        if receipt is None or not receipt.committed or receipt.idempotency_status == "duplicate_replayed":
            return preview_result

        preview_batch = preview_store.read_transactions()[-1]
        ordered_batch = self._ordered_conflict_batch(preview_batch)
        committed_receipt = store.append_batch(ordered_batch)
        if not committed_receipt.committed:
            failure_code = committed_receipt.failure.error_code if committed_receipt.failure is not None else "append_batch_failed"
            if failure_code in {"revision_conflict", "missing_expected_revision"}:
                failure_code = "p5_revision_stale"
            return self._rejected_conflict_result(failure_code=failure_code)

        return InvestigationConflictAuthorityResult(
            resolution=preview_result.resolution.model_copy(
                update={"committed_event_refs": tuple(committed_receipt.committed_event_ids)},
                deep=True,
            ),
            receipt=committed_receipt,
            settlement_plan=preview_result.settlement_plan,
        )

    @staticmethod
    def _ordered_conflict_batch(batch):
        priority = {
            "gameplay.investigation.observation_resolved": 0,
            "gameplay.conflict.attempt_resolved": 1,
            "gameplay.conflict.alarm_raised": 2,
            "gameplay.status_tag.applied": 3,
        }
        ordered_events = sorted(
            batch.events,
            key=lambda event: (priority.get(event.event_type, 99), event.event_id),
        )
        if list(ordered_events) == list(batch.events):
            return batch
        return batch.model_copy(update={"events": ordered_events}, deep=True)

    def _quest_view(self, *, recipient_ref: str, now: str) -> dict[str, object]:
        del now
        evidence_events: list[dict[str, object]] = []
        objective_events: list[dict[str, object]] = []
        source_revision_vector: dict[str, int] = {}
        for event in self._store.read_events():
            if event.event_type not in {
                "gameplay.quest.evidence_registered",
                "gameplay.quest.objective_transitioned",
            }:
                continue
            if not _is_visible(event.visibility_policy, recipient_ref):
                continue
            source_revision_vector[event.stream_id] = event.stream_revision
            payload = dict(event.payload)
            entry = {
                "event_type": event.event_type,
                "stream_id": event.stream_id,
                "visibility": event.visibility_policy,
                "payload": payload,
            }
            if event.event_type == "gameplay.quest.evidence_registered":
                evidence_events.append(entry)
            else:
                objective_events.append(entry)
        return {
            "evidence_events": tuple(evidence_events),
            "objective_events": tuple(objective_events),
            "source_revision_vector": dict(sorted(source_revision_vector.items())),
        }

    def _projection_state(self, *, now: str, recipient_ref: str) -> dict[str, object]:
        social_view = asdict(self._make_social_authority(self._store).view_for(recipient_ref=recipient_ref, now=now))
        quest_view = self._quest_view(recipient_ref=recipient_ref, now=now)
        conflict_view = self._make_conflict_authority(self._store).view_for(recipient_ref=recipient_ref, now=now)
        state = {
            "social": social_view,
            "quest": quest_view,
            "conflict": conflict_view,
        }
        state["source_revision_vector"] = self._combined_source_revision_vector(
            social_view=social_view,
            quest_view=quest_view,
            conflict_view=conflict_view,
        )
        return state

    def _combined_source_revision_vector(
        self,
        *,
        social_view: dict[str, object],
        quest_view: dict[str, object],
        conflict_view: dict[str, object],
    ) -> dict[str, int]:
        source_revision_vector: dict[str, int] = {}
        for view in (
            social_view,
            quest_view,
            conflict_view,
        ):
            for stream_ref, revision in dict(view.get("source_revision_vector", {})).items():
                source_revision_vector[str(stream_ref)] = int(revision)
        return dict(sorted(source_revision_vector.items()))

    def _last_global_sequence(self) -> int:
        return len(self._store.read_events())

    def _applied_event_ids(self) -> list[str]:
        return [event.event_id for event in self._store.read_events()]

    def _failed_replay(self, error_code: str, message: str) -> ReplayResult:
        from app.gameplay.models import GameplayFailure

        return ReplayResult(
            succeeded=False,
            projector_id=_PROJECTOR_ID,
            projector_version=_PROJECTOR_VERSION,
            failure=GameplayFailure(
                error_code=error_code,
                message=message,
                failed_stage="projection_replay",
            ),
        )


__all__ = ["BakeryTheftInvestigationSlice", "BakeryTheftInvestigationSliceResult"]
