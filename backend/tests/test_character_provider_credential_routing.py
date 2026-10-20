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


@pytest.mark.parametrize("transport_fails", [False, True])
def test_routed_laya_evidence_identifies_actual_transport(monkeypatch, transport_fails):
    monkeypatch.setenv("CHARACTER_LAYA_ENDPOINT", "http://127.0.0.1:8765/v1/systemone")

    class LayaEndpoint:
        def __init__(self, **configuration):
            pass

        def complete(self, request):
            if transport_fails:
                raise TimeoutError("endpoint timed out")
            return {"selected_intent": "observe"}

    monkeypatch.setattr("app.character_agent.gateway.model_provider.LayaSystemOneProvider", LayaEndpoint)
    provider = CharacterModelProvider(
        provider_kind="deepseek", endpoint_url="https://api.deepseek.com", model_name="reasoning-model"
    )
    request = {"task_kind": "l3_planning", "route": {"provider_kind": "laya"}}
    if transport_fails:
        with pytest.raises(TimeoutError):
            provider.complete(request)
    else:
        provider.complete(request)
    evidence = provider.last_call_evidence
    assert evidence.provider_kind == "laya"
    assert evidence.endpoint_host == "127.0.0.1"
    assert evidence.model_name == "multilingual"
    assert evidence.transport_succeeded is not transport_fails
    assert not evidence.fallback_used
