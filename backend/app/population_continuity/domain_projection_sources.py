from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.models.authority_event import AuthorityEvent
from app.population_continuity.siming_contracts import PopulationProjection


_EVIDENCE_EVENT = "gameplay.construction_production.work_completion_evidence_recorded"
_ADMITTED_SCOPES = frozenset({"organization:summary", "public"})
_PRODUCTION_OWNER = "actor_gameplay.organization_domain"
_PRODUCTION_ACCEPTED = "gameplay.organization.production_work_contribution_accepted"
_INVENTORY_ADMITTED_SCOPES = frozenset({"organization:summary", "public"})
_OUTPUT_CERTIFIED_EVENT = "gameplay.construction_production.production_output_certified@1"
_SOCIAL_SIGNAL_ADMITTED_SCOPES = frozenset({"public"})
_SOCIAL_SIGNAL_CAPABILITY = "population:social-population-signal:v1"
_TAX_PRESSURE_ADMITTED_SCOPES = frozenset({"public"})
_TAX_PRESSURE_CAPABILITY = "population:tax-pressure:v1"


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
        or organization_projection.get("visibility_scope")
        or organization_projection.get("scope", "")
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


def production_receipt_population_projections(
    *,
    owner_receipt: object,
    organization_projection: Mapping[str, object],
    scope: str,
) -> tuple[PopulationProjection, ...]:
    """Project one committed Production Owner receipt into the next read set."""
    if scope not in _ADMITTED_SCOPES:
        return ()
    if (
        getattr(owner_receipt, "owner_ref", "") != _PRODUCTION_OWNER
        or getattr(owner_receipt, "event_family", "") != _PRODUCTION_ACCEPTED
        or not getattr(owner_receipt, "committed", False)
        or (
            getattr(owner_receipt, "zero_write", True)
            and getattr(owner_receipt, "idempotency_status", "") != "duplicate_replayed"
        )
    ):
        return ()
    revision_vector = getattr(owner_receipt, "revision_vector", {})
    if not isinstance(revision_vector, Mapping) or not revision_vector:
        return ()
    organization = _payload(organization_projection)
    if (
        str(organization.get("scope") or organization.get("visibility_scope") or "") != scope
        or not isinstance(organization.get("source_revision_vector"), Mapping)
        or dict(organization["source_revision_vector"]) != dict(revision_vector)
    ):
        return ()
    receipt_ref = str(getattr(owner_receipt, "receipt_ref", ""))
    if not receipt_ref:
        return ()
    rows = organization.get("acceptance_rows") or organization.get("acceptances") or ()
    if isinstance(rows, Mapping):
        rows = (rows,)
    if not isinstance(rows, (tuple, list)):
        return ()
    row = next(
        (
            item
            for item in rows
            if isinstance(item, Mapping)
            and receipt_ref
            in {
                str(item.get("event_id") or ""),
                str(item.get("receipt_ref") or ""),
                str(item.get("owner_receipt_ref") or ""),
            }
        ),
        None,
    )
    if row is None:
        return ()
    actor_ref = str(row.get("recipient_ref") or row.get("actor_ref") or "")
    organization_ref = str(row.get("organization_ref") or organization.get("organization_ref") or "")
    if not actor_ref.startswith("character:") or not organization_ref.startswith("org:"):
        return ()
    payload: dict[str, Any] = {
        "candidate_kind": "organization_production_work_contribution",
        "behavior_kind": "organization_production_work_contribution",
        "capability_id": "population:organization-production-work-contribution:v1",
        "actor_ref": actor_ref,
        "organization_ref": organization_ref,
        "source_domain": "production",
        "source_owner_receipt_ref": receipt_ref,
        "source_owner_receipt_refs": (receipt_ref,),
        "source_event_refs": tuple(
            str(item)
            for item in (
                row.get("source_evidence_event_id") or row.get("source_event_refs") or receipt_ref,
            )
            if str(item)
        ),
        "evidence_refs": (receipt_ref,),
        "idempotency_key": f"population:production-receipt:{receipt_ref}:v1",
        "objective_risk": "low",
        "unresolved_owner_consequence": 0.0,
    }
    return (
        PopulationProjection(
            ref=f"projection:organization-production-receipt:{receipt_ref}",
            scope=scope,
            revision_vector=dict(revision_vector),
            payload=payload,
        ),
    )


