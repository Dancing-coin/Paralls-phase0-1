from __future__ import annotations

import json
from pathlib import Path

from app.character_agent.memory.episodic_memory import CharacterEpisodicMemory
from app.character_agent.memory.relational_memory import CharacterRelationalMemory
from app.character_agent.memory.working_memory import CharacterWorkingMemory
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState


class CharacterAgentMemoryStore:
    _SUMMARY_VALUE_CHARS = 240

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._working = CharacterWorkingMemory()
        self._episodic = CharacterEpisodicMemory()
        self._relational = CharacterRelationalMemory()
        self._events_by_actor: dict[str, list[dict[str, object]]] = {}
        self._storage_path: Path | None = None
        if storage_root is not None:
            root = Path(storage_root)
            root.mkdir(parents=True, exist_ok=True)
            self._storage_path = root / "character_agent_memory_store.json"
            self._load()

    def write_event(self, event: dict[str, object]) -> None:
        actor_id = str(event.get("actor_id", "") or "")
        if actor_id == "":
            return
        stored_event = dict(event)
        self._events_by_actor.setdefault(actor_id, []).append(stored_event)
        self._ingest_event(stored_event)
        self._persist()

    def _ingest_event(self, event: dict[str, object]) -> None:
        actor_id = str(event.get("actor_id", "") or "")
        if actor_id == "":
            return
        self._working.remember_event(actor_id, self._sanitize_working_memory_event(event))

        event_type = str(event.get("event_type", "") or "")
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        if event_type == "character_perceived_event":
            self._episodic.remember(
                actor_id=actor_id,
                summary=str(payload.get("summary", "") or ""),
                tags=[str(tag) for tag in payload.get("tags", [])] if isinstance(payload.get("tags", []), list) else [],
                source_event_id=str(event.get("event_id", "") or ""),
                producer_ts=int(event.get("producer_ts", 0) or 0),
            )
        elif event_type == "character_agent_settlement_result":
            settlement_summary = (
                str(payload.get("change_summary", "") or "").strip()
                or str(payload.get("constraint_summary", "") or "").strip()
                or str(payload.get("stable_state_summary", "") or "").strip()
                or str(payload.get("result_type", "") or "").strip()
            )
            self._episodic.remember(
                actor_id=actor_id,
                summary=settlement_summary,
                tags=["settlement"],
                source_event_id=str(event.get("event_id", "") or ""),
                producer_ts=int(event.get("producer_ts", 0) or 0),
            )
        elif event_type == "character_agent_dialogue_response":
            dialogue_summary = str(payload.get("content", "") or payload.get("summary", "") or "").strip()
            self._episodic.remember(
                actor_id=actor_id,
                summary=f"dialogue_response:{dialogue_summary}" if dialogue_summary else "dialogue_response",
                tags=["dialogue"],
                source_event_id=str(event.get("event_id", "") or ""),
                producer_ts=int(event.get("producer_ts", 0) or 0),
            )
        elif event_type == "relational_belief_event":
            self._relational.upsert_belief(
                actor_id=actor_id,
                entity_id=str(payload.get("entity_id", "") or ""),
                belief_type=str(payload.get("belief_type", "") or ""),
                value=str(payload.get("value", "") or ""),
                source_event_id=str(event.get("event_id", "") or ""),
                producer_ts=int(event.get("producer_ts", 0) or 0),
            )

    def retrieval_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
        return {
            "working_memory": self._working.recall(actor_id),
            "episodic_memories": self._episodic.recall(actor_id),
            "relational_memories": self._relational.recall(actor_id),
        }

    def working_memory_state(
        self,
        actor_id: str,
        private_snapshot: dict[str, object] | None = None,
    ) -> CharacterWorkingMemoryState:
        return self._working.build_state(actor_id, private_snapshot=private_snapshot)

    def _sanitize_working_memory_event(self, event: dict[str, object]) -> dict[str, object]:
        stored = dict(event)
        payload = stored.get("payload", {})
        if not isinstance(payload, dict):
            return stored
        event_type = str(stored.get("event_type", "") or "")
        if event_type == "l2_reasoning_request":
            context = payload.get("context", {})
            if isinstance(context, dict):
                stored["payload"] = {
                    "task_kind": str(payload.get("task_kind", "") or ""),
                    "actor_id": str(context.get("actor_id", "") or ""),
                    "control_mode": str(context.get("control_mode", "") or ""),
                    "snapshot_summary": self._snapshot_summary(context.get("snapshot", {})),
                    "memory_summary": self._memory_summary(context.get("memory", {})),
                    "event_summary": self._event_summary(context.get("event", {})),
                }
        return stored

    def _snapshot_summary(self, snapshot: object) -> dict[str, object]:
        snapshot_dict = snapshot if isinstance(snapshot, dict) else {}
        return {
            "visible_entities_count": self._count_of(snapshot_dict.get("visible_entities")),
            "audible_entities_count": self._count_of(snapshot_dict.get("audible_entities")),
            "attention_targets_count": self._count_of(snapshot_dict.get("attention_targets")),
            "focus_target": self._truncate(snapshot_dict.get("current_focus_target", "") or snapshot_dict.get("attention_target", "")),
        }

    def _memory_summary(self, memory: object) -> dict[str, object]:
        memory_dict = memory if isinstance(memory, dict) else {}
        return {
            "working_memory_count": self._count_of(memory_dict.get("working_memory")),
            "episodic_memories_count": self._count_of(memory_dict.get("episodic_memories")),
            "relational_memories_count": self._count_of(memory_dict.get("relational_memories")),
            "working_memory_sample": self._sample_summary(memory_dict.get("working_memory")),
            "episodic_memory_sample": self._sample_summary(memory_dict.get("episodic_memories")),
            "relational_memory_sample": self._sample_summary(memory_dict.get("relational_memories")),
        }

    def _event_summary(self, event: object) -> dict[str, object]:
        event_dict = event if isinstance(event, dict) else {}
        return {
            "event_type": self._truncate(event_dict.get("event_type", "") or event_dict.get("intent_type", "") or event_dict.get("body_state_class", "")),
            "summary": self._truncate(event_dict.get("perceived_summary", "") or event_dict.get("summary", "") or event_dict.get("interaction_type", "")),
            "source_ref": self._truncate(
                event_dict.get("source_candidate_event_id", "")
                or event_dict.get("source_body_result_id", "")
                or event_dict.get("request_id", "")
            ),
        }

    def _sample_summary(self, value: object) -> str:
        if not isinstance(value, list) or not value:
            return ""
        first = value[0]
        if isinstance(first, dict):
            return self._truncate(first.get("summary", "") or first.get("event_type", "") or first.get("relation_summary", ""))
        return self._truncate(first)

    def _count_of(self, value: object) -> int:
        if isinstance(value, list):
            return len(value)
        return 0

    def _truncate(self, value: object) -> str:
        text = str(value or "")
        if len(text) <= self._SUMMARY_VALUE_CHARS:
            return text
        return text[: self._SUMMARY_VALUE_CHARS - 3] + "..."

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return
        for actor_id, events in payload.items():
            if not isinstance(actor_id, str) or not isinstance(events, list):
                continue
            normalized_events = [dict(event) for event in events if isinstance(event, dict)]
            self._events_by_actor[actor_id] = normalized_events
            for event in normalized_events:
                self._ingest_event(event)

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.write_text(
            json.dumps(self._events_by_actor, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
