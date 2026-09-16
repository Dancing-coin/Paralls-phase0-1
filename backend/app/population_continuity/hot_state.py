from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import heapq
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
        self._columns: dict[str, list[object | None]] = {
            field: [] for field in sorted(self._allowed_fields)
        }
        self._revision: dict[str, int] = {}
        for actor_id in actor_ids:
            self._ensure_slot(actor_id)

    def register_fields(self, fields: Iterable[str]) -> None:
        """Register gameplay-package columns before batch updates use them."""
        normalized_fields = {str(field).strip() for field in fields}
        if any(not field for field in normalized_fields):
            raise ValueError("hot_state_field_invalid")
        added = normalized_fields.difference(self._allowed_fields)
        self._allowed_fields = self._allowed_fields.union(normalized_fields)
        for field in sorted(added):
            self._columns[field] = [None] * len(self._actor_by_slot)

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
        previous_revision = self._revision.get(actor_id, -1)
        if revision < previous_revision:
            raise ValueError("hot_state_revision_conflict")
        unknown = set(values).difference(self._allowed_fields)
        if unknown:
            raise ValueError("hot_state_field_not_allowed")
        slot = self._ensure_slot(actor_id)
        for field, value in values.items():
            self._columns[field][slot] = value
        self._revision[actor_id] = revision

    def read(self, actor_id: str) -> Mapping[str, object]:
        slot = self._slot_by_actor.get(actor_id)
        if slot is None or self._actor_by_slot[slot] is None:
            raise KeyError(actor_id)
        row = {
            field: values[slot]
            for field, values in self._columns.items()
            if values[slot] is not None
        }
        if actor_id in self._revision:
            row["revision"] = self._revision[actor_id]
        return row

    def remove(self, actor_id: str) -> None:
        slot = self._slot_by_actor.pop(actor_id, None)
        if slot is None:
            return
        self._actor_by_slot[slot] = None
        for values in self._columns.values():
            values[slot] = None
        self._revision.pop(actor_id, None)

    def due_actor_ids(self, tick: int) -> tuple[str, ...]:
        due: list[tuple[int, str]] = []
        for actor_id, slot in self._slot_by_actor.items():
            if self._actor_by_slot[slot] is None:
                continue
            due_tick = self._columns["next_due_tick"][slot]
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

    def export_rows(self) -> tuple[tuple[str, Mapping[str, object]], ...]:
        return tuple(
            (actor_id, self.read(actor_id))
            for actor_id in sorted(self._slot_by_actor)
            if self._actor_by_slot[self._slot_by_actor[actor_id]] is not None
        )

    def map_readonly(
        self,
        actor_ids: Iterable[str],
        evaluator,
        *,
        workers: int = 1,
    ) -> tuple[object, ...]:
        """并行只读计算；结果按 actor ID 合并，worker 不得写入任何 authority。"""
        ids = tuple(sorted(set(actor_ids)))
        if workers <= 1:
            values = [(actor_id, evaluator(actor_id, self.read(actor_id))) for actor_id in ids]
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    actor_id: pool.submit(evaluator, actor_id, self.read(actor_id))
                    for actor_id in ids
                }
                values = [(actor_id, futures[actor_id].result()) for actor_id in ids]
        return tuple(value for _, value in values)

    def _ensure_slot(self, actor_id: str) -> int:
        existing = self._slot_by_actor.get(actor_id)
        if existing is not None:
            return existing
        try:
            slot = self._actor_by_slot.index(None)
            self._actor_by_slot[slot] = actor_id
            for values in self._columns.values():
                values[slot] = None
        except ValueError:
            slot = len(self._actor_by_slot)
            self._actor_by_slot.append(actor_id)
            for values in self._columns.values():
                values.append(None)
        self._slot_by_actor[actor_id] = slot
        return slot


class PopulationDueIndex:
    """可重建的最小到期堆；重复 schedule 通过版本令牌失效。"""

    def __init__(self) -> None:
        self._heap: list[tuple[int, str, str, int]] = []
        self._tokens: dict[tuple[str, str], int] = {}

    def schedule(self, actor_id: str, obligation_id: str, due_tick: int, revision: int = 0) -> None:
        if due_tick < 0 or revision < 0:
            raise ValueError("population_due_invalid")
        key = (actor_id, obligation_id)
        self._tokens[key] = revision
        heapq.heappush(self._heap, (due_tick, actor_id, obligation_id, revision))

    def cancel(self, actor_id: str, obligation_id: str) -> None:
        self._tokens.pop((actor_id, obligation_id), None)

    def pop_due(self, tick: int) -> tuple[tuple[str, str, int], ...]:
        result: list[tuple[str, str, int]] = []
        while self._heap and self._heap[0][0] <= tick:
            due_tick, actor_id, obligation_id, revision = heapq.heappop(self._heap)
            if self._tokens.get((actor_id, obligation_id)) != revision:
                continue
            self._tokens.pop((actor_id, obligation_id), None)
            result.append((actor_id, obligation_id, due_tick))
        return tuple(result)


__all__ = ["HOT_FIELDS", "HotStateReceipt", "PopulationHotState", "PopulationDueIndex"]
