from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayFailure, GameplayOutboxEntry, StrictGameplayModel
from app.gameplay.organization_government_runtime import (
    GovernmentAuthority,
    OrganizationAuthority,
)
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.reference_data_runtime import ReferenceDataAuthority, ReferenceDatasetView
from app.gameplay.settlement_plan import SettlementPlan as EventStoreSettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope

from .batch import PopulationPlanner
from .branch_replay_contract import FixedBaseBranchReplayContract
from .models import BatchIntentCandidate, WorldModeProfile


def _digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _event_digest(events: list[object]) -> str:
    return _digest([event.model_dump(mode="json") for event in events])


class PreviewModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReferenceDataset(PreviewModel):
    dataset_ref: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    license_ref: str = Field(min_length=1)
    schema_revision: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    allowed_scopes: tuple[str, ...] = ()


class CalibrationInput(PreviewModel):
    calibration_ref: str = Field(min_length=1)
    dataset_ref: str = Field(min_length=1)
    parameter_mapping_revision: str = Field(min_length=1)
    world_revision: str = Field(min_length=1)
    ruleset_revision: str = Field(min_length=1)
    privacy_scope: str = Field(min_length=1)


class FrozenReferenceDatasetInput(PreviewModel):
    dataset_ref: str = Field(min_length=1)
    dataset_revision: int = Field(ge=1)
    projection_digest: str = Field(min_length=1)
    source_event_refs: tuple[str, ...] = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    allowed_scopes: tuple[str, ...] = Field(min_length=1)
    dataset_digest: str = Field(min_length=1)

    @classmethod
    def freeze(cls, *, view: ReferenceDatasetView) -> "FrozenReferenceDatasetInput":
        return cls(dataset_ref=view.dataset_ref, dataset_revision=view.dataset_revision, projection_digest=view.projection_digest, source_event_refs=view.source_event_refs, source_revision_vector=dict(view.source_revision_vector), allowed_scopes=view.allowed_scopes, dataset_digest=view.digest)

    def validate_against(self, *, store: GameplayEventStore) -> str | None:
        stream_id = ReferenceDataAuthority.dataset_stream_id(dataset_ref=self.dataset_ref)
        if set(self.source_revision_vector) != {stream_id}:
            return "reference_dataset_source_vector_invalid"
        result = ReferenceDataAuthority(store=store).view_for(dataset_ref=self.dataset_ref, reader_scope="authority", expected_dataset_revision=self.dataset_revision)
        if not result.accepted or result.view is None:
            return result.error_code or "reference_dataset_source_unavailable"
        if store.get_stream_head(stream_id) != self.source_revision_vector[stream_id]:
            return "reference_dataset_source_revision_stale"
        view = result.view
        if view.projection_digest != self.projection_digest:
            return "reference_dataset_projection_digest_mismatch"
        if view.source_event_refs != self.source_event_refs or view.digest != self.dataset_digest:
            return "reference_dataset_source_mismatch"
        if view.source_revision_vector != self.source_revision_vector:
            return "reference_dataset_source_vector_mismatch"
        if view.allowed_scopes != self.allowed_scopes:
            return "reference_dataset_scope_mismatch"
        if view.license_status != "permitted":
            return "reference_dataset_license_denied"
        return None



class FamilyOrganizationProjectionInput(PreviewModel):
    profile_ref: str = Field(min_length=1)
    source_projection_ref: str = Field(min_length=1)
    source_revision: int = Field(ge=0)
    privacy_scope: str = Field(min_length=1)
    digest: str = Field(min_length=1)


class BranchPreviewRequest(PreviewModel):
    branch_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    base_event_digest: str = Field(min_length=1)
    base_checkpoint_sequence: int = Field(default=0, ge=0)
    tail_boundary: int = Field(default=0, ge=0)
    source_digests: dict[str, str] = Field(default_factory=dict)
    deterministic_seed: str = Field(min_length=1)
    active_revision_refs: tuple[str, ...] = ()
    calibration_ref: str = Field(min_length=1)
    privacy_scope: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_boundaries(self) -> "BranchPreviewRequest":
        if self.tail_boundary < self.base_checkpoint_sequence:
            raise ValueError("branch_tail_before_base")
        if any(not value.startswith("sha256:") for value in self.source_digests.values()):
            raise ValueError("branch_source_digest_invalid")
        return self


class BranchPreviewResult(PreviewModel):
    accepted: bool
    error_code: str | None = None
    report_digest: str = ""
    public_report: dict[str, object] = Field(default_factory=dict)
    branch_event_count: int = Field(default=0, ge=0)


class BranchPromotionResult(PreviewModel):
    accepted: bool
    error_code: str | None = None


