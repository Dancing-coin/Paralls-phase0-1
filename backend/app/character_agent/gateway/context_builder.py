class CharacterContextBuilder:
    def build_context(
        self,
        *,
        actor_id: str,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]],
        control_mode: str,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        context = {
            "actor_id": actor_id,
            "control_mode": control_mode,
            "snapshot": dict(snapshot),
            "memory": {
                "working_memory": list(memory_bundle.get("working_memory", [])),
                "episodic_memories": list(memory_bundle.get("episodic_memories", [])),
                "relational_memories": list(memory_bundle.get("relational_memories", [])),
            },
        }
        if working_memory_state is not None:
            context["working_memory_state"] = dict(working_memory_state)
        return context
