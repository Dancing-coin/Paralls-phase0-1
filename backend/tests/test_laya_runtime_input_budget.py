import json

import pytest

from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation


def _request(monkeypatch, summary="Visible event"):
    monkeypatch.setenv("CHARACTER_LAYA_ENDPOINT", "http://127.0.0.1:1")
    interpretation = CharacterInterpretation(
        actor_id="char_a", interpreted_summary=summary,
        interpretation_type="ambiguous_event", salience_score=.8,
        ambiguity_level="high", risk_level="low", opportunity_level="low",
    )
    return json.loads(CharacterAgentL3Service().prepare_intent_plan(
        interpretation=interpretation, control_mode="agent_full_auto").request_json)


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_production_laya_freezes_default_complete_input_budget(monkeypatch, configured):
    monkeypatch.delenv("CHARACTER_LAYA_INPUT_MAX_LEN", raising=False)
    if configured is not None:
        monkeypatch.setenv("CHARACTER_LAYA_INPUT_MAX_LEN", configured)
    request = _request(monkeypatch)
    context = request["context"]
    assert context["input_budget_required"] is True
    assert context["max_len"] == LayaSystemOneProvider.DEFAULT_MAX_LEN
    assert context["head_max_len"] == LayaSystemOneProvider.OPTION_HEAD_MAX_LEN
    adapter = LayaSystemOneProvider(endpoint="http://127.0.0.1:1")
    monkeypatch.setattr(adapter, "_post", lambda _: pytest.fail("unverified input reached HTTP"))
    with pytest.raises(ValueError, match="pinned tokenizer"):
        adapter.complete(request)


def test_default_laya_budget_rejects_complete_state_overflow_before_http(monkeypatch):
    monkeypatch.delenv("CHARACTER_LAYA_INPUT_MAX_LEN", raising=False)
    request = _request(monkeypatch, "visible " * 3000)
    adapter = LayaSystemOneProvider(endpoint="http://127.0.0.1:1",
        option_tokenizer=lambda text: list(range(len(text.split()))), tokenizer_sha256="test:words")
    monkeypatch.setattr(adapter, "_post", lambda _: pytest.fail("oversized input reached HTTP"))
    with pytest.raises(ValueError, match="input budget exceeded before transport"):
        adapter.complete(request)


def test_laya_budget_remains_frozen_after_runtime_config_changes(monkeypatch):
    monkeypatch.delenv("CHARACTER_LAYA_INPUT_MAX_LEN", raising=False)
    request = _request(monkeypatch)
    frozen = json.dumps(request, sort_keys=True)
    monkeypatch.setenv("CHARACTER_LAYA_INPUT_MAX_LEN", "8192")
    adapter = LayaSystemOneProvider(endpoint="http://127.0.0.1:1",
        option_tokenizer=lambda text: list(range(len(text.split()))), tokenizer_sha256="test:words")
    wire = adapter.build_wire_request(request)
    assert wire["max_len"] == LayaSystemOneProvider.DEFAULT_MAX_LEN
    assert adapter.last_input_budget["max_len"] == wire["max_len"]
    assert json.dumps(request, sort_keys=True) == frozen
