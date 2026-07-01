from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle


class CharacterContextBuilder:
    _EMPTY_MEMORY_KEYS = (
        "working_memory",
        "event_memories",
        "observation_memories",
        "knowledge_memories",
        "social_memories",
        "higher_order_memories",
    )

    def build_context(
        self,
        *,
        actor_id: str,
        snapshot: dict[str, object] | object,
        memory_bundle: dict[str, list[dict[str, object]]],
        control_mode: str,
        working_memory_state: dict[str, object] | object | None = None,
        profile: dict[str, object] | object | None = None,
    ) -> dict[str, object]:
        normalized_memory = self.normalize_memory_bundle(memory_bundle)
        context = {
            "actor_id": actor_id,
            "profile": self._plain_mapping(profile),
            "control_mode": control_mode,
            "snapshot": self._plain_mapping(snapshot),
            "memory": normalized_memory,
        }
        if working_memory_state is not None:
            context["working_memory_state"] = self._plain_mapping(working_memory_state)
        return context

    @classmethod
    def normalize_memory_bundle(
        cls,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> dict[str, list[dict[str, object]]]:
        if isinstance(memory_bundle, CharacterMemoryRecordBundle):
            bundle = {
                "event_memories": [item.model_dump() for item in memory_bundle.event_memories],
                "observation_memories": [item.model_dump() for item in memory_bundle.observation_memories],
                "knowledge_memories": [item.model_dump() for item in memory_bundle.knowledge_memories],
                "social_memories": [item.model_dump() for item in memory_bundle.social_memories],
                "higher_order_memories": [item.model_dump() for item in memory_bundle.higher_order_memories],
            }
        else:
            bundle = memory_bundle or {}
        working_memory = cls._list_entries(bundle.get("working_memory"))
        event_memories = cls._list_entries(bundle.get("event_memories"))
        if not event_memories:
            event_memories = cls._list_entries(bundle.get("episodic_memories"))
        observation_memories = cls._list_entries(bundle.get("observation_memories"))
        knowledge_memories = cls._list_entries(bundle.get("knowledge_memories"))
        if not knowledge_memories:
            knowledge_memories = cls._knowledge_memories_from_legacy_relational(
                cls._list_entries(bundle.get("relational_memories"))
            )
        social_memories = cls._list_entries(bundle.get("social_memories"))
        higher_order_memories = cls._list_entries(bundle.get("higher_order_memories"))

        normalized_memory = {
            "working_memory": working_memory,
            "event_memories": event_memories,
            "observation_memories": observation_memories,
            "knowledge_memories": knowledge_memories,
            "social_memories": social_memories,
            "higher_order_memories": higher_order_memories,
            "episodic_memories": cls._list_entries(bundle.get("episodic_memories")) or list(event_memories),
            "relational_memories": cls._list_entries(bundle.get("relational_memories"))
            or cls._legacy_relational_memories(knowledge_memories),
        }

        for key in cls._EMPTY_MEMORY_KEYS:
            normalized_memory.setdefault(key, [])
        return normalized_memory

    @staticmethod
    def _list_entries(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [entry for entry in value if isinstance(entry, dict)]

    @staticmethod
    def _plain_mapping(value: object) -> dict[str, object]:
        if value is None:
            return {}
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dumped
        if isinstance(value, dict):
            return dict(value)
        return {}

    @classmethod
    def _knowledge_memories_from_legacy_relational(
        cls,
        relational_memories: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        knowledge_memories: list[dict[str, object]] = []
        for entry in relational_memories:
            entity_id = str(entry.get("entity_id", "") or "")
            belief_type = str(entry.get("belief_type", "") or "")
            value = str(entry.get("value", "") or "")
            proposition_key = str(entry.get("proposition_key", "") or "")
            proposition = str(entry.get("proposition", "") or "")
            if proposition_key == "" and entity_id and belief_type:
                proposition_key = f"social:{entity_id}:{belief_type}"
            if proposition == "" and entity_id and belief_type:
                proposition = f"{entity_id}:{belief_type}={value}"
            knowledge_entry = dict(entry)
            if proposition_key:
                knowledge_entry["proposition_key"] = proposition_key
            if proposition:
                knowledge_entry["proposition"] = proposition
            knowledge_memories.append(knowledge_entry)
        return knowledge_memories

    @classmethod
    def _legacy_relational_memories(
        cls,
        knowledge_memories: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        relational_memories: list[dict[str, object]] = []
        for entry in knowledge_memories:
            proposition_key = str(entry.get("proposition_key", "") or "")
            if not proposition_key.startswith("social:"):
                continue
            _, entity_id, belief_type = (proposition_key.split(":", 2) + ["", ""])[:3]
            if entity_id == "" or belief_type == "":
                continue
            proposition = str(entry.get("proposition", "") or "")
            expected_prefix = f"{entity_id}:{belief_type}="
            value = ""
            if proposition.startswith(expected_prefix):
                value = proposition[len(expected_prefix) :]
            elif "=" in proposition:
                value = proposition.split("=", 1)[1]
            relational_memories.append(
                {
                    "entity_id": entity_id,
                    "belief_type": belief_type,
                    "value": value,
                    "source_event_id": str(entry.get("source_event_id", "") or ""),
                    "producer_ts": int(entry.get("producer_ts", 0) or 0),
                }
            )
        return relational_memories
