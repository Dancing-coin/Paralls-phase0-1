from app.character_agent.gateway.model_provider import CharacterModelProvider


def test_model_provider_deepseek_path_is_live_by_default_without_env_gate() -> None:
    provider = CharacterModelProvider(provider_kind="deepseek")
    calls: list[dict[str, object]] = []

    def _fake_complete_via_deepseek(request: dict[str, object]) -> dict[str, object]:
        calls.append(request)
        return {"content": "Live response", "tone": "focused"}

    provider._complete_via_deepseek = _fake_complete_via_deepseek  # type: ignore[method-assign]

    output = provider.complete(
        {
            "task_kind": "dialogue_generation",
            "route": {"route_mode": "online_default", "provider_kind": "deepseek"},
            "context": {
                "actor_id": "char_a",
                "event": {"content": "Where is the letter?"},
            },
        }
    )

    assert calls
    assert output["content"] == "Live response"
    assert output["tone"] == "focused"


def test_model_provider_builds_deepseek_chat_completion_request() -> None:
    provider = CharacterModelProvider(
        provider_kind="deepseek",
        endpoint_url="https://api.deepseek.com",
        api_key="test-key",
        model_name="deepseek-chat",
    )

    payload = provider._build_deepseek_request(
        {
            "task_kind": "dialogue_generation",
            "prompt": {
                "system_instruction": "system",
                "user_instruction": "user",
                "required_output_keys": ["content", "tone"],
                "response_format": "json_object",
            },
            "policy": {
                "temperature": 0.2,
            },
        }
    )

    assert payload["model"] == "deepseek-chat"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"].startswith("user")
    assert "Return valid JSON only." in payload["messages"][1]["content"]
    assert '["content", "tone"]' in payload["messages"][1]["content"]
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0.2


def test_model_provider_normalizes_deepseek_chat_completion_response() -> None:
    provider = CharacterModelProvider(provider_kind="deepseek")

    output = provider._normalize_deepseek_response(
        {
            "choices": [
                {
                    "message": {
                        "content": "{\"content\": \"I am here.\", \"tone\": \"neutral\"}"
                    }
                }
            ]
        }
    )

    assert output["content"] == "I am here."
    assert output["tone"] == "neutral"


def test_model_provider_coerces_l3_string_fields_to_current_structured_contract() -> None:
    provider = CharacterModelProvider(provider_kind="deepseek")

    output = provider._coerce_output_for_task(
        "l3_planning",
        {
            "candidate_intents": "observe",
            "selected_intent": "observe",
            "recommended_intents": "observe",
            "risk_notes": "No risks detected",
            "why_this_now": "Nothing changed",
            "role_consistency_hint": "Stay calm",
        },
    )

    assert output["candidate_intents"] == ["observe"]
    assert output["recommended_intents"] == ["observe"]
    assert output["risk_notes"] == ["No risks detected"]


def test_model_provider_offline_l2_returns_extended_cognition_contract_keys() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    output = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {"attention_targets": ["char_b"]},
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [],
                    "social_memories": [],
                    "higher_order_memories": [],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "auditory",
                    "perceived_summary": "auditory_fact/speaker_active",
                    "target_actor_id": "char_b",
                    "clarity_score": 0.82,
                    "certainty_score": 0.61,
                },
            },
        }
    )

    assert "belief_deltas" in output
    assert "social_deltas" in output
    assert "higher_order_deltas" in output
    assert "dynamic_state_delta" in output
    assert "reasoning_trace_summary" in output


def test_model_provider_offline_l2_generates_cognition_deltas_for_guarded_social_signal() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    output = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {
                    "attention_targets": ["char_b"],
                    "clarity_score": 0.82,
                    "certainty_score": 0.61,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [],
                    "social_memories": [{"entity_id": "char_b", "trust_baseline": 0.25, "suspicion_baseline": 0.75}],
                    "higher_order_memories": [],
                    "relational_memories": [{"entity_id": "char_b", "belief_type": "trust_level", "value": "guarded"}],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "auditory",
                    "perceived_summary": "auditory_fact/speaker_active",
                    "target_actor_id": "char_b",
                    "clarity_score": 0.82,
                    "certainty_score": 0.61,
                },
            },
        }
    )

    assert output["belief_deltas"]
    assert output["belief_deltas"][0]["proposition_key"] == "char_b:is_probing"
    assert output["social_deltas"]
    assert output["social_deltas"][0]["entity_id"] == "char_b"
    assert output["higher_order_deltas"]
    assert output["higher_order_deltas"][0]["subject_actor_id"] == "char_b"
    assert output["dynamic_state_delta"]["social_pressure"] >= 0.5


