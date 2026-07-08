from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingOutput
from app.services.authority_event_bus import AuthorityEventBusPort


FORBIDDEN_CATALYST_PAYLOAD_FIELDS = {
    "actor_control_frames",
    "action_request_bundle",
    "character_agent_execution",
    "physical_success",
    "world_mutation",
    "private_memory_patch",
    "selected_intent",
    "command_type",
    "low_level_motion",
}


class SimingEventProducer:
    def __init__(self, bus: AuthorityEventBusPort) -> None:
        self._bus = bus

    def publish_outputs(self, outputs: list[SimingOutput]) -> list[AuthorityEvent]:
        published_events: list[AuthorityEvent] = []
        for output in outputs:
            event = self._to_authority_event(output)
            self._bus.publish(event)
            published_events.append(event)
        return published_events

    def _to_authority_event(self, output: SimingOutput) -> AuthorityEvent:
        event_type = self._event_type_for(output)
        if event_type == "siming.visual_observability_request" and not output.payload.get("established_fact_id"):
            raise ValueError("visual observability requests require established_fact_id")
        if output.selected_path == "character_input_path":
            target_actor_id = str(output.payload.get("target_actor_id", "") or "").strip()
            if target_actor_id == "":
                raise ValueError("character_input_path requires target_actor_id")
        forbidden_event_type = output.payload.get("event_type")
        if forbidden_event_type == "siming.dispatch_requested":
            raise ValueError("forbidden Siming event family: siming.dispatch_requested")
        forbidden_payload_fields = self._forbidden_payload_fields(output.payload)
        if forbidden_payload_fields:
            raise ValueError(f"forbidden Siming payload field(s): {', '.join(forbidden_payload_fields)}")

        return AuthorityEvent(
            event_id=f"siming:{output.output_type}:{output.producer_ts}:{output.causation_id}",
            event_type=event_type,
            producer_ts=output.producer_ts,
            room_id=output.room_id,
            scene_id=output.scene_id,
            zone_id=output.zone_id,
            source=AuthorityEventSource(layer="L2", system=self._source_system_for(output), actor_id=None),
            routing=AuthorityEventRouting(
                audience_mode="targeted" if output.selected_path not in (None, "no_action") else "audit",
                routing_mode="event_type",
                target_ids=self._target_ids_for(output),
            ),
            priority=output.priority,  # type: ignore[arg-type]
            ttl=output.ttl,
            durability=output.durability,  # type: ignore[arg-type]
            causation_id=output.causation_id,
            correlation_id=output.correlation_id,
            payload=dict(output.payload),
        )

    def _forbidden_payload_fields(self, value: object) -> list[str]:
        found: set[str] = set()

        def visit(current: object) -> None:
            if isinstance(current, dict):
                present = FORBIDDEN_CATALYST_PAYLOAD_FIELDS.intersection(current.keys())
                found.update(str(field) for field in present)
                for nested_value in current.values():
                    visit(nested_value)
            elif isinstance(current, list):
                for nested_value in current:
                    visit(nested_value)
            elif isinstance(current, tuple):
                for nested_value in current:
                    visit(nested_value)

        visit(value)
        return sorted(found)

    def _event_type_for(self, output: SimingOutput) -> str:
        if output.output_type == "fairness_snapshot":
            return "siming.fairness_snapshot"
        if output.output_type == "intervention_candidate":
            return "siming.intervention_candidate"
        if output.output_type == "intervention_decision":
            return "siming.intervention_decision"
        if output.output_type == "audit_record":
            return "siming.audit_recorded"
        if output.output_type == "no_action" or output.selected_path == "no_action":
            return "siming.no_action_recorded"
        if output.selected_path == "visual_fact_path":
            return "siming.visual_observability_request"
        if output.selected_path == "l3_highlight_path":
            return "siming.presentation_highlight_request"
        if output.selected_path == "environment_change_path":
            return "siming.environment_request"
        if output.selected_path == "character_input_path" and output.intervention_band == "impulse":
            return "siming.impulse"
        if output.selected_path == "character_input_path" and output.intervention_band == "opportunity":
            return "siming.opportunity"
        if output.selected_path == "character_input_path" and output.intervention_band == "fact_reveal":
            return "siming.fact_reveal"
        raise ValueError(f"unsupported Siming output mapping: {output.output_type}/{output.selected_path}/{output.intervention_band}")

    def _source_system_for(self, output: SimingOutput) -> str:
        if output.output_type in {"fairness_snapshot", "intervention_candidate", "intervention_decision"}:
            return "siming.orchestrator"
        return "siming.dispatcher"

    def _target_ids_for(self, output: SimingOutput) -> list[str]:
        if output.selected_path == "environment_change_path":
            return ["esm"]
        if output.selected_path == "visual_fact_path":
            return ["visual_fact"]
        if output.selected_path == "l3_highlight_path":
            return ["presentation"]
        if output.selected_path == "character_input_path":
            return [str(output.payload.get("target_actor_id", "") or "").strip()]
        return ["audit"]
