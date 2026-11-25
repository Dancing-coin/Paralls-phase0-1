from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import heapq
from threading import RLock
from types import MappingProxyType
from typing import Iterable, Mapping

from .daily_rhythm_projection import DailyRhythmProjection


HOT_FIELDS = frozenset(
    {
        "last_update_tick",
        "activity_phase",
        "fatigue",
        "need_pressure",
        "next_due_tick",
        "starvation_credit",
    }
)


def get_starvation_credit_for_siming(actor_id: str, b0_row: Mapping[str, object]) -> float:
    """Read-only Siming scheduler seam; B0 ownership and fields are unchanged."""
    return float(b0_row.get("starvation_credit", 0.0))
# DailyRhythm is the canonical source for all HOT_FIELDS.


class _ReadOnlyRow(dict[str, object]):
    def _immutable(self, *_args, **_kwargs) -> None:
        raise TypeError("hot_state_row_readonly")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


@dataclass(frozen=True)
class HotStateReceipt:
    actor_id: str
    status: str
    revision: int


class PopulationHotState:
    """稳定 actor ID 到紧凑槽位的热字段表；不保存身份、记忆或权限对象。"""

    def __init__(
        self,
        actor_ids: Iterable[str] = (),
        *,
        daily_rhythm_projection: DailyRhythmProjection,
        additional_fields: Iterable[str] = (),
    ) -> None:
        self._projection = daily_rhythm_projection
        normalized_fields = {str(field).strip() for field in additional_fields}
        if any(not field for field in normalized_fields):
            raise ValueError("hot_state_field_invalid")
        self._allowed_fields = HOT_FIELDS.union(normalized_fields)
        self._actor_ids = set(actor_ids)
        self._additional_rows: dict[str, dict[str, object]] = {}
        self._lock = RLock()

    def register_fields(self, fields: Iterable[str]) -> None:
        """Register gameplay-package columns before batch updates use them."""
        normalized_fields = {str(field).strip() for field in fields}
        if any(not field for field in normalized_fields):
            raise ValueError("hot_state_field_invalid")
        added = normalized_fields.difference(self._allowed_fields)
        self._allowed_fields = self._allowed_fields.union(normalized_fields)

    def register_group_fields(self, group_id: str, fields: Iterable[str]) -> None:
        """Compile a state-group field list into collision-resistant hot columns."""
        normalized_group = str(group_id).strip()
        if not normalized_group:
            raise ValueError("hot_state_group_invalid")
        normalized_fields = {str(field).strip() for field in fields}
        if any(not field for field in normalized_fields):
            raise ValueError("hot_state_field_invalid")
        self.register_fields(f"{normalized_group}.{field}" for field in normalized_fields)

    def upsert_population_view(self, view: object, *, revision: int) -> None:
        """Compile one already-redacted population view into group-qualified hot columns."""
        if getattr(view, "consumer", None) != "population":
            raise ValueError("population_view_required")
        actor_id = str(getattr(view, "actor_ref", "") or "")
        groups = getattr(view, "groups", None)
        if not actor_id or not isinstance(groups, Mapping):
            raise ValueError("population_view_invalid")
        values: dict[str, object] = {}
        for group_id, envelope in sorted(groups.items(), key=lambda item: str(item[0])):
            normalized_group = str(group_id).strip()
            payload = getattr(envelope, "payload", None)
            if not normalized_group or not isinstance(payload, Mapping):
                raise ValueError("population_view_invalid")
            self.register_group_fields(normalized_group, payload.keys())
            values.update(
                {
                    f"{normalized_group}.{field}": value
                    for field, value in payload.items()
                }
            )
        self.upsert(actor_id, values, revision)

    def upsert(self, actor_id: str, values: Mapping[str, object], revision: int) -> None:
        if not actor_id:
            raise ValueError("hot_state_actor_required")
        hot_fields_conflict = set(values).intersection(HOT_FIELDS)
        if hot_fields_conflict:
            raise ValueError(f"hot_fields_owned_by_daily_rhythm: {hot_fields_conflict}")
        unknown = set(values).difference(self._allowed_fields)
        if unknown:
            raise ValueError("hot_state_field_not_allowed")
        self._validate_values(values)
        with self._lock:
            row = dict(self._additional_rows.get(actor_id, {}))
            row.update(values)
            self._actor_ids.add(actor_id)
            self._additional_rows[actor_id] = row

    def read(self, actor_id: str) -> Mapping[str, object]:
        with self._lock:
            if actor_id not in self._actor_ids:
                raise KeyError(actor_id)
            additional = dict(self._additional_rows.get(actor_id, {}))
            row, _revision, _source_revision, _bounded = self._snapshot_for(actor_id)
        row.update(additional)
        return _ReadOnlyRow(row)

    def get_revision(self, actor_id: str) -> int:
        return self._projection.get_revision(actor_id)

    def _snapshot_for(self, actor_id: str) -> tuple[dict[str, object], int, int, bool]:
        if actor_id not in self._actor_ids:
            raise KeyError(actor_id)
        row, revision, source_revision, bounded = self._projection.snapshot(actor_id)
        row["revision"] = revision
        row.update(self._additional_rows.get(actor_id, {}))
        return row, revision, source_revision, bounded

    def remove(self, actor_id: str) -> None:
        with self._lock:
            self._actor_ids.discard(actor_id)
            self._additional_rows.pop(actor_id, None)

    def due_actor_ids(self, tick: int) -> tuple[str, ...]:
        due: list[tuple[int, str]] = []
        with self._lock:
            actor_ids = tuple(self._actor_ids)
        for actor_id in actor_ids:
            row = self.read(actor_id)
            due_tick = row.get("next_due_tick")
            if isinstance(due_tick, int) and not isinstance(due_tick, bool) and due_tick <= tick:
                due.append((due_tick, actor_id))
        return tuple(actor_id for _, actor_id in sorted(due))

    def apply_batch(
        self, updates: Iterable[tuple[str, Mapping[str, object], int]]
    ) -> tuple[HotStateReceipt, ...]:
        receipts: list[HotStateReceipt] = []
        for actor_id, values, revision in updates:
            try:
                self.upsert(actor_id, values, revision)
            except (KeyError, ValueError) as exc:
                receipts.append(HotStateReceipt(actor_id, f"rejected:{exc}", self.get_revision(actor_id)))
            else:
                receipts.append(HotStateReceipt(actor_id, "committed", self.get_revision(actor_id)))
        return tuple(receipts)

    def apply_batch_atomic(
        self,
        updates: Iterable[tuple[str, Mapping[str, object], int, int]],
    ) -> tuple[HotStateReceipt, ...]:
        """一次锁内校验并提交整个批次，任何版本冲突都保持零写入。"""
        pending = tuple(updates)
        self._commit_batch_atomic(pending)
        return tuple(
            HotStateReceipt(actor_id, "committed", revision)
            for actor_id, _values, _expected_revision, revision in pending
        )

    def commit_batch_atomic(
        self,
        updates: Iterable[tuple[str, Mapping[str, object], int, int]],
    ) -> int:
        """提交原子批次并返回写入数，供无需逐行 receipt 的生产确认路径使用。"""
        pending = tuple(updates)
        self._commit_batch_atomic(pending)
        return len(pending)

    def _commit_batch_atomic(
        self,
        pending: tuple[tuple[str, Mapping[str, object], int, int], ...],
    ) -> None:
        if len({actor_id for actor_id, _values, _expected, _revision in pending}) != len(pending):
            raise ValueError("hot_state_batch_duplicate_actor")
        with self._lock:
            prepared: list[tuple[str, dict[str, object]]] = []
            for actor_id, values, expected_revision, revision in pending:
                if actor_id not in self._actor_ids:
                    raise ValueError("hot_state_actor_missing")
                copied_values = dict(values)
                hot_fields_conflict = set(copied_values).intersection(HOT_FIELDS)
                if hot_fields_conflict:
                    raise ValueError(f"hot_fields_owned_by_daily_rhythm: {hot_fields_conflict}")
                fields = set(copied_values)
                if fields.difference(self._allowed_fields):
                    raise ValueError("hot_state_field_not_allowed")
                self._validate_values(copied_values)
                row = dict(self._additional_rows.get(actor_id, {}))
                row.update(copied_values)
                prepared.append((actor_id, row))
            for actor_id, row in prepared:
                self._additional_rows[actor_id] = row

    def export_rows(self) -> tuple[tuple[str, Mapping[str, object]], ...]:
        with self._lock:
            actor_ids = tuple(sorted(self._actor_ids))
        return tuple((actor_id, self.read(actor_id)) for actor_id in actor_ids)

    def map_readonly(
        self,
        actor_ids: Iterable[str],
        evaluator,
        *,
        workers: int = 1,
        batch_size: int = 256,
        source_revision_sink: dict[str, int] | None = None,
    ) -> tuple[object, ...]:
        """并行只读计算；结果按 actor ID 合并，worker 不得写入任何 authority。"""
        if workers < 1 or batch_size < 1:
            raise ValueError("hot_state_parallelism_invalid")
        ids = tuple(sorted(set(actor_ids)))
        with self._lock:
            snapshots = []
            for actor_id in ids:
                row, revision, source_revision, bounded = self._snapshot_for(actor_id)
                snapshots.append((
                    actor_id,
                    dict(self._additional_rows.get(actor_id, {})),
                    revision,
                    source_revision,
                    bounded,
                    MappingProxyType(row),
                ))
            snapshots = tuple(snapshots)
            if source_revision_sink is not None:
                source_revision_sink.update(
                    (actor_id, source_revision)
                    for actor_id, _additional, _revision, source_revision, _bounded, _row in snapshots
                )

        def evaluate_batch(batch):
            return tuple(
                evaluator(actor_id, row)
                for actor_id, _additional, _revision, _source_revision, _bounded, row in batch
            )

        if workers <= 1:
            values = evaluate_batch(snapshots)
        else:
            batches = tuple(
                snapshots[index:index + batch_size]
                for index in range(0, len(snapshots), batch_size)
            )
            if len(batches) <= 1:
                evaluated = (evaluate_batch(snapshots),)
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    evaluated = tuple(pool.map(evaluate_batch, batches))
            values = tuple(value for batch in evaluated for value in batch)
        with self._lock:
            projection_snapshots = {
                actor_id: (revision, source_revision, bounded)
                for actor_id, _additional, revision, source_revision, bounded, _row in snapshots
            }
            if (not self._projection.matches_snapshots(projection_snapshots)
                    or any(actor_id not in self._actor_ids
                           or self._additional_rows.get(actor_id, {}) != additional
                           for actor_id, additional, _revision, _source_revision, _bounded, _row in snapshots)):
                raise ValueError("hot_state_revision_conflict")
        return values

    def _row_for(self, actor_id: str) -> dict[str, object]:
        if actor_id not in self._actor_ids:
            raise KeyError(actor_id)
        return self._snapshot_for(actor_id)[0]

    @staticmethod
    def _validate_values(values: Mapping[str, object]) -> None:
        integer_fields = {"last_update_tick", "next_due_tick"}
        numeric_fields = {"fatigue", "need_pressure", "starvation_credit"}
        for key, value in values.items():
            if key in integer_fields and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError("hot_state_value_invalid")
            if key in numeric_fields and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not 0.0 <= float(value) <= 1.0
            ):
                raise ValueError("hot_state_value_invalid")
            if key == "activity_phase" and value not in {"morning", "afternoon", "evening", "night", "rest", "routine", "routine_work", "leisure"}:
                raise ValueError("hot_state_value_invalid")


