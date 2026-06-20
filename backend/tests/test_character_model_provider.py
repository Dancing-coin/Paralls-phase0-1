from app.character_agent.gateway.model_provider import CharacterModelProvider


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
