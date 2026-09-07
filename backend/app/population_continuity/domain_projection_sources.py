from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.models.authority_event import AuthorityEvent
from app.population_continuity.siming_contracts import PopulationProjection


_EVIDENCE_EVENT = "gameplay.construction_production.work_completion_evidence_recorded"
_ADMITTED_SCOPES = frozenset({"organization:summary", "public"})


def _payload(value: Mapping[str, object]) -> Mapping[str, object]:
    nested = value.get("payload")
    return nested if isinstance(nested, Mapping) else value


def _revision(event: object, payload: Mapping[str, object]) -> int:
    value = payload.get("stream_revision", payload.get("source_evidence_revision"))
    value = getattr(event, "stream_revision", value)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def production_work_population_projections(
    *,
    committed_events: tuple[AuthorityEvent, ...],
    organization_projection: Mapping[str, object],
    scope: str,
) -> tuple[PopulationProjection, ...]:
    """Project committed production evidence into a scoped population candidate."""
    if scope not in _ADMITTED_SCOPES:
        return ()
    organization = _payload(organization_projection)
    organization_scope = str(
        organization.get("visibility_scope")
        or organization.get("scope")
        or organization_projection.get("visibility_scope", "")
    )
    if organization_scope not in _ADMITTED_SCOPES or organization_scope != scope:
        return ()
    organization_ref = str(organization.get("organization_ref") or "")
    revision_vector = organization.get("source_revision_vector") or organization_projection.get("revision_vector")
    if not organization_ref.startswith("org:") or not isinstance(revision_vector, Mapping):
        return ()
    organization_stream = f"gameplay:organization:{organization_ref}"
    organization_revision = revision_vector.get(organization_stream)
    if not isinstance(organization_revision, int) or isinstance(organization_revision, bool) or organization_revision < 0:
        return ()
    schedule_event_id = str(organization.get("schedule_event_id") or "")
    schedule_revision = organization.get("schedule_event_revision")
    if not schedule_event_id or not isinstance(schedule_revision, int) or isinstance(schedule_revision, bool) or schedule_revision < 1:
        return ()
    schedule_rows = organization.get("schedules") or organization.get("schedule") or ()
    if isinstance(schedule_rows, Mapping):
        schedule_rows = (schedule_rows,)
    if not isinstance(schedule_rows, (tuple, list)):
        return ()
    projections: list[PopulationProjection] = []
    for event in committed_events:
        if getattr(event, "event_type", "") != _EVIDENCE_EVENT:
            continue
        evidence = _payload(getattr(event, "payload", {}))
        if evidence.get("committed") is False or evidence.get("evidence_kind") != "production-completed" or evidence.get("outcome") != "completed" or evidence.get("verification_state") != "verified":
            continue
        evidence_revision = _revision(event, evidence)
        source_stream = str(evidence.get("stream_ref") or getattr(event, "stream_id", ""))
        actor_ref = str(evidence.get("actor_ref") or "")
        assignment_ref = str(evidence.get("assignment_ref") or "")
        work_order_ref = str(evidence.get("work_order_ref") or "")
        observed_at = str(evidence.get("observed_at") or "")
        if not source_stream or evidence_revision < 1 or not actor_ref.startswith("character:") or not assignment_ref or not work_order_ref:
            continue
        try:
            datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        matching_schedule = False
        for row in schedule_rows:
            if not isinstance(row, Mapping):
                continue
            if (
                str(row.get("recipient_ref") or row.get("actor_ref") or "") == actor_ref
                and str(row.get("assignment_ref") or "") == assignment_ref
                and str(row.get("work_order_ref") or "") == work_order_ref
            ):
                matching_schedule = True
                break
        if not matching_schedule:
            continue
        event_id = str(getattr(event, "event_id", ""))
        if not event_id:
            continue
        idempotency_key = f"organization:production-work-contribution:{organization_ref}:{event_id}:{evidence_revision}:{schedule_event_id}:{schedule_revision}:v1"
        payload: dict[str, Any] = {
            "candidate_kind": "organization_production_work_contribution",
            "behavior_kind": "organization_production_work_contribution",
            "capability_id": "population:organization-production-work-contribution:v1",
            "intent_kind": "organization_production_work_contribution",
            "actor_ref": actor_ref,
            "organization_ref": organization_ref,
            "source_evidence_event_id": event_id,
            "source_stream_ref": source_stream,
            "source_evidence_revision": evidence_revision,
            "organization_stream_ref": organization_stream,
            "organization_stream_revision": organization_revision,
            "schedule_event_id": schedule_event_id,
            "schedule_event_revision": schedule_revision,
            "assignment_ref": assignment_ref,
            "work_order_ref": work_order_ref,
            "idempotency_key": idempotency_key,
            "source_event_refs": (event_id,),
            "evidence_refs": (str(evidence.get("evidence_ref") or event_id),),
            "source_domain": "production",
            "objective_risk": "low",
            "unresolved_owner_consequence": 1.0,
        }
        projections.append(
            PopulationProjection(
                ref=f"projection:organization-production-work-contribution:{event_id}",
                scope=scope,
                revision_vector={source_stream: evidence_revision, organization_stream: organization_revision},
                payload=payload,
            )
        )
    return tuple(projections)


__all__ = ["production_work_population_projections"]
