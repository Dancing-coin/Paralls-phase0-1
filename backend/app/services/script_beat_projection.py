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
        siming_summaries = [
            {
                "stage": event.stage,
                "summary": event.summary,
                "selected_path": event.selected_path,
                "intervention_band": event.intervention_band,
                "target_ref": event.target_ref,
                "causation_id": event.causation_id,
                "correlation_id": event.correlation_id,
                "reason_summary": event.reason_summary,
                "downstream_status": event.downstream_status,
                "no_action_reason": event.no_action_reason,
            }
            for event in siming_events
        ]
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
            siming_summaries=siming_summaries,
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
            dialogue_pairs=self._build_dialogue_pairs(actor_events, siming_summaries),
        )

    def _build_dialogue_pairs(
        self,
        actor_events: list[ActorDramaticEvent],
        siming_summaries: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        pair_rows: dict[str, dict[str, object]] = {}
        siming_delivery_evidence: list[dict[str, str]] = []
        for event in actor_events:
            siming_delivery = self._build_siming_delivery_evidence(event)
            if siming_delivery is not None:
                siming_delivery_evidence.append(siming_delivery)
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
        for row in pair_rows.values():
            siming_context = self._build_pair_siming_pressure_context(row, siming_summaries, siming_delivery_evidence)
            row["siming_pressure_context"] = siming_context
        return list(pair_rows.values())

    def _build_pair_siming_pressure_context(
        self,
        row: dict[str, object],
        siming_summaries: list[dict[str, object]],
        siming_delivery_evidence: list[dict[str, str]],
    ) -> str:
        speaker_actor_id = str(row.get("speaker_actor_id", "") or "")
        listener_actor_id = str(row.get("listener_actor_id", "") or "")
        pair_members = {speaker_actor_id, listener_actor_id}
        relevant_causation_ids = {
            evidence["causation_id"]
            for evidence in siming_delivery_evidence
            if evidence["delivered_actor_id"] in pair_members and evidence["causation_id"]
        }
        relevant_correlation_ids = {
            evidence["correlation_id"]
            for evidence in siming_delivery_evidence
            if evidence["delivered_actor_id"] in pair_members and evidence["correlation_id"]
        }
        context_rows: list[str] = []
        for summary in siming_summaries:
            target_ref = str(summary.get("target_ref", "") or "").strip()
            if (
                target_ref
                and target_ref not in pair_members
                and not self._summary_matches_explicit_delivery(
                    summary,
                    relevant_causation_ids,
                    relevant_correlation_ids,
                )
            ):
                continue
            summary_text = str(summary.get("summary", "") or "").strip()
            reason_text = str(summary.get("reason_summary", "") or "").strip()
            if not summary_text and not reason_text:
                continue
            if target_ref:
                context_text = f"司命关注 {target_ref}：{summary_text or reason_text}"
            else:
                context_text = f"司命上下文：{summary_text or reason_text}"
            if reason_text and reason_text != summary_text:
                context_text += f"（原因：{reason_text}）"
            context_rows.append(context_text)
        return "；".join(context_rows)

    def _build_siming_delivery_evidence(self, event: ActorDramaticEvent) -> dict[str, str] | None:
        detail = dict(event.detail)
        if str(detail.get("input_type", "") or "").strip() != "siming_high_level_message":
            return None
        delivered_actor_id = str(detail.get("target_actor_id", "") or event.actor_id or "").strip()
        if not delivered_actor_id:
            return None
        return {
            "delivered_actor_id": delivered_actor_id,
            "causation_id": str(detail.get("causation_id", "") or event.causation_id or "").strip(),
            "correlation_id": str(detail.get("correlation_id", "") or event.correlation_id or "").strip(),
        }

    def _summary_matches_explicit_delivery(
        self,
        summary: dict[str, object],
        relevant_causation_ids: set[str],
        relevant_correlation_ids: set[str],
    ) -> bool:
        causation_id = str(summary.get("causation_id", "") or "").strip()
        correlation_id = str(summary.get("correlation_id", "") or "").strip()
        return (
            bool(causation_id and causation_id in relevant_causation_ids)
            or bool(correlation_id and correlation_id in relevant_correlation_ids)
        )
