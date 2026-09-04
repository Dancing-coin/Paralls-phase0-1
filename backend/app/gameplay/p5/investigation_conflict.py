from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayFailure, OwnerAuthorizedFragment, ReplayResult
from app.gameplay.action_graph_content import ActionGraphDefinition
from app.gameplay.action_window_runtime import ActionWindowIntent, ActionWindowResult, ActionWindowValidator, SpatialSnapshotRef
from app.gameplay.p5.contracts import (
    P5ResolutionRequest,
    P5ResolutionResult,
    canonical_sha256_digest,
)
from app.gameplay.p5.registry import P5PolicyRegistry
from app.gameplay.shared_contracts import GameplayCommandEnvelope, SettlementPlan
from app.gameplay.settlement_plan import build_atomic_event_batch


_PRINCIPAL = "authority:p5:investigation-conflict"
_RULE_REF = "rule:p5:investigation-conflict"
_PROJECTOR_ID = "projector:p5:investigation-conflict"
_PROJECTOR_VERSION = "v1"
_INVESTIGATION_EVENT = "gameplay.investigation.observation_resolved"
_CONFLICT_EVENT = "gameplay.conflict.attempt_resolved"
_ALARM_EVENT = "gameplay.conflict.alarm_raised"
_ACTION_WINDOW_EVENTS = (
    "gameplay.conflict.encounter_started",
    "gameplay.conflict.action_window_resolved",
    "gameplay.conflict.control_changed",
    "gameplay.conflict.terminal_outcome_recorded",
    "gameplay.conflict.encounter_closed",
)


def _is_visible(visibility: str, recipient_ref: str) -> bool:
    if visibility == "public":
        return True
    if visibility == "authority_only":
        return recipient_ref.startswith("authority:")
    return visibility == f"actor:{recipient_ref}"


def _suffix(value: str) -> str:
    parts = [part for part in value.split(":") if part]
    return parts[-1] if parts else ""


def _canonical_investigation_stream(case_ref: str) -> str:
    slug = _suffix(case_ref)
    return f"gameplay:investigation:{slug}" if slug else ""


def _canonical_conflict_stream(attempt_ref: str) -> str:
    suffix = _suffix(attempt_ref)
    return f"gameplay:conflict:attempt-{suffix}" if suffix else ""


def _canonical_alarm_stream(attempt_ref: str) -> str:
    suffix = _suffix(attempt_ref)
    return f"gameplay:conflict:alarm-{suffix}" if suffix else ""


def _is_valid_event_visibility(visibility: str) -> bool:
    if visibility in {"public", "authority_only"}:
        return True
    return visibility.startswith("actor:") and len(visibility) > len("actor:")


def _event_mapping(fragments: tuple[OwnerAuthorizedFragment, ...]) -> dict[str, str | tuple[str, ...]]:
    mapping: dict[str, str | tuple[str, ...]] = {}
    for fragment in fragments:
        for stream_ref, specs in fragment.event_specs.items():
            mapping[stream_ref] = specs[0][0] if len(specs) == 1 else tuple(event_name for event_name, _payload in specs)
    return mapping


@dataclass(frozen=True)
class InvestigationConflictAuthorityResult:
    resolution: P5ResolutionResult
    receipt: Any | None
    settlement_plan: SettlementPlan | None


@dataclass(frozen=True)
class ActionWindowConflictResult:
    """Outcome of the additive action-window adapter over the P5 conflict owner."""

    committed: bool
    idempotency_status: str
    receipt: AppendBatchResult | None = None
    error_code: str | None = None
    window_result: ActionWindowResult | None = None


