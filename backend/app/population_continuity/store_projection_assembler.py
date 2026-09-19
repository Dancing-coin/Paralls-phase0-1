from __future__ import annotations

from collections.abc import Mapping
from collections import Counter
import hashlib
import json
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent, ProjectionCheckpoint
from app.population_continuity.domain_projection_sources import (
    _committed_marker_is_valid,
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


def _committed_events(store: GameplayEventStore, source_events: tuple[GameplayEvent, ...]) -> tuple[object, ...]:
    events: list[object] = []
    for event in source_events:
        payload = _event_payload(event)
        if not _committed_marker_is_valid(getattr(event, "committed", None)):
            continue
        if getattr(event, "global_sequence", 0) < 1 or getattr(event, "stream_revision", 0) < 1:
            continue
        if not _committed_marker_is_valid(payload.get("committed")):
            continue
        if _event_visibility(event, payload) not in _ADMITTED_EVENT_VISIBILITY:
            continue
        stream_id = str(getattr(event, "stream_id", ""))
        revision = getattr(event, "stream_revision", 0)
        if not stream_id or store.get_stream_head(stream_id) != revision:
            continue
        events.append(event)
    return tuple(events)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _checkpoint_digest(checkpoint: ProjectionCheckpoint) -> str:
    return _digest({"state": checkpoint.state, "sequence": checkpoint.last_global_sequence,
                    "revisions": checkpoint.source_revision_vector})


def _checkpoint_context(cadence: PopulationCadenceInput, organization: Mapping[str, object]) -> dict[str, object]:
    return {"world_ref": cadence.world_ref, "world_mode_revision": cadence.world_mode_revision,
            "report_scope": cadence.report_scope, "policy_revision": cadence.policy_revision,
            "selector_revision": cadence.selector_revision, "ruleset_revision": cadence.ruleset_revision,
            "organization_ref": organization.get("organization_ref")}


def _read_sources(
    store: GameplayEventStore, cadence: PopulationCadenceInput, organization: Mapping[str, object],
    checkpoint: ProjectionCheckpoint | None, incremental: bool,
) -> tuple[tuple[GameplayEvent, ...], ProjectionCheckpoint]:
    context = _checkpoint_context(cadence, organization)
    checkpoint_id = "checkpoint:population:" + _digest(context).split(":", 1)[1]
    if incremental and checkpoint is None:
        checkpoint = store.get_projection_checkpoint(checkpoint_id)
    cursor, current, revisions = 0, {}, {}
    if checkpoint is not None:
        if (checkpoint.projector_id != "population-continuity" or checkpoint.projector_version != "2"
                or checkpoint.projection_schema_version != 2):
            raise ValueError("projection_checkpoint_schema_mismatch")
        if checkpoint.projection_hash != _checkpoint_digest(checkpoint):
            raise ValueError("projection_checkpoint_digest_mismatch")
        if checkpoint.state.get("context") != context or checkpoint.state.get("report_scope") != cadence.report_scope:
            raise ValueError("projection_checkpoint_scope_mismatch")
        cursor = checkpoint.last_global_sequence
        if not 0 <= cursor <= store.get_last_global_sequence():
            raise ValueError("projection_gap")
        revisions = dict(checkpoint.source_revision_vector)
        sources = checkpoint.state.get("source_events")
        if not isinstance(sources, list) or any(not isinstance(item, dict) for item in sources):
            raise ValueError("projection_checkpoint_state_invalid")
        for raw in sources:
            event = GameplayEvent.model_validate(raw)
            if (event.stream_id in current or event.global_sequence > cursor
                    or revisions.get(event.stream_id) != event.stream_revision):
                raise ValueError("projection_checkpoint_state_invalid")
            current[event.stream_id] = event
    high_water = store.get_last_global_sequence()
    expected = cursor + 1
    tail_revisions = dict(revisions)
    seen_tail_revisions: dict[str, int] = {}
    while expected <= high_water:
        tail = store.read_events(global_sequence_after=expected - 1, limit=min(256, high_water - expected + 1))
        if not tail:
            raise ValueError("projection_gap")
        for event in tail:
            # 在过滤私有/无关事件前检查全局序号，分页不能跳过缺口或重置流版本。
            if event.global_sequence != expected:
                raise ValueError("projection_gap")
            admitted = (
                _event_allowed_for_scope(event, cadence.report_scope)
                and event.event_type in {
                    _SOCIAL_EVENT, "gameplay.construction_production.work_completion_evidence_recorded",
                    "gameplay.construction_production.production_output_certified@1",
                }
            )
            previous_revision = tail_revisions.get(
                event.stream_id, seen_tail_revisions.get(event.stream_id)
            )
            if previous_revision is not None or admitted:
                if previous_revision is None and event.stream_revision > 1:
                    previous = store.read_stream(
                        event.stream_id,
                        from_revision=event.stream_revision - 1,
                        to_revision=event.stream_revision - 1,
                        limit=1,
                    )
                    if (len(previous) != 1
                            or previous[0].stream_revision != event.stream_revision - 1
                            or previous[0].global_sequence > cursor):
                        raise ValueError("projection_gap")
                    previous_revision = previous[0].stream_revision
                if event.stream_revision != (previous_revision or 0) + 1:
                    raise ValueError("projection_gap")
            seen_tail_revisions[event.stream_id] = event.stream_revision
            if event.stream_id in tail_revisions or admitted:
                tail_revisions[event.stream_id] = event.stream_revision
            current.pop(event.stream_id, None)
            # 只保留当前流头，撤销或转为私有时必须移除旧公开来源。
            if admitted:
                current[event.stream_id] = event
            expected += 1
    if expected - 1 != store.get_last_global_sequence():
        raise ValueError("projection_gap")
    revisions = {event.stream_id: event.stream_revision for event in current.values()}
    if any(store.get_stream_head(stream_id) != revision for stream_id, revision in revisions.items()):
        raise ValueError("projection_gap")
    sources = tuple(sorted(current.values(), key=lambda event: event.global_sequence))
    next_checkpoint = ProjectionCheckpoint(
        checkpoint_id=checkpoint_id, projector_id="population-continuity", projector_version="2",
        projection_schema_version=2, source_revision_vector=revisions, last_global_sequence=expected - 1,
        state={"context": context, "report_scope": cadence.report_scope,
               "source_events": [event.model_dump(mode="json") for event in sources]},
        projection_hash="pending",
    )
    next_checkpoint = next_checkpoint.model_copy(update={"projection_hash": _checkpoint_digest(next_checkpoint)})
    return sources, next_checkpoint


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


def assemble_committed_population_projections(
    *,
    store: GameplayEventStore,
    cadence: PopulationCadenceInput,
    organization_projection: Mapping[str, object],
    checkpoint: ProjectionCheckpoint | None = None,
    incremental: bool = False,
) -> tuple[PopulationProjection, ...]:
    """Read committed, current, cadence-pinned facts without writing or settling."""
    if cadence.report_scope not in {"organization:summary", "public"}:
        if checkpoint is not None or incremental:
            raise ValueError("projection_checkpoint_scope_mismatch")
        return ()
    sources, next_checkpoint = _read_sources(store, cadence, organization_projection, checkpoint, incremental)
    events = _committed_events(store, sources)
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
                    scope="public",
                )
            )
    tax_projection = organization_projection.get("_tax_projection")
    if isinstance(tax_projection, Mapping):
        if (
            tax_projection.get("organization_ref") == organization_projection.get("organization_ref")
            and tax_projection.get("source_stream_ref") == "gameplay:economy"
            and tax_projection.get("status") in {"due", "overdue"}
            and isinstance(tax_projection.get("actor_ref"), str)
            and str(tax_projection["actor_ref"]).startswith("character:")
        ):
            candidates.extend(
                tax_pressure_population_projections(
                    tax_obligation_projection=tax_projection,
                    scope="public",
                )
            )

    accepted: dict[str, PopulationProjection] = {}
    for projection in candidates:
        if not _projection_is_pinned(projection, store=store, cadence=cadence):
            continue
        accepted[projection.ref] = accepted.get(projection.ref, projection)
    counts = Counter(item.ref for item in candidates)
    result = tuple(accepted[ref] for ref in sorted(accepted) if counts[ref] == 1)
    if incremental:
        store.save_projection_checkpoint(next_checkpoint)
    return result


__all__ = ["assemble_committed_population_projections"]
