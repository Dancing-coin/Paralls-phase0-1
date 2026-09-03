from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy
from app.character_agent.gateway.model_gateway import CharacterModelGateway


def test_recall_prefers_attention_and_goal_relevance_over_newest_irrelevant_memory() -> None:
    policy = CharacterMemoryRecallPolicy()
    memory = {
        "event_memories": [
            {
                "memory_id": "event:letter",
                "world_ts": 10,
                "summary": "the sealed letter was destroyed",
                "certainty_score": 0.9,
                "clarity_score": 0.9,
            },
            {
                "memory_id": "event:weather",
                "world_ts": 99,
                "summary": "the northern rain became heavier",
                "certainty_score": 1.0,
                "clarity_score": 1.0,
            },
        ],
        "knowledge_memories": [],
        "observation_memories": [],
        "social_memories": [],
        "higher_order_memories": [],
        "working_memory": [],
    }

    result = policy.select(
        memory,
        context={
            "snapshot": {"current_focus_target": "obj_letter"},
            "event": {"perceived_summary": "the letter is gone", "target_object_id": "obj_letter"},
            "current_goal_state": {"primary_goal": "understand what happened to the letter"},
        },
    )

    assert result.memory["event_memories"][0]["memory_id"] == "event:letter"
    assert result.metadata["selected_memory_refs"] == ["event:event:letter", "event:event:weather"]


def test_recall_enforces_pool_and_token_budgets_with_deterministic_metadata() -> None:
    policy = CharacterMemoryRecallPolicy(pool_limit=2, token_budget=80)
    memory = {
        "event_memories": [
            {"memory_id": f"event:{index}", "world_ts": index, "summary": "letter " + ("x" * 80)}
            for index in range(5)
        ],
        "observation_memories": [],
        "knowledge_memories": [],
        "social_memories": [],
        "higher_order_memories": [],
        "working_memory": [],
    }

    result = policy.select(memory, context={"snapshot": {}, "event": {}})

    assert len(result.memory["event_memories"]) == 2
    assert result.metadata["token_budget"] == 80
    assert result.metadata["estimated_tokens"] <= 80
    assert result.metadata["truncated"] is True
    assert result.metadata["context_hash"] == policy.select(memory, context={"snapshot": {}, "event": {}}).metadata["context_hash"]


def test_model_gateway_exposes_recall_metadata_alongside_selected_memory() -> None:
    gateway = CharacterModelGateway()
    request = gateway.prepare_run_request(
        task_kind="l2_reasoning",
        route_override="local_only",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {"current_focus_target": "obj_letter"},
            "event": {"perceived_summary": "letter removed", "target_object_id": "obj_letter"},
            "current_goal_state": {"primary_goal": "understand the letter"},
            "memory": {
                "working_memory": [],
                "event_memories": [{"memory_id": "event:letter", "world_ts": 1, "summary": "letter removed"}],
                "observation_memories": [],
                "knowledge_memories": [],
                "social_memories": [],
                "higher_order_memories": [],
            },
        },
    )

    recall = request["context"]["memory_recall"]
    assert recall["selected_memory_refs"] == ["event:event:letter"]
    assert recall["context_hash"]
    assert request["context"]["memory"]["event_memories"][0]["memory_id"] == "event:letter"
