from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.embodied_interaction import (
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
        auth_service: EmbodiedControllerAuthService,
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
        self.mutation_count = 0

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
