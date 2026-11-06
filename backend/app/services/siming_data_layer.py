"""Persistence and cache naming for the Phase-1 Siming data layer.

Two gaps motivated this module.  First, ``FairnessStateSnapshot``,
``InterventionCandidate`` and ``InterventionDecision`` were emitted as outputs and
never written anywhere, so a cycle could not be inspected after the fact.  Second,
cache keys had no single definition, so any future cache would have invented its
own spelling.

The cache here is deliberately in-process.  The spec places hot keys in Redis and
states they are never a replay source; until Redis exists, keeping the same key
vocabulary in a process-local store preserves the contract without pretending a
durability guarantee we cannot make.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable

from app.models.siming_event import (
    FairnessStateSnapshot,
    InterventionCandidate,
    InterventionDecision,
)

CACHE_KEY_PREFIX = "paralls:siming:"

# The six persistent tables the spec freezes.  Names are part of the contract.
TABLE_FAIRNESS_SNAPSHOTS = "siming_fairness_snapshots"
TABLE_INTERVENTION_CANDIDATES = "siming_intervention_candidates"
TABLE_INTERVENTION_DECISIONS = "siming_intervention_decisions"
TABLE_INTERVENTION_AUDITS = "siming_intervention_audits"
TABLE_CHECKPOINTS = "siming_checkpoints"
TABLE_NARRATIVE_READ_MODELS = "siming_narrative_read_models"

TABLE_NAMES: tuple[str, ...] = (
    TABLE_FAIRNESS_SNAPSHOTS,
    TABLE_INTERVENTION_CANDIDATES,
    TABLE_INTERVENTION_DECISIONS,
    TABLE_INTERVENTION_AUDITS,
    TABLE_CHECKPOINTS,
    TABLE_NARRATIVE_READ_MODELS,
)

# Every table is room-scoped: the spec makes room isolation a core principle, so
# the index leads with room_id on the query path (room + tick).
_SCHEMA: tuple[str, ...] = tuple(
    f"CREATE TABLE IF NOT EXISTS {table} ("
    "sequence INTEGER PRIMARY KEY, "
    "id TEXT NOT NULL, "
    "room_id TEXT NOT NULL, "
    "sim_tick_ts INTEGER NOT NULL, "
    "world_ts INTEGER NOT NULL, "
    "payload TEXT NOT NULL, "
    "UNIQUE(room_id, id))"
    for table in TABLE_NAMES
) + tuple(
    f"CREATE INDEX IF NOT EXISTS {table}_room_tick "
    f"ON {table}(room_id, sim_tick_ts DESC, world_ts DESC)"
    for table in TABLE_NAMES
)

# The five hot key families the spec freezes.
def fairness_latest_key(room_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}room:{room_id}:fairness:latest"


def fairness_snapshot_key(room_id: str, snapshot_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}room:{room_id}:fairness:snapshot:{snapshot_id}"


def cooldown_state_key(room_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}room:{room_id}:cooldown:state"


def readmodel_latest_key(room_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}room:{room_id}:readmodel:latest"


def decision_recent_key(room_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}room:{room_id}:decision:recent"


def auditor_latest_key(room_id: str, auditor_name: str) -> str:
    return f"{CACHE_KEY_PREFIX}room:{room_id}:auditor:{auditor_name}:latest"


def orchestrator_working_set_key(room_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}room:{room_id}:orchestrator:working_set"


class SimingDataLayer:
    """Room-scoped persistence for the three previously-ephemeral objects."""

    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        try:
            with self._connection:
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA synchronous=FULL")
                for statement in _SCHEMA:
                    self._connection.execute(statement)
        except BaseException:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def _put(
        self,
        table: str,
        *,
        identifier: str,
        room_id: str,
        sim_tick_ts: int,
        world_ts: int,
        payload: str,
    ) -> None:
        with self._connection:
            self._connection.execute(
                f"INSERT INTO {table}(id,room_id,sim_tick_ts,world_ts,payload) "
                "VALUES (?,?,?,?,?) ON CONFLICT(room_id,id) DO UPDATE SET "
                "sim_tick_ts=excluded.sim_tick_ts, world_ts=excluded.world_ts, "
                "payload=excluded.payload",
                (identifier, room_id, sim_tick_ts, world_ts, payload),
            )

    def save_snapshot(self, snapshot: FairnessStateSnapshot, *, sim_tick_ts: int, world_ts: int) -> None:
        self._put(
            TABLE_FAIRNESS_SNAPSHOTS,
            identifier=snapshot.snapshot_id,
            room_id=snapshot.room_id,
            sim_tick_ts=sim_tick_ts,
            world_ts=world_ts,
            payload=snapshot.model_dump_json(),
        )

    def save_candidate(
        self, candidate: InterventionCandidate, *, room_id: str, sim_tick_ts: int, world_ts: int
    ) -> None:
        self._put(
            TABLE_INTERVENTION_CANDIDATES,
            identifier=candidate.candidate_id,
            room_id=room_id,
            sim_tick_ts=sim_tick_ts,
            world_ts=world_ts,
            payload=candidate.model_dump_json(),
        )

    def save_decision(
        self, decision: InterventionDecision, *, room_id: str, sim_tick_ts: int, world_ts: int
    ) -> None:
        self._put(
            TABLE_INTERVENTION_DECISIONS,
            identifier=decision.decision_id,
            room_id=room_id,
            sim_tick_ts=sim_tick_ts,
            world_ts=world_ts,
            payload=decision.model_dump_json(),
        )

    def latest_snapshot(self, room_id: str) -> FairnessStateSnapshot | None:
        row = self._connection.execute(
            f"SELECT payload FROM {TABLE_FAIRNESS_SNAPSHOTS} "
            "WHERE room_id=? ORDER BY sim_tick_ts DESC, world_ts DESC, sequence DESC LIMIT 1",
            (room_id,),
        ).fetchone()
        return FairnessStateSnapshot.model_validate_json(row[0]) if row else None

    def decisions_for_room(self, room_id: str) -> list[InterventionDecision]:
        rows = self._connection.execute(
            f"SELECT payload FROM {TABLE_INTERVENTION_DECISIONS} "
            "WHERE room_id=? ORDER BY sim_tick_ts, world_ts, sequence",
            (room_id,),
        ).fetchall()
        return [InterventionDecision.model_validate_json(row[0]) for row in rows]


class SimingHotCache:
    """Process-local stand-in for the Redis hot keys.

    Explicitly **not** a replay source: entries expire and are never consulted to
    reconstruct history, only to serve the latest value cheaply.
    """

    def __init__(self, *, clock=time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[str, float | None]] = {}

    def put(self, key: str, value: object, *, ttl_seconds: float | None = None) -> None:
        encoded = json.dumps(value, sort_keys=True, default=str)
        expires_at = None if ttl_seconds is None else self._clock() + ttl_seconds
        self._entries[key] = (encoded, expires_at)

    def get(self, key: str) -> object | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        encoded, expires_at = entry
        if expires_at is not None and self._clock() >= expires_at:
            self._entries.pop(key, None)
            return None
        return json.loads(encoded)

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)

    def keys(self) -> Iterable[str]:
        return tuple(self._entries)
