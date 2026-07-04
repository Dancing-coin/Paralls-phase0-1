import importlib
import json as json_module

import httpx
import pytest

from app.config import Settings, SimingLlmRouteSettings
from app.models.siming_event import InterventionCandidate
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    HttpSimingLlmCandidateProvider,
    SimingLlmProviderError,
    SimingLlmProviderInvalidOutput,
    SimingLlmProviderTimeout,
    SimingLlmProviderRouter,
    build_siming_llm_provider,
)


def test_settings_disable_siming_llm_by_default() -> None:
    settings = Settings()

    assert settings.siming_llm_mode == "disabled"
    assert settings.siming_llm_api_key is None


def test_settings_repr_and_dump_hide_siming_llm_api_key() -> None:
    settings = Settings(siming_llm_mode="http", siming_llm_api_key="secret-key")

    assert "secret-key" not in repr(settings)
    assert "secret-key" not in str(settings.model_dump())
    assert "siming_llm_api_key" not in settings.model_dump()


def test_settings_repr_and_dump_hide_route_level_siming_llm_api_key() -> None:
    settings = Settings(
        siming_llm_mode="http",
        siming_llm_routes=[
            SimingLlmRouteSettings(route_id="fast", provider="openai_responses", api_key="route-secret")
        ],
    )

    assert "route-secret" not in repr(settings)
    assert "route-secret" not in str(settings.model_dump())


def test_env_siming_llm_routes_json_supports_multi_provider_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import config

    monkeypatch.setenv(
        "SIMING_LLM_ROUTES_JSON",
        json_module.dumps(
            [
                {
                    "route_id": "deepseek-live",
                    "provider": "deepseek_chat",
                    "model": "deepseek-chat",
                    "endpoint": "https://api.deepseek.com/chat/completions",
                    "api_key": "deepseek-secret",
                },
                {
                    "route_id": "qwen-live",
                    "provider": "qwen",
                    "model": "qwen3.7-plus",
                    "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                    "api_key": "qwen-secret",
                },
                {
                    "route_id": "seed-live",
                    "provider": "seed_doubao",
                    "model": "doubao-seed-2.0-pro",
                    "endpoint": "https://seed.example.invalid/chat/completions",
                    "api_key": "seed-secret",
                },
            ]
        ),
    )

    routes = config._env_siming_llm_routes()

    assert [route.provider for route in routes] == ["deepseek_chat", "qwen", "seed_doubao"]
    assert [route.route_id for route in routes] == ["deepseek-live", "qwen-live", "seed-live"]
    assert "qwen-secret" not in str(routes[1].model_dump())


def test_provider_factory_returns_disabled_without_api_key() -> None:
    provider = build_siming_llm_provider(Settings(siming_llm_mode="http", siming_llm_api_key=None))

    assert isinstance(provider, SimingLlmProviderRouter)
    assert isinstance(provider.providers[0], DisabledSimingLlmCandidateProvider)


def test_provider_factory_returns_http_provider_when_configured() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_endpoint="https://example.invalid/v1/responses",
            siming_llm_model="test-model",
        )
    )

    assert isinstance(provider, SimingLlmProviderRouter)
    assert isinstance(provider.providers[0], HttpSimingLlmCandidateProvider)


def test_provider_factory_orders_router_from_settings() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_provider_order=["disabled", "openai_responses"],
        )
    )

    assert isinstance(provider, SimingLlmProviderRouter)
    assert isinstance(provider.providers[0], DisabledSimingLlmCandidateProvider)
    assert isinstance(provider.providers[1], HttpSimingLlmCandidateProvider)


def test_provider_factory_builds_distinct_openai_response_routes() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_routes=[
                SimingLlmRouteSettings(
                    route_id="fast",
                    provider="openai_responses",
                    model="gpt-fast",
                    endpoint="https://example.invalid/v1/responses",
                    timeout_seconds=1.0,
                ),
                SimingLlmRouteSettings(
                    route_id="deep",
                    provider="openai_responses",
                    model="gpt-deep",
                    endpoint="https://example.invalid/v1/responses",
                    timeout_seconds=8.0,
                ),
            ],
        )
    )

    assert isinstance(provider, SimingLlmProviderRouter)
    first, second = provider.providers
    assert isinstance(first, HttpSimingLlmCandidateProvider)
    assert isinstance(second, HttpSimingLlmCandidateProvider)
    assert first.route_id == "fast"
    assert second.route_id == "deep"
    assert first.model == "gpt-fast"
    assert second.model == "gpt-deep"
    assert first.timeout_seconds == 1.0
    assert second.timeout_seconds == 8.0


