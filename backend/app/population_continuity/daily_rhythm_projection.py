from __future__ import annotations

from threading import RLock
from typing import Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent


class DailyRhythmProjection:
    """从 DailyRhythm 事件流重建 B0 状态。"""

    _EVENT_TYPES = frozenset({"daily_rhythm.initialized", "daily_rhythm.state_updated"})

    def __init__(self, event_store: GameplayEventStore) -> None:
        self._store = event_store
        self._cache: dict[str, dict[str, object]] = {}
        self._revision: dict[str, int] = {}
        self._source_revision: dict[str, int] = {}
        self._bounded: set[str] = set()
        self._lock = RLock()

    def rebuild(self, actor_id: str, *, until_revision: int | None = None, _incremental: bool = False) -> dict[str, object]:
        with self._lock:
            return self._rebuild(actor_id, until_revision=until_revision, _incremental=_incremental)

    def _rebuild(self, actor_id: str, *, until_revision: int | None, _incremental: bool) -> dict[str, object]:
        incremental = (
            actor_id in self._cache
            and (
                _incremental
                or until_revision is not None and until_revision >= self._revision[actor_id]
            )
        )
        stream_id = f"daily-rhythm:{actor_id}"
        source_head = self._store.get_stream_head(stream_id)
        from_revision = self._source_revision[actor_id] + 1 if incremental else 1
        events = self._store.read_stream(stream_id, from_revision=from_revision, to_revision=source_head)
        state = dict(self._cache[actor_id]) if incremental else self._default_state()
        revision = self._revision[actor_id] if incremental else 0
        consumed_stream_revision = from_revision - 1
        for event in events:
            if event.event_type not in self._EVENT_TYPES:
                consumed_stream_revision = event.stream_revision
                continue
            values = event.payload.get("state", {})
            if not isinstance(values, Mapping):
                raise ValueError("daily_rhythm_state_invalid")
            if event.event_type == "daily_rhythm.state_updated":
                event_revision = event.payload.get("revision", revision)
                if type(event_revision) is not int or event_revision < 0:
                    raise ValueError("daily_rhythm_revision_invalid")
                if until_revision is not None and event_revision > until_revision:
                    break
                revision = event_revision
            state.update(values)
            consumed_stream_revision = event.stream_revision

        self._cache[actor_id] = state
        self._revision[actor_id] = revision
        self._source_revision[actor_id] = consumed_stream_revision if until_revision is not None else source_head
        if until_revision is None:
            self._bounded.discard(actor_id)
        else:
            self._bounded.add(actor_id)
        return dict(state)

    def read(self, actor_id: str, *, refresh: bool = False) -> dict[str, object]:
        return self.snapshot(actor_id, refresh=refresh)[0]

    def snapshot(self, actor_id: str, *, refresh: bool = False) -> tuple[dict[str, object], int, int, bool]:
        with self._lock:
            if (refresh or actor_id not in self._cache
                    or actor_id not in self._bounded
                    and self._source_revision[actor_id] != self._store.get_stream_head(f"daily-rhythm:{actor_id}")):
                self._rebuild(actor_id, until_revision=None, _incremental=not refresh)
            return (dict(self._cache[actor_id]), self._revision[actor_id], self._source_revision[actor_id],
                    actor_id in self._bounded)

    def get_revision(self, actor_id: str) -> int:
        return self.snapshot(actor_id)[1]

    def revision_pin(self, actor_id: str) -> tuple[int, int]:
        _state, logical_revision, source_revision, _bounded = self.snapshot(actor_id)
        return logical_revision, source_revision

    def matches_snapshot(self, actor_id: str, source_revision: int) -> bool:
        return self._store.get_stream_head(f"daily-rhythm:{actor_id}") == source_revision

    def matches_snapshots(self, snapshots: Mapping[str, tuple[int, int, bool]]) -> bool:
        with self._lock:
            stream_heads = self._store.get_stream_heads()
            return all(
                self._revision.get(actor_id) == logical_revision
                and (bounded or stream_heads.get(f"daily-rhythm:{actor_id}", 0) == source_revision)
                and (actor_id in self._bounded) == bounded
                for actor_id, (logical_revision, source_revision, bounded) in snapshots.items()
            )

    def resume_live(self) -> None:
        with self._lock:
            self._bounded.clear()

    def advance_confirmed(self, events: tuple[GameplayEvent, ...]) -> None:
        with self._lock:
            for event in events:
                actor_id = event.payload["actor_id"]
                self._cache[actor_id].update(event.payload["state"])
                self._revision[actor_id] = event.payload["revision"]
                self._source_revision[actor_id] = event.stream_revision

    @staticmethod
    def _default_state() -> dict[str, object]:
        return {
            "fatigue": 0.2,
            "need_pressure": 0.1,
            "starvation_credit": 0.0,
            "activity_phase": "morning",
            "next_due_tick": 21_600,
            "last_update_tick": 0,
        }
