from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from app.models.authority_event import AuthorityEvent
from app.character_agent.models.memory_consistency import MemoryCorrectionRequest, MemoryCorrectionReceipt
from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.siming_catalyst import SimingCatalystInput
from app.models.siming_character_bridge import (
    CharacterDeliveryAuditSummary,
    CharacterSemanticIntentProposal,
    SimingCharacterCompatibilityInput,
)
from app.services.character_agent_runtime import CharacterAgentRuntime


SUPPORTED_SIMING_EVENT_TYPES = {
    "siming.impulse",
    "siming.opportunity",
    "siming.fact_reveal",
}


@dataclass(slots=True)
class SimingCharacterDispatchResult:
    delivery_inputs: list[SimingCharacterCompatibilityInput] = field(default_factory=list)
    audit_summaries: list[CharacterDeliveryAuditSummary] = field(default_factory=list)
    commands_by_actor: dict[str, list[CharacterGoalCommand]] = field(default_factory=dict)
    intent_proposals_by_actor: dict[str, CharacterSemanticIntentProposal] = field(default_factory=dict)


class SimingCharacterDispatchAdapter:
    def __init__(
        self,
        *,
        runtime: CharacterAgentRuntime,
        now_ts_provider: Callable[[], int] | None = None,
        memory_edit_principal_ref: str = "",
    ) -> None:
        self._runtime = runtime
        self._now_ts_provider = now_ts_provider or (lambda: 0)
        self._memory_edit_principal_ref = memory_edit_principal_ref

    def dispatch_memory_correction(self, request: MemoryCorrectionRequest) -> MemoryCorrectionReceipt:
        """Edit 身份由服务装配绑定，不从 catalyst 或请求载荷获取。"""
        return self._runtime.apply_memory_correction(request, principal_ref=self._memory_edit_principal_ref)

    def dispatch(self, event: AuthorityEvent) -> SimingCharacterDispatchResult:
        result = self.prepare_deliveries(event)
        for delivery in result.delivery_inputs:
            result.commands_by_actor[delivery.actor_id] = self._runtime.ingest_siming_output(delivery)
        return result

    def prepare_deliveries(self, event: AuthorityEvent) -> SimingCharacterDispatchResult:
        """只构造原过滤结果与稳定 delivery 身份；不进入 Character 认知。"""
        if event.event_type not in SUPPORTED_SIMING_EVENT_TYPES:
            return SimingCharacterDispatchResult()

        message_id = str(event.payload.get("message_id", "") or event.event_id)
        try:
            catalyst = SimingCatalystInput.from_authority_event(event)
        except ValueError:
            return SimingCharacterDispatchResult(
                audit_summaries=[
                    CharacterDeliveryAuditSummary(
                        message_id=message_id,
                        delivery_id=f"delivery:{message_id}:rejected",
                        actor_id=str(event.payload.get("target_actor_id", "") or event.routing.target_ids[0] if event.routing.target_ids else "*"),
                        status="rejected_by_filter",
                        producer_ts=event.producer_ts,
                        causation_id=event.causation_id,
                        correlation_id=event.correlation_id,
                    )
                ]
            )
        if self._is_expired(event):
            return SimingCharacterDispatchResult(
                audit_summaries=[
                    CharacterDeliveryAuditSummary(
                        message_id=message_id,
                        delivery_id=f"delivery:{message_id}:expired",
                        actor_id="*",
                        status="expired",
                        producer_ts=event.producer_ts,
                        causation_id=event.causation_id,
                        correlation_id=event.correlation_id,
                    )
                ]
            )

        result = SimingCharacterDispatchResult()
        seen_actor_ids: set[str] = set()
        for actor_id in event.routing.target_ids:
            if actor_id == "frontend_projector":
                continue
            if actor_id in seen_actor_ids:
                continue
            seen_actor_ids.add(actor_id)
            delivery_index = len(seen_actor_ids)
            delivery_id = f"delivery:{message_id}:{actor_id}:{delivery_index}"
            if not self._runtime.supports_actor(actor_id):
                result.audit_summaries.append(
                    CharacterDeliveryAuditSummary(
                        message_id=message_id,
                        delivery_id=delivery_id,
                        actor_id=actor_id,
                        status="target_unavailable",
                        producer_ts=event.producer_ts,
                        causation_id=event.causation_id,
                        correlation_id=event.correlation_id,
                    )
                )
                continue

            delivery_input = SimingCharacterCompatibilityInput(
                message_id=message_id,
                delivery_id=delivery_id,
                actor_id=actor_id,
                input_type="siming_high_level_message",
                band=cast("str", event.event_type.removeprefix("siming.")),
                producer_ts=event.producer_ts,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
                presentation_hint=catalyst.presentation_hint,
                pressure_hint=catalyst.pressure_hint,
                salience_boost=catalyst.salience_boost,
                reason_scope=catalyst.reason_scope,
                target_actor_id=actor_id,
                target_object_id=catalyst.target_object_id,
                target_environment_id=catalyst.target_environment_id,
                intent_tags=list(event.payload.get("intent_tags", []) or []),
                context_tags=list(event.payload.get("context_tags", []) or []),
                semantic_action_id=(
                    str(event.payload.get("semantic_action_id", "") or "") or None
                ),
                claims=list(event.payload.get("claims", []) or []),
                locomotion_relation=str(event.payload.get("locomotion_relation", "coexist") or "coexist"),
                presentation_cues=list(event.payload.get("presentation_cues", []) or []),
                reason_codes=list(event.payload.get("reason_codes", []) or []),
            )
            result.delivery_inputs.append(delivery_input)
            result.intent_proposals_by_actor[actor_id] = self._build_intent_proposal(delivery_input)

        return result

    @staticmethod
    def _build_intent_proposal(
        delivery_input: SimingCharacterCompatibilityInput,
    ) -> CharacterSemanticIntentProposal:
        target_ref = (
            delivery_input.target_actor_id
            or delivery_input.target_object_id
            or delivery_input.target_environment_id
        )
        cues = list(delivery_input.presentation_cues)
        if delivery_input.presentation_hint and "presentation:siming_hint" not in cues:
            cues.append("presentation:siming_hint")
        context_tags = list(delivery_input.context_tags)
        if delivery_input.pressure_hint:
            context_tags.append("constraint:siming_pressure")
        return CharacterSemanticIntentProposal(
            actor_ref=f"character:{delivery_input.actor_id}",
            source_id="siming",
            intent_tags=list(delivery_input.intent_tags),
            context_tags=list(dict.fromkeys(context_tags)),
            semantic_action_id=delivery_input.semantic_action_id,
            target_ref=target_ref,
            claims=list(delivery_input.claims),
            locomotion_relation=delivery_input.locomotion_relation,
            presentation_cues=cues,
            reason_codes=list(delivery_input.reason_codes)
            + ([delivery_input.reason_scope] if delivery_input.reason_scope else []),
            source="siming_catalyst",
            confidence=delivery_input.salience_boost,
            provenance={"message_id": delivery_input.message_id, "delivery_id": delivery_input.delivery_id},
            privacy_scope=f"actor_private:{delivery_input.actor_id}",
            authority_scope="world:default",
            causation_id=delivery_input.causation_id,
            correlation_id=delivery_input.correlation_id,
        )

    def _is_expired(self, event: AuthorityEvent) -> bool:
        if event.ttl is None:
            return False
        return self._now_ts_provider() > event.producer_ts + event.ttl
