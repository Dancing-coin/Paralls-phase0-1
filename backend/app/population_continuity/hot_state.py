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

    def __init__(self, actor_ids: Iterable[str] = ()) -> None:
        self._slot_by_actor: dict[str, int] = {}
        self._actor_by_slot: list[str | None] = []
        self._rows: list[dict[str, object] | None] = []
        self._revision: dict[str, int] = {}
        for actor_id in actor_ids:
            self._ensure_slot(actor_id)

    def upsert(self, actor_id: str, values: Mapping[str, object], revision: int) -> None:
        if not actor_id:
            raise ValueError("hot_state_actor_required")
        if isinstance(revision, bool) or revision < 0:
            raise ValueError("hot_state_revision_invalid")
        previous_revision = self._revision.get(actor_id, -1)
        if revision < previous_revision:
            raise ValueError("hot_state_revision_conflict")
        unknown = set(values).difference(HOT_FIELDS)
        if unknown:
            raise ValueError("hot_state_field_not_allowed")
        slot = self._ensure_slot(actor_id)
        row = dict(self._rows[slot] or {})
        row.update(values)
        row["revision"] = revision
        self._rows[slot] = row
        self._revision[actor_id] = revision

    def read(self, actor_id: str) -> Mapping[str, object]:
        slot = self._slot_by_actor.get(actor_id)
        if slot is None or self._rows[slot] is None:
            raise KeyError(actor_id)
        return dict(self._rows[slot] or {})

    def remove(self, actor_id: str) -> None:
        slot = self._slot_by_actor.pop(actor_id, None)
        if slot is None:
            return
        self._actor_by_slot[slot] = None
        self._rows[slot] = None
        self._revision.pop(actor_id, None)

    def due_actor_ids(self, tick: int) -> tuple[str, ...]:
        due: list[tuple[int, str]] = []
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

    def export_rows(self) -> tuple[tuple[str, Mapping[str, object]], ...]:
        return tuple(
            (actor_id, self.read(actor_id))
            for actor_id in sorted(self._slot_by_actor)
            if self._rows[self._slot_by_actor[actor_id]] is not None
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
            self._rows[slot] = {}
        except ValueError:
            slot = len(self._actor_by_slot)
            self._actor_by_slot.append(actor_id)
            self._rows.append({})
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
