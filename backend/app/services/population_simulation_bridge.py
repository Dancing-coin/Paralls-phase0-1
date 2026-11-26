from __future__ import annotations

from collections import Counter
from typing import Any

from app.models.siming_runtime_state import GroupSimulationBranchSnapshot


class PopulationGroupSimulationBridge:
    """Read-only bridge from population hot projections into Siming."""

    def __init__(self, world_runtime: Any | None) -> None:
        self._world_runtime = world_runtime

    def summarize(self, *, room_id: str) -> GroupSimulationBranchSnapshot:
        if self._world_runtime is None:
            return GroupSimulationBranchSnapshot(status="unavailable", summary={"room_id": room_id})
        rows = tuple(self._world_runtime.export_rows())
        if not rows:
            return GroupSimulationBranchSnapshot(
                status="fresh",
                summary={
                    "mode": "live", "room_id": room_id, "actor_count": 0,
                    "avg_fatigue": 0.0, "avg_need_pressure": 0.0,
                    "phase_distribution": {}, "last_batch_tick": None,
                },
            )
        fatigue = [float(row.get("fatigue", 0.0)) for _actor, row in rows]
        pressure = [float(row.get("need_pressure", 0.0)) for _actor, row in rows]
        phases = Counter(str(row.get("activity_phase", "unknown")) for _actor, row in rows)
        confirmation = getattr(self._world_runtime, "latest_confirmation", None)
        return GroupSimulationBranchSnapshot(
            status="fresh",
            summary={
                "mode": "live", "room_id": room_id, "actor_count": len(rows),
                "avg_fatigue": round(sum(fatigue) / len(fatigue), 6),
                "avg_need_pressure": round(sum(pressure) / len(pressure), 6),
                "phase_distribution": dict(sorted(phases.items())),
                "last_batch_tick": getattr(confirmation, "window_end", None),
            },
        )


__all__ = ["PopulationGroupSimulationBridge"]