def inventory_output_custody_population_projections(
    *,
    committed_events: tuple[AuthorityEvent, ...] = (),
    scope: str,
    certified_output_projection: Mapping[str, object] | None = None,
) -> tuple[PopulationProjection, ...]:
    """Project one committed, certified output into an Inventory Owner candidate.

    The projection intentionally carries only the certification pin. Inventory
    derives holder, container, quantity, and destination stream from its family
    binding when the Owner executes the intent.
    """
    if scope not in _INVENTORY_ADMITTED_SCOPES:
        return ()
    events: tuple[object, ...] = committed_events
    if certified_output_projection is not None:
        event_id = str(certified_output_projection.get("event_id") or "")
        event_payload = certified_output_projection.get("payload")
        if isinstance(event_payload, Mapping):
            event = type("CertifiedProjection", (), {
                "event_id": event_id,
                "event_type": certified_output_projection.get("event_type", _OUTPUT_CERTIFIED_EVENT),
                "stream_id": certified_output_projection.get("stream_id", ""),
                "stream_revision": certified_output_projection.get("stream_revision", 0),
                "payload": event_payload,
            })()
            events = (event,)
    projections: list[PopulationProjection] = []
    for event in events:
        if getattr(event, "event_type", "") != _OUTPUT_CERTIFIED_EVENT:
            continue
        payload = _payload(getattr(event, "payload", {}))
        if payload.get("family_ref") != "production_output_certification@1":
            continue
        if payload.get("visibility_policy") not in (None, "project"):
            continue
        event_id = str(getattr(event, "event_id", ""))
        stream_ref = str(payload.get("stream_ref") or getattr(event, "stream_id", ""))
        revision = _revision(event, payload)
        quantity = payload.get("quantity")
        if not event_id or not stream_ref or revision < 1 or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            continue
        certification_revision = payload.get("stream_revision", revision)
        if not isinstance(certification_revision, int) or isinstance(certification_revision, bool) or certification_revision < 1:
            certification_revision = revision
        actor_ref = str(payload.get("actor_ref") or payload.get("facility_ref") or f"production:{event_id}")
        expected_inventory_revision = payload.get("expected_inventory_stream_revision")
        projection_payload: dict[str, Any] = {
            "candidate_kind": "inventory_output_custody",
            "behavior_kind": "inventory_output_custody",
            "capability_id": "population:inventory-output-custody:v1",
            "intent_kind": "inventory_output_custody",
            "actor_ref": actor_ref,
            "source_domain": "inventory",
            "source_certification_event_id": event_id,
            "source_certification_revision": certification_revision,
            "source_stream_ref": stream_ref,
            "source_event_refs": (event_id,),
            "evidence_refs": (event_id,),
            "idempotency_key": f"population:inventory-output-custody:{event_id}:{certification_revision}:v1",
            "objective_risk": "low",
            "unresolved_owner_consequence": 1.0,
        }
        if isinstance(expected_inventory_revision, int) and not isinstance(expected_inventory_revision, bool) and expected_inventory_revision >= 0:
            projection_payload["expected_inventory_stream_revision"] = expected_inventory_revision
        projections.append(
            PopulationProjection(
                ref=f"projection:inventory-output-custody:{event_id}",
                scope=scope,
                revision_vector={stream_ref: revision},
                payload=projection_payload,
            )
        )
    return tuple(projections)


