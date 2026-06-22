from __future__ import annotations

from app.models.observatory import ActorDramaticEvent, ScriptBeat, SimingDramaticEvent, WorldOutcomeEvent


class ScriptBeatProjection:
    def project(
        self,
        actor_events: list[ActorDramaticEvent],
        siming_events: list[SimingDramaticEvent],
        world_events: list[WorldOutcomeEvent],
    ) -> ScriptBeat:
        first = actor_events[0] if actor_events else siming_events[0] if siming_events else world_events[0]
        correlation_id = first.correlation_id
        causation_id = first.causation_id
        producer_ts = max(
            [event.producer_ts for event in actor_events + siming_events + world_events] or [first.producer_ts]
        )
        participants: list[str] = []
        for event in actor_events + siming_events + world_events:
            for participant in event.participants:
                if participant not in participants:
                    participants.append(participant)
        dramatic_pieces = [event.summary for event in actor_events] + [
            event.summary for event in siming_events
        ] + [event.dramatic_consequence_summary for event in world_events]
        return ScriptBeat(
            beat_id=f"beat-{correlation_id}-1",
            producer_ts=producer_ts,
            causation_id=causation_id,
            correlation_id=correlation_id,
            participants=participants,
            dramatic_summary=" | ".join(filter(None, dramatic_pieces)),
            actor_event_refs=[event.event_ref for event in actor_events],
            siming_event_refs=[event.event_ref for event in siming_events],
            world_event_refs=[event.event_ref for event in world_events],
        )
