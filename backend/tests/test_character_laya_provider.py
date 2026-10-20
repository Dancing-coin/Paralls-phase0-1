import json
import pytest
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.character_agent.planning.l3_planner import CandidateCompiler, CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation


@pytest.mark.parametrize("field,value", [
    ("active_goal_tags", ["inspect_notice"]),
    ("active_goal_frame", {"primary_goal": "inspect_notice"}),
    ("current_goal_state", {"immediate_goal": "inspect_notice"}),
    ("memory", {"observation_memories": [{"summary": "notice is unread"}]}),
    ("semantic_cards", [{"summary": "notice is unread", "source_refs": ["memory:1"]}]),
    ("need_tension_state", {"safety": 0.4}),
    ("dynamic_state", {"curiosity": 0.6}),
    ("supervision_state", {"status": "inactive"}),
    ("background_agenda_state", {"pending": ["inspect_notice"]}),
    ("unresolved_tensions", [{"summary": "notice is unread"}]),
])
def test_laya_preserves_frozen_deliberation_inputs_without_grading(field, value):
    context = {"interpretation": {"interpreted_summary": "Visible notice"},
               field: value, "grading": {"answer": "grading-sentinel"},
               "private_truth_profile": {"secret": "archive-sentinel"}}
    original = json.dumps(context, sort_keys=True)
    state = json.loads(LayaSystemOneProvider._state(context))
    assert state[field] == value
    assert "grading-sentinel" not in json.dumps(state)
    assert "archive-sentinel" not in json.dumps(state)
    assert json.dumps(context, sort_keys=True) == original


def test_laya_runtime_role_conditions_reach_wire_without_private_archive():
    interpretation = CharacterInterpretation(
        actor_id="char_a", interpreted_summary="Inspect the visible lock",
        interpretation_type="ambiguous_event", salience_score=0.5,
        ambiguity_level="high", risk_level="low", opportunity_level="low",
    )
    profile = {
        "identity_core": {"character_id": "char_a", "occupation_role": "archive attendant"},
        "capability_constraint_layer": {"knowledge_domains": ["archive procedure"]},
        "private_truth_profile": {"content": "private-sentinel"},
        "life_memory_backbone": {"defining_memories": ["private-sentinel"]},
    }
    prepared = CharacterAgentL3Service().prepare_intent_plan(
        interpretation=interpretation, control_mode="agent_full_auto",
        profile=profile, effective_profile=profile,
    )
    request = json.loads(prepared.request_json)
    state = LayaSystemOneProvider._state(request["context"])
    assert "archive attendant" in state
    assert "archive procedure" in state
    assert "max_reasoning_hops" in state
    assert "provider_thinking_effort" in state
    assert "private-sentinel" not in state


def test_laya_prepared_goal_and_recall_reach_the_actual_http_payload():
    interpretation = CharacterInterpretation(
        actor_id="char_a", interpreted_summary="The notice is unread",
        interpretation_type="ambiguous_event", salience_score=0.5,
        ambiguity_level="high", risk_level="low", opportunity_level="low",
    )
    prepared = CharacterAgentL3Service().prepare_intent_plan(
        interpretation=interpretation, control_mode="agent_full_auto",
        current_goal_state={"primary_goal": "read_notice", "immediate_goal": "inspect_notice"},
    )
    request = json.loads(prepared.request_json)
    original = json.dumps(request, sort_keys=True)
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1")
    wire = provider.build_wire_request(request)
    state = json.loads(wire["state"])
    assert state["active_goal_frame"]["immediate_goal"] == "inspect_notice"
    for key in ("active_goal_tags", "active_goal_frame", "current_goal_state", "memory"):
        assert state[key] == request["context"][key]
    assert list(wire["questions"]["choice"]["criteria"]) == request["context"]["candidate_intents"]
    assert json.dumps(request, sort_keys=True) == original


def test_laya_counts_recalled_memory_in_total_budget_before_http():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1",
        option_tokenizer=lambda text: text.split(), tokenizer_sha256="test:words")
    request = {"task_kind": "l3_planning", "context": {
        "candidate_intents": ["observe"], "input_budget_required": True,
        "max_len": 512, "memory": {"observation_memories": [{"summary": "memory " * 600}]},
    }}
    with pytest.raises(ValueError, match="input budget exceeded before transport"):
        provider.build_wire_request(request)


def test_explicit_event_does_not_override_runtime_role_conditions():
    state = LayaSystemOneProvider._state({
        "laya_state": "Visible lock damaged",
        "effective_profile": {"identity_core": {"character_id": "char_b", "occupation_role": "security"}},
        "grading": {"rationale": "grading-sentinel"},
    })
    assert "Visible lock damaged" in state
    assert "security" in state
    assert "grading-sentinel" not in state


