from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from app.character_agent.memory.event_memory import CharacterEventMemory
from app.character_agent.memory.knowledge_memory import CharacterKnowledgeMemory
from app.character_agent.memory.observation_memory import CharacterObservationMemory
from app.character_agent.memory.social_memory import CharacterSocialMemory
from app.character_agent.memory.working_memory import CharacterWorkingMemory
from app.character_agent.models.knowledge_state import KnowledgeState
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState


class CharacterAgentMemoryStore:
    _SUMMARY_VALUE_CHARS = 240
    _SOCIAL_BELIEF_TRUST_BASELINES = {
        "guarded": 0.25,
        "neutral": 0.5,
        "trusting": 0.75,
        "trusted": 0.9,
    }

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._working = CharacterWorkingMemory()
        self._event = CharacterEventMemory()
        self._observation = CharacterObservationMemory()
        self._knowledge = CharacterKnowledgeMemory()
        self._social = CharacterSocialMemory()
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
        stored_event = deepcopy(event)
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
            summary = str(payload.get("summary", "") or "")
            source_event_id = str(event.get("event_id", "") or "")
            producer_ts = int(event.get("producer_ts", 0) or 0)
            self._event.record_event(
                actor_id=actor_id,
                source_event_id=source_event_id,
                world_ts=producer_ts,
                event_type=event_type,
                summary=summary,
                clarity_score=float(payload.get("clarity_score", 1.0) or 1.0),
                certainty_score=float(payload.get("certainty_score", 1.0) or 1.0),
                refs=[source_event_id] if source_event_id else [],
                event_id=source_event_id,
            )
            observed_entity_id = str(
                payload.get("target_actor_id", "")
                or payload.get("source_actor_id", "")
                or payload.get("source_candidate_event_id", "")
                or "scene"
            )
            self._observation.record_observation(
                actor_id=actor_id,
                source_event_id=source_event_id,
                world_ts=producer_ts,
                observed_entity_id=observed_entity_id,
                observation_type=str(payload.get("percept_channel", "") or "perception"),
                observation_summary=summary,
                clarity_score=float(payload.get("clarity_score", 1.0) or 1.0),
                certainty_score=float(payload.get("certainty_score", 1.0) or 1.0),
                distortion_tags=[],
                refs=[source_event_id] if source_event_id else [],
            )
        elif event_type == "character_agent_settlement_result":
            settlement_summary = (
                str(payload.get("change_summary", "") or "").strip()
                or str(payload.get("constraint_summary", "") or "").strip()
                or str(payload.get("stable_state_summary", "") or "").strip()
                or str(payload.get("result_type", "") or "").strip()
            )
            source_event_id = str(event.get("event_id", "") or "")
            producer_ts = int(event.get("producer_ts", 0) or 0)
            self._event.record_event(
                actor_id=actor_id,
                source_event_id=source_event_id,
                world_ts=producer_ts,
                event_type=event_type,
                summary=settlement_summary,
                clarity_score=1.0,
                certainty_score=1.0,
                refs=[source_event_id] if source_event_id else [],
                event_id=source_event_id,
            )
            proposition_key, proposition = self._settlement_knowledge_record(payload, settlement_summary)
            self._knowledge.upsert_proposition(
                actor_id=actor_id,
                proposition_key=proposition_key,
                proposition=proposition,
                state=self._settlement_knowledge_state(payload),
                confidence=self._settlement_knowledge_confidence(payload),
                source_event_id=source_event_id,
                producer_ts=producer_ts,
            )
        elif event_type == "character_agent_dialogue_response":
            dialogue_summary = str(payload.get("content", "") or payload.get("summary", "") or "").strip()
            source_event_id = str(event.get("event_id", "") or "")
            producer_ts = int(event.get("producer_ts", 0) or 0)
            self._event.record_event(
                actor_id=actor_id,
                source_event_id=source_event_id,
                world_ts=producer_ts,
                event_type=event_type,
                summary=f"dialogue_response:{dialogue_summary}" if dialogue_summary else "dialogue_response",
                clarity_score=1.0,
                certainty_score=1.0,
                refs=[source_event_id] if source_event_id else [],
                event_id=source_event_id,
            )
        elif event_type == "relational_belief_event":
            source_event_id = str(event.get("event_id", "") or "")
            producer_ts = int(event.get("producer_ts", 0) or 0)
            entity_id = str(payload.get("entity_id", "") or "")
            belief_type = str(payload.get("belief_type", "") or "")
            value = str(payload.get("value", "") or "")
            if entity_id == "" or belief_type == "":
                return
            self._knowledge.upsert_proposition(
                actor_id=actor_id,
                proposition_key=f"social:{entity_id}:{belief_type}",
                proposition=f"{entity_id}:{belief_type}={value}",
                state=KnowledgeState.TENTATIVELY_BELIEVED,
                confidence=0.65,
                source_event_id=source_event_id,
                producer_ts=producer_ts,
            )
            if belief_type != "trust_level":
                return
            self._social.upsert_relation(
                actor_id=actor_id,
                entity_id=entity_id,
                trust_baseline=self._trust_baseline_for_belief(belief_type, value),
                suspicion_baseline=self._suspicion_baseline_for_belief(belief_type, value),
                intimacy=0.0,
                dependency=0.0,
                unresolved_tension=0.5 if value == "guarded" else 0.0,
                shared_secret_refs=[],
                source_event_id=source_event_id,
                producer_ts=producer_ts,
            )

    def retrieval_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
        event_memories = self._event.recall(actor_id)
        observation_memories = self._observation.recall(actor_id)
        knowledge_memories = self._knowledge.recall(actor_id)
        social_memories = self._social.recall(actor_id)
        return {
            "working_memory": self._working.recall(actor_id),
            "event_memories": event_memories,
            "observation_memories": observation_memories,
            "knowledge_memories": knowledge_memories,
            "social_memories": social_memories,
            "episodic_memories": self._legacy_episodic_memories(event_memories),
            "relational_memories": self._legacy_relational_memories(knowledge_memories),
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
            "event_memories_count": self._count_of(memory_dict.get("event_memories")),
            "observation_memories_count": self._count_of(memory_dict.get("observation_memories")),
            "knowledge_memories_count": self._count_of(memory_dict.get("knowledge_memories")),
            "social_memories_count": self._count_of(memory_dict.get("social_memories")),
            "working_memory_sample": self._sample_summary(memory_dict.get("working_memory")),
            "event_memory_sample": self._sample_summary(memory_dict.get("event_memories")),
            "observation_memory_sample": self._sample_summary(memory_dict.get("observation_memories")),
            "relational_memory_sample": self._sample_summary(memory_dict.get("relational_memories")),
            "knowledge_memory_sample": self._sample_summary(memory_dict.get("knowledge_memories")),
            "social_memory_sample": self._sample_summary(memory_dict.get("social_memories")),
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
            return self._truncate(
                first.get("summary", "")
                or first.get("observation_summary", "")
                or first.get("proposition", "")
                or first.get("entity_id", "")
                or first.get("event_type", "")
            )
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

    def _trust_baseline_for_belief(self, belief_type: str, value: str) -> float:
        if belief_type != "trust_level":
            return 0.5
        return self._SOCIAL_BELIEF_TRUST_BASELINES.get(value, 0.5)

    def _suspicion_baseline_for_belief(self, belief_type: str, value: str) -> float:
        if belief_type != "trust_level":
            return 0.0
        if value == "guarded":
            return 0.75
        if value in {"trusting", "trusted"}:
            return 0.1
        return 0.25

    def _settlement_knowledge_record(self, payload: dict[str, object], settlement_summary: str) -> tuple[str, str]:
        target_kind, target_ref = self._settlement_target_ref(payload)
        result_type = str(payload.get("result_type", "") or "").strip() or "result"
        proposition_key = f"settlement:{target_kind}:{target_ref}:{result_type}"
        proposition = f"{target_kind} {target_ref} {result_type}: {settlement_summary or result_type}"
        return proposition_key, proposition

    def _settlement_target_ref(self, payload: dict[str, object]) -> tuple[str, str]:
        target_actor_id = str(payload.get("target_actor_id", "") or "").strip()
        if target_actor_id != "":
            return "actor", target_actor_id
        target_object_id = str(payload.get("target_object_id", "") or "").strip()
        if target_object_id != "":
            return "object", target_object_id
        target_environment_id = str(payload.get("target_environment_id", "") or "").strip()
        if target_environment_id != "":
            return "environment", target_environment_id
        return "world", "world"

    def _settlement_knowledge_state(self, payload: dict[str, object]) -> KnowledgeState:
        result_type = str(payload.get("result_type", "") or "").strip()
        if result_type == "constraint_state_result":
            return KnowledgeState.NOTICED
        return KnowledgeState.BELIEVED

    def _settlement_knowledge_confidence(self, payload: dict[str, object]) -> float:
        result_type = str(payload.get("result_type", "") or "").strip()
        if result_type == "constraint_state_result":
            return 0.7
        return 0.9

    def _legacy_episodic_memories(
        self,
        event_memories: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return [
            {
                "summary": str(entry.get("summary", "") or ""),
                "source_event_id": str(entry.get("source_event_id", "") or ""),
                "producer_ts": int(entry.get("world_ts", 0) or 0),
                "tags": [],
            }
            for entry in event_memories
        ]

    def _legacy_relational_memories(
        self,
        knowledge_memories: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        relational_memories: list[dict[str, object]] = []
        for entry in knowledge_memories:
            proposition_key = str(entry.get("proposition_key", "") or "")
            if not proposition_key.startswith("social:"):
                continue
            entity_id, belief_type = self._parse_social_proposition_key(proposition_key)
            if entity_id == "" or belief_type == "":
                continue
            relational_memories.append(
                {
                    "entity_id": entity_id,
                    "belief_type": belief_type,
                    "value": self._parse_social_proposition_value(
                        str(entry.get("proposition", "") or ""),
                        entity_id,
                        belief_type,
                    ),
                    "source_event_id": str(entry.get("source_event_id", "") or ""),
                    "producer_ts": int(entry.get("producer_ts", 0) or 0),
                }
            )
        return relational_memories

    def _parse_social_proposition_key(self, proposition_key: str) -> tuple[str, str]:
        _, entity_id, belief_type = (proposition_key.split(":", 2) + ["", ""])[:3]
        return entity_id, belief_type

    def _parse_social_proposition_value(
        self,
        proposition: str,
        entity_id: str,
        belief_type: str,
    ) -> str:
        expected_prefix = f"{entity_id}:{belief_type}="
        if proposition.startswith(expected_prefix):
            return proposition[len(expected_prefix) :]
        if "=" in proposition:
            return proposition.split("=", 1)[1]
        return ""

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