def test_model_provider_offline_l2_generates_knowledge_and_dynamic_deltas_for_world_change() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    output = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {
                    "recent_world_changes": ["env_lamp changed from stable to alerted"],
                    "attention_targets": ["env_lamp"],
                    "clarity_score": 1.0,
                    "certainty_score": 1.0,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [],
                    "social_memories": [],
                    "higher_order_memories": [],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "visual",
                    "perceived_summary": "visual_fact/light_level_drop",
                    "target_environment_id": "env_lamp",
                    "clarity_score": 1.0,
                    "certainty_score": 1.0,
                },
            },
        }
    )

    assert output["belief_deltas"]
    assert output["belief_deltas"][0]["proposition_key"] == "env_lamp:state_change"
    assert output["dynamic_state_delta"]["vigilance_level"] >= 0.6


def test_model_provider_offline_l2_generates_self_state_deltas_for_body_state_events() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    output = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_b",
                "snapshot": {
                    "body_state_hints": ["interaction_strain:body_state_result/interaction_strain=engaged"],
                    "clarity_score": 1.0,
                    "certainty_score": 1.0,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [],
                    "social_memories": [],
                    "higher_order_memories": [],
                },
                "event": {
                    "actor_id": "char_b",
                    "body_state_class": "interaction_strain",
                    "perceived_summary": "body_state_result/interaction_strain=engaged",
                    "clarity_score": 1.0,
                    "certainty_score": 1.0,
                },
            },
        }
    )

    assert output["belief_deltas"]
    assert output["belief_deltas"][0]["proposition_key"] == "self:interaction_strain"
    assert output["dynamic_state_delta"]["stress_load"] >= 0.6


def test_model_provider_offline_l2_generates_dynamic_pressure_for_siming_input_without_fake_world_truth() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    output = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {
                    "last_siming_catalyst": "watch env_lamp",
                    "attention_targets": ["env_lamp"],
                    "vigilance_level": "elevated",
                    "clarity_score": 0.85,
                    "certainty_score": 0.9,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [],
                    "social_memories": [],
                    "higher_order_memories": [],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "siming",
                    "presentation_hint": "watch env_lamp",
                    "pressure_hint": "crowd closing in",
                    "reason_scope": "threat_scan",
                    "target_environment_id": "env_lamp",
                    "salience_boost": 0.85,
                    "clarity_score": 0.85,
                    "certainty_score": 0.9,
                },
            },
        }
    )

    assert output["belief_deltas"] == []
    assert output["dynamic_state_delta"]["vigilance_level"] >= 0.8
    assert output["dynamic_state_delta"]["distraction_level"] >= 0.7
    assert output["dynamic_state_delta"]["stress_load"] >= 0.5


def test_model_provider_offline_l2_uses_existing_higher_order_memory_to_raise_masking_pressure() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    output = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {
                    "attention_targets": ["char_b"],
                    "clarity_score": 0.92,
                    "certainty_score": 0.94,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [],
                    "social_memories": [{"entity_id": "char_b", "trust_baseline": 0.65, "suspicion_baseline": 0.2}],
                    "higher_order_memories": [
                        {
                            "subject_actor_id": "char_b",
                            "proposition_key": "social_probe:knowledge_asymmetry",
                            "meta_belief": "char_b suspects char_a knows more",
                            "confidence": 0.72,
                        }
                    ],
                    "relational_memories": [],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "auditory",
                    "perceived_summary": "auditory_fact/speaker_active",
                    "target_actor_id": "char_b",
                    "clarity_score": 0.92,
                    "certainty_score": 0.94,
                },
            },
        }
    )

    assert output["dynamic_state_delta"]["masking_pressure"] >= 0.6
    assert output["dynamic_state_delta"]["social_pressure"] >= 0.6


