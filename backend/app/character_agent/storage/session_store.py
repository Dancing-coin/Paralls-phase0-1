from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import tempfile
from threading import RLock
from uuid import uuid4


class CharacterAgentSessionStore:
    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._lock = RLock()
        self._runtime_id = uuid4().hex
        self._events_by_actor: dict[str, list[dict[str, object]]] = {}
        self._storage_path: Path | None = None
        self._actors_root: Path | None = None
        self._needs_actor_migration = False
        if storage_root is not None:
            root = Path(storage_root)
            root.mkdir(parents=True, exist_ok=True)
            self._storage_path = root / "character_agent_session_store.json"
            self._actors_root = root / "character_agent_session_store" / "actors"
            self._load()

    def append_event(
        self,
        actor_id: str,
        event_type: str,
        producer_ts: int,
        payload: dict[str, object],
        expected_revision: int | None = None,
    ) -> dict[str, object]:
        with self._lock:
            timeline = self._events_by_actor.setdefault(actor_id, [])
            if expected_revision is not None and expected_revision != len(timeline):
                raise ValueError("character_revision_conflict")
            event_index = len(timeline) + 1
            entry = {
                "event_id": f"{actor_id}:{event_type}:{producer_ts}:{self._runtime_id}:{event_index}",
                "event_index": event_index,
                "actor_id": actor_id,
                "event_type": event_type,
                "producer_ts": producer_ts,
                "payload": dict(payload),
            }
            timeline.append(entry)
            try:
                self._persist(actor_id, entry)
            except Exception:
                timeline.pop()
                raise
            return entry

    def list_events(self, actor_id: str) -> list[dict[str, object]]:
        with self._lock:
            return [dict(event) for event in self._events_by_actor.get(actor_id, [])]

    def event_count(self, actor_id: str) -> int:
        with self._lock:
            return len(self._events_by_actor.get(actor_id, []))

    def list_events_after(
        self, actor_id: str, event_count: int
    ) -> list[dict[str, object]]:
        with self._lock:
            return [
                dict(event)
                for event in self._events_by_actor.get(actor_id, [])[event_count:]
            ]

    def last_event(self, actor_id: str) -> dict[str, object] | None:
        with self._lock:
            events = self._events_by_actor.get(actor_id, [])
            return dict(events[-1]) if events else None

    def list_all_events(self) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            return {
                actor_id: [dict(event) for event in events]
                for actor_id, events in self._events_by_actor.items()
            }

    def actor_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._events_by_actor)

    def _load(self) -> None:
        if self._storage_path is None:
            return
        if self._storage_path.exists():
            raw = self._storage_path.read_text(encoding="utf-8").strip()
            if raw:
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    if self._actors_root is None or not self._actors_root.exists():
                        raise
                else:
                    if isinstance(payload, dict) and payload.get("schema_version") != 2:
                        for actor_id, events in payload.items():
                            if not isinstance(actor_id, str) or not isinstance(events, list):
                                continue
                            loaded_events = self._normalize_event_sequence(events)
                            if any(event["actor_id"] != actor_id for event in loaded_events):
                                raise ValueError("session_event_actor_mismatch")
                            self._events_by_actor[actor_id] = loaded_events
                        self._needs_actor_migration = True
        self._load_actor_files()

    def _load_actor_files(self) -> None:
        if self._actors_root is None or not self._actors_root.exists():
            return
        known_events = {
            actor_id: {str(event["event_id"]): event for event in events}
            for actor_id, events in self._events_by_actor.items()
        }
        for path in sorted(self._actors_root.glob("*.jsonl")):
            data = path.read_bytes()
            lines = data.splitlines(keepends=True)
            valid_size = 0
            truncated = False
            for index, raw_line in enumerate(lines):
                terminated = raw_line.endswith((b"\n", b"\r"))
                content = raw_line.rstrip(b"\r\n")
                try:
                    line = content.decode("utf-8")
                except UnicodeDecodeError:
                    if index == len(lines) - 1 and not terminated:
                        self._truncate_file(path, valid_size)
                        truncated = True
                        break
                    raise
                if not line.strip():
                    valid_size += len(raw_line)
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    if index == len(lines) - 1 and not terminated:
                        self._truncate_file(path, valid_size)
                        truncated = True
                        break
                    raise
                normalized = self._validate_event(event)
                actor_id = str(normalized["actor_id"])
                event_id = str(normalized["event_id"])
                if path != self._actor_storage_path(actor_id):
                    raise ValueError("session_event_actor_path_mismatch")
                actor_events = known_events.setdefault(actor_id, {})
                previous = actor_events.get(event_id)
                if previous is not None:
                    if previous != normalized:
                        raise ValueError("session_event_id_conflict")
                else:
                    if int(normalized["event_index"]) != len(
                        self._events_by_actor.get(actor_id, [])
                    ) + 1:
                        raise ValueError("session_event_index_gap")
                    self._events_by_actor.setdefault(actor_id, []).append(normalized)
                    actor_events[event_id] = normalized
                valid_size += len(raw_line)
            if data and not truncated and not data.endswith((b"\n", b"\r")):
                with path.open("ab") as stream:
                    stream.write(b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())

    def _actor_storage_path(self, actor_id: str) -> Path:
        if self._actors_root is None:
            raise RuntimeError("session_store_not_durable")
        digest = hashlib.sha256(actor_id.encode("utf-8")).hexdigest()
        return self._actors_root / f"{digest}.jsonl"

    def _persist(self, actor_id: str, entry: dict[str, object]) -> None:
        if self._storage_path is None or self._actors_root is None:
            return
        self._actors_root.mkdir(parents=True, exist_ok=True)
        if self._needs_actor_migration:
            for existing_actor, events in self._events_by_actor.items():
                path = self._actor_storage_path(existing_actor)
                events_to_write = events[:-1] if existing_actor == actor_id and events and events[-1] == entry else events
                self._replace_bytes(
                    path,
                    "".join(
                        json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
                        for event in events_to_write
                    ).encode("utf-8"),
                )
            self._write_schema_marker()
            self._needs_actor_migration = False
        elif not self._storage_path.exists():
            self._write_schema_marker()
        path = self._actor_storage_path(actor_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous_size = path.stat().st_size if path.exists() else 0
        try:
            data = (json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            try:
                with path.open("ab") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileNotFoundError:
                self._needs_actor_migration = True
                self._replace_bytes(
                    self._storage_path,
                    json.dumps(
                        self._events_by_actor,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                )
                return
        except Exception:
            if path.exists():
                with path.open("r+b") as stream:
                    stream.truncate(previous_size)
                    stream.flush()
                    os.fsync(stream.fileno())
            raise

    def _write_schema_marker(self) -> None:
        if self._storage_path is None:
            return
        self._replace_bytes(
            self._storage_path,
            json.dumps({"schema_version": 2}, separators=(",", ":")).encode("utf-8"),
        )

    @staticmethod
    def _replace_bytes(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=".tmp-",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_event(event: object) -> dict[str, object]:
        if not isinstance(event, dict):
            raise ValueError("session_event_invalid")
        required = {
            "event_id": str,
            "event_index": int,
            "actor_id": str,
            "event_type": str,
            "producer_ts": int,
            "payload": dict,
        }
        if any(
            key not in event
            or isinstance(event[key], bool)
            or not isinstance(event[key], expected_type)
            for key, expected_type in required.items()
        ):
            raise ValueError("session_event_invalid")
        if (
            not str(event["event_id"])
            or int(event["event_index"]) < 1
            or not str(event["actor_id"])
            or not str(event["event_type"])
        ):
            raise ValueError("session_event_invalid")
        return dict(event)

    @classmethod
    def _normalize_event_sequence(
        cls, events: list[object]
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        by_id: dict[str, dict[str, object]] = {}
        for raw_event in events:
            event = cls._validate_event(raw_event)
            event_id = str(event["event_id"])
            previous = by_id.get(event_id)
            if previous is not None:
                if previous != event:
                    raise ValueError("session_event_id_conflict")
                continue
            if int(event["event_index"]) != len(normalized) + 1:
                raise ValueError("session_event_index_gap")
            normalized.append(event)
            by_id[event_id] = event
        return normalized

    @staticmethod
    def _truncate_file(path: Path, size: int) -> None:
        with path.open("r+b") as stream:
            stream.truncate(size)
            stream.flush()
            os.fsync(stream.fileno())