def social_population_signal_population_projections(
    *,
    population_signal_projection: Mapping[str, object] | None = None,
    signal_projection: Mapping[str, object] | None = None,
    scope: str,
) -> tuple[PopulationProjection, ...]:
    """Admit one public, revision-pinned Social signal as a population candidate."""
    if scope not in _SOCIAL_SIGNAL_ADMITTED_SCOPES:
        return ()
    source = population_signal_projection or signal_projection
    if not isinstance(source, Mapping):
        return ()
    payload = _payload(source)
    if str(payload.get("visibility_scope") or payload.get("visibility") or "") != "public":
        return ()
    source_domain = payload.get("source_domain") or payload.get("domain")
    if source_domain is not None and str(source_domain) != "social":
        return ()
    if any(
        "private" in str(key).lower()
        or "relationship" in str(key).lower()
        or "participant" in str(key).lower()
        for key in payload
    ):
        return ()
    signal_ref = str(payload.get("signal_ref") or "")
    provenance_ref = str(payload.get("provenance_ref") or "")
    source_stream_ref = str(payload.get("source_stream_ref") or payload.get("stream_ref") or "")
    source_revision_pin = payload.get("source_revision_pin")
    if (
        not signal_ref.startswith("signal:")
        or not provenance_ref
        or not source_stream_ref
        or not isinstance(source_revision_pin, int)
        or isinstance(source_revision_pin, bool)
        or source_revision_pin < 0
        or str(payload.get("materialization_state") or "") != "proposed"
    ):
        return ()
    revision_vector = payload.get("revision_vector") or {source_stream_ref: source_revision_pin}
    if not isinstance(revision_vector, Mapping) or revision_vector.get(source_stream_ref) != source_revision_pin:
        return ()
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in revision_vector.values()
    ):
        return ()
    idempotency_key = f"social:population-signal:{signal_ref}:{source_revision_pin}:v1"
    candidate_payload: dict[str, Any] = {
        "candidate_kind": "social_population_signal",
        "behavior_kind": "social_population_signal",
        "capability_id": _SOCIAL_SIGNAL_CAPABILITY,
        "intent_kind": "social_population_signal",
        "actor_ref": signal_ref,
        "signal_ref": signal_ref,
        "provenance_ref": provenance_ref,
        "source_revision_pin": source_revision_pin,
        "source_stream_ref": source_stream_ref,
        "materialization_state": "proposed",
        "visibility_scope": "public",
        "source_domain": "social",
        "idempotency_key": idempotency_key,
        "source_event_refs": tuple(str(item) for item in (payload.get("source_event_refs") or (source_stream_ref,))),
        "evidence_refs": tuple(str(item) for item in (payload.get("evidence_refs") or (provenance_ref,))),
        "objective_risk": "low",
        "unresolved_owner_consequence": 1.0,
    }
    return (
        PopulationProjection(
            ref=f"projection:social-population-signal:{signal_ref}",
            scope="public",
            revision_vector=dict(revision_vector),
            payload=candidate_payload,
        ),
    )


def tax_pressure_population_projections(
    *,
    tax_obligation_projection: Mapping[str, object] | None = None,
    scope: str,
) -> tuple[PopulationProjection, ...]:
    """Redact one due tax obligation into a report-only pressure candidate."""
    if scope not in _TAX_PRESSURE_ADMITTED_SCOPES or not isinstance(tax_obligation_projection, Mapping):
        return ()
    source = _payload(tax_obligation_projection)
    obligation_ref = str(source.get("obligation_ref") or "")
    actor_ref = str(source.get("actor_ref") or source.get("character_ref") or "")
    stream_ref = str(source.get("source_stream_ref") or source.get("stream_ref") or "")
    revision = source.get("source_revision_pin", source.get("stream_revision"))
    if (
        not obligation_ref.startswith("obligation:economy:tax:")
        or not actor_ref.startswith("character:")
        or stream_ref != "gameplay:economy"
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 1
        or str(source.get("status") or "") not in {"due", "overdue"}
    ):
        return ()
    payload: dict[str, Any] = {
        "candidate_kind": "tax_pressure",
        "behavior_kind": "tax_pressure",
        "capability_id": _TAX_PRESSURE_CAPABILITY,
        "actor_ref": actor_ref,
        "tax_pressure_ref": f"tax-pressure:{obligation_ref}:{revision}",
        "source_domain": "economy",
        "idempotency_key": f"population:tax-pressure:{obligation_ref}:{revision}:v1",
        "objective_risk": "none",
        "narrative_obligation_pressure": 1.0,
    }
    return (
        PopulationProjection(
            ref=f"projection:tax-pressure:{obligation_ref}",
            scope=scope,
            revision_vector={stream_ref: revision},
            payload=payload,
        ),
    )


social_population_signal_projections = social_population_signal_population_projections
tax_obligation_population_projections = tax_pressure_population_projections


# Keep the source name discoverable for callers that describe the input rather
# than the resulting Owner operation.
certified_output_population_projections = inventory_output_custody_population_projections


__all__ = [
    "certified_output_population_projections",
    "inventory_output_custody_population_projections",
    "production_receipt_population_projections",
    "production_work_population_projections",
    "social_population_signal_population_projections",
    "social_population_signal_projections",
    "tax_obligation_population_projections",
    "tax_pressure_population_projections",
]