class _Handler(BaseHTTPRequestHandler):
    request_body = None

    def do_POST(self):
        size = int(self.headers["Content-Length"])
        _Handler.request_body = json.loads(self.rfile.read(size))
        payload = {
            "model": "laya-rl-agent",
            "answers": {
                "choice": {
                    "type": "choice",
                    "choice": "attack_boss",
                    "probabilities": {"attack_boss": 0.8, "observe_boss": 0.2},
                    "confidence": 0.4,
                    "answer_confidence": 0.8,
                }
            },
            "usage": {"input_tokens": 10, "output_tokens": 0},
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def test_laya_maps_real_systemone_wire_to_l3_choice():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        provider = LayaSystemOneProvider(endpoint=f"http://127.0.0.1:{server.server_port}")
        result = provider.complete(
            {
                "task_kind": "l3_planning",
                "context": {
                    "actor_id": "char_a",
                    "interpretation": {"interpreted_summary": "Boss charging"},
                    "candidate_intents": ["attack_boss", "observe_boss"],
                    "active_goal_frame": {"primary_goal": "survive"},
                },
            }
        )
        assert result["selected_intent"] == "attack_boss"
        assert result["candidate_intents"] == ["attack_boss", "observe_boss"]
        assert result["recommended_intents"] == ["attack_boss"]
        assert _Handler.request_body["questions"]["choice"]["type"] == "choice"
        assert list(_Handler.request_body["questions"]["choice"]["criteria"]) == [
            "attack_boss", "observe_boss"
        ]
    finally:
        server.shutdown()


def test_laya_preserves_frozen_pin_evidence_and_candidate_order():
    class ReorderedProvider(LayaSystemOneProvider):
        def _post(self, payload):
            assert list(payload["questions"]["choice"]["criteria"]) == ["observe", "retreat"]
            return {
                "answers": {
                    "choice": {
                        "choice": "retreat",
                        "probabilities": {"retreat": 0.7, "observe": 0.3},
                    }
                }
            }

    provider = ReorderedProvider(endpoint="http://127.0.0.1:1")
    result = provider.complete(
        {
            "task_kind": "l3_planning",
            "context": {
                "candidate_intents": ["observe", "retreat"],
                "source_ref": "siming:event:42",
                "frame_digest": "frame:42",
                "expiry": 99.5,
                "policy_revision": "policy:character-runtime:v1",
                "input_revision_vector": {"l1_input": 42},
                "memory_revision_vector": {"memory": 7},
                "provider_revision": LayaSystemOneProvider.PROVIDER_REVISION,
            },
        }
    )
    assert result["candidate_intents"] == ["observe", "retreat"]
    assert result["selected_intent"] == "retreat"
    assert result["laya_evidence"]["frozen_request"] == {
        "candidate_ids": ["observe", "retreat"],
        "source_ref": "siming:event:42",
        "frame_digest": "frame:42",
        "expiry": 99.5,
        "policy_revision": "policy:character-runtime:v1",
        "input_revision_vector": {"l1_input": 42},
        "memory_revision_vector": {"memory": 7},
    }


def test_laya_rejects_stale_provider_revision_without_transport():
    class MustNotTransport(LayaSystemOneProvider):
        def _post(self, payload):
            raise AssertionError("stale revision must be rejected before transport")

    provider = MustNotTransport(endpoint="http://127.0.0.1:1")
    try:
        provider.complete(
            {
                "task_kind": "l3_planning",
                "context": {
                    "candidate_intents": ["observe"],
                    "provider_revision": "laya:old-source:old-checkpoint",
                },
            }
        )
    except ValueError as exc:
        assert str(exc) == "laya provider revision is stale"
    else:
        raise AssertionError("stale provider revision must be rejected")


def test_laya_rejects_invalid_candidate_shape_and_duplicates():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1")
    for candidates, expected in (("observe", "laya provider requires a frozen candidate list"),
                                 (["observe", "observe"], "laya provider requires unique frozen candidates")):
        try:
            provider.complete({"task_kind": "l3_planning", "context": {"candidate_intents": candidates}})
        except ValueError as exc:
            assert str(exc) == expected
        else:
            raise AssertionError("invalid candidates must be rejected")


def test_laya_unavailable_provider_is_fail_closed():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", timeout_seconds=0.05)
    try:
        provider.complete({"task_kind": "l3_planning", "context": {"candidate_intents": ["observe"]}})
    except ValueError as exc:
        assert str(exc).startswith("laya provider request failed:")
    else:
        raise AssertionError("unavailable Laya must fail closed")


def test_laya_timeout_is_fail_closed():
    class TimeoutProvider(LayaSystemOneProvider):
        def _post(self, payload):
            raise TimeoutError("provider timeout")

    provider = TimeoutProvider(endpoint="http://127.0.0.1:8765")
    try:
        provider.complete({"task_kind": "l3_planning", "context": {"candidate_intents": ["observe"]}})
    except ValueError as exc:
        assert str(exc) == "laya provider request failed: TimeoutError"
    else:
        raise AssertionError("Laya timeout must fail closed")


def test_laya_rejects_unknown_choice_without_fallback():
    class UnknownProvider(LayaSystemOneProvider):
        def _post(self, payload):
            return {"answers": {"choice": {"choice": "not_present", "probabilities": {}}}}

    provider = UnknownProvider(endpoint="http://127.0.0.1:1")
    try:
        provider.complete({"task_kind": "l3_planning", "context": {"candidate_intents": ["observe"]}})
    except ValueError as exc:
        assert str(exc) == "laya choice is not in frozen candidates"
    else:
        raise AssertionError("unknown Laya choice must be rejected")


def test_gateway_laya_route_preserves_provider_evidence():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        provider = CharacterModelProvider(
            provider_kind="laya", endpoint_url=f"http://127.0.0.1:{server.server_port}"
        )
        gateway = CharacterModelGateway(provider=provider)
        request = gateway.prepare_run_request(
            task_kind="l3_planning",
            route_override="laya",
            context={
                "actor_id": "char_a",
                "candidate_intents": ["attack_boss", "observe_boss"],
                "active_goal_frame": {"primary_goal": "survive"},
                "interpretation": {},
                "snapshot": {},
                "memory": {},
            },
        )
        output = gateway.complete_prepared_request(gateway.freeze_prepared_request(request))
        assert output["selected_intent"] == "attack_boss"
        assert provider.last_call_evidence.transport_succeeded is True
        assert provider.last_call_evidence.fallback_used is False
    finally:
        server.shutdown()


def test_l3_prepared_request_freezes_candidate_ids_for_laya_wire():
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="Boss is charging",
        interpretation_type="combat_threat",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="high",
        opportunity_level="low",
        attention_target="boss",
    )
    prepared = CharacterAgentL3Service().prepare_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"current_attention_targets": ["boss"]},
    )
    request = json.loads(prepared.request_json)
    assert request["context"]["candidate_intents"]
    assert request["context"]["candidate_intents"][0] == "observe"


