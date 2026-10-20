from __future__ import annotations

import copy
import io
import json

import pytest

from app.character_agent.cognition.cognition_policy import CognitionPolicy
from app.character_agent.gateway import model_provider as transport


def frozen_request(task="l2_reasoning", *, l2=31, l3=47, dialogue=19, requested=800):
    policy = CognitionPolicy.model_validate({
        "policy_id": "policy:test", "actor_id": "char_a", "turn_id": "turn:test",
        "tier": "fast", "provider_thinking_effort": "unsupported",
        "memory": {"recall_limit": 2, "token_budget": 120},
        "reasoning": {"l2_max_tokens": l2, "l3_max_tokens": l3,
            "max_active_hypotheses": 2, "max_reasoning_hops": 1,
            "max_candidate_intents": 3, "planning_horizon": "short"},
        "dialogue": {"max_tokens": dialogue, "explanation_depth": "brief"},
        "envelope_digest": "test-envelope"})
    return {"task_kind": task, "context": {"actor_id": "char_a",
        "cognition_policy": policy.model_dump(mode="json")},
        "policy": {"max_tokens": requested}, "prompt": {}}


@pytest.fixture
def http(monkeypatch):
    sent = []

    def open_request(req, **kwargs):
        payload = json.loads(req.data)
        sent.append(payload)
        if payload.get("stream"):
            return io.BytesIO(b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n')
        return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop",
            "message": {"content": '{"content":"hello","tone":"neutral"}'}}]}).encode())

    monkeypatch.setattr(transport, "urlopen", open_request)
    provider = transport.CharacterModelProvider(provider_kind="openai_compatible",
        endpoint_url="http://synthetic.invalid/v1", api_key="test", model_name="test")
    return provider, sent


@pytest.mark.parametrize("task,limit", [("l2_reasoning", 31), ("l3_planning", 47), ("dialogue_generation", 19)])
def test_frozen_task_budget_caps_actual_serialized_http_request(http, task, limit):
    provider, sent = http
    request = frozen_request(task)
    original = copy.deepcopy(request)
    provider.complete(request)
    assert sent[0]["max_tokens"] == limit
    assert request == original


def test_frozen_dialogue_budget_caps_sse_transport(http):
    provider, sent = http
    events = list(provider.stream_dialogue(frozen_request("dialogue_generation"), cancelled=lambda: False))
    assert sent[0]["stream"] is True
    assert sent[0]["max_tokens"] == 19
    assert events[-1]["event"] == "completed"


def test_smaller_prompt_limit_is_preserved(http):
    provider, sent = http
    provider.complete(frozen_request(requested=7))
    assert sent[0]["max_tokens"] == 7


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("invalid", ["zero", "tampered", "missing_digest", "other_actor"])
def test_invalid_or_zero_budget_rejects_without_network_or_fallback(http, stream, invalid):
    provider, sent = http
    request = frozen_request("dialogue_generation", dialogue=0 if invalid == "zero" else 19)
    policy = request["context"]["cognition_policy"]
    if invalid == "tampered":
        policy["dialogue"]["max_tokens"] = 9000
    elif invalid == "missing_digest":
        del policy["policy_digest"]
    elif invalid == "other_actor":
        request["context"]["actor_id"] = "char_b"
    with pytest.raises(ValueError):
        if stream:
            list(provider.stream_dialogue(request, cancelled=lambda: False))
        else:
            provider.complete(request)
    assert not sent


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("provider_kind", ["openai_compatible", "hybrid", "local"])
@pytest.mark.parametrize("requested", [0, -1, True, "4"])
def test_invalid_requested_limit_cannot_escape_through_stream_fallback(http, monkeypatch, stream, provider_kind, requested):
    provider, sent = http
    provider._provider_kind = provider_kind
    monkeypatch.setattr(transport.settings, "character_model_require_online", False)
    monkeypatch.delenv("CHARACTER_MODEL_REQUIRE_ONLINE", raising=False)
    request = frozen_request("dialogue_generation", requested=requested)
    with pytest.raises(ValueError):
        if stream:
            list(provider.stream_dialogue(request, cancelled=lambda: False))
        else:
            provider.complete(request)
    assert not sent
