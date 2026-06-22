from __future__ import annotations

from app.models.authority_event import AuthorityEvent
from app.models.observatory import SimingDramaticEvent, SimingDramaticState


class SimingDebugProjection:
    def project_snapshot(
        self,
        *,
        source_event: AuthorityEvent,
        fairness_summary: str,
        intervention_candidate: str,
        intervention_decision: str,
        selected_path: str,
        intervention_band: str,
        target_ref: str,
        reason_summary: str,
        downstream_status: str,
        no_action_reason: str,
    ) -> SimingDramaticState:
        return SimingDramaticState(
            producer_ts=source_event.producer_ts,
            causation_id=source_event.event_id,
            correlation_id=source_event.correlation_id,
            participants=self._participants(source_event, target_ref),
            fairness_summary=fairness_summary,
            intervention_candidate=intervention_candidate,
            intervention_decision=intervention_decision,
            selected_path=selected_path,
            intervention_band=intervention_band,
            target_ref=target_ref,
            reason_summary=reason_summary,
            downstream_status=downstream_status,
            no_action_reason=no_action_reason,
        )

    def project_event(
        self,
        *,
        source_event: AuthorityEvent,
        stage: str,
        summary: str,
        selected_path: str,
        intervention_band: str,
        target_ref: str,
        reason_summary: str,
        downstream_status: str,
        no_action_reason: str,
    ) -> SimingDramaticEvent:
        return SimingDramaticEvent(
            producer_ts=source_event.producer_ts,
            causation_id=source_event.event_id,
            correlation_id=source_event.correlation_id,
            participants=self._participants(source_event, target_ref),
            stage=stage,
            summary=summary,
            selected_path=selected_path,
            intervention_band=intervention_band,
            target_ref=target_ref,
            reason_summary=reason_summary,
            downstream_status=downstream_status,
            no_action_reason=no_action_reason,
        )

    def _participants(self, source_event: AuthorityEvent, target_ref: str) -> list[str]:
        participants: list[str] = []
        if source_event.source.actor_id:
            participants.append(source_event.source.actor_id)
        if target_ref:
            participants.append(target_ref)
        return participants
