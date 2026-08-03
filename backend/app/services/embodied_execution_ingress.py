from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.embodied_interaction import LocalExecutionOutcome, RealizationRoute
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService


class EmbodiedIngressResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    route: str = "embodied_execution_ingress"
    message_type: str = ""
    error_code: str = ""
    idempotent: bool = False
    accepted_payload: dict[str, object] = Field(default_factory=dict)
    outbound: list[dict[str, object]] = Field(default_factory=list)


class RouteGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    route: RealizationRoute | None = None
    error_code: str = ""


class EmbodiedExecutionIngress:
    ALLOWED_INBOUND_TYPES = {
        "embodied_controller_bind",
        "embodied_phase_event",
        "embodied_local_outcome",
        "embodied_resync_request",
    }

    def __init__(self, *, auth_service: EmbodiedControllerAuthService) -> None:
        self._auth = auth_service
        self._phase_sequences: dict[str, dict[int, str]] = {}
        self._terminal_results: dict[str, EmbodiedIngressResult] = {}

    def handle_phase_event(self, payload: dict[str, object]) -> EmbodiedIngressResult:
        grant_id = str(payload.get("grant_id", "") or "")
        connection_epoch = int(payload.get("connection_epoch", 0) or 0)
        source_sequence = int(payload.get("source_sequence", 0) or 0)
        payload_digest = str(payload.get("payload_digest", "") or "")
        validation = self._auth.validate_grant_for_phase(grant_id=grant_id, connection_epoch=connection_epoch)
        if not validation.accepted:
            return EmbodiedIngressResult(accepted=False, message_type="embodied_phase_event", error_code=validation.error_code)
        if source_sequence < 1:
            return EmbodiedIngressResult(accepted=False, message_type="embodied_phase_event", error_code="source_sequence_invalid")
        sequence_map = self._phase_sequences.setdefault(grant_id, {})
        existing_digest = sequence_map.get(source_sequence)
        if existing_digest is not None:
            if existing_digest == payload_digest:
                return EmbodiedIngressResult(
                    accepted=True,
                    message_type="embodied_phase_event",
                    idempotent=True,
                    accepted_payload=dict(payload),
                    outbound=[self._ack("embodied_phase_event", True, "embodied_execution_ingress")],
                )
            return EmbodiedIngressResult(accepted=False, message_type="embodied_phase_event", error_code="source_sequence_digest_mismatch")
        expected = max(sequence_map.keys(), default=0) + 1
        if source_sequence != expected:
            return EmbodiedIngressResult(accepted=False, message_type="embodied_phase_event", error_code="source_sequence_gap")
        sequence_map[source_sequence] = payload_digest
        return EmbodiedIngressResult(
            accepted=True,
            message_type="embodied_phase_event",
            accepted_payload=dict(payload),
            outbound=[self._ack("embodied_phase_event", True, "embodied_execution_ingress")],
        )

    def handle_local_outcome(self, payload: dict[str, object], *, now: int) -> EmbodiedIngressResult:
        grant_id = str(payload.get("controller_grant_id", "") or "")
        terminal_key = f"{grant_id}:{payload.get('payload_digest', '')}:{payload.get('outcome_nonce', '')}"
        if terminal_key in self._terminal_results:
            stored = self._terminal_results[terminal_key]
            return stored.model_copy(update={"idempotent": True})
        outcome = LocalExecutionOutcome.model_validate(payload)
        validation = self._auth.consume_grant_for_outcome(
            grant_id=outcome.controller_grant_id,
            connection_epoch=outcome.connection_epoch,
            outcome_nonce=outcome.outcome_nonce,
            payload_digest=outcome.payload_digest,
            now=now,
        )
        if not validation.accepted:
            return EmbodiedIngressResult(accepted=False, message_type="embodied_local_outcome", error_code=validation.error_code)
        result = EmbodiedIngressResult(
            accepted=True,
            message_type="embodied_local_outcome",
            accepted_payload=outcome.model_dump(mode="json"),
            outbound=[
                self._ack("embodied_local_outcome", True, "embodied_execution_ingress"),
                {
                    "message_type": "embodied_settlement_result",
                    "payload": {
                        "interaction_attempt_id": outcome.interaction_attempt_id,
                        "outcome": "not_committed",
                        "settlement_status": "attested_pending_authority_settlement",
                        "causation_id": outcome.causation_id,
                        "correlation_id": outcome.correlation_id,
                    },
                },
            ],
        )
        self._terminal_results[terminal_key] = result
        return result

    @staticmethod
    def protocol_error(source_type: str, error_code: str) -> list[dict[str, object]]:
        return [EmbodiedExecutionIngress._ack(source_type, False, "embodied_execution_ingress", error_code=error_code)]

    @staticmethod
    def _ack(source_type: str, accepted: bool, route: str, *, error_code: str = "") -> dict[str, object]:
        payload: dict[str, object] = {
            "accepted": accepted,
            "source_type": source_type,
            "route": route,
        }
        if error_code:
            payload["error_code"] = error_code
        return {"message_type": "ack", "payload": payload}


class EmbodiedRealizationRouteGate:
    def __init__(self) -> None:
        self._active_attempt_routes: dict[str, RealizationRoute] = {}
        self.embodied_controller_enabled = True

    def start_attempt(self, interaction_attempt_id: str, route: RealizationRoute) -> RouteGateResult:
        existing = self._active_attempt_routes.get(interaction_attempt_id)
        if existing is not None:
            if existing == route:
                return RouteGateResult(accepted=True, route=route)
            return RouteGateResult(accepted=False, route=existing, error_code="realization_route_already_selected")
        if route == "embodied_controller_v1" and not self.embodied_controller_enabled:
            return RouteGateResult(accepted=False, error_code="embodied_controller_route_disabled")
        self._active_attempt_routes[interaction_attempt_id] = route
        return RouteGateResult(accepted=True, route=route)

    def disable_embodied_controller_route(self, reason: str) -> list[dict[str, object]]:
        self.embodied_controller_enabled = False
        cancellations: list[dict[str, object]] = []
        for attempt_id, route in list(self._active_attempt_routes.items()):
            if route != "embodied_controller_v1":
                continue
            cancellations.append(
                {
                    "interaction_attempt_id": attempt_id,
                    "directive": "cancel_and_recover",
                    "reason": reason,
                }
            )
            del self._active_attempt_routes[attempt_id]
        return cancellations
