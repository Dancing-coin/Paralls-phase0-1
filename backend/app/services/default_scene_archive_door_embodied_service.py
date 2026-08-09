from __future__ import annotations

from dataclasses import dataclass

from app.contracts.l1.action_request import ActionRequest
from app.models.embodied_interaction import (
    ControllerExecutionGrant,
    EmbodiedActionRequest,
    EmbodiedPresentationObservation,
    LocalExecutionOutcome,
)
from app.models.player_input import InteractIntent
from app.models.world_result import ConstraintStateResult, ObjectStateResult
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.esm_service import ESMService


@dataclass(slots=True)
class _DoorAttempt:
    event: InteractIntent
    action_request: ActionRequest
    request: EmbodiedActionRequest
    grant: ControllerExecutionGrant
    previous_state: str
    current_state: str
    machine_id: str
    connection_ref: str


@dataclass(slots=True)
class DoorEmbodiedPreflightResult:
    accepted: bool
    action_request: ActionRequest
    embodied_action_request: dict[str, object] | None = None
    constraint: ConstraintStateResult | None = None
    error_code: str = ""


@dataclass(slots=True)
class DoorEmbodiedOutcomeResult:
    accepted: bool
    settlement_payload: dict[str, object] | None = None
    object_result: ObjectStateResult | None = None
    error_code: str = ""


@dataclass(slots=True)
class DoorPresentationObservationResult:
    accepted: bool
    idempotent: bool = False
    error_code: str = ""


