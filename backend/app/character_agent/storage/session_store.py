from __future__ import annotations

import json
import hashlib
from pathlib import Path
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
                try:
                    self._persist(actor_id, entry)
                except TypeError:
                    # 保留旧测试/注入点的无参 persist 约定；真实实现的 TypeError 继续上抛。
                    if getattr(self._persist, "__self__", None) is not None:
                        raise
                    self._persist()
            except Exception:
                timeline.pop()
                raise
            return entry

    def list_events(self, actor_id: str) -> list[dict[str, object]]:
        with self._lock:
            return [dict(event) for event in self._events_by_actor.get(actor_id, [])]

    def list_all_events(self) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            return {
                actor_id: [dict(event) for event in events]
                for actor_id, events in self._events_by_actor.items()
            }

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        raw = self._storage_path.read_text(encoding="utf-8").strip()
        if raw:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("schema_version") == 2:
                self._load_actor_files()
                return
            if isinstance(payload, dict):
                loaded: dict[str, list[dict[str, object]]] = {}
                for actor_id, events in payload.items():
                    if not isinstance(actor_id, str) or not isinstance(events, list):
                        continue
                    loaded[actor_id] = [dict(event) for event in events if isinstance(event, dict)]
                self._events_by_actor = loaded
                self._needs_actor_migration = True
        self._load_actor_files()

    def _load_actor_files(self) -> None:
        if self._actors_root is None or not self._actors_root.exists():
            return
        for path in sorted(self._actors_root.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                actor_id = event.get("actor_id") if isinstance(event, dict) else None
                if isinstance(actor_id, str) and isinstance(event, dict):
                    self._events_by_actor.setdefault(actor_id, []).append(dict(event))

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
                path.write_text(
                    "".join(
                        json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
                        for event in events_to_write
                    ),
                    encoding="utf-8",
                )
            self._needs_actor_migration = False
        path = self._actor_storage_path(actor_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous_size = path.stat().st_size if path.exists() else 0
        try:
            data = (json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            try:
                with path.open("ab") as stream:
                    stream.write(data)
            except FileNotFoundError:
                # 外部运行时可能替换临时 storage root；保留可恢复的旧 JSON 快照作为降级锚点。
                self._needs_actor_migration = True
                self._storage_path.write_text(
                    json.dumps(self._events_by_actor, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                return
            self._storage_path.write_text(
                json.dumps({"schema_version": 2}, separators=(",", ":")),
                encoding="utf-8",
            )
        except Exception:
            if path.exists():
                with path.open("r+b") as stream:
                    stream.truncate(previous_size)
            raise
