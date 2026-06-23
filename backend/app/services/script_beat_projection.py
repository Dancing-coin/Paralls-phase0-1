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
            actor_summaries=[
                {
                    "actor_id": event.actor_id,
                    "stage": event.stage,
                    "summary": event.summary,
                    "focus_target": event.focus_target,
                    "intent_label": event.intent_label,
                    "detail": dict(event.detail),
                }
                for event in actor_events
            ],
            siming_summaries=[
                {
                    "stage": event.stage,
                    "summary": event.summary,
                    "selected_path": event.selected_path,
                    "intervention_band": event.intervention_band,
                    "target_ref": event.target_ref,
                    "reason_summary": event.reason_summary,
                    "downstream_status": event.downstream_status,
                    "no_action_reason": event.no_action_reason,
                }
                for event in siming_events
            ],
            world_summaries=[
                {
                    "actor_id": event.actor_id,
                    "target_ref": event.target_ref,
                    "request_type": event.request_type,
                    "settlement_status": event.settlement_status,
                    "constraint_summary": event.constraint_summary,
                    "world_change_summary": event.world_change_summary,
                    "dramatic_consequence_summary": event.dramatic_consequence_summary,
                }
                for event in world_events
            ],
            dialogue_pairs=self._build_dialogue_pairs(actor_events),
        )

    def _build_dialogue_pairs(self, actor_events: list[ActorDramaticEvent]) -> list[dict[str, object]]:
        pair_rows: dict[str, dict[str, object]] = {}
        for event in actor_events:
            if event.stage not in {"decision", "execution_request", "dialogue_writeback", "suggestion_packet"}:
                continue
            detail = dict(event.detail)
            target_ref = str(detail.get("target_actor_id", "") or event.focus_target or "")
            if not target_ref.startswith("char_"):
                continue
            pair_members = sorted([event.actor_id, target_ref])
            pair_key = "%s<->%s" % (pair_members[0], pair_members[1])
            row = pair_rows.setdefault(
                pair_key,
                {
                    "pair_key": pair_key,
                    "speaker_actor_id": pair_members[0],
                    "listener_actor_id": pair_members[1],
                    "speaker_perceived_summary": "",
                    "listener_perceived_summary": "",
                    "speaker_interpreted_summary": "",
                    "listener_interpreted_summary": "",
                    "speaker_said": "",
                    "listener_said": "",
                    "speaker_alignment_label": "alignment",
                    "listener_alignment_label": "alignment",
                    "correlation_id": event.correlation_id,
                },
            )
            role_prefix = "speaker" if event.actor_id == row["speaker_actor_id"] else "listener"
            row[f"{role_prefix}_perceived_summary"] = str(detail.get("perceived_summary", "") or event.summary)
            row[f"{role_prefix}_interpreted_summary"] = str(detail.get("interpreted_summary", "") or event.summary)
            row[f"{role_prefix}_said"] = str(detail.get("spoken_content", "") or detail.get("content", "") or event.summary)
            row[f"{role_prefix}_alignment_label"] = (
                "mismatch" if str(detail.get("alignment_label", "") or "") == "mismatch" else "alignment"
            )
        return list(pair_rows.values())
