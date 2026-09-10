from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.domain_projection_sources import (
    committed_event_payload,
    event_visibility_policy,
    inventory_output_custody_population_projections,
    production_work_population_projections,
    social_population_signal_population_projections,
    tax_pressure_population_projections,
)
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection


_ADMITTED_EVENT_VISIBILITY = frozenset({"project", "public", "organization:summary"})
_SOCIAL_EVENT = "gameplay.social.population_signal_recorded@1"
_TAX_EVENT_TYPES = frozenset(
    {
        "gameplay.economy.tax_obligation_recorded@1",
        "gameplay.economy.tax_obligation_opened",
        "gameplay.economy.tax_obligation_due_projection",
    }
)


def _event_payload(event: object) -> dict[str, Any]:
    return dict(committed_event_payload(event))


def _event_visibility(event: object, payload: Mapping[str, object]) -> str:
    return event_visibility_policy(event, payload)


def _committed_events(store: GameplayEventStore) -> tuple[object, ...]:
    events: list[object] = []
    for event in store.read_events():
        payload = _event_payload(event)
        if getattr(event, "committed", True) is False:
            continue
        if getattr(event, "global_sequence", 0) < 1 or getattr(event, "stream_revision", 0) < 1:
            continue
        committed = payload.get("committed")
        if committed is not None and committed is not True:
            continue
        if _event_visibility(event, payload) not in _ADMITTED_EVENT_VISIBILITY:
            continue
        stream_id = str(getattr(event, "stream_id", ""))
        revision = getattr(event, "stream_revision", 0)
        if not stream_id or store.get_stream_head(stream_id) != revision:
            continue
        events.append(event)
    return tuple(events)


def _event_allowed_for_scope(event: object, scope: str) -> bool:
    visibility = _event_visibility(event, _event_payload(event))
    if scope == "public":
        return visibility == "public"
    return visibility in _ADMITTED_EVENT_VISIBILITY


def _projection_is_pinned(
    projection: PopulationProjection,
    *,
    store: GameplayEventStore,
    cadence: PopulationCadenceInput,
) -> bool:
    if not projection.revision_vector or projection.scope not in {"organization:summary", "public"}:
        return False
    for stream_id, revision in projection.revision_vector.items():
        if cadence.base_revision_vector.get(stream_id) != revision:
            return False
        if store.get_stream_head(stream_id) != revision:
            return False
    return True


def _social_source(event: object) -> dict[str, object]:
    payload = _event_payload(event)
    stream_id = str(getattr(event, "stream_id", ""))
    revision = getattr(event, "stream_revision", 0)
    payload["source_stream_ref"] = stream_id
    payload["source_revision_pin"] = revision
    payload.setdefault("signal_ref", payload.get("signal_id", ""))
    payload.setdefault("provenance_ref", payload.get("source_event_id", getattr(event, "event_id", "")))
    payload.setdefault("visibility_scope", _event_visibility(event, payload))
    payload.setdefault("revision_vector", {stream_id: revision})
    return payload


def _tax_source(event: object) -> dict[str, object]:
    payload = _event_payload(event)
    stream_id = str(getattr(event, "stream_id", ""))
    revision = getattr(event, "stream_revision", 0)
    payload["source_stream_ref"] = stream_id
    payload["source_revision_pin"] = revision
    payload.setdefault("obligation_ref", payload.get("obligation_id", ""))
    payload.setdefault("actor_ref", payload.get("character_ref", ""))
    if "status" not in payload and "due" in str(getattr(event, "event_type", "")):
        payload["status"] = "due"
    payload.setdefault("visibility_scope", _event_visibility(event, payload))
    return payload


def assemble_committed_population_projections(
    *,
    store: GameplayEventStore,
    cadence: PopulationCadenceInput,
    organization_projection: Mapping[str, object],
) -> tuple[PopulationProjection, ...]:
    """Read committed, current, cadence-pinned facts without writing or settling."""
    events = _committed_events(store)
    if not events or cadence.report_scope not in {"organization:summary", "public"}:
        return ()

    candidates: list[PopulationProjection] = []
    scoped_events = tuple(event for event in events if _event_allowed_for_scope(event, cadence.report_scope))
    candidates.extend(
        production_work_population_projections(
            committed_events=scoped_events,
            organization_projection=organization_projection,
            scope=cadence.report_scope,
        )
    )
    candidates.extend(
        inventory_output_custody_population_projections(
            committed_events=scoped_events,
            scope=cadence.report_scope,
        )
    )
    for event in events:
        event_payload = _event_payload(event)
        declared_source_stream = event_payload.get("source_stream_ref", event_payload.get("stream_ref"))
        if declared_source_stream is not None and str(declared_source_stream) != str(getattr(event, "stream_id", "")):
            continue
        if (
            getattr(event, "event_type", "") == _SOCIAL_EVENT
            and _event_visibility(event, event_payload) == "public"
        ):
            candidates.extend(
                social_population_signal_population_projections(
                    population_signal_projection=_social_source(event),
                    scope=cadence.report_scope,
                )
            )
        if (
            getattr(event, "event_type", "") in _TAX_EVENT_TYPES
            and _event_visibility(event, event_payload) == "public"
        ):
            candidates.extend(
                tax_pressure_population_projections(
                    tax_obligation_projection=_tax_source(event),
                    scope=cadence.report_scope,
                )
            )

    accepted: dict[str, PopulationProjection] = {}
    for projection in candidates:
        if not _projection_is_pinned(projection, store=store, cadence=cadence):
            continue
        accepted[projection.ref] = accepted.get(projection.ref, projection)
    duplicate_refs = {ref for ref, projection in accepted.items() if sum(item.ref == ref for item in candidates) > 1}
    return tuple(accepted[ref] for ref in sorted(accepted) if ref not in duplicate_refs)


__all__ = ["assemble_committed_population_projections"]
