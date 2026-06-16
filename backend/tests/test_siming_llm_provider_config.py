import importlib

import httpx
import pytest

from app.config import Settings
from app.models.siming_event import InterventionCandidate
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    HttpSimingLlmCandidateProvider,
    SimingLlmProviderError,
    SimingLlmProviderInvalidOutput,
    SimingLlmProviderTimeout,
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


def test_provider_factory_returns_disabled_without_api_key() -> None:
    provider = build_siming_llm_provider(Settings(siming_llm_mode="http", siming_llm_api_key=None))

    assert isinstance(provider, DisabledSimingLlmCandidateProvider)


def test_provider_factory_returns_http_provider_when_configured() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_endpoint="https://example.invalid/v1/responses",
            siming_llm_model="test-model",
        )
    )

    assert isinstance(provider, HttpSimingLlmCandidateProvider)


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
        return FakeResponse({"candidates": [make_candidate_payload()]})

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
        {"candidates": None},
        {"candidates": [make_candidate_payload(candidate_id=None)]},
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
