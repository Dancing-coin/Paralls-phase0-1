"""T4 的墙钟输入配方；窗口事件用于观测，不能调用 driver.tick 推进时间。"""
from dataclasses import dataclass
from heapq import merge
from itertools import count
from typing import Iterator
import asyncio
import math
from time import perf_counter


@dataclass(frozen=True)
class MixedLoadEvent:
    at_ms: int
    kind: str
    ordinal: int
    transaction_id: str
    window_index: int | None = None
    actor_indices: tuple[int, ...] = ()


class MixedLoadSchedule:
    """同 seed 重放相同配方；独立局必须使用不同 seed，隔离事务身份。"""

    def __init__(self, population: int, seed: int, mode: str) -> None:
        if type(population) is not int or population <= 0:
            raise ValueError("population must be a positive integer")
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if mode not in {"one_x", "ten_x"}:
            raise ValueError("mode must be one_x or ten_x")
        self.population, self.seed, self.mode = population, seed, mode
        self.window_ms = 1000 if mode == "one_x" else 100

    def _periodic(self, kind: str, period_ms: int, until_ms: int, *, first_ms: int | None = None) -> Iterator[MixedLoadEvent]:
        for ordinal, at_ms in zip(count(1), range(first_ms or period_ms, until_ms + 1, period_ms)):
            window = at_ms // self.window_ms if kind in {"window_due", "regular_due", "due_peak", "owner_contention"} else None
            actor_count = min(36, self.population) if kind == "regular_due" else min(self.population // 10, 100) if kind == "due_peak" else 0
            # 只选择当前有限 due 集合。fixture 负责合法 state 和预算，不能直接指定角色层级。
            start = (self.seed + (window or 0) * 36) % self.population
            actors = tuple((start + offset) % self.population for offset in range(actor_count))
            yield MixedLoadEvent(at_ms, kind, ordinal,
                f"mixed:{self.population}:{self.seed}:{self.mode}:{kind}:{ordinal}", window, actors)

    def events(self, duration_seconds: int) -> Iterator[MixedLoadEvent]:
        if type(duration_seconds) is not int or duration_seconds <= 0:
            raise ValueError("duration_seconds must be a positive integer")
        until = duration_seconds * 1000
        periods = {
            "window_due": self.window_ms,
            "regular_due": self.window_ms,
            "due_peak": 300 * self.window_ms,
            "owner_contention": 60 * self.window_ms,
            "health": 500, "ws_read": 1000, "fact": 2000, "interaction": 5000,
            "character_model": 60_000, "siming_model": 60_000,
        }
        streams = [self._periodic(kind, period, until) for kind, period in periods.items()]
        # 故障按真实分钟重复；短测不压缩这些时点来冒充长测。
        faults = {
            "provider_timeout": 300_000,
            "slow_consumer": 600_000, "resume_consumer": 605_000,
            "disconnect": 900_000, "reconnect": 902_000,
            "sqlite_busy": 1_200_000, "sqlite_release": 1_202_000,
        }
        streams.extend(self._periodic(kind, 1_800_000, until, first_ms=first) for kind, first in faults.items())

        def order(event: MixedLoadEvent):
            # 同一时刻先装配故障和合法 due，再发送外部请求；不依赖线程竞态决定配方。
            priority = 0 if event.kind in faults else 1 if event.kind in {"regular_due", "due_peak"} else 2
            return event.at_ms, priority, event.kind

        yield from merge(*streams, key=order)


class MixedLoadRunner:
    """按绝对墙钟驱动已装配的真实入口；handler 完成不等于 authority 提交。"""

    def __init__(self, handlers: dict, *, capacity: int = 128, drain_seconds: float = 30) -> None:
        if not handlers or any(not callable(handler) for handler in handlers.values()):
            raise ValueError("mixed_load_handlers_required")
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError("mixed_load_capacity_invalid")
        if type(drain_seconds) not in (int, float) or not math.isfinite(drain_seconds) or drain_seconds <= 0:
            raise ValueError("mixed_load_drain_invalid")
        self.handlers, self.capacity, self.drain_seconds = dict(handlers), capacity, drain_seconds

    async def run(self, duration_seconds: int, schedule: MixedLoadSchedule, *, origin: float | None = None) -> dict:
        from scripts.verification.verify_population_service_isolation import until

        if type(duration_seconds) is not int or duration_seconds <= 0:
            raise ValueError("mixed_load_duration_invalid")
        origin = perf_counter() if origin is None else origin
        if type(origin) not in (int, float) or not math.isfinite(origin) or origin <= 0:
            raise ValueError("mixed_load_origin_invalid")
        pending, rows, peak = set(), [], 0

        async def invoke(event, row):
            row["issued_at"] = perf_counter()
            try:
                row["result"] = await self.handlers[event.kind](event)
                if row["status"] != "drain_timeout":
                    row["status"] = "handler_finished"
            except asyncio.CancelledError:
                if row["status"] != "drain_timeout":
                    row["status"] = "cancelled"
                raise
            except Exception as error:
                # 只留异常类型，网络错误正文可能含 URL 凭据或模型内容。
                row["error"] = type(error).__name__
                if row["status"] != "drain_timeout":
                    row["status"] = "handler_failed"
            finally:
                row["finished_at"] = perf_counter()

        try:
            for event in schedule.events(duration_seconds):
                if event.kind not in self.handlers:
                    continue
                expected = origin + event.at_ms / 1000
                await until(expected)
                row = dict(key=event.transaction_id, kind=event.kind, ordinal=event.ordinal,
                           expected_at=expected, offered_at=perf_counter(), status="pending")
                rows.append(row)
                if len(pending) >= self.capacity:
                    row["status"] = "capacity_exhausted"
                    continue
                task = asyncio.create_task(invoke(event, row))
                pending.add(task)
                task.add_done_callback(pending.discard)
                peak = max(peak, len(pending))
            await until(origin + duration_seconds)
            if pending:
                _, unfinished = await asyncio.wait(tuple(pending), timeout=self.drain_seconds)
                if unfinished:
                    for row in rows:
                        if row["status"] == "pending":
                            row["status"] = "drain_timeout"
        finally:
            remaining = tuple(pending)
            for task in remaining:
                task.cancel()
            if remaining:
                await asyncio.gather(*remaining, return_exceptions=True)
        if not rows:
            raise ValueError("mixed_load_no_matching_events")
        return dict(origin=origin, load_end=origin + duration_seconds, finished_at=perf_counter(),
                    offered=len(rows), dispatched=sum("issued_at" in row for row in rows),
                    failed=sum(row["status"] != "handler_finished" for row in rows),
                    peak_in_flight=peak, requests=rows)