class DefaultSceneArchiveDoorEmbodiedService:
    """Backend-owned embodied preflight and one-time settlement for obj_archive_door/open."""

    target_object_id = "obj_archive_door"
    interaction_type = "open"
    affordance_id = "affordance:obj_archive_door:open"
    authority_preflight_prefix = "preflight:obj_archive_door"
    execution_profile_ref = "execution_profile:obj_archive_door:open:v1"
    observation_rule_ref = "observation_rule:archive_door_contact:v1"
    contact_alignment_tolerance_m = 0.08
    # Time values are Godot monotonic milliseconds; retain a bounded window for approach/align/contact.
    grant_ttl = 30_000

    def __init__(
        self,
        *,
        esm_service: ESMService,
        auth_service: EmbodiedControllerAuthService,
        evidence_ledger: EmbodiedEvidenceLedger,
    ) -> None:
        self._esm = esm_service
        self._auth = auth_service
        self._evidence_ledger = evidence_ledger
        self.scene_revision = 1
        self.binding_revision = 4
        self.policy_revision = 1
        self.commit_count = 0
        self._preflight_by_request_id: dict[str, DoorEmbodiedPreflightResult] = {}
        self._attempts_by_grant: dict[str, _DoorAttempt] = {}
        self._active_request_id_by_target: dict[str, str] = {}
        self._outcome_cache: dict[str, DoorEmbodiedOutcomeResult] = {}
        self._applied_settlement_ids_by_attempt: dict[str, str] = {}

    def handles_grant(self, grant_id: str) -> bool:
        return grant_id in self._attempts_by_grant

    def preflight(
        self,
        *,
        event: InteractIntent,
        action_request: ActionRequest,
        actor_position: tuple[float, float, float] | None,
        connection_ref: str,
        now: int,
    ) -> DoorEmbodiedPreflightResult:
        request_id = action_request.request_id
        cached = self._preflight_by_request_id.get(request_id)
        if cached is not None:
            return cached

        if event.interaction_type == "close":
            return DoorEmbodiedPreflightResult(
                accepted=False,
                action_request=action_request,
                constraint=self._constraint(
                    event,
                    constraint_type="interaction_policy_constraint",
                    constraint_code="physical_close_not_implemented",
                    constraint_summary="obj_archive_door close remains fail-closed until the physical path is implemented",
                ),
            )

        binding_result = self._auth.resolve_controller_binding(
            actor_id=event.actor_id,
            connection_ref=connection_ref,
        )
        if not binding_result.accepted or binding_result.binding is None:
            return DoorEmbodiedPreflightResult(
                accepted=False,
                action_request=action_request,
                constraint=self._constraint(
                    event,
                    constraint_type="controller_binding_constraint",
                    constraint_code="controller_binding_required",
                    constraint_summary="door embodiment requires a trusted controller binding on this connection",
                ),
                error_code=binding_result.error_code,
            )

        self._release_expired_local_reservation(now=now)
        active_request_id = self._active_request_id_by_target.get(self.target_object_id)
        if active_request_id is not None and active_request_id != request_id:
            return DoorEmbodiedPreflightResult(
                accepted=False,
                action_request=action_request,
                constraint=self._constraint(
                    event,
                    constraint_type="interaction_occupancy_constraint",
                    constraint_code="stance_occupied",
                    constraint_summary="obj_archive_door already has an active embodied attempt",
                ),
            )

        interaction_policy = self._esm.interaction_policy_for(
            self.target_object_id,
            self.interaction_type,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
        )
        if interaction_policy is None:
            return DoorEmbodiedPreflightResult(
                accepted=False,
                action_request=action_request,
                constraint=self._esm.reject_unsupported_interaction(event),
            )
        if not bool(interaction_policy.get("state_match", True)):
            return DoorEmbodiedPreflightResult(
                accepted=False,
                action_request=action_request,
                constraint=self._esm.reject_interaction_state(
                    event,
                    expected_state=str(interaction_policy["previous_state"]),
                    actual_state=self._esm.interaction_state_for(
                        room_id=event.room_id,
                        scene_id=event.scene_id,
                        zone_id=event.zone_id,
                        target_object_id=event.target_object_id,
                    ),
                ),
            )

        semantic_result = self._esm.resolve_interaction(event, actor_position=actor_position)
        if isinstance(semantic_result, ConstraintStateResult):
            return DoorEmbodiedPreflightResult(
                accepted=False,
                action_request=action_request,
                constraint=semantic_result,
            )

        request = EmbodiedActionRequest.model_validate(
            {
                "request_id": f"embodied_action_request:{request_id}",
                "interaction_attempt_id": f"attempt:{self.target_object_id}:{request_id}",
                "actor_id": event.actor_id,
                "target_ref": self.target_object_id,
                "action_semantic": self.interaction_type,
                "affordance_id": self.affordance_id,
                "authority_preflight_ref": f"{self.authority_preflight_prefix}:{request_id}",
                "policy_revision": self.policy_revision,
                "scene_revision": self.scene_revision,
                "binding_revision": self.binding_revision,
                "required_anchor_roles": ["approach_stance", "contact"],
                "execution_profile_ref": self.execution_profile_ref,
                "expiration_tick": now + self.grant_ttl,
                "causation_id": action_request.causation_id,
                "correlation_id": action_request.correlation_id,
                "realization_route": "embodied_controller_v1",
                "settlement_writer_kind": "esm_compatibility_adapter",
            }
        )
        grant = self._auth.issue_execution_grant(
            binding=binding_result.binding,
            request=request,
            issued_at=now,
            ttl=self.grant_ttl,
        )
        previous_state = str(interaction_policy["previous_state"])
        current_state = str(interaction_policy["current_state"])
        machine_id = str(interaction_policy["machine_id"])
        self._attempts_by_grant[grant.grant_id] = _DoorAttempt(
            event=event,
            action_request=action_request,
            request=request,
            grant=grant,
            previous_state=previous_state,
            current_state=current_state,
            machine_id=machine_id,
            connection_ref=connection_ref,
        )
        attempt = self._attempts_by_grant[grant.grant_id]
        if not self._record_preflight_evidence(attempt, now=now):
            self._attempts_by_grant.pop(grant.grant_id, None)
            return DoorEmbodiedPreflightResult(
                accepted=False,
                action_request=action_request,
                error_code="evidence_ledger_rejected",
            )
        self._active_request_id_by_target[self.target_object_id] = request_id
        result = DoorEmbodiedPreflightResult(
            accepted=True,
            action_request=action_request,
            embodied_action_request={
                "request": request.model_dump(mode="json"),
                "grant": grant.model_dump(mode="json"),
                "idempotent": False,
            },
        )
        self._preflight_by_request_id[request_id] = result
        return result

    def handle_local_outcome(
        self,
        payload: dict[str, object],
        *,
        connection_ref: str,
        now: int,
    ) -> DoorEmbodiedOutcomeResult:
        grant_id = str(payload.get("controller_grant_id", "") or "")
        cache_key = self._outcome_cache_key(payload)
        cached = self._outcome_cache.get(cache_key)
        if cached is not None:
            settlement_payload = dict(cached.settlement_payload or {})
            settlement_payload["idempotent"] = True
            return DoorEmbodiedOutcomeResult(
                accepted=True,
                settlement_payload=settlement_payload,
                object_result=cached.object_result,
            )

        attempt = self._attempts_by_grant.get(grant_id)
        if attempt is None:
            return DoorEmbodiedOutcomeResult(accepted=False, error_code="controller_binding_required")
        try:
            outcome = LocalExecutionOutcome.model_validate(payload)
        except ValueError:
            return DoorEmbodiedOutcomeResult(accepted=False, error_code="outcome_schema_invalid")

        validation = self._auth.consume_grant_for_outcome(
            grant_id=outcome.controller_grant_id,
            connection_epoch=outcome.connection_epoch,
            outcome_nonce=outcome.outcome_nonce,
            payload_digest=outcome.payload_digest,
            now=now,
            connection_ref=connection_ref,
        )
        if not validation.accepted and not validation.idempotent:
            return DoorEmbodiedOutcomeResult(accepted=False, error_code=validation.error_code)

        terminal_evidence = self._evidence_ledger.append(
            attempt_id=attempt.request.interaction_attempt_id,
            event_kind="terminal_local_observation",
            emitter_kind="controller",
            emitter_id=attempt.grant.controller_instance_id,
            emitter_epoch=attempt.grant.connection_epoch,
            source_sequence=outcome.terminal_sequence,
            payload_digest=outcome.payload_digest,
            payload=outcome.model_dump(mode="json"),
            occurred_at=outcome.observed_at,
            recorded_at=now,
        )
        if not terminal_evidence.accepted:
            return DoorEmbodiedOutcomeResult(accepted=False, error_code=terminal_evidence.error_code)

        result = self._settle_attempt(attempt, outcome)
        if result.settlement_payload is not None:
            settlement_evidence = self._evidence_ledger.append(
                attempt_id=attempt.request.interaction_attempt_id,
                event_kind="settlement",
                emitter_kind="backend",
                emitter_id="default_scene_archive_door_authority",
                emitter_epoch=1,
                source_sequence=3,
                payload_digest=f"sha256:{result.settlement_payload['settlement_id']}",
                payload=dict(result.settlement_payload),
                occurred_at=now,
                recorded_at=now,
            )
            if not settlement_evidence.accepted:
                return DoorEmbodiedOutcomeResult(accepted=False, error_code=settlement_evidence.error_code)
        if result.object_result is not None and result.settlement_payload is not None:
            self._applied_settlement_ids_by_attempt[attempt.request.interaction_attempt_id] = str(
                result.settlement_payload["settlement_id"]
            )
        self._outcome_cache[cache_key] = result
        self._active_request_id_by_target.pop(self.target_object_id, None)
        return result

    def _settle_attempt(self, attempt: _DoorAttempt, outcome: LocalExecutionOutcome) -> DoorEmbodiedOutcomeResult:
        settlement_id = self._settlement_id(attempt)
        if attempt.request.binding_revision != self.binding_revision:
            return DoorEmbodiedOutcomeResult(
                accepted=True,
                settlement_payload=self._settlement_payload(
                    attempt=attempt,
                    outcome="rejected",
                    settlement_status="rejected",
                    error_code="binding_revision_mismatch",
                    settlement_id=settlement_id,
                ),
            )
        if (
            attempt.request.scene_revision != self.scene_revision
            or attempt.request.policy_revision != self.policy_revision
        ):
            return DoorEmbodiedOutcomeResult(
                accepted=True,
                settlement_payload=self._settlement_payload(
                    attempt=attempt,
                    outcome="rejected",
                    settlement_status="rejected",
                    error_code="revision_conflict",
                    settlement_id=settlement_id,
                ),
            )
        if outcome.terminal_status != "contact_observed":
            return DoorEmbodiedOutcomeResult(
                accepted=True,
                settlement_payload=self._settlement_payload(
                    attempt=attempt,
                    outcome="not_committed",
                    settlement_status="rejected",
                    error_code=outcome.failure_code or outcome.terminal_status,
                    settlement_id=settlement_id,
                ),
            )
        if (
            outcome.contact_observation is None
            or outcome.contact_observation.actor_contact_ref != f"collider:{attempt.request.actor_id}:hand_r"
            or outcome.contact_observation.target_collider_ref != "collider:obj_archive_door:body"
            or outcome.contact_observation.observation_rule_ref != self.observation_rule_ref
            or outcome.contact_observation.hand_alignment_error_m is None
            or outcome.contact_observation.hand_alignment_error_m > self.contact_alignment_tolerance_m
            or outcome.object_observation is not None
        ):
            return DoorEmbodiedOutcomeResult(
                accepted=True,
                settlement_payload=self._settlement_payload(
                    attempt=attempt,
                    outcome="observation_rejected",
                    settlement_status="rejected",
                    error_code="observation_rule_failed",
                    settlement_id=settlement_id,
                ),
            )

        interaction_policy = self._esm.interaction_policy_for(
            self.target_object_id,
            self.interaction_type,
            room_id=attempt.event.room_id,
            scene_id=attempt.event.scene_id,
            zone_id=attempt.event.zone_id,
            actor_id=attempt.event.actor_id,
        )
        if interaction_policy is None or not bool(interaction_policy.get("state_match", True)):
            return DoorEmbodiedOutcomeResult(
                accepted=True,
                settlement_payload=self._settlement_payload(
                    attempt=attempt,
                    outcome="rejected",
                    settlement_status="rejected",
                    error_code="door_state_stale",
                    settlement_id=settlement_id,
                ),
            )

        self._esm.commit_interaction_state(
            room_id=attempt.event.room_id,
            scene_id=attempt.event.scene_id,
            zone_id=attempt.event.zone_id,
            target_object_id=self.target_object_id,
            current_state=attempt.current_state,
        )
        object_result = self._esm.emit_object_state_result(
            room_id=attempt.event.room_id,
            scene_id=attempt.event.scene_id,
            zone_id=attempt.event.zone_id,
            actor_id=attempt.event.actor_id,
            target_object_id=self.target_object_id,
            previous_state=attempt.previous_state,
            current_state=attempt.current_state,
            machine_id=attempt.machine_id,
            producer_ts=outcome.observed_at + 1,
            request_ref=attempt.action_request.request_id,
            causation_id=attempt.action_request.causation_id,
            correlation_id=attempt.action_request.correlation_id,
            settlement_id=settlement_id,
            interaction_attempt_id=attempt.request.interaction_attempt_id,
            grant_id=attempt.grant.grant_id,
        )
        self.commit_count += 1
        return DoorEmbodiedOutcomeResult(
            accepted=True,
            settlement_payload=self._settlement_payload(
                attempt=attempt,
                outcome="committed",
                settlement_status="applied",
                error_code="",
                settlement_id=settlement_id,
            ),
            object_result=object_result,
        )

    def _settlement_payload(
        self,
        *,
        attempt: _DoorAttempt,
        outcome: str,
        settlement_status: str,
        error_code: str,
        settlement_id: str,
    ) -> dict[str, object]:
        return {
            "settlement_id": settlement_id,
            "interaction_attempt_id": attempt.request.interaction_attempt_id,
            "grant_id": attempt.grant.grant_id,
            "outcome": outcome,
            "settlement_status": settlement_status,
            "error_code": error_code,
            "idempotent": False,
        }

    def record_phase_event(self, payload: dict[str, object], *, now: int) -> bool:
        grant_id = str(payload.get("grant_id", "") or "")
        attempt = self._attempts_by_grant.get(grant_id)
        if attempt is None:
            return False
        evidence = self._evidence_ledger.append(
            attempt_id=attempt.request.interaction_attempt_id,
            event_kind="local_phase",
            emitter_kind="controller",
            emitter_id=attempt.grant.controller_instance_id,
            emitter_epoch=attempt.grant.connection_epoch,
            source_sequence=int(payload.get("source_sequence", 0) or 0),
            payload_digest=str(payload.get("payload_digest", "") or ""),
            payload={
                "grant_id": grant_id,
                "connection_epoch": int(payload.get("connection_epoch", 0) or 0),
            },
            occurred_at=now,
            recorded_at=now,
        )
        return evidence.accepted

    def record_presentation_observation(
        self,
        payload: dict[str, object],
        *,
        connection_ref: str,
        now: int,
    ) -> DoorPresentationObservationResult:
        try:
            observation = EmbodiedPresentationObservation.model_validate(payload)
        except ValueError:
            return DoorPresentationObservationResult(accepted=False, error_code="presentation_schema_invalid")

        attempt = next(
            (
                candidate
                for candidate in self._attempts_by_grant.values()
                if candidate.request.interaction_attempt_id == observation.interaction_attempt_id
            ),
            None,
        )
        if attempt is None:
            return DoorPresentationObservationResult(accepted=False, error_code="presentation_attempt_unknown")
        if attempt.connection_ref != connection_ref:
            return DoorPresentationObservationResult(accepted=False, error_code="controller_binding_required")
        if self._applied_settlement_ids_by_attempt.get(observation.interaction_attempt_id) != observation.settlement_id:
            return DoorPresentationObservationResult(accepted=False, error_code="presentation_settlement_mismatch")

        evidence = self._evidence_ledger.append(
            attempt_id=observation.interaction_attempt_id,
            event_kind="presentation",
            emitter_kind="godot_mirror",
            emitter_id="archive_door_physical_presentation",
            emitter_epoch=attempt.grant.connection_epoch,
            source_sequence=1,
            payload_digest=observation.snapshot_digest,
            payload={
                "interaction_attempt_id": observation.interaction_attempt_id,
                "settlement_id": observation.settlement_id,
                "snapshot_digest": observation.snapshot_digest,
            },
            occurred_at=now,
            recorded_at=now,
        )
        return DoorPresentationObservationResult(
            accepted=evidence.accepted,
            idempotent=evidence.idempotent,
            error_code=evidence.error_code,
        )

    def _record_preflight_evidence(self, attempt: _DoorAttempt, *, now: int) -> bool:
        request_evidence = self._evidence_ledger.append(
            attempt_id=attempt.request.interaction_attempt_id,
            event_kind="request_authorized",
            emitter_kind="backend",
            emitter_id="default_scene_archive_door_authority",
            emitter_epoch=1,
            source_sequence=1,
            payload_digest=self._auth.request_digest(attempt.request),
            payload={
                "request_id": attempt.request.request_id,
                "grant_id": attempt.grant.grant_id,
                "affordance_id": attempt.request.affordance_id,
            },
            occurred_at=now,
            recorded_at=now,
        )
        if not request_evidence.accepted:
            return False
        binding_evidence = self._evidence_ledger.append(
            attempt_id=attempt.request.interaction_attempt_id,
            event_kind="registry_binding",
            emitter_kind="backend",
            emitter_id="default_scene_archive_door_authority",
            emitter_epoch=1,
            source_sequence=2,
            payload_digest=f"sha256:binding:{attempt.request.interaction_attempt_id}:{attempt.request.binding_revision}",
            payload={
                "binding_revision": attempt.request.binding_revision,
                "policy_revision": attempt.request.policy_revision,
                "scene_revision": attempt.request.scene_revision,
            },
            occurred_at=now,
            recorded_at=now,
        )
        return binding_evidence.accepted

    @staticmethod
    def _settlement_id(attempt: _DoorAttempt) -> str:
        return f"settlement:{attempt.request.interaction_attempt_id}"

    def _release_expired_local_reservation(self, *, now: int) -> None:
        """Release only the door's abandoned lease after its authoritative grant expires."""

        active_request_id = self._active_request_id_by_target.get(self.target_object_id)
        if active_request_id is None:
            return
        for grant_id, attempt in tuple(self._attempts_by_grant.items()):
            if attempt.action_request.request_id != active_request_id:
                continue
            if now <= attempt.grant.expires_at:
                return
            self._attempts_by_grant.pop(grant_id, None)
            self._active_request_id_by_target.pop(self.target_object_id, None)
            return

    def _constraint(
        self,
        event: InteractIntent,
        *,
        constraint_type: str,
        constraint_code: str,
        constraint_summary: str,
    ) -> ConstraintStateResult:
        request_ref = f"interact:{event.producer_ts}:{event.target_object_id}"
        return ConstraintStateResult(
            request_ref=request_ref,
            result_id=f"constraint:{request_ref}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            source_type="player",
            entity_id=event.target_object_id,
            target_object_id=event.target_object_id,
            result_type="constraint_state_result",
            causation_id=f"interact:{event.producer_ts}",
            correlation_id=f"interact:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            constraint_type=constraint_type,
            constraint_code=constraint_code,
            constraint_summary=constraint_summary,
            blocking_entity_refs=[event.target_object_id],
            settlement_status="rejected",
        )

    @staticmethod
    def _outcome_cache_key(payload: dict[str, object]) -> str:
        grant_id = str(payload.get("controller_grant_id", "") or "")
        digest = str(payload.get("payload_digest", "") or "")
        nonce = str(payload.get("outcome_nonce", "") or "")
        return f"{grant_id}:{digest}:{nonce}"
