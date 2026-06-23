from __future__ import annotations

from dataclasses import dataclass, field

from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.siming_character_bridge import CharacterDeliveryAuditSummary


@dataclass(slots=True)
class CharacterOutcomePublishResult:
    role_events: list[dict[str, object]] = field(default_factory=list)
    linked_authority_results: list[dict[str, object]] = field(default_factory=list)
    restricted_audit_records: list[dict[str, object]] = field(default_factory=list)


class CharacterOutcomePublisher:
    def publish_commands(
        self,
        *,
        actor_id: str,
        commands: list[CharacterGoalCommand],
    ) -> CharacterOutcomePublishResult:
        role_events: list[dict[str, object]] = []
        for command in commands:
            if command.actor_id != actor_id:
                raise ValueError("command.actor_id must match publish actor_id")
            role_events.append(self._role_event_for_command(command=command))
        return CharacterOutcomePublishResult(role_events=role_events)

    def publish_restricted_audit_summaries(
        self,
        *,
        summaries: list[CharacterDeliveryAuditSummary],
    ) -> CharacterOutcomePublishResult:
        return CharacterOutcomePublishResult(
            restricted_audit_records=[
                {
                    "record_type": "CharacterDeliveryAuditSummary",
                    "visibility": "restricted_audit",
                    "message_id": summary.message_id,
                    "delivery_id": summary.delivery_id,
                    "actor_id": summary.actor_id,
                    "status": summary.status,
                    "producer_ts": summary.producer_ts,
                    "causation_id": summary.causation_id,
                    "correlation_id": summary.correlation_id,
                }
                for summary in summaries
            ]
        )

    def link_authority_result(
        self,
        *,
        actor_id: str,
        delivery_id: str,
        authority_event_type: str,
        authority_event_id: str,
        correlation_id: str,
        causation_id: str,
    ) -> dict[str, object]:
        return {
            "link_type": "authority_result_link",
            "link_mode": "reference_only",
            "actor_id": actor_id,
            "delivery_id": delivery_id,
            "authority_event_type": authority_event_type,
            "authority_event_id": authority_event_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
        }

    def _role_event_for_command(
        self,
        *,
        command: CharacterGoalCommand,
    ) -> dict[str, object]:
        if command.command_type == "speak":
            return {
                "event_type": "SpeechActPublished",
                "actor_id": command.actor_id,
                "producer_ts": command.producer_ts,
                "ttl_ms": command.ttl_ms,
                "causation_id": command.causation_id,
                "correlation_id": command.correlation_id,
                "payload": {
                    "dialogue_text": command.dialogue_text or "",
                    "command_type": command.command_type,
                    "role_state_hint": command.role_state_hint,
                    "physiology_hint": command.physiology_hint,
                    "execution_payload": command.execution_payload,
                },
            }
        return {
            "event_type": "ActionRequestIssued",
            "actor_id": command.actor_id,
            "producer_ts": command.producer_ts,
            "ttl_ms": command.ttl_ms,
            "causation_id": command.causation_id,
            "correlation_id": command.correlation_id,
            "payload": {
                "command_type": command.command_type,
                "target_actor_id": command.target_actor_id,
                "target_object_id": command.target_object_id,
                "target_environment_id": command.target_environment_id,
                "target_position": command.target_position,
                "role_state_hint": command.role_state_hint,
                "physiology_hint": command.physiology_hint,
                "execution_payload": command.execution_payload,
            },
        }