def test_l3_prepared_request_freezes_complete_candidates_without_attention_target_fallback():
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="Boss is charging",
        interpretation_type="combat_threat",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="high",
        opportunity_level="low",
        attention_target="char_player",
    )
    prepared = CharacterAgentL3Service().prepare_intent_plan(
        interpretation=interpretation,
        control_mode="agent_full_auto",
        snapshot={"current_attention_targets": ["char_player"]},
    )
    request = json.loads(prepared.request_json)
    assert request["context"]["candidate_digest"] == prepared.candidate_digest
    assert request["context"]["candidate_mapping"]["observe"]["target_refs"] == {}
    assert all(not item["target_refs"] for item in prepared.frozen_candidates)
    assert "short_punch" not in request["context"]["candidate_intents"]


def test_laya_strict_mapping_rejects_reordered_or_diagnosed_candidates():
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1")
    compilation = CandidateCompiler().compile(candidates=[
        {"candidate_id": "observe", "wire_label": "observe", "action_family": "observation", "semantic_intent_id": "observe", "target_refs": {}},
        {"candidate_id": "probe", "wire_label": "probe", "action_family": "observation", "semantic_intent_id": "ask_probe", "target_refs": {}},
    ])
    base = {
        "candidate_intents": ["observe", "probe"],
        "frozen_candidates": compilation.presented,
        "candidate_mapping": compilation.by_wire_label,
        "candidate_digest": compilation.digest,
    }
    with pytest.raises(ValueError, match="candidate order"):
        provider.complete({"task_kind": "l3_planning", "context": {**base, "candidate_intents": ["probe", "observe"]}})
    diagnosed = dict(base["candidate_mapping"])
    diagnosed["probe"] = {**diagnosed["probe"], "diagnosis": {"status": "blocked"}}
    with pytest.raises(ValueError, match="diagnosed"):
        provider.complete({"task_kind": "l3_planning", "context": {**base, "candidate_mapping": diagnosed}})