def test_provider_factory_builds_distinct_deepseek_routes() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_routes=[
                SimingLlmRouteSettings(
                    route_id="fast",
                    provider="deepseek_chat",
                    model="deepseek-chat",
                    endpoint="https://api.deepseek.com/chat/completions",
                    timeout_seconds=1.0,
                ),
                SimingLlmRouteSettings(
                    route_id="deep",
                    provider="deepseek_chat",
                    model="deepseek-reasoner",
                    endpoint="https://api.deepseek.com/chat/completions",
                    timeout_seconds=8.0,
                ),
            ],
        )
    )

    assert isinstance(provider, SimingLlmProviderRouter)
    first, second = provider.providers
    assert isinstance(first, HttpSimingLlmCandidateProvider)
    assert isinstance(second, HttpSimingLlmCandidateProvider)
    assert first.route_id == "fast"
    assert second.route_id == "deep"
    assert first.model == "deepseek-chat"
    assert second.model == "deepseek-reasoner"
    assert first.timeout_seconds == 1.0
    assert second.timeout_seconds == 8.0


def test_provider_factory_uses_legacy_order_as_route_fallback() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_routes=[
                SimingLlmRouteSettings(route_id="placeholder", provider="openai_responses", enabled=False)
            ],
            siming_llm_provider_order=["openai_responses"],
            siming_llm_model="legacy-model",
        )
    )

    assert isinstance(provider, SimingLlmProviderRouter)
    first, second = provider.providers
    assert isinstance(first, DisabledSimingLlmCandidateProvider)
    assert isinstance(second, HttpSimingLlmCandidateProvider)
    assert second.route_id == "openai_responses"
    assert second.model == "legacy-model"


def test_provider_factory_builds_deepseek_provider_when_configured() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="deepseek-key",
            siming_llm_endpoint="https://api.deepseek.com/chat/completions",
            siming_llm_model="deepseek-chat",
            siming_llm_provider_order=["deepseek_chat"],
        )
    )

    assert isinstance(provider, SimingLlmProviderRouter)
    assert isinstance(provider.providers[0], HttpSimingLlmCandidateProvider)
    assert provider.providers[0].route_id == "deepseek_chat"


@pytest.mark.parametrize("provider_name", ["seed_doubao", "qwen"])
def test_provider_factory_builds_recommended_chat_completion_providers(provider_name: str) -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_endpoint="https://example.invalid/api/v3/chat/completions",
            siming_llm_model="recommended-model",
            siming_llm_provider_order=[provider_name],
        )
    )

    assert isinstance(provider, SimingLlmProviderRouter)
    assert isinstance(provider.providers[0], HttpSimingLlmCandidateProvider)
    assert provider.providers[0].route_id == provider_name


def test_route_level_openai_response_config_is_used_for_http_request(monkeypatch: pytest.MonkeyPatch) -> None:
    router = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="global-key",
            siming_llm_endpoint="https://global.invalid/v1/responses",
            siming_llm_model="global-model",
            siming_llm_timeout_seconds=9.0,
            siming_llm_routes=[
                SimingLlmRouteSettings(
                    route_id="fast",
                    provider="openai_responses",
                    api_key="route-key",
                    model="gpt-fast",
                    endpoint="https://route.invalid/v1/responses",
                    timeout_seconds=1.0,
                )
            ],
        )
    )
    assert isinstance(router, SimingLlmProviderRouter)
    provider = router.providers[0]
    assert isinstance(provider, HttpSimingLlmCandidateProvider)
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse({"output_text": '{"candidates":[]}'})

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    assert provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[]) == []
    assert captured["url"] == "https://route.invalid/v1/responses"
    assert captured["headers"] == {"Authorization": "Bearer route-key"}
    assert captured["json"]["model"] == "gpt-fast"
    assert captured["timeout"] == 1.0


def test_route_level_deepseek_config_is_used_for_http_request(monkeypatch: pytest.MonkeyPatch) -> None:
    router = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="global-key",
            siming_llm_endpoint="https://global.invalid/v1/responses",
            siming_llm_model="global-model",
            siming_llm_timeout_seconds=9.0,
            siming_llm_routes=[
                SimingLlmRouteSettings(
                    route_id="deepseek-fast",
                    provider="deepseek_chat",
                    api_key="route-key",
                    model="deepseek-chat",
                    endpoint="https://api.deepseek.com/chat/completions",
                    timeout_seconds=1.0,
                )
            ],
        )
    )
    assert isinstance(router, SimingLlmProviderRouter)
    provider = router.providers[0]
    assert isinstance(provider, HttpSimingLlmCandidateProvider)
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"candidates":[]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    assert provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[]) == []
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer route-key"}
    assert captured["json"]["model"] == "deepseek-chat"
    assert captured["timeout"] == 1.0
    assert captured["json"]["response_format"]["type"] == "json_object"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["messages"][1]["role"] == "user"


