from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import heapq
from threading import RLock
from types import MappingProxyType
from typing import Iterable, Mapping


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
        additional_fields: Iterable[str] = (),
    ) -> None:
        normalized_fields = {str(field).strip() for field in additional_fields}
        if any(not field for field in normalized_fields):
            raise ValueError("hot_state_field_invalid")
        self._allowed_fields = HOT_FIELDS.union(normalized_fields)
        self._slot_by_actor: dict[str, int] = {}
        self._actor_by_slot: list[str | None] = []
        self._rows: list[dict[str, object] | None] = []
        self._revision: dict[str, int] = {}
        self._generation_by_actor: dict[str, int] = {}
        self._next_generation = 0
        self._free_slots: list[int] = []
        self._lock = RLock()
        for actor_id in actor_ids:
            self._ensure_slot(actor_id)

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
        if isinstance(revision, bool) or revision < 0:
            raise ValueError("hot_state_revision_invalid")
        unknown = set(values).difference(self._allowed_fields)
        if unknown:
            raise ValueError("hot_state_field_not_allowed")
        self._validate_values(values)
        with self._lock:
            previous_revision = self._revision.get(actor_id, -1)
            if revision < previous_revision:
                raise ValueError("hot_state_revision_conflict")
            slot = self._ensure_slot(actor_id)
            row = dict(self._rows[slot] or self._default_row())
            changed = any(row.get(key) != value for key, value in values.items())
            if revision == previous_revision and changed:
                raise ValueError("hot_state_revision_conflict")
            row.update(values)
            row["revision"] = revision
            self._rows[slot] = row
            self._revision[actor_id] = revision

    def read(self, actor_id: str) -> Mapping[str, object]:
        with self._lock:
            slot = self._slot_by_actor.get(actor_id)
            if slot is None or self._rows[slot] is None:
                raise KeyError(actor_id)
            return _ReadOnlyRow(self._rows[slot] or {})

    def remove(self, actor_id: str) -> None:
        with self._lock:
            slot = self._slot_by_actor.pop(actor_id, None)
            if slot is None:
                return
            self._actor_by_slot[slot] = None
            self._rows[slot] = None
            self._revision.pop(actor_id, None)
            self._generation_by_actor.pop(actor_id, None)
            heapq.heappush(self._free_slots, slot)

    def due_actor_ids(self, tick: int) -> tuple[str, ...]:
        due: list[tuple[int, str]] = []
        with self._lock:
            for actor_id, slot in self._slot_by_actor.items():
                row = self._rows[slot]
                if row is None:
                    continue
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
                receipts.append(HotStateReceipt(actor_id, f"rejected:{exc}", self._revision.get(actor_id, 0)))
            else:
                receipts.append(HotStateReceipt(actor_id, "committed", revision))
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
            prepared: list[tuple[str, int, dict[str, object], int]] = []
            for actor_id, values, expected_revision, revision in pending:
                slot = self._slot_by_actor.get(actor_id)
                if slot is None or self._rows[slot] is None:
                    raise ValueError("hot_state_actor_missing")
                copied_values = dict(values)
                fields = set(copied_values)
                if fields.difference(self._allowed_fields):
                    raise ValueError("hot_state_field_not_allowed")
                self._validate_values(copied_values)
                current = self._revision.get(actor_id, 0)
                if current != expected_revision or revision != expected_revision + 1:
                    raise ValueError("hot_state_revision_conflict")
                if len(copied_values) == len(HOT_FIELDS):
                    row = copied_values
                else:
                    row = dict(self._rows[slot] or self._default_row())
                    row.update(copied_values)
                row["revision"] = revision
                prepared.append((actor_id, slot, row, revision))
            for actor_id, slot, row, revision in prepared:
                self._rows[slot] = row
                self._revision[actor_id] = revision

    def export_rows(self) -> tuple[tuple[str, Mapping[str, object]], ...]:
        with self._lock:
            return tuple(
                (actor_id, _ReadOnlyRow(self._rows[slot] or {}))
                for actor_id, slot in sorted(self._slot_by_actor.items())
                if self._rows[slot] is not None
            )

    def map_readonly(
        self,
        actor_ids: Iterable[str],
        evaluator,
        *,
        workers: int = 1,
        batch_size: int = 256,
    ) -> tuple[object, ...]:
        """并行只读计算；结果按 actor ID 合并，worker 不得写入任何 authority。"""
        if workers < 1 or batch_size < 1:
            raise ValueError("hot_state_parallelism_invalid")
        ids = tuple(sorted(set(actor_ids)))
        with self._lock:
            snapshots = tuple(
                (
                    actor_id,
                    self._revision.get(actor_id, 0),
                    self._generation_by_actor[actor_id],
                    MappingProxyType(self._row_for(actor_id)),
                )
                for actor_id in ids
            )

        def evaluate_batch(batch):
            return tuple(
                evaluator(actor_id, row)
                for actor_id, _revision, _generation, row in batch
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
            if any(
                actor_id not in self._slot_by_actor
                or self._revision.get(actor_id, 0) != revision
                or self._generation_by_actor.get(actor_id) != generation
                for actor_id, revision, generation, _row in snapshots
            ):
                raise ValueError("hot_state_revision_conflict")
        return values

    def _ensure_slot(self, actor_id: str) -> int:
        existing = self._slot_by_actor.get(actor_id)
        if existing is not None:
            return existing
        if self._free_slots:
            slot = heapq.heappop(self._free_slots)
            self._actor_by_slot[slot] = actor_id
            self._rows[slot] = self._default_row()
        else:
            slot = len(self._actor_by_slot)
            self._actor_by_slot.append(actor_id)
            self._rows.append(self._default_row())
        self._slot_by_actor[actor_id] = slot
        self._next_generation += 1
        self._generation_by_actor[actor_id] = self._next_generation
        return slot

    def _row_for(self, actor_id: str) -> dict[str, object]:
        slot = self._slot_by_actor.get(actor_id)
        if slot is None or self._rows[slot] is None:
            raise KeyError(actor_id)
        return self._rows[slot] or self._default_row()

    @staticmethod
    def _default_row() -> dict[str, object]:
        return {
            "last_update_tick": 0,
            "activity_phase": "rest",
            "fatigue": 0.2,
            "need_pressure": 0.1,
            "next_due_tick": 21_600,
            "starvation_credit": 0.0,
            "revision": 0,
        }

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
            if key == "activity_phase" and value not in {"rest", "routine", "routine_work", "leisure"}:
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
            if obligation_id is not None and current_obligation_id != obligation_id:
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


__all__ = ["HOT_FIELDS", "HotStateReceipt", "PopulationHotState", "PopulationDueIndex"]