class PopulationDueIndex:
    """可重建的最小到期堆；重复 schedule 通过版本令牌失效。"""

    def __init__(self) -> None:
        self._heap: list[tuple[int, str, str, int]] = []
        self._entries: dict[tuple[str, str], tuple[int, int, int]] = {}
        self._generation = 0

    def schedule(self, actor_id: str, obligation_id: str, due_tick: int, revision: int = 0) -> None:
        if due_tick < 0 or revision < 0:
            raise ValueError("population_due_invalid")
        key = (actor_id, obligation_id)
        existing = self._entries.get(key)
        if existing is not None and existing[0] == due_tick:
            # 到期点未变时仅刷新版本，不能每个窗口新增一份失效堆项。
            self._entries[key] = (due_tick, revision, existing[2])
            return
        self._generation += 1
        generation = self._generation
        self._entries[key] = (due_tick, revision, generation)
        heapq.heappush(self._heap, (due_tick, actor_id, obligation_id, generation))

    def cancel(self, actor_id: str, obligation_id: str) -> None:
        self._entries.pop((actor_id, obligation_id), None)

    def get(self, actor_id: str, obligation_id: str) -> tuple[int, int] | None:
        entry = self._entries.get((actor_id, obligation_id))
        return None if entry is None else entry[:2]

    def due_items(self, tick: int) -> tuple[tuple[str, str, int], ...]:
        if not self._heap or self._heap[0][0] > tick:
            return ()
        heap = list(self._heap)
        result: list[tuple[str, str, int]] = []
        while heap and heap[0][0] <= tick:
            due_tick, actor_id, obligation_id, generation = heapq.heappop(heap)
            current = self._entries.get((actor_id, obligation_id))
            if current is None or current[2] != generation:
                continue
            result.append((actor_id, obligation_id, due_tick))
        return tuple(result)

    def pop_due(
        self,
        tick: int,
        *,
        limit: int | None = None,
        obligation_id: str | None = None,
        actor_ids: frozenset[str] | None = None,
    ) -> tuple[tuple[str, str, int], ...]:
        if limit is not None and limit < 0:
            raise ValueError("population_due_limit_invalid")
        result: list[tuple[str, str, int]] = []
        preserved: list[tuple[int, str, str, int]] = []
        while self._heap and self._heap[0][0] <= tick and (limit is None or len(result) < limit):
            due_tick, actor_id, current_obligation_id, generation = heapq.heappop(self._heap)
            current = self._entries.get((actor_id, current_obligation_id))
            if current is None or current[2] != generation:
                continue
            if ((obligation_id is not None and current_obligation_id != obligation_id)
                    or (actor_ids is not None and actor_id not in actor_ids)):
                preserved.append((due_tick, actor_id, current_obligation_id, generation))
                continue
            self._entries.pop((actor_id, current_obligation_id), None)
            result.append((actor_id, current_obligation_id, due_tick))
        for item in preserved:
            heapq.heappush(self._heap, item)
        return tuple(result)

    def rebuild(self, entries: Iterable[tuple[str, str, int, int]]) -> None:
        self._heap.clear()
        self._entries.clear()
        self._generation = 0
        for actor_id, obligation_id, due_tick, revision in entries:
            self.schedule(actor_id, obligation_id, due_tick, revision)

    def export_entries(self) -> tuple[tuple[str, str, int, int], ...]:
        """导出当前有效任务；不序列化已失效堆项和内部 generation。"""
        return tuple((actor_id, obligation_id, entry[0], entry[1])
                     for (actor_id, obligation_id), entry in sorted(self._entries.items()))


__all__ = ["HOT_FIELDS", "HotStateReceipt", "PopulationHotState", "PopulationDueIndex", "get_starvation_credit_for_siming"]
