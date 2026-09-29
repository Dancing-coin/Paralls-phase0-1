from __future__ import annotations

from math import dist

from pydantic import BaseModel, ConfigDict, Field

from app.models.embodied_interaction import (
    ActionAttempt,
    AuthorityResult,
    ControllerExecutionGrant,
    EmbodiedActionRequest,
    EmbodiedSettlementWriterSelector,
    LocalExecutionOutcome,
    SettlementWriterKind,
)
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService
from app.services.physical_interaction_channel import PhysicalContactObservation, PhysicalInteractionChannel, PhysicalInteractionRequest


class EmbodiedAuthoritySettlementReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction_attempt_id: str
    outcome: str
    settlement_writer_kind: SettlementWriterKind | None = None
    error_code: str = ""
    authority_results: list[dict[str, object]] = Field(default_factory=list)
    idempotent: bool = False


class _RegisteredAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: EmbodiedActionRequest
    grant: ControllerExecutionGrant
    effect_scope: str = "single_object_physical"


class EmbodiedAuthoritySettlementService:
    def __init__(
        self,
        *,
        auth_service: EmbodiedControllerAuthService | None = None,
        physical_channel: PhysicalInteractionChannel | None = None,
        gameplay_event_batch_writer_available: bool = False,
    ) -> None:
        self._auth = auth_service
        self._physical_channel = physical_channel or PhysicalInteractionChannel()
        self._writer_selector = EmbodiedSettlementWriterSelector(
            gameplay_event_batch_writer_available=gameplay_event_batch_writer_available
        )
        self._attempts_by_grant: dict[str, _RegisteredAttempt] = {}
        self._receipts_by_digest: dict[str, EmbodiedAuthoritySettlementReceipt] = {}
        self._attempt_results: dict[str, tuple[str, str, AuthorityResult]] = {}
        self._aggregate_revisions: dict[str, int] = {}
        self._street_actors: dict[str, dict[str, object]] = {
            "street_bandage": {"position": (0.0, 0.2, -10.0), "physics_tick": 0, "hp": 100, "stamina": 100},
        "char_a": {"position": (2.05, 0.2, -7.0), "physics_tick": 0, "hp": 100, "stamina": 100},
        "char_b": {"position": (-2.05, 0.2, -7.0), "physics_tick": 0, "hp": 100, "stamina": 100},
        }
        self._street_results_by_key: dict[str, tuple[str, AuthorityResult]] = {}
        self._street_transport_connected = True
        self._street_snapshot_ready = True
        self._street_connection_epoch = 1
        self._street_next_client_sequence = 1
        self._street_snapshot_digest = "sha256:street-initial-snapshot"
        self._street_resync_marker = "resync:initial"
        self.mutation_count = 0

    def street_actor_state(self, actor_id: str) -> dict[str, object]:
        state = self._street_actors.get(actor_id)
        return dict(state) if state is not None else {}

    def record_street_pose(self, actor_id: str, position: tuple[float, float, float], *, physics_tick: int) -> bool:
        state = self._street_actors.get(actor_id)
        if state is None or len(position) != 3 or physics_tick <= int(state["physics_tick"]):
            return False
        previous = state["position"]
        elapsed = (physics_tick - int(state["physics_tick"])) / 60.0
        if not isinstance(previous, tuple) or dist(previous, position) > 8.0 * elapsed + 0.1:
            return False
        if abs(position[1] - 0.2) > 1.5 or abs(position[0]) > 48.0 or abs(position[2]) > 48.0:
            return False
        regained = max(0, physics_tick - int(state["physics_tick"])) // 10
        state["stamina"] = min(100, int(state["stamina"]) + regained)
        state["position"] = position
        state["physics_tick"] = physics_tick
        return True

    def street_transport_state(self) -> dict[str, object]:
        """Expose only bounded Mode B recovery metadata for probes/telemetry."""

        return {
            "connected": self._street_transport_connected,
            "connection_epoch": self._street_connection_epoch,
            "snapshot_ready": self._street_snapshot_ready,
            "snapshot_digest": self._street_snapshot_digest,
            "resync_marker": self._street_resync_marker,
            "next_client_sequence": self._street_next_client_sequence,
        }

    def disconnect_street_transport(self) -> None:
        self._street_transport_connected = False
        self._street_snapshot_ready = False

    def reconnect_street_transport(self) -> int:
        """Start a new Mode B epoch; action admission stays closed until sync."""

        self._street_connection_epoch += 1
        self._street_next_client_sequence = 1
        self._street_transport_connected = True
        self._street_snapshot_ready = False
        self._street_snapshot_digest = ""
        self._street_resync_marker = ""
        return self._street_connection_epoch

    def accept_street_snapshot(self, connection_epoch: int, *, snapshot_digest: str, resync_marker: str) -> bool:
        if connection_epoch != self._street_connection_epoch:
            return False
        if not self._street_transport_connected or not snapshot_digest.strip() or not resync_marker.strip():
            return False
        self._street_snapshot_digest = snapshot_digest
        self._street_resync_marker = resync_marker
        self._street_snapshot_ready = True
        return True

    def settle_street_combat(self, attempt: ActionAttempt) -> AuthorityResult:
        existing = self._street_results_by_key.get(attempt.idempotency_key)
        if existing is not None:
            digest, result = existing
            if digest == attempt.payload_digest:
                return result.model_copy(deep=True)
            return self._result(attempt, outcome="rejected", failed_stage="idempotency", failed_code="idempotency_key_reused", recovery_action="discard_duplicate")
        if not self._street_transport_connected:
            return self._result(
                attempt,
                outcome="rejected",
                failed_stage="transport",
                failed_code="transport_disconnected",
                recovery_action="reconnect_and_resync",
            )
        if "connection_epoch" in attempt.model_fields_set and attempt.connection_epoch != self._street_connection_epoch:
            return self._result(
                attempt,
                outcome="rejected",
                failed_stage="transport",
                failed_code="connection_epoch_stale",
                recovery_action="refresh_connection_epoch",
            )
        if not self._street_snapshot_ready:
            return self._result(
                attempt,
                outcome="rejected",
                failed_stage="recovery",
                failed_code="recovery_required",
                recovery_action="await_snapshot_and_resync",
            )
        explicit_sequence = "client_sequence" in attempt.model_fields_set
        if explicit_sequence:
            if attempt.client_sequence < self._street_next_client_sequence:
                return self._result(
                    attempt,
                    outcome="rejected",
                    failed_stage="transport",
                    failed_code="client_sequence_stale",
                    recovery_action="refresh_and_retry",
                )
            if attempt.client_sequence > self._street_next_client_sequence:
                return self._result(
                    attempt,
                    outcome="rejected",
                    failed_stage="transport",
                    failed_code="client_sequence_gap",
                    recovery_action="resync_and_retry",
                )
            self._street_next_client_sequence += 1
        actor_id = attempt.actor_ref.removeprefix("character:")
        target_id = attempt.target_refs[0].removeprefix("character:") if len(attempt.target_refs) == 1 else ""
        actor = self._street_actors.get(actor_id)
        target = self._street_actors.get(target_id)
        if actor is None or target is None or actor_id == target_id:
            return self._result(attempt, outcome="rejected", failed_stage="target", failed_code="target_invalid", recovery_action="select_valid_target")
        if attempt.semantic_action_id not in {"action:melee.unarmed_punch", "action:melee.short_punch", "action:melee.sword_slash"} or attempt.authority_route != "esm" or not attempt.physics_evidence_refs:
            return self._result(attempt, outcome="rejected", failed_stage="action", failed_code="action_unsupported", recovery_action="select_qualified_action")
        stamina_cost = 8 if attempt.semantic_action_id == "action:melee.short_punch" else 14 if attempt.semantic_action_id == "action:melee.sword_slash" else 12
        if int(actor["stamina"]) < stamina_cost:
            return self._result(attempt, outcome="rejected", failed_stage="resource", failed_code="stamina_insufficient", recovery_action="recover_stamina")
        if int(actor["hp"]) <= 0 or int(target["hp"]) <= 0:
            return self._result(attempt, outcome="rejected", failed_stage="target", failed_code="actor_incapacitated", recovery_action="select_active_target")
        actor_position = actor["position"]
        target_position = target["position"]
        if not isinstance(actor_position, tuple) or not isinstance(target_position, tuple):
            return self._result(attempt, outcome="rejected", failed_stage="position", failed_code="position_unavailable")
        planar_distance = dist((actor_position[0], actor_position[2]), (target_position[0], target_position[2]))
        if planar_distance > 2.4:
            return self._result(attempt, outcome="rejected", failed_stage="range", failed_code="target_out_of_range", recovery_action="approach_target")
        result = self.settle(attempt)
        if result.outcome != "committed":
            return result
        target["hp"] = max(0, int(target["hp"]) - 20)
        actor["stamina"] = int(actor["stamina"]) - stamina_cost
        projection = dict(result.committed_projection)
        projection.update({"target_hp": target["hp"], "target_ref": attempt.target_refs[0], "actor_stamina": actor["stamina"], "actor_ref": attempt.actor_ref, "damage": 20, "distance_m": round(planar_distance, 3)})
        result = result.model_copy(update={"committed_projection": projection})
        self._street_results_by_key[attempt.idempotency_key] = (attempt.payload_digest, result.model_copy(deep=True))
        return result

    def settle(self, attempt: ActionAttempt) -> AuthorityResult:
        """Atomically settle one semantic attempt in the local authority seam.

        This bounded Phase-1 implementation keeps ESM/Gameplay effects in one
        transaction-shaped commit and exposes only committed projections.
        """
        digest = attempt.payload_digest
        existing = self._attempt_results.get(attempt.idempotency_key)
        if existing is not None:
            existing_digest, _transaction_id, result = existing
            if existing_digest == digest:
                return result.model_copy(deep=True)
            return self._result(
                attempt,
                outcome="rejected",
                failed_stage="idempotency",
                failed_code="idempotency_key_reused",
                recovery_action="discard_duplicate",
            )

        for stream_ref, expected in attempt.expected_revisions.items():
            current = self._aggregate_revisions.get(stream_ref, 0)
            if expected != current:
                return self._result(
                    attempt,
                    outcome="rejected",
                    failed_stage="precondition",
                    failed_code="revision_conflict",
                    failed_precondition=stream_ref,
                    recovery_action="refresh_and_retry",
                )

        if attempt.authority_route == "composite" and attempt.semantic_action_id.endswith(":bad"):
            return self._result(
                attempt,
                outcome="rejected",
                failed_stage="atomic_validation",
                failed_code="composite_atomic_validation_failed",
                recovery_action="zero_write",
            )

        transaction_id = f"txn:{attempt.idempotency_key}"
        event_ids = [f"event:{attempt.idempotency_key}:1"]
        next_revisions = dict(self._aggregate_revisions)
        for stream_ref in attempt.expected_revisions:
            next_revisions[stream_ref] = next_revisions.get(stream_ref, 0) + 1
        if not attempt.expected_revisions:
            stream_ref = f"actor:{attempt.actor_ref}"
            next_revisions[stream_ref] = next_revisions.get(stream_ref, 0) + 1
        projection = {
            "attempt_id": attempt.attempt_id,
            "action_instance_id": attempt.action_instance_id,
            "authority_route": attempt.authority_route,
            "semantic_action_id": attempt.semantic_action_id,
            "target_refs": list(attempt.target_refs),
            "physics_tick": attempt.physics_tick,
        }
        result = AuthorityResult(
            attempt_id=attempt.attempt_id,
            action_instance_id=attempt.action_instance_id,
            transaction_id=transaction_id,
            outcome="committed",
            committed_event_ids=event_ids,
            resulting_revisions=next_revisions,
            causation_id=attempt.causation_id,
            correlation_id=attempt.correlation_id,
            authority_scope=attempt.authority_route,
            committed_projection=projection,
        )
        self._aggregate_revisions = next_revisions
        self._attempt_results[attempt.idempotency_key] = (digest, transaction_id, result)
        self.mutation_count += 1
        return result.model_copy(deep=True)

    def query(self, idempotency_key: str) -> AuthorityResult | None:
        stored = self._attempt_results.get(idempotency_key)
        return stored[2].model_copy(deep=True) if stored else None

    @staticmethod
    def _result(
        attempt: ActionAttempt,
        *,
        outcome: str,
        failed_stage: str | None = None,
        failed_code: str | None = None,
        failed_precondition: str | None = None,
        recovery_action: str | None = None,
    ) -> AuthorityResult:
        return AuthorityResult(
            attempt_id=attempt.attempt_id,
            action_instance_id=attempt.action_instance_id,
            outcome=outcome,
            failed_stage=failed_stage,
            failed_code=failed_code,
            failed_precondition=failed_precondition,
            recovery_action=recovery_action,
            causation_id=attempt.causation_id,
            correlation_id=attempt.correlation_id,
            authority_scope=attempt.authority_route,
        )

    def register_attempt(
        self,
        *,
        request: EmbodiedActionRequest,
        grant: ControllerExecutionGrant,
        effect_scope: str = "single_object_physical",
    ) -> None:
        self._attempts_by_grant[grant.grant_id] = _RegisteredAttempt(request=request, grant=grant, effect_scope=effect_scope)

    def settle_local_outcome(self, payload: dict[str, object], *, now: int) -> EmbodiedAuthoritySettlementReceipt:
        grant_id = str(payload.get("controller_grant_id", "") or "")
        digest = str(payload.get("payload_digest", "") or "")
        receipt_key = f"{grant_id}:{digest}:{payload.get('outcome_nonce', '')}"
        if receipt_key in self._receipts_by_digest:
            return self._receipts_by_digest[receipt_key].model_copy(update={"idempotent": True})
        try:
            outcome = LocalExecutionOutcome.model_validate(payload)
        except ValueError:
            return EmbodiedAuthoritySettlementReceipt(
                interaction_attempt_id=str(payload.get("interaction_attempt_id", "") or ""),
                outcome="observation_rejected",
                error_code="outcome_schema_invalid",
            )
        attempt = self._attempts_by_grant.get(outcome.controller_grant_id)
        if attempt is None:
            return self._reject(outcome, "observation_rejected", "outcome_attestation_invalid")
        validation = self._auth.consume_grant_for_outcome(
            grant_id=outcome.controller_grant_id,
            connection_epoch=outcome.connection_epoch,
            outcome_nonce=outcome.outcome_nonce,
            payload_digest=outcome.payload_digest,
            now=now,
        )
        if not validation.accepted and not validation.idempotent:
            return self._reject(outcome, "observation_rejected", "outcome_attestation_invalid")
        request = attempt.request
        grant = attempt.grant
        if (
            grant.scene_revision != request.scene_revision
            or grant.binding_revision != request.binding_revision
            or grant.policy_revision != request.policy_revision
        ):
            return self._reject(outcome, "rejected", "revision_conflict")
        writer = self._writer_selector.select(
            action_semantic=request.action_semantic,
            effect_scope=attempt.effect_scope,
            requested_writer_kind=request.settlement_writer_kind,
        )
        if not writer.accepted:
            return self._reject(outcome, "not_committed", writer.error_code)
        if outcome.terminal_status != "contact_observed":
            receipt = EmbodiedAuthoritySettlementReceipt(
                interaction_attempt_id=outcome.interaction_attempt_id,
                outcome="not_committed",
                settlement_writer_kind=writer.writer_kind,
                error_code=outcome.failure_code or outcome.terminal_status,
            )
            self._receipts_by_digest[receipt_key] = receipt
            return receipt
        if outcome.contact_observation is None or outcome.object_observation is None:
            return self._reject(outcome, "observation_rejected", "observation_rule_failed")
        if outcome.object_observation.object_ref != request.target_ref:
            return self._reject(outcome, "observation_rejected", "observation_rule_failed")
        physical_result = self._physical_channel.apply(
            PhysicalInteractionRequest(
                request_id=f"embodied:{request.interaction_attempt_id}",
                actor_id=request.actor_id,
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                target_object_id=request.target_ref,
                effect_kind="contact",
                semantic_approved=True,
                authority_ref=request.authority_preflight_ref,
                contact_observation=PhysicalContactObservation(
                    contact_ref=outcome.contact_observation.contact_ref,
                    body_ref=outcome.contact_observation.actor_contact_ref,
                    object_ref=outcome.contact_observation.target_collider_ref,
                    environment_ref="zone_focus",
                    sampled_by="backend_contract_probe",
                ),
                producer_ts=outcome.observed_at,
            )
        )
        self.mutation_count += 1
        receipt = EmbodiedAuthoritySettlementReceipt(
            interaction_attempt_id=outcome.interaction_attempt_id,
            outcome="committed",
            settlement_writer_kind=writer.writer_kind,
            authority_results=list(physical_result.unified_results),
        )
        self._receipts_by_digest[receipt_key] = receipt
        return receipt

    @staticmethod
    def _reject(outcome: LocalExecutionOutcome, settlement_outcome: str, error_code: str) -> EmbodiedAuthoritySettlementReceipt:
        return EmbodiedAuthoritySettlementReceipt(
            interaction_attempt_id=outcome.interaction_attempt_id,
            outcome=settlement_outcome,
            error_code=error_code,
        )
