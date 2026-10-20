import pytest

from app.character_agent.gateway.model_provider import CharacterModelProvider


@pytest.mark.parametrize(
    "provider_kind,provider_key,laya_key,expected_key",
    [
        ("deepseek", "reasoning-provider-secret", "", ""),
        ("deepseek", "reasoning-provider-secret", "dedicated-laya-credential", "dedicated-laya-credential"),
        ("laya", "explicit-laya-credential", "dedicated-laya-credential", "explicit-laya-credential"),
        ("laya", "", "dedicated-laya-credential", "dedicated-laya-credential"),
    ],
)
def test_laya_route_uses_only_its_own_provider_credential(
    monkeypatch, provider_kind, provider_key, laya_key, expected_key
):
    monkeypatch.setenv("CHARACTER_LAYA_ENDPOINT", "http://127.0.0.1:8765/v1/systemone")
    monkeypatch.setenv("CHARACTER_LAYA_API_KEY", laya_key)
    received = {}

    class LayaEndpoint:
        def __init__(self, **configuration):
            received.update(configuration)

        def complete(self, request):
            return {"selected_intent": "observe"}

    monkeypatch.setattr("app.character_agent.gateway.model_provider.LayaSystemOneProvider", LayaEndpoint)
    provider = CharacterModelProvider(provider_kind=provider_kind, api_key=provider_key)
    output = provider.complete({"task_kind": "l3_planning", "route": {"provider_kind": "laya"}})
    assert output["selected_intent"] == "observe"
    assert received["api_key"] == expected_key
    assert received["endpoint"] == "http://127.0.0.1:8765/v1/systemone"
    assert provider.last_call_evidence.transport_succeeded
    assert not provider.last_call_evidence.fallback_used