def test_l3_can_select_laya_route_without_changing_l2_provider(monkeypatch):
    monkeypatch.setenv("CHARACTER_LAYA_ENDPOINT", "http://127.0.0.1:8765")
    monkeypatch.setenv("CHARACTER_LAYA_API_KEY", "test-key")
    service = CharacterAgentL3Service()
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="Boss is charging",
        interpretation_type="combat_threat",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="high",
        opportunity_level="low",
        attention_target="boss",
    )
    prepared = service.prepare_intent_plan(interpretation=interpretation, control_mode="agent_full_auto")
    request = json.loads(prepared.request_json)
    assert request["route"]["provider_kind"] == "laya"
    assert request["route"]["route_mode"] == "laya_systemone"
    assert request["context"]["provider_revision"] == LayaSystemOneProvider.PROVIDER_REVISION
    assert service._gateway._provider._provider_kind != "laya"
    assert CharacterModelProvider()._provider_kind != "laya"


def test_runtime_laya_explicit_budget_is_frozen_before_dispatch(monkeypatch):
    monkeypatch.setenv("CHARACTER_LAYA_ENDPOINT", "http://127.0.0.1:8765")
    monkeypatch.setenv("CHARACTER_LAYA_INPUT_MAX_LEN", "8192")
    interpretation = CharacterInterpretation(
        actor_id="char_a", interpreted_summary="Visible event", interpretation_type="ambiguous_event",
        salience_score=.8, ambiguity_level="high", risk_level="low", opportunity_level="low")
    request = json.loads(CharacterAgentL3Service().prepare_intent_plan(
        interpretation=interpretation, control_mode="agent_full_auto").request_json)
    assert request["context"]["input_budget_required"] is True
    assert request["context"]["max_len"] == 8192
    with pytest.raises(ValueError, match="pinned tokenizer"):
        CharacterModelProvider().complete(request)


def test_runtime_laya_adapter_receives_explicit_tokenizer_pin(monkeypatch):
    seen = {}
    class Adapter:
        def __init__(self, **kwargs):
            seen.update(kwargs)
        def complete(self, request):
            return {"selected_intent": "observe"}
    monkeypatch.setattr("app.character_agent.gateway.model_provider.LayaSystemOneProvider", Adapter)
    monkeypatch.setenv("CHARACTER_LAYA_TOKENIZER_PATH", "fixed/tokenizer.json")
    monkeypatch.setenv("CHARACTER_LAYA_TOKENIZER_SHA256", "sha256:fixed")
    CharacterModelProvider(provider_kind="laya", endpoint_url="http://127.0.0.1:8765").complete(
        {"task_kind": "l3_planning", "context": {}})
    assert seen["tokenizer_path"] == "fixed/tokenizer.json"
    assert seen["tokenizer_sha256"] == "sha256:fixed"


def test_laya_route_uses_its_endpoint_instead_of_reasoning_endpoint(monkeypatch):
    seen = {}
    class Adapter:
        def __init__(self, **kwargs):
            seen.update(kwargs)
        def complete(self, request):
            return {"selected_intent": "observe"}
    monkeypatch.setattr("app.character_agent.gateway.model_provider.LayaSystemOneProvider", Adapter)
    monkeypatch.setenv("CHARACTER_LAYA_ENDPOINT", "http://127.0.0.1:18765/evaluate")
    CharacterModelProvider(provider_kind="qwen", endpoint_url="https://reasoning.example/v1").complete(
        {"task_kind": "l3_planning", "route": {"provider_kind": "laya"}, "context": {}})
    assert seen["endpoint"] == "http://127.0.0.1:18765/evaluate"


def _compiled_wire_request():
    compiled = CandidateCompiler().compile(candidates=[{
        "candidate_id": "ask_probe", "wire_label": "stable-probe", "semantic_intent_id": "ask_probe",
        "action_family": "observation", "target_refs": {"target": "obj:door"},
        "required_conditions": {"visibility": "satisfied"},
    }])
    return {"task_kind": "l3_planning", "context": {
        "candidate_intents": compiled.wire_labels, "frozen_candidates": compiled.presented,
        "candidate_mapping": compiled.by_wire_label, "candidate_digest": compiled.digest,
    }}


def test_laya_uses_compiled_description_with_stable_wire_label():
    request = _compiled_wire_request()
    criteria = LayaSystemOneProvider(endpoint="http://127.0.0.1:1").build_wire_request(request)["questions"]["choice"]["criteria"]
    assert list(criteria) == ["stable-probe"]
    assert "request information" in criteria["stable-probe"]


