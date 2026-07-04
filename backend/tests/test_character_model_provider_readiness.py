from __future__ import annotations

import json

from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.world_runtime.model_provider_readiness import build_model_provider_readiness_report


def test_character_qwen_route_is_not_real_verified_without_credentials() -> None:
    report = build_model_provider_readiness_report(
        env={
            "CHARACTER_MODEL_PROVIDER_KIND": "qwen",
            "CHARACTER_MODEL_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "CHARACTER_MODEL_MODEL": "qwen3.7-plus",
        }
    )
    row = {item.provider_kind: item for item in report.rows}["character_text"]

    assert row.mode == "http"
    assert row.provider_id == "qwen"
    assert row.model_id == "qwen3.7-plus"
    assert row.readiness_status == "blocked_missing_credentials"
    assert row.readiness_status != "real_provider_verified"


def test_character_local_route_is_contract_ready_only() -> None:
    report = build_model_provider_readiness_report(env={"CHARACTER_MODEL_PROVIDER_KIND": "local"})
    row = {item.provider_kind: item for item in report.rows}["character_text"]

    assert row.mode == "local"
    assert row.readiness_status == "contract_ready"
    assert "fallback is not real-provider proof" in row.timeout_degrade_status


def test_character_qwen_provider_uses_chat_completions_transport(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "content": "Ready.",
                                        "tone": "neutral",
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.character_agent.gateway.model_provider.urlopen", fake_urlopen)

    provider = CharacterModelProvider(
        provider_kind="qwen",
        endpoint_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
        model_name="qwen3.7-plus",
        timeout_seconds=1.5,
    )
    output = provider.complete(
        {
            "task_kind": "dialogue_generation",
            "prompt": {
                "system_instruction": "stay in role",
                "user_instruction": "say hello",
                "required_output_keys": ["content", "tone"],
            },
            "policy": {"temperature": 0.1, "max_tokens": 80},
        }
    )

    assert output == {"content": "Ready.", "tone": "neutral"}
    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "qwen3.7-plus"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["timeout"] == 1.5
