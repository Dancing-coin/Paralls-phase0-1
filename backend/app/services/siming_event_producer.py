from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_catalyst import validate_siming_authority_event
from app.models.siming_event import SimingOutput
from app.services.authority_event_bus import AuthorityEventBusPort


class SimingEventProducer:
    def __init__(self, bus: AuthorityEventBusPort | None = None, *, authority_event_bus: AuthorityEventBusPort | None = None) -> None:
        self._bus = bus or authority_event_bus
        if self._bus is None:
            raise ValueError("SimingEventProducer requires an authority event bus")

    def publish_outputs(self, outputs: list[SimingOutput]) -> list[AuthorityEvent]:
        published_events: list[AuthorityEvent] = []
        for output in outputs:
            event = self._to_authority_event(output)
            validate_siming_authority_event(event)
            self._bus.publish(event)
            published_events.append(event)
        return published_events

    def publish_siming_event(
        self,
        *,
        event_type: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_ids: list[str],
        payload: dict[str, object],
        producer_ts: int = 0,
        priority: str = "p1",
        ttl: int | None = None,
        durability: str = "replayable",
        causation_id: str = "siming:manual",
        correlation_id: str = "siming:manual",
    ) -> AuthorityEvent:
        event = AuthorityEvent(
            event_id=f"{event_type}:{producer_ts}:{causation_id}",
            event_type=event_type,
            producer_ts=producer_ts,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            source=AuthorityEventSource(layer="L2", system="siming.dispatcher", actor_id=None),
            routing=AuthorityEventRouting(
                audience_mode="targeted",
                routing_mode="event_type",
                target_ids=target_ids,
            ),
            priority=priority,  # type: ignore[arg-type]
            ttl=ttl,
            durability=durability,  # type: ignore[arg-type]
            causation_id=causation_id,
            correlation_id=correlation_id,
            payload=dict(payload),
        )
        validate_siming_authority_event(event)
        self._bus.publish(event)
        return event

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
        if "physical_success" in output.payload:
            raise ValueError("Siming outputs must not claim physical_success")

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
            return ["frontend_projector"]
        if output.selected_path == "l3_highlight_path":
            return ["frontend_projector"]
        if output.selected_path == "character_input_path":
            return [str(output.payload.get("target_actor_id", "") or "").strip(), "frontend_projector"]
        return ["audit"]
