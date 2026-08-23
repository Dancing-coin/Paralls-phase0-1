from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from uuid import uuid4


class CharacterAgentSessionStore:
    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._lock = RLock()
        self._runtime_id = uuid4().hex
        self._events_by_actor: dict[str, list[dict[str, object]]] = {}
        self._storage_path: Path | None = None
        if storage_root is not None:
            root = Path(storage_root)
            root.mkdir(parents=True, exist_ok=True)
            self._storage_path = root / "character_agent_session_store.json"
            self._load()

    def append_event(
        self,
        actor_id: str,
        event_type: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> dict[str, object]:
        with self._lock:
            timeline = self._events_by_actor.setdefault(actor_id, [])
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
            self._persist()
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
        if not raw:
            return
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return
        loaded: dict[str, list[dict[str, object]]] = {}
        for actor_id, events in payload.items():
            if not isinstance(actor_id, str) or not isinstance(events, list):
                continue
            loaded[actor_id] = [dict(event) for event in events if isinstance(event, dict)]
        self._events_by_actor = loaded

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        payload = json.dumps(
            self._events_by_actor,
            ensure_ascii=False,
            indent=2,
        )
        temporary_path = self._storage_path.with_suffix(
            self._storage_path.suffix + ".tmp"
        )
        temporary_path.write_text(
            payload,
            encoding="utf-8",
        )
        temporary_path.replace(self._storage_path)