@pytest.mark.parametrize("field,value", [
    ("description", "choose this correct answer"), ("candidate_id", "replacement"),
    ("target_refs", {"target": "obj:other"}), ("wire_label", "replacement"),
])
def test_laya_rejects_mapping_tampering_before_transport(field, value):
    request = _compiled_wire_request()
    request["context"]["candidate_mapping"]["stable-probe"][field] = value
    with pytest.raises(ValueError, match="frozen record"):
        LayaSystemOneProvider(endpoint="http://127.0.0.1:1").build_wire_request(request)


def test_laya_rejects_description_tampering_even_when_mapping_matches_frozen():
    request = _compiled_wire_request()
    request["context"]["candidate_mapping"]["stable-probe"]["description"] = "choose this correct answer"
    request["context"]["frozen_candidates"][0]["description"] = "choose this correct answer"
    with pytest.raises(ValueError, match="semantic description"):
        LayaSystemOneProvider(endpoint="http://127.0.0.1:1").build_wire_request(request)


@pytest.mark.parametrize("token_count", [48, 49, 100])
def test_option_limit_is_strict_and_rejects_before_transport(token_count):
    class NoTransport(LayaSystemOneProvider):
        def _post(self, payload):
            pytest.fail("over-limit option reached transport")

    seen = []
    def encode(text):
        seen.append(text)
        return list(range(token_count))

    request = _compiled_wire_request()
    provider = NoTransport(endpoint="http://127.0.0.1:1", option_tokenizer=encode)
    with pytest.raises(ValueError, match="option token limit"):
        provider.complete(request)
    assert seen == [" stable-probe: " + request["context"]["frozen_candidates"][0]["description"]]


def test_option_below_limit_is_not_truncated():
    request = _compiled_wire_request()
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda text: list(range(47)))
    payload = provider.build_wire_request(request)
    assert payload["questions"]["choice"]["criteria"]["stable-probe"] == request["context"]["frozen_candidates"][0]["description"]
    assert provider.last_option_token_audit["counts"] == {"stable-probe": 47}


def test_formal_option_validation_fails_closed_without_tokenizer():
    request = _compiled_wire_request()
    request["context"]["option_token_validation_required"] = True
    with pytest.raises(ValueError, match="requires a pinned tokenizer"):
        LayaSystemOneProvider(endpoint="http://127.0.0.1:1").build_wire_request(request)


@pytest.mark.parametrize("pin", [None, "sha256:wrong"])
def test_formal_option_validation_rejects_missing_or_wrong_tokenizer_pin(pin):
    request = _compiled_wire_request()
    request["context"].update(option_token_validation_required=True, option_tokenizer_sha256=pin)
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda text: [1], tokenizer_sha256="sha256:" + "a" * 64)
    with pytest.raises(ValueError, match="tokenizer pin"):
        provider.build_wire_request(request)


def test_aggregate_option_budget_cannot_trigger_laya_head_truncation():
    request = {"task_kind": "l3_planning", "context": {"candidate_intents": [f"c{i}" for i in range(6)]}}
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda text: list(range(47)))
    with pytest.raises(ValueError, match="option head budget"):
        provider.build_wire_request(request)


def test_formal_option_validation_accepts_pinned_current_contract():
    request = _compiled_wire_request()
    pin = "sha256:" + "a" * 64
    request["context"].update(option_token_validation_required=True, option_tokenizer_sha256=pin)
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda text: [1], tokenizer_sha256=pin)
    provider.build_wire_request(request)
    assert provider.last_option_token_audit["formal_pins_verified"] is True


def test_formal_option_validation_rejects_archived_v4_contract():
    compiled = CandidateCompiler(description_contract_revision="candidate-semantics:v4:1").compile(candidates=[{
        "candidate_id": "observe", "action_family": "observation", "semantic_intent_id": "observe",
    }])
    pin = "sha256:" + "a" * 64
    request = {"task_kind": "l3_planning", "context": {
        "candidate_intents": compiled.wire_labels, "frozen_candidates": compiled.presented,
        "candidate_mapping": compiled.by_wire_label, "candidate_digest": compiled.digest,
        "option_token_validation_required": True, "option_tokenizer_sha256": pin,
    }}
    provider = LayaSystemOneProvider(endpoint="http://127.0.0.1:1", option_tokenizer=lambda text: [1], tokenizer_sha256=pin)
    with pytest.raises(ValueError, match="current candidate semantics"):
        provider.build_wire_request(request)
    request["context"]["option_token_validation_required"] = False
    assert provider.build_wire_request(request)["questions"]["choice"]["criteria"]["observe"] == compiled.presented[0]["description"]