class InvestigationConflictAuthority:
    def __init__(self, *, registry: P5PolicyRegistry, store: GameplayEventStore) -> None:
        self._registry = registry
        self._store = store

    def resolve_action_window(
        self,
        *,
        command: GameplayCommandEnvelope,
        intent: ActionWindowIntent,
        graph: object,
        spatial_snapshot: SpatialSnapshotRef,
        role_ref: str,
        now: str,
    ) -> ActionWindowConflictResult:
        """Persist one validated window using the existing conflict event spine.

        This is intentionally additive: the P5 registry, event store, receipt,
        idempotency and replay reader remain the authority surface.  The action
        window validator must run before this method is called.
        """
        del now
        if not role_ref:
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_scope_invalid")
        graph_value = graph
        if not isinstance(graph_value, ActionGraphDefinition):
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_graph_invalid")
        window_result = ActionWindowValidator.validate(
            intent,
            graph=graph_value,
            spatial_snapshot=spatial_snapshot,
        )
        if not window_result.accepted:
            return ActionWindowConflictResult(False, "rejected", error_code=window_result.error_code, window_result=window_result)
        if command.principal_ref != _PRINCIPAL or command.actor_ref != intent.actor_ref:
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_owner_invalid", window_result=window_result)
        if role_ref not in graph_value.role_refs:
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_role_invalid", window_result=window_result)
        if len(command.expected_revisions) != 1:
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_write_revision_invalid", window_result=window_result)
        stream_id = next(iter(command.expected_revisions), "")
        expected_revision = command.expected_revisions.get(stream_id)
        if expected_revision is None:
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_conflict_revision_missing", window_result=window_result)
        if not stream_id.startswith("gameplay:conflict:encounter:"):
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_stream_invalid", window_result=window_result)
        for event_type in _ACTION_WINDOW_EVENTS:
            try:
                self._registry.require_event(event_type, 1)
            except ValueError:
                return ActionWindowConflictResult(False, "rejected", error_code="action_window_event_unregistered", window_result=window_result)
        command_source_revisions = dict(command.read_set_revisions)
        intent_source_revisions = dict(intent.expected_revision_vector)
        if set(command_source_revisions) != set(intent_source_revisions):
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_source_revision_missing", window_result=window_result)
        if command_source_revisions != intent_source_revisions:
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_source_revision_stale", window_result=window_result)
        idempotency_key = command.idempotency_key
        payload = {
            "attempt_ref": intent.attempt_ref,
            "encounter_ref": intent.encounter_ref,
            "actor_ref": intent.actor_ref,
            "role_ref": role_ref,
            "window_index": intent.window_index,
            "window_start_tick": intent.window_start_tick,
            "window_end_tick": intent.window_end_tick,
            "graph_ref": intent.graph_ref,
            "graph_revision": intent.graph_revision,
            "node_ref": intent.node_ref,
            "intent_digest": canonical_sha256_digest(intent.model_dump(mode="json")),
            "command_digest": canonical_sha256_digest(command.model_dump(mode="json")),
            "deterministic_seed": intent.deterministic_seed,
            "outcome": "resolved",
            "perception": window_result.perception.model_dump(mode="json") if window_result.perception is not None else {},
            "source_revision_vector": dict(intent.expected_revision_vector),
            "spatial_revisions": {
                "navigation": intent.navigation_revision,
                "collision": intent.collision_revision,
                "occlusion": intent.occlusion_revision,
                "sound_zone": intent.sound_zone_revision,
            },
            "evidence_refs": tuple(intent.evidence_refs),
            "visibility_policy": "project",
        }
        digest = canonical_sha256_digest(payload)
        existing = self._store.get_idempotency_record(_PRINCIPAL, idempotency_key)
        if existing is not None:
            receipt = self._store.get_by_idempotency(_PRINCIPAL, idempotency_key)
            prior = self._store.get_event(receipt.committed_event_ids[0]) if receipt and receipt.committed_event_ids else None
            expected_prior = {**payload, "event_kind": "encounter_started"}
            if prior is None or canonical_sha256_digest(prior.payload) != canonical_sha256_digest(expected_prior):
                return ActionWindowConflictResult(False, "rejected", error_code="action_window_idempotency_reused", window_result=window_result)
            duplicate_receipt = receipt.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True) if receipt is not None else None
            return ActionWindowConflictResult(True, "duplicate_replayed", receipt=duplicate_receipt, window_result=window_result)
        if any(self._store.get_stream_head(source_stream) != revision for source_stream, revision in command.read_set_revisions.items()):
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_source_revision_stale", window_result=window_result)
        if self._store.get_stream_head(stream_id) != expected_revision:
            return ActionWindowConflictResult(False, "rejected", error_code="action_window_conflict_revision_stale")
        event_specs = tuple(
            (
                event_type,
                {
                    **payload,
                    "event_kind": event_type.rsplit(".", 1)[-1],
                    **({"terminal_kind": "case_death"} if event_type.endswith("terminal_outcome_recorded") else {}),
                },
            )
            for event_type in _ACTION_WINDOW_EVENTS
        )
        batch = build_atomic_event_batch(
            command_id=f"action-window:{intent.attempt_ref}:{intent.window_index}",
            principal_ref=_PRINCIPAL,
            stream_id=stream_id,
            expected_revision=expected_revision,
            read_stream_revisions={**dict(command.read_set_revisions), stream_id: expected_revision},
            event_specs=event_specs,
            idempotency_key=idempotency_key,
            causation_id=f"action-window:{intent.attempt_ref}",
            correlation_id=intent.encounter_ref,
            pinned_revisions={
                "graph": 1,
                "navigation": 1,
                "collision": 1,
                "occlusion": 1,
                "sound_zone": 1,
            },
        )
        receipt = self._store.append_batch(batch)
        if not receipt.committed:
            return ActionWindowConflictResult(
                False,
                "rejected",
                receipt=receipt,
                error_code=receipt.failure.error_code if receipt.failure is not None else "action_window_append_failed",
            )
        return ActionWindowConflictResult(True, "new_commit", receipt=receipt, window_result=window_result)

    def confirm_world_death(
        self,
        *,
        command: GameplayCommandEnvelope,
        intent: "WorldDeathConfirmationIntent",
    ) -> ActionWindowConflictResult:
        """Commit an explicit world-death decision from a case-death event."""
        from app.gameplay.action_consequence_runtime import ActionConsequenceBoundary

        validation = ActionConsequenceBoundary(self._store).validate_world_death(intent)
        if not validation.accepted:
            return ActionWindowConflictResult(False, "rejected", error_code=validation.error_code)
        source = self._store.get_event(intent.source_event_id)
        if self._store.get_stream_head(source.stream_id) != intent.expected_source_revision:
            return ActionWindowConflictResult(False, "rejected", error_code="world_death_source_revision_stale")
        event_type = (
            "gameplay.conflict.world_death_commit_confirmed"
            if intent.confirmed
            else "gameplay.conflict.world_death_commit_rejected"
        )
        payload = {
            "source_event_id": source.event_id,
            "target_actor_ref": intent.target_actor_ref,
            "confirmation_ref": intent.confirmation_ref,
            "confirmed": intent.confirmed,
            "policy_revision": intent.policy_revision,
            "source_revision": source.stream_revision,
            "visibility_policy": "project",
        }
        batch = build_atomic_event_batch(
            command_id=command.command_id,
            principal_ref=_PRINCIPAL,
            stream_id=source.stream_id,
            expected_revision=intent.expected_source_revision,
            read_stream_revisions={source.stream_id: intent.expected_source_revision},
            event_specs=((event_type, payload),),
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            pinned_revisions={"source": intent.expected_source_revision},
        )
        receipt = self._store.append_batch(batch)
        if not receipt.committed:
            return ActionWindowConflictResult(False, "rejected", receipt=receipt, error_code=receipt.failure.error_code if receipt.failure else "world_death_append_failed")
        return ActionWindowConflictResult(True, "new_commit", receipt=receipt)

    def resolve(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        owner_fragments: tuple[OwnerAuthorizedFragment, ...] = (),
        now: str,
    ) -> InvestigationConflictAuthorityResult:
        del now
        digest = self._request_digest(command=command, request=request, owner_fragments=owner_fragments)
        existing = self._store.get_idempotency_record(_PRINCIPAL, command.idempotency_key)
        adverse = bool(owner_fragments)
        if existing is not None:
            if existing.payload_digest == digest:
                receipt = self._store.get_by_idempotency(_PRINCIPAL, command.idempotency_key)
                return self._committed_result(receipt, adverse=adverse, settlement_plan=None, duplicate=True)
            return self._rejected("idempotency_key_reused")

        try:
            request = self._registry.validate_request(request)
        except ValueError as exc:
            return self._rejected(str(exc))

        payload = dict(command.payload)
        failure = self._validate_common(
            command=command,
            request=request,
            payload=payload,
        )
        if failure is not None:
            return self._rejected(failure)

        failure = self._validate_fragments(
            command=command,
            request=request,
            owner_fragments=owner_fragments,
        )
        if failure is not None:
            return self._rejected(failure)

        primary_fragment = self._primary_fragment(
            command=command,
            request=request,
            payload=payload,
            adverse=adverse,
        )
        fragments = tuple(sorted((primary_fragment, *owner_fragments), key=lambda fragment: fragment.fragment_id))

        failure = self._validate_fragment_set(fragments=fragments)
        if failure is not None:
            return self._rejected(failure)

        settlement_plan = SettlementPlan(
            plan_id=f"settlement:{command.command_id}",
            command_id=command.command_id,
            expected_revision_vector=dict(request.expected_revisions.entries),
            proposals=(),
            event_mapping=_event_mapping(fragments),
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        )

        batch = self._build_batch(
            command=command,
            request=request,
            owner_fragments=owner_fragments,
            fragments=fragments,
            digest=digest,
        )
        receipt = self._store.append_batch(batch)
        if not receipt.committed:
            failure_code = receipt.failure.error_code if receipt.failure is not None else "append_batch_failed"
            if failure_code in {"revision_conflict", "missing_expected_revision"}:
                failure_code = "p5_revision_stale"
            return self._rejected(failure_code)
        return self._committed_result(receipt, adverse=adverse, settlement_plan=settlement_plan, duplicate=False)

    def view_for(self, *, recipient_ref: str, now: str) -> dict[str, object]:
        del now
        investigations: list[dict[str, object]] = []
        conflicts: list[dict[str, object]] = []
        consequences: list[dict[str, object]] = []
        source_revision_vector: dict[str, int] = {}

        for event in self._store.read_events():
            payload = dict(event.payload)
            if not _is_visible(event.visibility_policy, recipient_ref):
                continue
            source_revision_vector[event.stream_id] = event.stream_revision
            if event.event_type == _INVESTIGATION_EVENT:
                entry = {
                    "case_ref": payload.get("case_ref"),
                    "attempt_ref": payload.get("attempt_ref"),
                    "actor_ref": payload.get("actor_ref"),
                    "target_ref": payload.get("target_ref"),
                    "relationship_ref": payload.get("relationship_ref"),
                    "perception_ref": payload.get("perception_ref"),
                    "visibility": payload.get("visibility"),
                }
                if recipient_ref == str(payload.get("actor_ref")) or recipient_ref.startswith("authority:"):
                    entry["hidden_clue_ref"] = payload.get("hidden_clue_ref")
                    entry["hidden_evidence"] = payload.get("hidden_clue_ref")
                investigations.append(entry)
                continue
            if event.event_type == _CONFLICT_EVENT:
                conflicts.append(
                    {
                        "attempt_ref": payload.get("attempt_ref"),
                        "actor_ref": payload.get("actor_ref"),
                        "target_ref": payload.get("target_ref"),
                        "outcome": payload.get("outcome"),
                        "risk_ref": payload.get("risk_ref"),
                        "visibility": payload.get("visibility"),
                    }
                )
                continue
            consequences.append(
                {
                    "event_type": event.event_type,
                    "stream_ref": event.stream_id,
                    "visibility": event.visibility_policy,
                    "payload": payload,
                }
            )

        view = {
            "investigations": investigations,
            "conflicts": conflicts,
            "consequences": consequences,
            "source_revision_vector": dict(sorted(source_revision_vector.items())),
        }
        view["projection_hash"] = canonical_sha256_digest(view)
        return view

    def replay_full(self, *, now: str) -> ReplayResult:
        del now
        state = self._projection_state(self._store.read_events())
        return ReplayResult(
            succeeded=True,
            projector_id=_PROJECTOR_ID,
            projector_version=_PROJECTOR_VERSION,
            projection_hash=canonical_sha256_digest(state),
            state=state,
            source_revision_vector=dict(state["source_revision_vector"]),
            last_global_sequence=int(state["last_global_sequence"]),
            applied_event_ids=list(state["applied_event_ids"]),
            applied_event_count=len(state["applied_event_ids"]),
        )

    def replay_checkpoint_tail(self, *, checkpoint, now: str) -> ReplayResult:
        del now
        if checkpoint.projector_id != _PROJECTOR_ID or checkpoint.projector_version != _PROJECTOR_VERSION:
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint projector mismatch")
        if checkpoint.projection_schema_version != 1:
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint schema version mismatch")
        if checkpoint.registry_revision not in {None, self._registry.registry_revision}:
            return self._failed_replay("p5_checkpoint_incompatible", "checkpoint registry revision mismatch")

        prefix_events = self._store.read_events(limit=checkpoint.last_global_sequence)
        prefix_state = self._projection_state(prefix_events)
        if not self._matches_checkpoint(prefix_state=prefix_state, checkpoint=checkpoint):
            return self._failed_replay("p5_checkpoint_mismatch", "checkpoint state does not match event log prefix")

        tail_events = self._store.read_events(global_sequence_after=checkpoint.last_global_sequence)
        state = self._projection_state(tail_events, seed_state=prefix_state)
        return ReplayResult(
            succeeded=True,
            projector_id=_PROJECTOR_ID,
            projector_version=_PROJECTOR_VERSION,
            projection_hash=canonical_sha256_digest(state),
            state=state,
            source_revision_vector=dict(state["source_revision_vector"]),
            last_global_sequence=int(state["last_global_sequence"]),
            applied_event_ids=list(state["applied_event_ids"]),
            applied_event_count=len(state["applied_event_ids"]),
        )

    def _request_digest(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        owner_fragments: tuple[OwnerAuthorizedFragment, ...],
    ) -> str:
        return canonical_sha256_digest(
            {
                "command": command.model_dump(mode="json"),
                "request": request.model_dump(mode="json"),
                "owner_fragments": [
                    fragment.model_dump(mode="json")
                    for fragment in sorted(owner_fragments, key=lambda item: item.fragment_id)
                ],
            }
        )

    def _schema_pin_for(self, event_name: str):
        event = self._registry.require_event(event_name, 1)
        return self._registry.require_schema(event.schema_ref, event.schema_version)

    def _required_events(self, request: P5ResolutionRequest) -> dict[str, object] | None:
        event_map = {event.event_name: event for event in request.proposed_events}
        if set(event_map) != {_INVESTIGATION_EVENT, _CONFLICT_EVENT, _ALARM_EVENT}:
            return None
        if len(event_map) != 3:
            return None
        return event_map

    def _validate_common(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        payload: dict[str, object],
    ) -> str | None:
        actor_ref = str(payload.get("actor_ref", ""))
        target_ref = str(payload.get("target_ref", ""))
        case_ref = str(payload.get("case_ref", ""))
        attempt_ref = str(payload.get("attempt_ref", ""))
        perception_ref = str(payload.get("perception_ref", ""))
        hidden_clue_ref = str(payload.get("hidden_clue_ref", ""))
        affordance_ref = str(payload.get("affordance_ref", ""))
        skill_ref = str(payload.get("skill_ref", ""))
        resistance_ref = str(payload.get("resistance_ref", ""))
        status_revision_ref = str(payload.get("status_revision_ref", ""))
        alarm_ref = str(payload.get("alarm_ref", ""))
        relationship_ref = str(payload.get("relationship_ref", ""))
        perception_visibility = str(payload.get("perception_visibility", ""))
        investigation_stream_ref = str(payload.get("investigation_stream_ref", ""))
        conflict_stream_ref = str(payload.get("conflict_stream_ref", ""))
        alarm_stream_ref = str(payload.get("alarm_stream_ref", ""))
        knowledge_stream_ref = str(payload.get("knowledge_stream_ref", ""))

        if command.command_type != "gameplay.investigation.resolve_conflict":
            return "p5_command_type_invalid"
        if not all(
            (
                actor_ref,
                target_ref,
                case_ref,
                attempt_ref,
                perception_ref,
                hidden_clue_ref,
                affordance_ref,
                skill_ref,
                resistance_ref,
                status_revision_ref,
                alarm_ref,
                relationship_ref,
                investigation_stream_ref,
                conflict_stream_ref,
                alarm_stream_ref,
                knowledge_stream_ref,
            )
        ):
            return "p5_investigation_input_invalid"
        if command.actor_ref != actor_ref or request.subject_scope_ref != actor_ref:
            return "p5_subject_scope_mismatch"
        if relationship_ref != request.relationship_ref:
            return "p5_relationship_ref_mismatch"
        if perception_visibility != "public":
            return "p5_perception_hidden"
        if affordance_ref != "affordance:investigate" or skill_ref != "skill:observe":
            return "p5_capability_unauthorized"
        if resistance_ref != "resistance:guard-alert":
            return "p5_resistance_unregistered"
        if investigation_stream_ref != _canonical_investigation_stream(case_ref):
            return "p5_canonical_stream_mismatch"
        if conflict_stream_ref != _canonical_conflict_stream(attempt_ref):
            return "p5_canonical_stream_mismatch"
        if alarm_stream_ref != _canonical_alarm_stream(attempt_ref):
            return "p5_canonical_stream_mismatch"
        if knowledge_stream_ref not in request.read_set_revisions.entries:
            return "p5_read_vector_mismatch"
        if dict(command.expected_revisions) != dict(request.expected_revisions.entries):
            return "p5_revision_vector_mismatch"
        if dict(command.read_set_revisions) != dict(request.read_set_revisions.entries):
            return "p5_read_vector_mismatch"
        for schema_pin in request.required_schema_pins:
            if command.pinned_revisions.get(schema_pin.schema_ref) != schema_pin.schema_version:
                return "p5_schema_pin_mismatch"

        required_events = self._required_events(request)
        if required_events is None:
            return "p5_required_events_invalid"
        if required_events[_INVESTIGATION_EVENT].stream_ref != investigation_stream_ref:
            return "p5_required_events_invalid"
        if required_events[_INVESTIGATION_EVENT].visibility != "public":
            return "p5_perception_hidden"
        if required_events[_CONFLICT_EVENT].stream_ref != conflict_stream_ref:
            return "p5_required_events_invalid"
        if required_events[_CONFLICT_EVENT].visibility != "authority_only":
            return "p5_required_events_invalid"
        if required_events[_ALARM_EVENT].stream_ref != alarm_stream_ref:
            return "p5_required_events_invalid"
        if required_events[_ALARM_EVENT].visibility != "authority_only":
            return "p5_required_events_invalid"

        for revisions in (request.expected_revisions.entries, request.read_set_revisions.entries):
            for stream_ref, expected_revision in revisions.items():
                if self._store.get_stream_head(stream_ref) != expected_revision:
                    return "p5_revision_stale"
        return None

    def _validate_fragments(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        owner_fragments: tuple[OwnerAuthorizedFragment, ...],
    ) -> str | None:
        owner = self._registry.require_owner_adapter(request.owner_adapter_ref)
        for fragment in owner_fragments:
            if fragment.owner_principal_ref != request.owner_adapter_ref:
                return "p5_owner_fragment_rejected"
            for schema_ref, schema_version in fragment.pinned_revisions.items():
                if command.pinned_revisions.get(schema_ref) != schema_version:
                    return "p5_owner_fragment_rejected"
            for stream_ref, revision in fragment.expected_revisions.items():
                if command.expected_revisions.get(stream_ref) != revision:
                    return "p5_owner_fragment_rejected"
            for stream_ref, revision in fragment.read_set_revisions.items():
                if command.read_set_revisions.get(stream_ref) != revision:
                    return "p5_owner_fragment_rejected"
            for stream_ref, specs in fragment.event_specs.items():
                policies = fragment.event_visibility_policies.get(stream_ref, ())
                if not policies or len(policies) != len(specs):
                    return "p5_owner_fragment_rejected"
                for (event_name, _payload), visibility in zip(specs, policies, strict=False):
                    if visibility == "project" or not _is_valid_event_visibility(visibility):
                        return "p5_owner_fragment_rejected"
                    if event_name not in owner.allowed_event_names:
                        return "p5_owner_fragment_rejected"
                    try:
                        entry = self._registry.require_event(event_name, 1)
                        if entry.stream_grammar_ref not in owner.allowed_stream_grammar_refs:
                            return "p5_owner_fragment_rejected"
                        self._registry.require_stream(stream_ref, entry.stream_grammar_ref)
                    except ValueError:
                        return "p5_owner_fragment_rejected"
        return None

    def _primary_fragment(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        payload: dict[str, object],
        adverse: bool,
    ) -> OwnerAuthorizedFragment:
        investigation_pin = self._schema_pin_for(_INVESTIGATION_EVENT)
        conflict_pin = self._schema_pin_for(_CONFLICT_EVENT)
        alarm_pin = self._schema_pin_for(_ALARM_EVENT)
        proposed_events = {event.event_name: event for event in request.proposed_events}
        investigation_stream_ref = str(payload["investigation_stream_ref"])
        conflict_stream_ref = str(payload["conflict_stream_ref"])
        alarm_stream_ref = str(payload["alarm_stream_ref"])

        investigation_payload = {
            "request_ref": request.request_ref,
            "case_ref": payload["case_ref"],
            "attempt_ref": payload["attempt_ref"],
            "actor_ref": payload["actor_ref"],
            "target_ref": payload["target_ref"],
            "relationship_ref": payload["relationship_ref"],
            "perception_ref": payload["perception_ref"],
            "hidden_clue_ref": payload["hidden_clue_ref"],
            "knowledge_stream_ref": payload["knowledge_stream_ref"],
            "affordance_ref": payload["affordance_ref"],
            "skill_ref": payload["skill_ref"],
            "resistance_ref": payload["resistance_ref"],
            "status_revision_ref": payload["status_revision_ref"],
            "alarm_ref": payload["alarm_ref"],
            "visibility": proposed_events[_INVESTIGATION_EVENT].visibility,
            "provenance_source_ref": request.provenance_source_ref,
            "registry_ref": request.registry_ref,
            "registry_revision": request.registry_revision,
            "registry_digest": request.registry_digest,
            "schema_ref": investigation_pin.schema_ref,
            "schema_version": investigation_pin.schema_version,
            "schema_digest": investigation_pin.schema_digest,
            "expected_stream_revisions": dict(request.expected_revisions.entries),
            "read_stream_revisions": dict(request.read_set_revisions.entries),
        }
        conflict_payload = {
            "request_ref": request.request_ref,
            "case_ref": payload["case_ref"],
            "attempt_ref": payload["attempt_ref"],
            "actor_ref": payload["actor_ref"],
            "target_ref": payload["target_ref"],
            "relationship_ref": payload["relationship_ref"],
            "affordance_ref": payload["affordance_ref"],
            "skill_ref": payload["skill_ref"],
            "resistance_ref": payload["resistance_ref"],
            "status_revision_ref": payload["status_revision_ref"],
            "alarm_ref": payload["alarm_ref"],
            "risk_ref": "risk:investigation:guard-alert",
            "outcome": "adverse" if adverse else "resolved",
            "visibility": proposed_events[_CONFLICT_EVENT].visibility,
            "provenance_source_ref": request.provenance_source_ref,
            "registry_ref": request.registry_ref,
            "registry_revision": request.registry_revision,
            "registry_digest": request.registry_digest,
            "schema_ref": conflict_pin.schema_ref,
            "schema_version": conflict_pin.schema_version,
            "schema_digest": conflict_pin.schema_digest,
            "expected_stream_revisions": dict(request.expected_revisions.entries),
            "read_stream_revisions": dict(request.read_set_revisions.entries),
        }

        event_specs: dict[str, tuple[tuple[str, dict[str, object]], ...]] = {
            investigation_stream_ref: ((_INVESTIGATION_EVENT, investigation_payload),),
            conflict_stream_ref: ((_CONFLICT_EVENT, conflict_payload),),
        }
        event_visibility_policies: dict[str, tuple[str, ...]] = {
            investigation_stream_ref: (proposed_events[_INVESTIGATION_EVENT].visibility,),
            conflict_stream_ref: (proposed_events[_CONFLICT_EVENT].visibility,),
        }
        expected_revisions = {
            investigation_stream_ref: int(request.expected_revisions.entries[investigation_stream_ref]),
            conflict_stream_ref: int(request.expected_revisions.entries[conflict_stream_ref]),
        }

        if adverse:
            alarm_payload = {
                "request_ref": request.request_ref,
                "case_ref": payload["case_ref"],
                "attempt_ref": payload["attempt_ref"],
                "actor_ref": payload["actor_ref"],
                "target_ref": payload["target_ref"],
                "relationship_ref": payload["relationship_ref"],
                "alarm_ref": payload["alarm_ref"],
                "status_revision_ref": payload["status_revision_ref"],
                "risk_ref": "risk:investigation:alarm",
                "visibility": proposed_events[_ALARM_EVENT].visibility,
                "provenance_source_ref": request.provenance_source_ref,
                "registry_ref": request.registry_ref,
                "registry_revision": request.registry_revision,
                "registry_digest": request.registry_digest,
                "schema_ref": alarm_pin.schema_ref,
                "schema_version": alarm_pin.schema_version,
                "schema_digest": alarm_pin.schema_digest,
                "expected_stream_revisions": dict(request.expected_revisions.entries),
                "read_stream_revisions": dict(request.read_set_revisions.entries),
            }
            event_specs[alarm_stream_ref] = ((_ALARM_EVENT, alarm_payload),)
            event_visibility_policies[alarm_stream_ref] = (proposed_events[_ALARM_EVENT].visibility,)
            expected_revisions[alarm_stream_ref] = int(request.expected_revisions.entries[alarm_stream_ref])

        return OwnerAuthorizedFragment.model_validate(
            {
                "fragment_id": f"fragment:{command.command_id}:investigation-primary",
                "owner_principal_ref": request.owner_adapter_ref,
                "source_rule_ref": _RULE_REF,
                "expected_revisions": expected_revisions,
                "read_set_revisions": dict(request.read_set_revisions.entries),
                "event_specs": event_specs,
                "event_visibility_policies": event_visibility_policies,
                "pinned_revisions": dict(command.pinned_revisions),
            }
        )

    def _validate_fragment_set(self, *, fragments: tuple[OwnerAuthorizedFragment, ...]) -> str | None:
        expected_revisions: dict[str, int] = {}
        read_revisions: dict[str, int] = {}
        pinned_revisions: dict[str, int] = {}
        for fragment in fragments:
            overlap = set(expected_revisions) & set(fragment.expected_revisions)
            if overlap:
                return "p5_atomicity_violation"
            expected_revisions.update(fragment.expected_revisions)
            for stream_ref, revision in fragment.read_set_revisions.items():
                prior = read_revisions.get(stream_ref)
                if prior is not None and prior != revision:
                    return "p5_atomicity_violation"
                read_revisions[stream_ref] = revision
            for pin_ref, revision in fragment.pinned_revisions.items():
                prior = pinned_revisions.get(pin_ref)
                if prior is not None and prior != revision:
                    return "p5_atomicity_violation"
                pinned_revisions[pin_ref] = revision
        return None

    def _build_batch(
        self,
        *,
        command: GameplayCommandEnvelope,
        request: P5ResolutionRequest,
        owner_fragments: tuple[OwnerAuthorizedFragment, ...],
        fragments: tuple[OwnerAuthorizedFragment, ...],
        digest: str,
    ) -> dict[str, object]:
        transaction_id = command.transaction_id or f"transaction:{command.command_id}"
        events: list[dict[str, object]] = []
        event_counter = 0
        for fragment in fragments:
            for stream_ref in sorted(fragment.event_specs):
                specs = fragment.event_specs[stream_ref]
                policies = tuple(fragment.event_visibility_policies.get(stream_ref, ()))
                for (event_name, payload), visibility_policy in zip(specs, policies, strict=False):
                    event_counter += 1
                    events.append(
                        {
                            "event_id": f"event:{command.command_id}:{event_counter}",
                            "event_type": event_name,
                            "schema_version": 1,
                            "stream_id": stream_ref,
                            "stream_revision": 0,
                            "global_sequence": 0,
                            "transaction_id": transaction_id,
                            "command_id": command.command_id,
                            "causation_id": command.causation_id,
                            "correlation_id": command.correlation_id,
                            "visibility_policy": visibility_policy,
                            "payload": payload,
                        }
                    )

        return {
            "transaction_id": transaction_id,
            "command_id": command.command_id,
            "expected_stream_revisions": dict(request.expected_revisions.entries),
            "read_stream_revisions": dict(request.read_set_revisions.entries),
            "pinned_revisions": dict(command.pinned_revisions),
            "events": events,
            "idempotency_record": {
                "principal_ref": _PRINCIPAL,
                "idempotency_key": command.idempotency_key,
                "payload_digest": digest,
            },
            "owner_fragments": [
                fragment.model_dump(mode="json")
                for fragment in sorted(owner_fragments, key=lambda item: item.fragment_id)
            ],
            "outbox_entries": [],
            "result_digest": digest,
            "projection_refresh_hints": [],
        }

    def _projection_state(
        self,
        events: list[Any],
        *,
        seed_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        investigations = [dict(item) for item in list(seed_state.get("investigations", []))] if seed_state else []
        conflicts = [dict(item) for item in list(seed_state.get("conflicts", []))] if seed_state else []
        consequences = [dict(item) for item in list(seed_state.get("consequences", []))] if seed_state else []
        source_revision_vector = dict(seed_state.get("source_revision_vector", {})) if seed_state else {}
        applied_event_ids = list(seed_state.get("applied_event_ids", [])) if seed_state else []
        last_global_sequence = int(seed_state.get("last_global_sequence", 0)) if seed_state else 0

        for event in events:
            applied_event_ids.append(event.event_id)
            last_global_sequence = max(last_global_sequence, event.global_sequence)
            source_revision_vector[event.stream_id] = event.stream_revision
            if event.event_type == _INVESTIGATION_EVENT:
                investigations.append(
                    {
                        "case_ref": event.payload.get("case_ref"),
                        "attempt_ref": event.payload.get("attempt_ref"),
                        "actor_ref": event.payload.get("actor_ref"),
                        "target_ref": event.payload.get("target_ref"),
                        "relationship_ref": event.payload.get("relationship_ref"),
                    }
                )
                continue
            if event.event_type == _CONFLICT_EVENT:
                conflicts.append(
                    {
                        "attempt_ref": event.payload.get("attempt_ref"),
                        "outcome": event.payload.get("outcome"),
                        "risk_ref": event.payload.get("risk_ref"),
                    }
                )
                continue
            consequences.append(
                {
                    "event_type": event.event_type,
                    "stream_ref": event.stream_id,
                }
            )

        return {
            "investigations": investigations,
            "conflicts": conflicts,
            "consequences": consequences,
            "source_revision_vector": dict(sorted(source_revision_vector.items())),
            "applied_event_ids": applied_event_ids,
            "last_global_sequence": last_global_sequence,
        }

    def _matches_checkpoint(self, *, prefix_state: dict[str, object], checkpoint) -> bool:
        expected_hash = canonical_sha256_digest(prefix_state)
        return (
            dict(prefix_state["source_revision_vector"]) == dict(checkpoint.source_revision_vector)
            and int(prefix_state["last_global_sequence"]) == checkpoint.last_global_sequence
            and list(prefix_state["applied_event_ids"]) == list(checkpoint.applied_event_ids)
            and prefix_state == dict(checkpoint.state)
            and expected_hash == checkpoint.projection_hash
        )

    def _rejected(self, failure_code: str) -> InvestigationConflictAuthorityResult:
        return InvestigationConflictAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind="rejected_zero_write",
                registry_ref=self._registry.registry_ref,
                registry_revision=self._registry.registry_revision,
                registry_digest=self._registry.registry_digest,
                committed_event_refs=(),
                failure_code=failure_code,
            ),
            receipt=None,
            settlement_plan=None,
        )

    def _committed_result(
        self,
        receipt,
        *,
        adverse: bool,
        settlement_plan: SettlementPlan | None,
        duplicate: bool,
    ) -> InvestigationConflictAuthorityResult:
        normalized_receipt = receipt.model_copy(
            update={"idempotency_status": "duplicate_replayed" if duplicate else receipt.idempotency_status},
            deep=True,
        )
        return InvestigationConflictAuthorityResult(
            resolution=P5ResolutionResult(
                result_kind="committed_adverse_outcome" if adverse else "committed_success",
                registry_ref=self._registry.registry_ref,
                registry_revision=self._registry.registry_revision,
                registry_digest=self._registry.registry_digest,
                committed_event_refs=tuple(normalized_receipt.committed_event_ids),
                failure_code=None,
            ),
            receipt=normalized_receipt,
            settlement_plan=settlement_plan,
        )

    def _failed_replay(self, error_code: str, message: str) -> ReplayResult:
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


__all__ = ["ActionWindowConflictResult", "InvestigationConflictAuthority", "InvestigationConflictAuthorityResult"]