def test_model_provider_offline_l2_emits_goal_hints_for_high_pressure_social_probe() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    output = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {
                    "attention_targets": ["char_b"],
                    "clarity_score": 0.82,
                    "certainty_score": 0.61,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [
                        {
                            "proposition_key": "char_b:is_hiding_something",
                            "proposition": "char_b may be hiding something",
                            "state": "suspected",
                            "confidence": 0.62,
                        }
                    ],
                    "social_memories": [{"entity_id": "char_b", "trust_baseline": 0.25, "suspicion_baseline": 0.75}],
                    "higher_order_memories": [
                        {
                            "subject_actor_id": "char_b",
                            "proposition_key": "social_probe:knowledge_asymmetry",
                            "meta_belief": "char_b suspects char_a knows more",
                            "confidence": 0.72,
                        }
                    ],
                    "relational_memories": [],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "auditory",
                    "perceived_summary": "auditory_fact/speaker_active",
                    "target_actor_id": "char_b",
                    "clarity_score": 0.82,
                    "certainty_score": 0.61,
                },
            },
        }
    )

    assert output["goal_hints"]
    assert output["goal_hints"][0]["goal"] == "protect_secret"
    assert output["goal_hints"][0]["source"] == "social_signal"
    assert output["goal_hints"][0]["strength"] >= 0.7
    assert "guarded_attention" in output["goal_hints"][0]["evidence_tags"]
    assert any(item["goal"] == "clarify_intent" for item in output["goal_hints"])


def test_model_provider_offline_l2_scales_goal_hint_strength_with_knowledge_confidence() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    high_confidence = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {
                    "attention_targets": ["char_b"],
                    "clarity_score": 0.92,
                    "certainty_score": 0.94,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [
                        {
                            "proposition_key": "char_b:is_hiding_something",
                            "proposition": "char_b may be hiding something",
                            "state": "suspected",
                            "confidence": 0.82,
                        }
                    ],
                    "social_memories": [],
                    "higher_order_memories": [],
                    "relational_memories": [],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "auditory",
                    "perceived_summary": "auditory_fact/speaker_active",
                    "target_actor_id": "char_b",
                    "clarity_score": 0.92,
                    "certainty_score": 0.94,
                },
            },
        }
    )
    low_confidence = provider.complete(
        {
            "task_kind": "l2_reasoning",
            "route": {"route_mode": "local_only", "provider_kind": "local"},
            "context": {
                "actor_id": "char_a",
                "snapshot": {
                    "attention_targets": ["char_b"],
                    "clarity_score": 0.92,
                    "certainty_score": 0.94,
                },
                "memory": {
                    "working_memory": [],
                    "event_memories": [],
                    "observation_memories": [],
                    "knowledge_memories": [
                        {
                            "proposition_key": "char_b:is_hiding_something",
                            "proposition": "char_b may be hiding something",
                            "state": "suspected",
                            "confidence": 0.35,
                        }
                    ],
                    "social_memories": [],
                    "higher_order_memories": [],
                    "relational_memories": [],
                },
                "event": {
                    "actor_id": "char_a",
                    "percept_channel": "auditory",
                    "perceived_summary": "auditory_fact/speaker_active",
                    "target_actor_id": "char_b",
                    "clarity_score": 0.92,
                    "certainty_score": 0.94,
                },
            },
        }
    )

    high_clarify = next(item for item in high_confidence["goal_hints"] if item["goal"] == "clarify_intent")
    low_clarify = next(item for item in low_confidence["goal_hints"] if item["goal"] == "clarify_intent")

    assert high_clarify["strength"] > low_clarify["strength"]


def test_model_provider_hybrid_falls_back_to_offline_on_provider_error() -> None:
    provider = CharacterModelProvider(
        provider_kind="hybrid",
        endpoint_url="https://api.deepseek.com",
        model_name="deepseek-chat",
    )

    provider._complete_via_deepseek = lambda request: (_ for _ in ()).throw(ValueError("boom"))  # type: ignore[method-assign]

    output = provider.complete(
        {
            "task_kind": "dialogue_generation",
            "route": {"route_mode": "hybrid_ready", "provider_kind": "hybrid"},
            "context": {
                "actor_id": "char_a",
                "event": {"content": "Where is the letter?"},
            },
        }
    )

    assert output["content"] == "I saw something move near the desk."
    assert output["tone"] == "alert"


def test_model_provider_deepseek_route_surfaces_provider_error() -> None:
    provider = CharacterModelProvider(
        provider_kind="deepseek",
        endpoint_url="https://api.deepseek.com",
        model_name="deepseek-chat",
    )

    provider._complete_via_deepseek = lambda request: (_ for _ in ()).throw(ValueError("boom"))  # type: ignore[method-assign]

    try:
        provider.complete(
            {
                "task_kind": "dialogue_generation",
                "route": {"route_mode": "online_default", "provider_kind": "deepseek"},
                "context": {
                    "actor_id": "char_a",
                    "event": {"content": "Where is the letter?"},
                },
            }
        )
    except ValueError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected deepseek provider error to surface for strict online route")
