from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from app.models.authority_event import AuthorityEvent
from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.siming_character_bridge import (
    CharacterDeliveryAuditSummary,
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


class SimingCharacterDispatchAdapter:
    def __init__(
        self,
        *,
        runtime: CharacterAgentRuntime,
        now_ts_provider: Callable[[], int] | None = None,
    ) -> None:
        self._runtime = runtime
        self._now_ts_provider = now_ts_provider or (lambda: 0)

    def dispatch(self, event: AuthorityEvent) -> SimingCharacterDispatchResult:
        if event.event_type not in SUPPORTED_SIMING_EVENT_TYPES:
            return SimingCharacterDispatchResult()

        message_id = str(event.payload.get("message_id", "") or event.event_id)
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
                presentation_hint=self._optional_str(event.payload.get("presentation_hint")),
                target_actor_id=actor_id,
                target_object_id=self._optional_str(event.payload.get("target_object_id")),
                target_environment_id=self._optional_str(event.payload.get("target_environment_id")),
            )
            result.delivery_inputs.append(delivery_input)
            result.commands_by_actor[actor_id] = self._runtime.ingest_siming_output(delivery_input)

        return result

    def _is_expired(self, event: AuthorityEvent) -> bool:
        if event.ttl is None:
            return False
        return self._now_ts_provider() > event.producer_ts + event.ttl

    def _optional_str(self, value: object) -> str | None:
        rendered = str(value or "").strip()
        return rendered or None