class FakeResponse:
    def __init__(self, payload: object, *, raise_http_error: Exception | None = None) -> None:
        self._payload = payload
        self._raise_http_error = raise_http_error

    def raise_for_status(self) -> None:
        if self._raise_http_error is not None:
            raise self._raise_http_error

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def make_http_provider() -> HttpSimingLlmCandidateProvider:
    return HttpSimingLlmCandidateProvider(
        api_key="test-key",
        endpoint="https://example.invalid/v1/responses",
        model="test-model",
        timeout_seconds=1.5,
    )


def make_candidate_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_id": "cand:http:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300:char_c:light_level_drop",
        "correlation_id": "visual_fact:300",
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "target_environment_id": "env_lamp",
        "established_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "explanation": "Reveal the established light drop to a nearby actor.",
        "confidence": 0.72,
        "reason_tags": ["visibility_imbalance"],
        "source": "llm",
    }
    payload.update(overrides)
    return payload


def make_snapshot() -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id="fairness:visual_fact:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
    )


def make_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "visual_fact:300:char_c:light_level_drop",
            "event_type": "visual_fact_event",
            "producer_ts": 300,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "visual_fact:300",
            "correlation_id": "visual_fact:300",
            "payload": {
                "fact_type": "light_level_drop",
                "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            },
        }
    )


def test_http_provider_returns_validated_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_http_provider()
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"candidates":[%s]}' % json_module.dumps(make_candidate_payload()),
                            }
                        ],
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    candidates = provider.generate_candidates(
        snapshot=make_snapshot(),
        recent_events=[make_event()],
        recent_audit=[],
    )

    assert len(candidates) == 1
    assert isinstance(candidates[0], InterventionCandidate)
    assert candidates[0].candidate_id == "cand:http:1"
    assert captured["url"] == "https://example.invalid/v1/responses"
    assert captured["headers"] == {"Authorization": "Bearer test-key"}
    assert captured["timeout"] == 1.5
    request_payload = captured["json"]
    assert isinstance(request_payload, dict)
    assert request_payload["model"] == "test-model"
    assert isinstance(request_payload["instructions"], str)
    assert isinstance(request_payload["input"], list)
    assert request_payload["input"][0]["role"] == "user"
    assert request_payload["input"][0]["content"][0]["type"] == "input_text"
    assert "snapshot" in request_payload["input"][0]["content"][0]["text"]
    text_format = request_payload["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["name"] == "siming_intervention_candidates"
    assert text_format["strict"] is True
    assert text_format["schema"]["required"] == ["candidates"]
    assert "candidates" not in request_payload


def test_http_provider_parses_deepseek_chat_completion_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpSimingLlmCandidateProvider(
        api_key="test-key",
        endpoint="https://api.deepseek.com/chat/completions",
        model="deepseek-chat",
        timeout_seconds=1.5,
        route_id="deepseek_chat",
        provider_name="deepseek_chat",
    )
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"candidates":[%s]}' % json_module.dumps(make_candidate_payload())
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    candidates = provider.generate_candidates(
        snapshot=make_snapshot(),
        recent_events=[make_event()],
        recent_audit=[],
    )

    assert len(candidates) == 1
    assert candidates[0].candidate_id == "cand:http:1"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer test-key"}
    assert captured["timeout"] == 1.5
    request_payload = captured["json"]
    assert request_payload["model"] == "deepseek-chat"
    assert request_payload["response_format"] == {"type": "json_object"}
    assert request_payload["messages"][0]["role"] == "system"
    assert request_payload["messages"][1]["role"] == "user"
    assert "snapshot" in request_payload["messages"][1]["content"]
    system_prompt = request_payload["messages"][0]["content"]
    assert "candidate_id" in system_prompt
    assert "target_object_id" in system_prompt
    assert "established_fact_ids" in system_prompt
    assert 'source="llm"' in system_prompt
    assert "Do not omit keys" in system_prompt
    assert "Use null" in system_prompt
    assert "snapshot.eligible_actor_ids" in system_prompt
    assert "recent_events" in system_prompt