class BranchPreviewAuthority:
    """Isolated analysis buffer; only explicit creator-debug snapshots may append."""

    def __init__(self, *, store: GameplayEventStore, registry: CharacterProfileRegistry) -> None:
        self.store = store
        self.registry = registry
        # This is an isolated, non-production analysis buffer. Snapshot storage
        # is explicit and uses only the existing creator-debug branch stream.
        self._buffers: dict[str, tuple[dict[str, object], ...]] = {}

    _PRINCIPAL = "authority:branch_preview"
    _ADMISSION_STREAM_PREFIX = "gameplay:branch_preview:"

    @classmethod
    def admission_stream_id(cls, *, branch_ref: str) -> str:
        return f"{cls._ADMISSION_STREAM_PREFIX}{branch_ref}"

    def preview(
        self,
        *,
        request: BranchPreviewRequest,
        dataset: ReferenceDataset,
        calibration: CalibrationInput,
        family_inputs: tuple[FamilyOrganizationProjectionInput, ...],
        candidates: tuple[BatchIntentCandidate, ...],
        mode: WorldModeProfile,
    ) -> BranchPreviewResult:
        if request.privacy_scope not in dataset.allowed_scopes or calibration.privacy_scope not in dataset.allowed_scopes:
            return BranchPreviewResult(accepted=False, error_code="dataset_scope_denied")
        if calibration.calibration_ref != request.calibration_ref or calibration.dataset_ref != dataset.dataset_ref:
            return BranchPreviewResult(accepted=False, error_code="calibration_dataset_mismatch")
        base_events = self.store.read_events()
        if request.tail_boundary > len(base_events) or request.base_checkpoint_sequence > request.tail_boundary:
            return BranchPreviewResult(accepted=False, error_code="branch_tail_boundary_mismatch")
        base_prefix = base_events[: request.base_checkpoint_sequence]
        base_digest = _event_digest(base_prefix)
        if request.base_event_digest != base_digest and not (request.base_event_digest == "sha256:empty" and not base_prefix):
            return BranchPreviewResult(accepted=False, error_code="branch_base_mismatch")
        calibration_digest = _digest(calibration.model_dump(mode="json"))
        expected_calibration_digest = request.source_digests.get("calibration")
        if expected_calibration_digest is not None and expected_calibration_digest != calibration_digest:
            return BranchPreviewResult(accepted=False, error_code="branch_source_digest_mismatch")
        if any(not item.profile_ref.startswith("character:") for item in family_inputs):
            return BranchPreviewResult(accepted=False, error_code="family_projection_invalid")
        try:
            for item in family_inputs:
                self.registry.profile_ref(item.profile_ref)
            for candidate in candidates:
                self.registry.profile_ref(candidate.profile_ref)
        except KeyError:
            return BranchPreviewResult(accepted=False, error_code="profile_not_registered")
        candidate_digests = tuple(
            (candidate.intent_ref, _digest(candidate.model_dump(mode="json")))
            for candidate in candidates
        )
        replay_contract = FixedBaseBranchReplayContract.from_preview_inputs(
            branch_ref=request.branch_ref,
            base_event_digest=base_digest,
            base_checkpoint_sequence=request.base_checkpoint_sequence,
            tail_boundary=request.tail_boundary,
            calibration_ref=calibration.calibration_ref,
            calibration=calibration.model_dump(mode="json"),
            source_digests=request.source_digests,
            candidate_digests=candidate_digests,
            family_digests=tuple(item.digest for item in family_inputs),
            dataset_digest=dataset.digest,
            privacy_scope=request.privacy_scope,
            stream_id=self.admission_stream_id(branch_ref=request.branch_ref),
        )
        plan = PopulationPlanner().plan(
            batch_ref=f"preview:{request.branch_ref}", world_ref=request.world_ref, mode=mode,
            candidates=candidates,
            input_digest=_digest(
                {
                    "base": base_digest,
                    "tail_event_ids": [
                        event.event_id
                        for event in base_events[
                            request.base_checkpoint_sequence : request.tail_boundary
                        ]
                    ],
                    "family": [item.digest for item in family_inputs],
                    "dataset": dataset.digest,
                    "source_digests": dict(sorted(request.source_digests.items())),
                }
            ),
            deterministic_seed=request.deterministic_seed,
        ) if candidates else None
        descriptor = {
            "kind": "branch_descriptor",
            "branch_ref": request.branch_ref,
            "plan_digest": _digest(plan.model_dump(mode="json")) if plan else _digest({"empty": request.branch_ref}),
            "base_event_digest": base_digest,
            "base_checkpoint_sequence": request.base_checkpoint_sequence,
            "tail_boundary": request.tail_boundary,
            "source_digests": dict(sorted(request.source_digests.items())),
            "active_revision_refs": request.active_revision_refs,
            "calibration_ref": calibration.calibration_ref,
            "dataset_digest": dataset.digest,
            "replay_contract": replay_contract.model_dump(mode="json"),
            "replay_contract_digest": replay_contract.contract_digest,
        }
        ordered_candidates = plan.candidates if plan is not None else ()
        candidate_events = tuple(
            {
                "kind": "branch_candidate_proposed",
                "sequence": index,
                "intent_ref": candidate.intent_ref,
                "profile_ref": candidate.profile_ref,
                "intent_kind": candidate.intent_kind,
                "candidate_digest": _digest(candidate.model_dump(mode="json")),
            }
            for index, candidate in enumerate(ordered_candidates, start=1)
        )
        disposition_events = tuple(
            {
                "kind": "branch_owner_disposition",
                "sequence": index,
                "intent_ref": candidate.intent_ref,
                "intent_kind": candidate.intent_kind,
                "disposition": "admitted_owner_analysis" if candidate.intent_kind in {"supply", "inspection"} else "blocked_owner_mapping",
                "owner_ref": (
                    "actor_gameplay.organization_domain"
                    if candidate.intent_kind == "supply"
                    else "actor_gameplay.government_domain"
                    if candidate.intent_kind == "inspection"
                    else None
                ),
            }
            for index, candidate in enumerate(ordered_candidates, start=1)
        )
        consequence_events = tuple(
            self._evaluate_owner_consequence(candidate=candidate, sequence=index)
            for index, candidate in enumerate(ordered_candidates, start=1)
        )
        projection_events = tuple(
            self._project_owner_consequence(event)
            for event in consequence_events
            if event["kind"] == "branch_owner_consequence_evaluated"
        )
        buffer = (descriptor, *candidate_events, *disposition_events, *consequence_events, *projection_events)
        self._buffers[request.branch_ref] = buffer
        projection = self.branch_projection(request.branch_ref)
        replay_contract = replay_contract.with_projection_digest(str(projection["projection_hash"]))
        descriptor = {
            **descriptor,
            "replay_contract": replay_contract.model_dump(mode="json"),
            "replay_contract_digest": replay_contract.contract_digest,
        }
        buffer = (descriptor, *buffer[1:])
        self._buffers[request.branch_ref] = buffer
        full_report = {"branch_ref": request.branch_ref, "base_event_digest": base_digest, "base_checkpoint_sequence": request.base_checkpoint_sequence, "tail_boundary": request.tail_boundary, "dataset_digest": dataset.digest, "family_inputs": tuple(item.model_dump(mode="json") for item in family_inputs), "candidate_count": len(candidates), "branch_event_count": len(buffer)}
        public_report = {"branch_ref": request.branch_ref, "candidate_count": len(candidates), "family_inputs": (), "branch_event_count": len(buffer)}
        return BranchPreviewResult(accepted=True, report_digest=_digest(full_report), public_report=public_report, branch_event_count=len(buffer))

    def record_isolated_branch_snapshot(
        self,
        *,
        branch_ref: str,
        expected_revision: int,
        idempotency_key: str,
        privacy_scope: str,
    ) -> AppendBatchResult:
        """Persist an already accepted analysis buffer on its non-production stream."""
        if privacy_scope != "creator_debug":
            return self._snapshot_failure(branch_ref, "branch_snapshot_privacy_denied")
        buffer = self._buffers.get(branch_ref)
        if buffer is None:
            return self._snapshot_failure(branch_ref, "branch_snapshot_buffer_missing")
        stream_id = self.admission_stream_id(branch_ref=branch_ref)
        records = self._redacted_snapshot_records(buffer)
        descriptor = next((item for item in records if item.get("kind") == "branch_descriptor"), None)
        if not isinstance(descriptor, dict) or descriptor.get("branch_ref") != branch_ref:
            return self._snapshot_failure(branch_ref, "branch_snapshot_buffer_invalid")
        try:
            replay_contract = FixedBaseBranchReplayContract.from_descriptor(descriptor)
        except ValueError as exc:
            return self._snapshot_failure(branch_ref, str(exc))
        stream_error = replay_contract.validate_branch_stream(
            stream_id=stream_id,
            branch_ref=branch_ref,
            privacy_scope=privacy_scope,
        )
        if stream_error is not None:
            return self._snapshot_failure(branch_ref, stream_error)
        existing = self.store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        resolved_revision = expected_revision
        if existing is not None and existing.committed and len(existing.committed_event_ids) == 1:
            prior = self.store.get_event(existing.committed_event_ids[0])
            if (
                prior.stream_id == stream_id
                and prior.event_type == "gameplay.branch_preview.isolated_snapshot_recorded"
                and prior.payload.get("branch_ref") == branch_ref
                and prior.payload.get("buffer_digest") == _digest(records)
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._snapshot_failure(branch_ref, "idempotency_key_reused")
        if self.store.get_stream_head(stream_id) != resolved_revision:
            return self._snapshot_failure(branch_ref, "revision_conflict")
        if any(
            event.event_type == "gameplay.branch_preview.isolated_snapshot_recorded"
            for event in self.store.read_stream(stream_id)
        ):
            return self._snapshot_failure(branch_ref, "branch_snapshot_already_recorded")
        command_id = f"command:branch-snapshot:{branch_ref}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.branch_preview.record_isolated_snapshot",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: resolved_revision},
            read_set_revisions={},
            causation_id=_digest(records),
            correlation_id=f"branch-preview:snapshot:{branch_ref}",
            source_ref=self._PRINCIPAL,
            submitted_at="branch-snapshot",
            pinned_revisions={},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.branch_preview.isolated_snapshot_recorded",
                "visibility_policy": "creator_debug",
                "branch_ref": branch_ref,
                "base_event_digest": descriptor.get("base_event_digest"),
                "buffer_digest": _digest(records),
                "records": records,
            },
        )
        try:
            batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.branch_preview.isolated_snapshot",
                            audience="creator_debug",
                            payload_projection={"branch_ref": branch_ref, "buffer_digest": _digest(records)},
                        )
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._snapshot_failure(branch_ref, str(exc))
        return self.store.append_batch(batch)

    def record_isolated_branch_evolution(
        self,
        *,
        branch_ref: str,
        intent_ref: str,
        expected_revision: int,
        idempotency_key: str,
        privacy_scope: str,
    ) -> AppendBatchResult:
        """Append one fixed, redacted owner-consequence step to an isolated branch."""
        if privacy_scope != "creator_debug":
            return self._evolution_failure(branch_ref, "branch_evolution_privacy_denied")
        stream_id = self.admission_stream_id(branch_ref=branch_ref)
        snapshots = [
            event
            for event in self.store.read_stream(stream_id)
            if event.event_type == "gameplay.branch_preview.isolated_snapshot_recorded"
        ]
        if len(snapshots) != 1:
            return self._evolution_failure(branch_ref, "branch_evolution_snapshot_missing")
        snapshot = snapshots[0]
        records = snapshot.payload.get("records")
        if not isinstance(records, (list, tuple)) or snapshot.visibility_policy != "creator_debug":
            return self._evolution_failure(branch_ref, "branch_evolution_snapshot_invalid")
        evaluated = next(
            (
                record
                for record in records
                if isinstance(record, dict)
                and record.get("kind") == "branch_owner_consequence_evaluated"
                and record.get("intent_ref") == intent_ref
            ),
            None,
        )
        if not isinstance(evaluated, dict):
            return self._evolution_failure(branch_ref, "branch_evolution_intent_unsupported")
        existing = self.store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        evolution_payload = {
            "branch_ref": branch_ref,
            "intent_ref": intent_ref,
            "owner_ref": str(evaluated.get("owner_ref", "")),
            "intent_kind": str(evaluated.get("intent_kind", "")),
            "fragment_digest": str(evaluated.get("fragment_digest", "")),
            "evolution_ref": f"branch-evolution:{branch_ref}:{intent_ref}",
        }
        if existing is not None and existing.committed and len(existing.committed_event_ids) == 1:
            prior = self.store.get_event(existing.committed_event_ids[0])
            if (
                prior.stream_id == stream_id
                and prior.event_type == "gameplay.branch_preview.owner_consequence_applied"
                and prior.payload == evolution_payload
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._evolution_failure(branch_ref, "idempotency_key_reused")
        if self.store.get_stream_head(stream_id) != expected_revision:
            return self._evolution_failure(branch_ref, "revision_conflict")
        if any(
            event.event_type == "gameplay.branch_preview.owner_consequence_applied"
            and event.payload.get("intent_ref") == intent_ref
            for event in self.store.read_stream(stream_id)
        ):
            return self._evolution_failure(branch_ref, "branch_evolution_already_recorded")
        command_id = f"command:branch-evolution:{branch_ref}:{intent_ref}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.branch_preview.record_isolated_evolution",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            read_set_revisions={stream_id: snapshot.stream_revision},
            causation_id=_digest(evolution_payload),
            correlation_id=f"branch-preview:evolution:{branch_ref}:{intent_ref}",
            source_ref=self._PRINCIPAL,
            submitted_at="branch-evolution",
            pinned_revisions={"snapshot_revision": snapshot.stream_revision},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.branch_preview.owner_consequence_applied",
                "visibility_policy": "creator_debug",
                **evolution_payload,
            },
        )
        try:
            batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.branch_preview.isolated_evolution",
                            audience="creator_debug",
                            payload_projection={"branch_ref": branch_ref, "intent_ref": intent_ref, "evolution_ref": evolution_payload["evolution_ref"]},
                        )
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._evolution_failure(branch_ref, str(exc))
        return self.store.append_batch(batch)

    def durable_branch_projection(self, branch_ref: str, *, checkpoint_at: int | None = None) -> dict[str, object]:
        """Rebuild an isolated branch from its persisted creator-debug snapshot."""
        stream_id = self.admission_stream_id(branch_ref=branch_ref)
        snapshots = [
            event
            for event in self.store.read_stream(stream_id)
            if event.event_type == "gameplay.branch_preview.isolated_snapshot_recorded"
        ]
        if len(snapshots) != 1:
            raise ValueError("branch_snapshot_unavailable")
        event = snapshots[0]
        payload = event.payload
        records = payload.get("records")
        if (
            event.stream_id != stream_id
            or event.visibility_policy != "creator_debug"
            or payload.get("branch_ref") != branch_ref
            or not isinstance(records, (list, tuple))
            or not records
            or payload.get("buffer_digest") != _digest(records)
        ):
            raise ValueError("branch_snapshot_invalid")
        normalized_records = [dict(record) for record in records if isinstance(record, dict)]
        normalized = tuple(normalized_records)
        if len(normalized) != len(records):
            raise ValueError("branch_snapshot_invalid")
        descriptor = next((record for record in normalized if record.get("kind") == "branch_descriptor"), None)
        if not isinstance(descriptor, dict):
            raise ValueError("branch_snapshot_invalid")
        replay_contract = FixedBaseBranchReplayContract.from_descriptor(descriptor)
        stream_error = replay_contract.validate_branch_stream(
            stream_id=stream_id,
            branch_ref=branch_ref,
            privacy_scope=event.visibility_policy,
        )
        if stream_error is not None:
            raise ValueError(stream_error)
        for evolution in self.store.read_stream(stream_id):
            if evolution.event_type != "gameplay.branch_preview.owner_consequence_applied":
                continue
            if evolution.visibility_policy != "creator_debug" or evolution.payload.get("branch_ref") != branch_ref:
                raise ValueError("branch_evolution_invalid")
            normalized_records.append(
                {
                    "kind": "branch_owner_consequence_applied",
                    "sequence": len(normalized_records) + 1,
                    "intent_ref": evolution.payload.get("intent_ref"),
                    "owner_ref": evolution.payload.get("owner_ref"),
                    "intent_kind": evolution.payload.get("intent_kind"),
                    "fragment_digest": evolution.payload.get("fragment_digest"),
                    "evolution_ref": evolution.payload.get("evolution_ref"),
                }
            )
        normalized = tuple(normalized_records)
        previous = self._buffers.get(branch_ref)
        self._buffers[branch_ref] = normalized
        try:
            return self.branch_projection(branch_ref, checkpoint_at=checkpoint_at)
        finally:
            if previous is None:
                self._buffers.pop(branch_ref, None)
            else:
                self._buffers[branch_ref] = previous

    def production_replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="population-production", projector_version="1")
        events = [
            event
            for event in self.store.read_events()
            if not event.stream_id.startswith(
                (
                    OrganizationAuthority._BRANCH_STREAM_PREFIX,
                    GovernmentAuthority._BRANCH_STREAM_PREFIX,
                    self._ADMISSION_STREAM_PREFIX,
                )
            )
        ]
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def preview_authorized(self, *, request: BranchPreviewRequest, dataset_input: FrozenReferenceDatasetInput, calibration: CalibrationInput, family_inputs: tuple[FamilyOrganizationProjectionInput, ...], candidates: tuple[BatchIntentCandidate, ...], mode: WorldModeProfile) -> BranchPreviewResult:
        error_code = dataset_input.validate_against(store=self.store)
        if error_code is not None:
            return BranchPreviewResult(accepted=False, error_code=error_code)
        return self.preview(request=request, dataset=ReferenceDataset(dataset_ref=dataset_input.dataset_ref, provenance="authority-scoped", license_ref="authority-scoped", schema_revision=f"authority:{dataset_input.dataset_revision}", digest=dataset_input.dataset_digest, classification="authority-admitted", allowed_scopes=dataset_input.allowed_scopes), calibration=calibration, family_inputs=family_inputs, candidates=candidates, mode=mode)

    def branch_replay_digest(self, branch_ref: str) -> str:
        if branch_ref not in self._buffers:
            raise KeyError(branch_ref)
        return _digest(self._buffers[branch_ref])

    def branch_projection(self, branch_ref: str, *, checkpoint_at: int | None = None) -> dict[str, object]:
        """Replay isolated branch records without touching production history."""
        if branch_ref not in self._buffers:
            raise KeyError(branch_ref)
        events = self._buffers[branch_ref]
        if checkpoint_at is None:
            checkpoint_at = 0
        if checkpoint_at < 0 or checkpoint_at > len(events):
            raise ValueError("branch_checkpoint_out_of_range")
        def apply(state: dict[str, object], event: dict[str, object]) -> dict[str, object]:
            if event["kind"] == "branch_descriptor":
                return {"descriptor": event, "candidate_intent_refs": ()}
            if event["kind"] == "branch_candidate_proposed":
                values = tuple(state.get("candidate_intent_refs", ())) + (str(event["intent_ref"]),)
                return {**state, "candidate_intent_refs": values}
            if event["kind"] == "branch_owner_disposition":
                key = "admitted_owner_intent_refs" if event["disposition"] == "admitted_owner_analysis" else "blocked_owner_intent_refs"
                values = tuple(state.get(key, ())) + (str(event["intent_ref"]),)
                return {**state, key: values}
            if event["kind"] in {"branch_owner_consequence_evaluated", "branch_owner_consequence_blocked"}:
                accepted = event["kind"] == "branch_owner_consequence_evaluated"
                ref_key = "accepted_owner_consequence_intent_refs" if accepted else "rejected_owner_consequence_intent_refs"
                refs = tuple(state.get(ref_key, ())) + (str(event["intent_ref"]),)
                next_state = {**state, ref_key: refs}
                if accepted:
                    digests = dict(state.get("owner_consequence_digests", {}))
                    digests[str(event["intent_ref"])] = str(event["fragment_digest"])
                    next_state["owner_consequence_digests"] = digests
                return next_state
            if event["kind"] == "branch_owner_consequence_applied":
                refs = tuple(state.get("applied_owner_consequence_intent_refs", ())) + (str(event["intent_ref"]),)
                return {**state, "applied_owner_consequence_intent_refs": refs}
            if event["kind"] == "branch_owner_consequence_projected":
                projected_kind = str(event["projected_kind"])
                key = "planned_commitments" if projected_kind == "commerce_commitment" else "planned_inspections"
                values = tuple(state.get(key, ())) + (dict(event["projection"]),)
                return {**state, key: values}
            raise ValueError("branch_event_kind_invalid")
        state: dict[str, object] = {}
        for event in events[:checkpoint_at]:
            state = apply(state, event)
        checkpoint = dict(state)
        for event in events[checkpoint_at:]:
            checkpoint = apply(checkpoint, event)
        descriptor = checkpoint.get("descriptor")
        if not isinstance(descriptor, dict):
            raise ValueError("branch_replay_contract_missing")
        replay_contract = FixedBaseBranchReplayContract.from_descriptor(descriptor)
        projection = {
            "branch_ref": branch_ref,
            "candidate_intent_refs": tuple(checkpoint.get("candidate_intent_refs", ())),
            "admitted_owner_intent_refs": tuple(checkpoint.get("admitted_owner_intent_refs", ())),
            "blocked_owner_intent_refs": tuple(checkpoint.get("blocked_owner_intent_refs", ())),
            "accepted_owner_consequence_intent_refs": tuple(checkpoint.get("accepted_owner_consequence_intent_refs", ())),
            "rejected_owner_consequence_intent_refs": tuple(checkpoint.get("rejected_owner_consequence_intent_refs", ())),
            "applied_owner_consequence_intent_refs": tuple(checkpoint.get("applied_owner_consequence_intent_refs", ())),
            "owner_consequence_digests": dict(sorted(dict(checkpoint.get("owner_consequence_digests", {})).items())),
            "planned_commitments": tuple(checkpoint.get("planned_commitments", ())),
            "planned_inspections": tuple(checkpoint.get("planned_inspections", ())),
            "event_count": len(events),
        }
        projection_digest = FixedBaseBranchReplayContract.projection_digest_for_projection(projection)
        return {
            **projection,
            "projection_hash": projection_digest,
            "replay_contract_projection_digest": projection_digest,
            "replay_contract_digest": replay_contract.contract_digest,
        }

    def settle_accepted_supply_scenario(
        self,
        *,
        branch_ref: str,
        intent_ref: str,
        privacy_scope: str = "creator_debug",
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
    ) -> AppendBatchResult:
        """Ask the existing Organization owner to settle one evaluated supply scenario."""
        if privacy_scope != "creator_debug":
            return self._scenario_failure(branch_ref, "branch_scenario_privacy_denied")
        resolved_idempotency_key = idempotency_key or f"branch-scenario:{branch_ref}:{intent_ref}"
        try:
            descriptor, evaluated = self._accepted_supply_evaluation(branch_ref=branch_ref, intent_ref=intent_ref)
            specs = evaluated["fragment_event_specs"]
            if not isinstance(specs, dict) or len(specs) != 1:
                raise ValueError("branch_scenario_candidate_unavailable")
            source_stream, rows = next(iter(specs.items()))
            if not isinstance(source_stream, str) or not isinstance(rows, tuple) or not rows:
                raise ValueError("branch_scenario_candidate_unavailable")
            row = rows[0]
            if not isinstance(row, dict) or row.get("event_type") != "gameplay.organization.commerce_commitment_accepted":
                raise ValueError("branch_scenario_candidate_unavailable")
            payload = row.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("branch_scenario_candidate_unavailable")
            organization_ref = str(payload.get("organization_ref", ""))
            expected_source_stream = f"gameplay:organization:{organization_ref}"
            source_vector = evaluated.get("source_revision_vector")
            if (
                source_stream != expected_source_stream
                or not isinstance(source_vector, dict)
                or set(source_vector) != {source_stream}
                or not isinstance(source_vector.get(source_stream), int)
            ):
                raise ValueError("branch_scenario_source_revision_conflict")
            scenario_stream = OrganizationAuthority.branch_scenario_stream_id(branch_ref=branch_ref, organization_ref=organization_ref)
            resolved_expected_revision = self.store.get_stream_head(scenario_stream) if expected_revision is None else expected_revision
            existing = self.store.get_by_idempotency(OrganizationAuthority._PRINCIPAL, resolved_idempotency_key)
            if existing is not None and expected_revision is None and len(existing.committed_event_ids) == 1:
                prior_event = self.store.get_event(existing.committed_event_ids[0])
                if (
                    prior_event.stream_id == scenario_stream
                    and prior_event.event_type == "gameplay.organization.branch_commerce_commitment_recorded"
                    and prior_event.payload.get("branch_ref") == branch_ref
                    and prior_event.payload.get("candidate_digest") == self._candidate_digest(branch_ref=branch_ref, intent_ref=intent_ref)
                    and prior_event.payload.get("organization_ref") == organization_ref
                    and prior_event.payload.get("commitment_ref") == str(payload.get("commitment_ref", ""))
                    and prior_event.payload.get("counterparty_organization_ref") == str(payload.get("counterparty_organization_ref", ""))
                    and prior_event.payload.get("policy_revision") == str(payload.get("policy_revision", ""))
                    and prior_event.payload.get("source_organization_revision") == source_vector[source_stream]
                ):
                    # Rebuild the original envelope; append_batch remains the idempotency arbiter.
                    resolved_expected_revision = prior_event.stream_revision - 1
            admission_event_id = self._record_accepted_supply_admission(
                branch_ref=branch_ref,
                intent_ref=intent_ref,
                descriptor=descriptor,
                evaluated=evaluated,
                payload=payload,
                source_stream=source_stream,
                source_revision=source_vector[source_stream],
            )
            return OrganizationAuthority(store=self.store).settle_branch_commerce_commitment(
                branch_ref=branch_ref,
                base_event_digest=str(descriptor["base_event_digest"]),
                candidate_digest=self._candidate_digest(branch_ref=branch_ref, intent_ref=intent_ref),
                source_stream=source_stream,
                organization_ref=organization_ref,
                commitment_ref=str(payload.get("commitment_ref", "")),
                counterparty_organization_ref=str(payload.get("counterparty_organization_ref", "")),
                policy_revision=str(payload.get("policy_revision", "")),
                source_organization_revision=source_vector[source_stream],
                expected_revision=resolved_expected_revision,
                idempotency_key=resolved_idempotency_key,
                correlation_id=f"branch-scenario:{branch_ref}:{intent_ref}",
                privacy_scope=privacy_scope,
                organization_grant_refs=tuple(str(value) for value in payload.get("organization_grant_refs", ())),
                budget_reservation_refs=tuple(str(value) for value in payload.get("budget_reservation_refs", ())),
                fragment_digest=str(evaluated.get("fragment_digest", "")),
                admission_event_id=admission_event_id,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return self._scenario_failure(branch_ref, str(exc) or "branch_scenario_candidate_unavailable")

    def branch_scenario_projection(
        self, branch_ref: str, *, organization_ref: str, checkpoint_at: int | None = None
    ) -> dict[str, object]:
        return OrganizationAuthority(store=self.store).branch_scenario_projection(
            branch_ref=branch_ref, organization_ref=organization_ref, checkpoint_at=checkpoint_at
        )

    def _record_accepted_supply_admission(
        self,
        *,
        branch_ref: str,
        intent_ref: str,
        descriptor: dict[str, object],
        evaluated: dict[str, object],
        payload: dict[str, object],
        source_stream: str,
        source_revision: int,
    ) -> str:
        stream_id = self.admission_stream_id(branch_ref=branch_ref)
        idempotency_key = f"branch-preview-admission:{branch_ref}:{intent_ref}"
        existing = self.store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            if not existing.committed or len(existing.committed_event_ids) != 1:
                raise ValueError("branch_scenario_admission_unavailable")
            return existing.committed_event_ids[0]
        admission_payload = {
            "branch_ref": branch_ref,
            "intent_ref": intent_ref,
            "base_event_digest": str(descriptor["base_event_digest"]),
            "candidate_digest": self._candidate_digest(branch_ref=branch_ref, intent_ref=intent_ref),
            "fragment_digest": str(evaluated.get("fragment_digest", "")),
            "organization_ref": str(payload.get("organization_ref", "")),
            "commitment_ref": str(payload.get("commitment_ref", "")),
            "counterparty_organization_ref": str(payload.get("counterparty_organization_ref", "")),
            "policy_revision": str(payload.get("policy_revision", "")),
            "organization_grant_refs": tuple(str(value) for value in payload.get("organization_grant_refs", ())),
            "budget_reservation_refs": tuple(str(value) for value in payload.get("budget_reservation_refs", ())),
            "source_stream": source_stream,
            "source_organization_revision": source_revision,
        }
        replay_contract = FixedBaseBranchReplayContract.from_descriptor(descriptor)
        admission_payload["replay_contract"] = replay_contract.model_dump(mode="json")
        admission_payload["replay_contract_digest"] = replay_contract.contract_digest
        if not admission_payload["fragment_digest"].startswith("sha256:"):
            raise ValueError("branch_scenario_admission_invalid")
        command_id = f"command:{idempotency_key}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.branch_preview.record_supply_admission",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: self.store.get_stream_head(stream_id)},
            read_set_revisions={source_stream: source_revision},
            causation_id=str(admission_payload["candidate_digest"]),
            correlation_id=f"branch-preview:{branch_ref}:{intent_ref}",
            source_ref=self._PRINCIPAL,
            submitted_at="branch-scenario",
            pinned_revisions={"organization_source": source_revision},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.branch_preview.supply_admission_recorded",
                "visibility_policy": "creator_debug",
                **admission_payload,
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.branch_preview.supply_admission",
                        audience="creator_debug",
                        payload_projection={
                            "branch_ref": branch_ref,
                            "intent_ref": intent_ref,
                            "organization_ref": admission_payload["organization_ref"],
                        },
                    )
                ]
            },
            deep=True,
        )
        result = self.store.append_batch(batch)
        if not result.committed or len(result.committed_event_ids) != 1:
            raise ValueError(
                result.failure.error_code
                if result.failure is not None
                else "branch_scenario_admission_unavailable"
            )
        return result.committed_event_ids[0]

    def settle_accepted_inspection_scenario(
        self,
        *,
        branch_ref: str,
        intent_ref: str,
        privacy_scope: str = "creator_debug",
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
    ) -> AppendBatchResult:
        """Ask the existing Government owner to settle one passed inspection scenario."""
        if privacy_scope != "creator_debug":
            return self._scenario_failure(branch_ref, "branch_scenario_privacy_denied")
        resolved_idempotency_key = idempotency_key or f"branch-scenario:{branch_ref}:{intent_ref}"
        try:
            descriptor, evaluated = self._accepted_inspection_evaluation(branch_ref=branch_ref, intent_ref=intent_ref)
            specs = evaluated["fragment_event_specs"]
            if not isinstance(specs, dict) or len(specs) != 1:
                raise ValueError("branch_scenario_candidate_unavailable")
            source_stream, rows = next(iter(specs.items()))
            if not isinstance(source_stream, str) or not isinstance(rows, tuple) or not rows:
                raise ValueError("branch_scenario_candidate_unavailable")
            row = rows[0]
            if not isinstance(row, dict) or row.get("event_type") != "gameplay.government.inspection_recorded":
                raise ValueError("branch_scenario_candidate_unavailable")
            payload = row.get("payload")
            if not isinstance(payload, dict) or payload.get("passed") is not True:
                raise ValueError("branch_scenario_inspection_must_pass")
            organization_ref = str(payload.get("organization_ref", ""))
            expected_source_stream = f"gameplay:government:{organization_ref}"
            source_vector = evaluated.get("source_revision_vector")
            if (
                source_stream != expected_source_stream
                or not isinstance(source_vector, dict)
                or set(source_vector) != {source_stream}
                or not isinstance(source_vector.get(source_stream), int)
            ):
                raise ValueError("branch_scenario_source_revision_conflict")
            scenario_stream = GovernmentAuthority.branch_scenario_stream_id(branch_ref=branch_ref, organization_ref=organization_ref)
            resolved_expected_revision = self.store.get_stream_head(scenario_stream) if expected_revision is None else expected_revision
            existing = self.store.get_by_idempotency(GovernmentAuthority._PRINCIPAL, resolved_idempotency_key)
            if existing is not None and expected_revision is None and len(existing.committed_event_ids) == 1:
                prior_event = self.store.get_event(existing.committed_event_ids[0])
                if (
                    prior_event.stream_id == scenario_stream
                    and prior_event.event_type == "gameplay.government.branch_inspection_recorded"
                    and prior_event.payload.get("branch_ref") == branch_ref
                    and prior_event.payload.get("candidate_digest") == self._candidate_digest(branch_ref=branch_ref, intent_ref=intent_ref)
                    and prior_event.payload.get("organization_ref") == organization_ref
                    and prior_event.payload.get("inspection_ref") == str(payload.get("inspection_ref", ""))
                    and prior_event.payload.get("policy_revision") == str(payload.get("policy_revision", ""))
                    and prior_event.payload.get("source_government_revision") == source_vector[source_stream]
                ):
                    resolved_expected_revision = prior_event.stream_revision - 1
            admission_event_id = self._record_accepted_inspection_admission(
                branch_ref=branch_ref,
                intent_ref=intent_ref,
                descriptor=descriptor,
                evaluated=evaluated,
                payload=payload,
                source_stream=source_stream,
                source_revision=source_vector[source_stream],
            )
            return GovernmentAuthority(store=self.store).settle_branch_inspection(
                admission_event_id=admission_event_id,
                expected_revision=resolved_expected_revision,
                idempotency_key=resolved_idempotency_key,
                correlation_id=f"branch-scenario:{branch_ref}:{intent_ref}",
                privacy_scope=privacy_scope,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return self._scenario_failure(branch_ref, str(exc) or "branch_scenario_candidate_unavailable")

    def government_branch_scenario_projection(
        self, branch_ref: str, *, organization_ref: str, checkpoint_at: int | None = None
    ) -> dict[str, object]:
        return GovernmentAuthority(store=self.store).branch_scenario_projection(
            branch_ref=branch_ref, organization_ref=organization_ref, checkpoint_at=checkpoint_at
        )

    def _record_accepted_inspection_admission(
        self,
        *,
        branch_ref: str,
        intent_ref: str,
        descriptor: dict[str, object],
        evaluated: dict[str, object],
        payload: dict[str, object],
        source_stream: str,
        source_revision: int,
    ) -> str:
        stream_id = self.admission_stream_id(branch_ref=branch_ref)
        idempotency_key = f"branch-preview-admission:{branch_ref}:{intent_ref}"
        existing = self.store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            if not existing.committed or len(existing.committed_event_ids) != 1:
                raise ValueError("branch_scenario_admission_unavailable")
            return existing.committed_event_ids[0]
        admission_payload = {
            "branch_ref": branch_ref,
            "intent_ref": intent_ref,
            "base_event_digest": str(descriptor["base_event_digest"]),
            "candidate_digest": self._candidate_digest(branch_ref=branch_ref, intent_ref=intent_ref),
            "fragment_digest": str(evaluated.get("fragment_digest", "")),
            "organization_ref": str(payload.get("organization_ref", "")),
            "inspection_ref": str(payload.get("inspection_ref", "")),
            "jurisdiction_ref": str(payload.get("jurisdiction_ref", "")),
            "policy_revision": str(payload.get("policy_revision", "")),
            "policy_digest": str(payload.get("policy_digest", "")),
            "evidence_ref": str(payload.get("evidence_ref", "")),
            "passed": payload.get("passed"),
            "source_stream": source_stream,
            "source_government_revision": source_revision,
        }
        if admission_payload["passed"] not in (True, False) or not str(admission_payload["fragment_digest"]).startswith("sha256:"):
            raise ValueError("branch_scenario_admission_invalid")
        command_id = f"command:{idempotency_key}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.branch_preview.record_inspection_admission",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: self.store.get_stream_head(stream_id)},
            read_set_revisions={source_stream: source_revision},
            causation_id=str(admission_payload["candidate_digest"]),
            correlation_id=f"branch-preview:{branch_ref}:{intent_ref}",
            source_ref=self._PRINCIPAL,
            submitted_at="branch-scenario",
            pinned_revisions={"government_source": source_revision},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.branch_preview.inspection_admission_recorded",
                "visibility_policy": "creator_debug",
                **admission_payload,
            },
        )
        batch = EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(
            outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id,
            event_id=event.event_id, global_sequence=0,
            topic="world.branch_preview.inspection_admission", audience="creator_debug",
            payload_projection={"branch_ref": branch_ref, "intent_ref": intent_ref, "passed": admission_payload["passed"]},
        )]}, deep=True)
        result = self.store.append_batch(batch)
        if not result.committed or len(result.committed_event_ids) != 1:
            raise ValueError(
                result.failure.error_code
                if result.failure is not None
                else "branch_scenario_admission_unavailable"
            )
        return result.committed_event_ids[0]

    def settle_accepted_failed_inspection_remediation_scenario(
        self,
        *,
        branch_ref: str,
        intent_ref: str,
        privacy_scope: str = "creator_debug",
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
    ) -> AppendBatchResult:
        """Ask the existing Government owner to record one fixed false-inspection scenario."""
        if privacy_scope != "creator_debug":
            return self._scenario_failure(branch_ref, "branch_scenario_privacy_denied")
        resolved_idempotency_key = idempotency_key or f"branch-remediation:{branch_ref}:{intent_ref}"
        try:
            descriptor, evaluated = self._accepted_inspection_evaluation(
                branch_ref=branch_ref, intent_ref=intent_ref
            )
            specs = evaluated["fragment_event_specs"]
            if not isinstance(specs, dict) or len(specs) != 1:
                raise ValueError("branch_scenario_candidate_unavailable")
            source_stream, rows = next(iter(specs.items()))
            if not isinstance(source_stream, str) or not isinstance(rows, tuple) or not rows:
                raise ValueError("branch_scenario_candidate_unavailable")
            row = rows[0]
            if not isinstance(row, dict) or row.get("event_type") != "gameplay.government.inspection_recorded":
                raise ValueError("branch_scenario_candidate_unavailable")
            payload = row.get("payload")
            if not isinstance(payload, dict) or payload.get("passed") is not False:
                raise ValueError("branch_scenario_inspection_must_fail")
            organization_ref = str(payload.get("organization_ref", ""))
            expected_source_stream = f"gameplay:government:{organization_ref}"
            source_vector = evaluated.get("source_revision_vector")
            if (
                source_stream != expected_source_stream
                or not isinstance(source_vector, dict)
                or set(source_vector) != {source_stream}
                or not isinstance(source_vector.get(source_stream), int)
            ):
                raise ValueError("branch_scenario_source_revision_conflict")
            scenario_stream = GovernmentAuthority.branch_scenario_stream_id(
                branch_ref=branch_ref, organization_ref=organization_ref
            )
            resolved_expected_revision = (
                self.store.get_stream_head(scenario_stream)
                if expected_revision is None
                else expected_revision
            )
            candidate_digest = self._candidate_digest(branch_ref=branch_ref, intent_ref=intent_ref)
            existing = self.store.get_by_idempotency(
                GovernmentAuthority._PRINCIPAL, resolved_idempotency_key
            )
            if existing is not None and expected_revision is None and len(existing.committed_event_ids) == 1:
                prior_event = self.store.get_event(existing.committed_event_ids[0])
                if (
                    prior_event.stream_id == scenario_stream
                    and prior_event.event_type == "gameplay.government.branch_inspection_remediation_recorded"
                    and prior_event.payload.get("branch_ref") == branch_ref
                    and prior_event.payload.get("candidate_digest") == candidate_digest
                    and prior_event.payload.get("organization_ref") == organization_ref
                    and prior_event.payload.get("inspection_ref") == str(payload.get("inspection_ref", ""))
                    and prior_event.payload.get("policy_revision") == str(payload.get("policy_revision", ""))
                    and prior_event.payload.get("source_government_revision") == source_vector[source_stream]
                ):
                    resolved_expected_revision = prior_event.stream_revision - 1
            admission_event_id = self._record_accepted_inspection_admission(
                branch_ref=branch_ref,
                intent_ref=intent_ref,
                descriptor=descriptor,
                evaluated=evaluated,
                payload=payload,
                source_stream=source_stream,
                source_revision=source_vector[source_stream],
            )
            return GovernmentAuthority(store=self.store).settle_branch_inspection_remediation(
                admission_event_id=admission_event_id,
                expected_revision=resolved_expected_revision,
                idempotency_key=resolved_idempotency_key,
                correlation_id=f"branch-remediation:{branch_ref}:{intent_ref}",
                privacy_scope=privacy_scope,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return self._scenario_failure(
                branch_ref, str(exc) or "branch_scenario_candidate_unavailable"
            )

    def _accepted_supply_evaluation(self, *, branch_ref: str, intent_ref: str) -> tuple[dict[str, object], dict[str, object]]:
        buffer = self._buffers.get(branch_ref)
        if buffer is None:
            raise ValueError("branch_scenario_candidate_unavailable")
        descriptor = next((event for event in buffer if event.get("kind") == "branch_descriptor"), None)
        evaluated = next(
            (
                event
                for event in buffer
                if event.get("kind") == "branch_owner_consequence_evaluated"
                and event.get("intent_ref") == intent_ref
                and event.get("intent_kind") == "supply"
                and event.get("owner_ref") == OrganizationAuthority._PRINCIPAL
            ),
            None,
        )
        if not isinstance(descriptor, dict) or not isinstance(evaluated, dict):
            raise ValueError("branch_scenario_candidate_unavailable")
        return descriptor, evaluated

    def _accepted_inspection_evaluation(self, *, branch_ref: str, intent_ref: str) -> tuple[dict[str, object], dict[str, object]]:
        buffer = self._buffers.get(branch_ref)
        if buffer is None:
            raise ValueError("branch_scenario_candidate_unavailable")
        descriptor = next((event for event in buffer if event.get("kind") == "branch_descriptor"), None)
        evaluated = next(
            (
                event
                for event in buffer
                if event.get("kind") == "branch_owner_consequence_evaluated"
                and event.get("intent_ref") == intent_ref
                and event.get("intent_kind") == "inspection"
                and event.get("owner_ref") == GovernmentAuthority._PRINCIPAL
            ),
            None,
        )
        if not isinstance(descriptor, dict) or not isinstance(evaluated, dict):
            raise ValueError("branch_scenario_candidate_unavailable")
        return descriptor, evaluated

    def _candidate_digest(self, *, branch_ref: str, intent_ref: str) -> str:
        buffer = self._buffers[branch_ref]
        event = next((item for item in buffer if item.get("kind") == "branch_candidate_proposed" and item.get("intent_ref") == intent_ref), None)
        if not isinstance(event, dict) or not isinstance(event.get("candidate_digest"), str):
            raise ValueError("branch_scenario_candidate_unavailable")
        return str(event["candidate_digest"])

    @staticmethod
    def _scenario_failure(branch_ref: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:branch-scenario:{branch_ref}",
            command_id=f"branch-scenario:{branch_ref}",
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="branch_scenario"),
        )

    @staticmethod
    def _snapshot_failure(branch_ref: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:branch-snapshot:{branch_ref}",
            command_id=f"command:branch-snapshot:{branch_ref}",
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="branch_snapshot"),
        )

    @staticmethod
    def _evolution_failure(branch_ref: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:branch-evolution:{branch_ref}",
            command_id=f"command:branch-evolution:{branch_ref}",
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="branch_evolution"),
        )

    @staticmethod
    def _redacted_snapshot_records(buffer: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
        """Persist branch projection inputs, never reusable owner-fragment data."""
        records: list[dict[str, object]] = []
        for record in buffer:
            if record.get("kind") == "branch_owner_consequence_evaluated":
                records.append(
                    {
                        key: value
                        for key, value in record.items()
                        if key
                        in {
                            "kind",
                            "sequence",
                            "intent_ref",
                            "intent_kind",
                            "owner_ref",
                            "fragment_digest",
                        }
                    }
                )
            else:
                records.append(dict(record))
        return tuple(records)

    def _evaluate_owner_consequence(
        self, *, candidate: BatchIntentCandidate, sequence: int
    ) -> dict[str, object]:
        """Validate the two approved owner rows without producing domain truth."""
        payload = candidate.payload
        organization_ref = str(payload.get("organization_ref", ""))
        try:
            if candidate.intent_kind == "supply":
                stream_id = f"gameplay:organization:{organization_ref}"
                expected_revision = candidate.expected_revisions.get(stream_id)
                if expected_revision is None or len(candidate.expected_revisions) != 1:
                    raise ValueError("branch_owner_revision_missing")
                fragment = OrganizationAuthority(store=self.store).build_commerce_commitment_fragment(
                    organization_ref=organization_ref,
                    commitment_ref=str(payload.get("commitment_ref", "")),
                    counterparty_organization_ref=str(payload.get("counterparty_organization_ref", "")),
                    organization_grant_refs=tuple(str(value) for value in payload.get("organization_grant_refs", ())),
                    budget_reservation_refs=tuple(str(value) for value in payload.get("budget_reservation_refs", ())),
                    policy_revision=candidate.policy_revision,
                    expected_revision=expected_revision,
                )
            elif candidate.intent_kind == "inspection":
                stream_id = f"gameplay:government:{organization_ref}"
                expected_revision = candidate.expected_revisions.get(stream_id)
                if expected_revision is None or len(candidate.expected_revisions) != 1:
                    raise ValueError("branch_owner_revision_missing")
                if self.store.get_stream_head(stream_id) != expected_revision:
                    raise ValueError("revision_conflict")
                passed = payload.get("passed")
                if not isinstance(passed, bool):
                    raise ValueError("branch_scenario_inspection_passed_invalid")
                fragment = GovernmentAuthority(store=self.store).build_commercial_inspection_fragment(
                    inspection_ref=str(payload.get("inspection_ref", "")),
                    organization_ref=organization_ref,
                    jurisdiction_ref=str(payload.get("jurisdiction_ref", "")),
                    policy_revision=candidate.policy_revision,
                    policy_digest=str(payload.get("policy_digest", "")),
                    evidence_ref=str(payload.get("evidence_ref", "")),
                    passed=passed,
                )
            else:
                raise ValueError("branch_owner_mapping_unsupported")
        except (KeyError, TypeError, ValueError) as exc:
            return {
                "kind": "branch_owner_consequence_blocked",
                "sequence": sequence,
                "intent_ref": candidate.intent_ref,
                "intent_kind": candidate.intent_kind,
                "reason_code": str(exc) or "branch_owner_evaluation_rejected",
            }
        return {
            "kind": "branch_owner_consequence_evaluated",
            "sequence": sequence,
            "intent_ref": candidate.intent_ref,
            "intent_kind": candidate.intent_kind,
            "owner_ref": fragment.owner_principal_ref,
            "source_revision_vector": dict(fragment.expected_revisions),
            "fragment_digest": _digest(fragment.model_dump(mode="json")),
            "fragment_event_specs": {
                stream_id: tuple(
                    {"event_type": event_type, "payload": dict(event_payload)}
                    for event_type, event_payload in event_specs
                )
                for stream_id, event_specs in fragment.event_specs.items()
            },
        }

    @staticmethod
    def _project_owner_consequence(event: dict[str, object]) -> dict[str, object]:
        """Translate only fixed owner event semantics into a redacted branch fact."""
        specs = event.get("fragment_event_specs")
        if not isinstance(specs, dict):
            raise ValueError("branch_owner_fragment_specs_invalid")
        rows = [
            item
            for values in specs.values()
            if isinstance(values, tuple)
            for item in values
            if isinstance(item, dict)
        ]
        commitment = next((item.get("payload") for item in rows if item.get("event_type") == "gameplay.organization.commerce_commitment_accepted"), None)
        if isinstance(commitment, dict):
            projection = {
                "commitment_ref": str(commitment["commitment_ref"]),
                "organization_ref": str(commitment["organization_ref"]),
                "counterparty_organization_ref": str(commitment["counterparty_organization_ref"]),
                "policy_revision": str(commitment["policy_revision"]),
            }
            projected_kind = "commerce_commitment"
        else:
            inspection = next((item.get("payload") for item in rows if item.get("event_type") == "gameplay.government.inspection_recorded"), None)
            if not isinstance(inspection, dict):
                raise ValueError("branch_owner_fragment_semantics_unsupported")
            projection = {
                "inspection_ref": str(inspection["inspection_ref"]),
                "organization_ref": str(inspection["organization_ref"]),
                "jurisdiction_ref": str(inspection["jurisdiction_ref"]),
                "passed": bool(inspection["passed"]),
                "policy_revision": str(inspection["policy_revision"]),
            }
            projected_kind = "commercial_inspection"
        return {
            "kind": "branch_owner_consequence_projected",
            "sequence": event["sequence"],
            "intent_ref": event["intent_ref"],
            "owner_ref": event["owner_ref"],
            "projected_kind": projected_kind,
            "fragment_digest": event["fragment_digest"],
            "projection": projection,
        }

    @staticmethod
    def promote(branch_ref: str) -> BranchPromotionResult:
        """Promotion is deliberately absent until a separately approved owner exists."""
        return BranchPromotionResult(accepted=False, error_code="branch_promotion_unsupported")


__all__ = ["BranchPreviewAuthority", "BranchPreviewRequest", "BranchPreviewResult", "BranchPromotionResult", "CalibrationInput", "FamilyOrganizationProjectionInput", "FrozenReferenceDatasetInput", "ReferenceDataset"]
