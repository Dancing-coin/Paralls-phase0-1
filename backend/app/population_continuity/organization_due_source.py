"""从 Organization 已提交排班与窗口增量形成内部 B1 来源，不写领域事实。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent, ProjectionCheckpoint
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.siming_contracts import PopulationProjection
from app.population_continuity.store_projection_assembler import _checkpoint_digest, _digest


SCHEDULE = "gameplay.organization.work_order_recorded"
CLOSED = "gameplay.organization.operating_window_closed"
SETTLED = "gameplay.organization.operating_window_due_recorded"
POLICY = "organization-window-due-source:v1"


@dataclass(frozen=True)
class OrganizationWindowDueRead:
    projections: tuple[PopulationProjection, ...]
    diagnostics: tuple[tuple[str, str], ...]
    cursor: int


def _instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("organization_due_timestamp_invalid")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("organization_due_timezone_required")
    return result


def project_organization_due(schedules, windows, current_windows, stream_heads, *, window_end, observed_at, scope):
    """原已验证Owner当前来源的纯join；生产读取和离线证据使用同一资格/顺序。"""
    observed = _instant(observed_at)
    if scope != 'organization:summary':
        return (), ()
    grouped = {}
    for event in schedules.values():
        grouped.setdefault(event.payload["operating_window_ref"], []).append(event)
    projections, diagnostics = [], []
    for window, bindings in sorted(grouped.items()):
        current = current_windows.get(window)
        closed = windows.get(window)
        if closed is None or current != closed:
            diagnostics.append((window, "closed_source_unavailable"))
            continue
        state = closed.payload
        due = state.get("closes_at_tick")
        if type(due) is not int or due < 0:
            diagnostics.append((window, "window_binding_invalid"))
            continue
        valid_bindings = []
        for schedule in bindings:
            work = schedule.payload
            if work["organization_ref"] != state.get("organization_ref"):
                diagnostics.append((window, "window_binding_invalid"))
                continue
            try:
                active = observed >= _instant(work["effective_from"]) and (work.get("effective_to") is None or observed < _instant(work["effective_to"]))
            except (KeyError, TypeError, ValueError):
                active = False
            if not active:
                diagnostics.append((window, "schedule_inactive"))
                continue
            valid_bindings.append(schedule)
        if not valid_bindings:
            continue
        if len(valid_bindings) != 1:
            diagnostics.append((window, "window_binding_ambiguous"))
            continue
        schedule = valid_bindings[0]
        work = schedule.payload
        if due > window_end:
            continue
        identity = _digest([POLICY, schedule.event_id, schedule.stream_revision, closed.event_id, closed.stream_revision])
        projections.append(PopulationProjection(ref="projection:organization-window-due:" + identity.split(":", 1)[1],
            scope=scope, revision_vector={schedule.stream_id: stream_heads[schedule.stream_id],
                                          closed.stream_id: closed.stream_revision},
            payload=dict(actor_ref=work["recipient_ref"], candidate_kind="organization_operating_window_due",
                source_domain="organization", intent_kind="operating_window_due", fidelity_tier="B1", due=True,
                due_tick=due, organization_ref=work["organization_ref"], window_ref=window, stream_ref=closed.stream_id,
                work_order_ref=work["work_order_ref"], assignment_ref=work["assignment_ref"],
                schedule_event_id=schedule.event_id, schedule_event_revision=schedule.stream_revision,
                closed_event_id=closed.event_id, closed_event_revision=closed.stream_revision, source_policy_revision=POLICY)))
    return tuple(projections), tuple(diagnostics)


class OrganizationWindowDueSource:
    """仅保存未完成来源及增量游标；多组织共享下一层已有32角色选择预算。"""

    def __init__(self, *, store: GameplayEventStore, world_ref: str, roster: PopulationRoster) -> None:
        if not world_ref:
            raise ValueError("organization_due_world_required")
        self._store = store
        self._actors = frozenset("character:" + actor for actor in roster.actor_ids)
        self._context = dict(world_ref=world_ref, roster_digest=_digest(roster.actor_ids), policy=POLICY)
        self.checkpoint_id = "checkpoint:population-organization-due:" + _digest(self._context).split(":", 1)[1]

    def _owner_event(self, event: GameplayEvent) -> bool:
        batch = self._store.get_transaction(event.transaction_id)
        return (batch is not None and batch.idempotency_record.principal_ref == OrganizationAuthority._PRINCIPAL
                and event in batch.events and event.global_sequence > 0 and event.stream_revision > 0)

    def _head(self, window_ref: str) -> GameplayEvent | None:
        stream = "gameplay:organization:window:" + window_ref
        head = self._store.get_stream_head(stream)
        events = self._store.read_stream(stream, from_revision=head, to_revision=head, limit=1) if head else []
        return events[0] if events else None

    def _apply(self, event, schedules, windows):
        payload = event.payload
        if event.event_type == SCHEDULE:
            organization, work = payload.get("organization_ref"), payload.get("work_order_ref")
            if not isinstance(organization, str) or not isinstance(work, str) or not work or event.stream_id != "gameplay:organization:" + organization:
                return
            key = organization, work
            schedules.pop(key, None)
            if (event.visibility_policy == "organization:summary" and payload.get("visibility_scope") == "organization:summary"
                    and payload.get("recipient_ref") in self._actors and payload.get("operating_window_ref")
                    and payload.get("assignment_ref")):
                schedules[key] = event
        elif event.stream_id.startswith("gameplay:organization:window:"):
            window = payload.get("window_ref")
            if not isinstance(window, str) or event.stream_id != "gameplay:organization:window:" + window:
                return
            windows.pop(window, None)
            if event.event_type == CLOSED and event.visibility_policy == "project" and payload.get("status") == "closed":
                windows[window] = event
            if event.event_type == SETTLED:
                # 仅移除已被领域Owner结算的来源；不把别人的receipt计成本任务完成。
                for key in [key for key, row in schedules.items() if row.payload["operating_window_ref"] == window]:
                    del schedules[key]

    def _restore(self):
        checkpoint = self._store.get_projection_checkpoint(self.checkpoint_id)
        if checkpoint is None:
            return {}, {}, 0, None, None
        if (checkpoint.projector_id != "population-organization-window-due" or checkpoint.projector_version != "1"
                or checkpoint.projection_schema_version != 1 or checkpoint.state.get("context") != self._context
                or checkpoint.projection_hash != _checkpoint_digest(checkpoint)
                or not 0 <= checkpoint.last_global_sequence <= self._store.get_last_global_sequence()):
            raise ValueError("organization_due_checkpoint_invalid")
        cursor = checkpoint.last_global_sequence
        anchor = checkpoint.state.get("anchor")
        if cursor:
            if not isinstance(anchor, dict):
                raise ValueError("organization_due_checkpoint_anchor_invalid")
            actual = self._store.get_event(anchor["event_id"])
            if actual.global_sequence != cursor or _digest(actual.model_dump(mode="json")) != anchor.get("digest"):
                raise ValueError("organization_due_checkpoint_anchor_invalid")
        elif anchor is not None:
            raise ValueError("organization_due_checkpoint_anchor_invalid")
        raw = checkpoint.state.get("source_events")
        if not isinstance(raw, list):
            raise ValueError("organization_due_checkpoint_sources_invalid")
        schedules, windows, revisions, seen = {}, {}, {}, set()
        for value in raw:
            event = GameplayEvent.model_validate(value)
            if (event.event_id in seen or event.global_sequence > cursor or event.event_type not in {SCHEDULE, CLOSED}
                    or event != self._store.get_event(event.event_id) or not self._owner_event(event)):
                raise ValueError("organization_due_source_event_invalid")
            seen.add(event.event_id)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            self._apply(event, schedules, windows)
        if revisions != checkpoint.source_revision_vector:
            raise ValueError("organization_due_checkpoint_revisions_invalid")
        return schedules, windows, cursor, anchor, checkpoint

    def read(self, *, window_end: int, observed_at: str, scope: str) -> OrganizationWindowDueRead:
        if type(window_end) is not int or window_end < 0:
            raise ValueError("organization_due_tick_invalid")
        _instant(observed_at)
        # 该窄授权从project窗口和summary排班join而来，绝不下沉到public B0/mirror。
        if scope != "organization:summary":
            return OrganizationWindowDueRead((), (), 0)
        schedules, windows, cursor, anchor, prior_checkpoint = self._restore()
        high_water = self._store.get_last_global_sequence()
        while cursor < high_water:
            tail = self._store.read_events(global_sequence_after=cursor, limit=min(256, high_water - cursor))
            if not tail:
                raise ValueError("organization_due_projection_gap")
            for event in tail:
                if event.global_sequence != cursor + 1:
                    raise ValueError("organization_due_projection_gap")
                if (event.event_type == SCHEDULE or event.stream_id.startswith("gameplay:organization:window:")) and self._owner_event(event):
                    self._apply(event, schedules, windows)
                cursor = event.global_sequence
                anchor = dict(event_id=event.event_id, digest=_digest(event.model_dump(mode="json")))
        if cursor != self._store.get_last_global_sequence():
            raise ValueError("organization_due_source_changed")
        current_windows = {}
        for window in {event.payload['operating_window_ref'] for event in schedules.values()}:
            current = self._head(window)
            current_windows[window] = current
            if current is not None and self._owner_event(current):
                self._apply(current, schedules, windows)
        projections, diagnostics = project_organization_due(schedules, windows, current_windows,
            {event.stream_id: self._store.get_stream_head(event.stream_id) for event in schedules.values()},
            window_end=window_end, observed_at=observed_at, scope=scope)
        pending_windows = {event.payload["operating_window_ref"] for event in schedules.values()}
        events = sorted((*schedules.values(), *(event for window, event in windows.items() if window in pending_windows)),
                        key=lambda event: event.global_sequence)
        revisions = {}
        for event in events:
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        checkpoint = ProjectionCheckpoint(checkpoint_id=self.checkpoint_id, projector_id="population-organization-window-due",
            projector_version="1", projection_schema_version=1, source_revision_vector=revisions, last_global_sequence=cursor,
            state=dict(context=self._context, anchor=anchor, source_events=[event.model_dump(mode="json") for event in events]),
            projection_hash="pending")
        checkpoint.projection_hash = _checkpoint_digest(checkpoint)
        if self._store.get_last_global_sequence() != high_water:
            raise ValueError("organization_due_source_changed")
        if checkpoint != prior_checkpoint:
            self._store.save_projection_checkpoint(checkpoint)
        return OrganizationWindowDueRead(tuple(projections), tuple(diagnostics), cursor)