@pytest.mark.parametrize("missing_field", ["source", "explanation", "confidence", "reason_tags"])
def test_deepseek_provider_rejects_candidates_missing_explicit_llm_fields(
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:
    provider = HttpSimingLlmCandidateProvider(
        api_key="test-key",
        endpoint="https://api.deepseek.com/chat/completions",
        model="deepseek-chat",
        timeout_seconds=1.5,
        route_id="deepseek_chat",
        provider_name="deepseek_chat",
    )
    candidate_payload = make_candidate_payload()
    candidate_payload.pop(missing_field)

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"candidates":[%s]}' % json_module.dumps(candidate_payload)
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    with pytest.raises(SimingLlmProviderInvalidOutput, match=missing_field):
        provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])


def test_http_provider_maps_timeout_to_provider_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_http_provider()

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    with pytest.raises(SimingLlmProviderTimeout):
        provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])


def test_http_provider_maps_http_error_to_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_http_provider()

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        request = httpx.Request("POST", "https://example.invalid/v1/responses")
        response = httpx.Response(500, request=request)
        return FakeResponse({}, raise_http_error=httpx.HTTPStatusError("boom", request=request, response=response))

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    with pytest.raises(SimingLlmProviderError):
        provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])


@pytest.mark.parametrize(
    "payload",
    [
        ["not-a-dict"],
        {},
        {"output_text": '{"candidates": null}'},
        {"output_text": '{"candidates": [%s]}' % json_module.dumps(make_candidate_payload(candidate_id=None))},
    ],
)
def test_http_provider_maps_malformed_output_to_invalid_output(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    provider = make_http_provider()

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse(payload)

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    with pytest.raises(SimingLlmProviderInvalidOutput):
        provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])


def test_http_provider_maps_json_parse_error_to_invalid_output(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_http_provider()

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse(ValueError("bad json"))

    monkeypatch.setattr("app.services.siming_llm_provider.httpx.post", fake_post)

    with pytest.raises(SimingLlmProviderInvalidOutput):
        provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])


class TimeoutProvider:
    def generate_candidates(self, **_: object) -> list[InterventionCandidate]:
        raise SimingLlmProviderTimeout("timed out")


class RecordingProvider:
    def __init__(self, candidates: list[InterventionCandidate]) -> None:
        self.calls = 0
        self._candidates = candidates

    def generate_candidates(self, **_: object) -> list[InterventionCandidate]:
        self.calls += 1
        return self._candidates


def test_router_falls_back_to_next_provider_after_failure() -> None:
    candidate = InterventionCandidate.model_validate(make_candidate_payload())
    fallback = RecordingProvider([candidate])
    router = SimingLlmProviderRouter([TimeoutProvider(), fallback])

    candidates = router.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])

    assert candidates == [candidate]
    assert fallback.calls == 1


def test_router_returns_first_non_empty_candidate_result() -> None:
    first = RecordingProvider([])
    second_candidate = InterventionCandidate.model_validate(make_candidate_payload(candidate_id="cand:second"))
    second = RecordingProvider([second_candidate])
    router = SimingLlmProviderRouter([first, second])

    candidates = router.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])

    assert candidates == [second_candidate]
    assert first.calls == 1
    assert second.calls == 1


def test_reset_runtime_state_builds_and_injects_provider_without_calling_it(monkeypatch: pytest.MonkeyPatch) -> None:
    app_main = importlib.import_module("app.main")
    built_provider = object()
    calls: list[Settings] = []
    injected_runtime: list[object] = []

    def fake_build(settings: Settings) -> object:
        calls.append(settings)
        return built_provider

    class RecordingSimingRuntime:
        def __init__(self, *, llm_provider: object | None = None, **_: object) -> None:
            self.llm_provider = llm_provider

    class RecordingSimingEventPipeline:
        def __init__(self, *, runtime: object, **_: object) -> None:
            injected_runtime.append(runtime)

        def handle_event(self, event: object) -> None:
            return None

    monkeypatch.setattr(app_main, "build_siming_llm_provider", fake_build)
    monkeypatch.setattr(app_main, "SimingRuntime", RecordingSimingRuntime)
    monkeypatch.setattr(app_main, "SimingEventPipeline", RecordingSimingEventPipeline)

    app_main.reset_runtime_state()

    assert calls == [app_main.settings]
    assert len(injected_runtime) == 1
    assert injected_runtime[0].llm_provider is built_provider
