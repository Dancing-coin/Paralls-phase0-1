from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock

from app.models.harness_execution import CapabilityGrant


class HarnessCapabilityStore:
    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(str(self._path), check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def issue(self, grant: CapabilityGrant) -> CapabilityGrant:
        with self._lock:
            existing = self._connection.execute(
                "SELECT grant_json FROM harness_capabilities WHERE grant_id = ?",
                (grant.grant_id,),
            ).fetchone()
            if existing is not None:
                prior = CapabilityGrant.model_validate_json(existing[0])
                if prior != grant:
                    raise ValueError("capability_identity_conflict")
                return prior
            with self._connection:
                self._connection.execute(
                    "INSERT INTO harness_capabilities(grant_id, task_id, phase, state, grant_json) VALUES (?, ?, ?, ?, ?)",
                    (grant.grant_id, grant.task_id, grant.phase, grant.state, self._dump(grant)),
                )
            return grant.model_copy(deep=True)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def consume(
        self,
        *,
        grant_id: str,
        principal_ref: str,
        task_id: str,
        phase: str,
        policy_revision: str,
        correlation_id: str,
        now: int,
    ) -> CapabilityGrant:
        del correlation_id
        with self._lock:
            row = self._connection.execute(
                "SELECT grant_json FROM harness_capabilities WHERE grant_id = ?",
                (grant_id,),
            ).fetchone()
            if row is None:
                raise ValueError("capability_unknown")
            grant = CapabilityGrant.model_validate_json(row[0])
            if grant.state != "issued":
                raise ValueError("capability_already_consumed")
            if grant.expires_at <= now:
                self._set_state(grant, "expired")
                raise ValueError("capability_expired")
            if grant.principal_ref != principal_ref or grant.task_id != task_id:
                raise ValueError("capability_scope_denied")
            if grant.phase != phase or grant.policy_revision != policy_revision:
                raise ValueError("capability_revision_mismatch")
            consumed = grant.model_copy(update={"state": "consumed"}, deep=True)
            with self._connection:
                result = self._connection.execute(
                    "UPDATE harness_capabilities SET state = ?, grant_json = ? WHERE grant_id = ? AND state = 'issued'",
                    (consumed.state, self._dump(consumed), grant_id),
                )
                if result.rowcount != 1:
                    raise ValueError("capability_already_consumed")
            return consumed

    def read(self, grant_id: str) -> CapabilityGrant:
        row = self._connection.execute(
            "SELECT grant_json FROM harness_capabilities WHERE grant_id = ?",
            (grant_id,),
        ).fetchone()
        if row is None:
            raise ValueError("capability_unknown")
        return CapabilityGrant.model_validate_json(row[0])

    def delete_task(self, task_id: str) -> None:
        """Clear grants for a task that is rebuilt after authority loss."""
        with self._lock:
            with self._connection:
                self._connection.execute(
                    "DELETE FROM harness_capabilities WHERE task_id = ?",
                    (task_id,),
                )

    def _set_state(self, grant: CapabilityGrant, state: str) -> None:
        updated = grant.model_copy(update={"state": state}, deep=True)
        with self._connection:
            self._connection.execute(
                "UPDATE harness_capabilities SET state = ?, grant_json = ? WHERE grant_id = ? AND state = 'issued'",
                (state, self._dump(updated), grant.grant_id),
            )

    def _migrate(self) -> None:
        with self._connection:
            self._connection.execute("CREATE TABLE IF NOT EXISTS harness_capability_schema(version INTEGER PRIMARY KEY)")
            versions = [row[0] for row in self._connection.execute("SELECT version FROM harness_capability_schema")]
            if versions and versions != [self.SCHEMA_VERSION]:
                raise ValueError(f"unsupported harness capability schema: {versions}")
            if not versions:
                self._connection.execute("INSERT INTO harness_capability_schema(version) VALUES (?)", (self.SCHEMA_VERSION,))
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS harness_capabilities(grant_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, phase TEXT NOT NULL, state TEXT NOT NULL, grant_json TEXT NOT NULL)"
            )

    @staticmethod
    def _dump(value: object) -> str:
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = ["HarnessCapabilityStore"]
