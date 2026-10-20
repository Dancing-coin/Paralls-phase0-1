import copy
import json

import pytest

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.character_agent.models.mind_frame import CharacterMindFrame, MindFrameProvenance
from app.character_agent.models.turn_context import CharacterTurnContext
from app.config import settings
from app.character_agent.cognition.capability_envelope import CapabilityEnvelope, CognitiveLimits
from app.character_agent.cognition.cognition_policy import CognitionPolicy


class RecordingProvider:
    def __init__(self, output):
        self.output = output
        self.requests = []

    def complete(self, request):
        self.requests.append(copy.deepcopy(request))
        return self.output


def proposal_context():
    turn = CharacterTurnContext(
        turn_id="turn:1", actor_id="char_a", source_event_ref="outcome:1",
        causation_id="cause:1", correlation_id="correlation:1", lifecycle="prepared",
        input_revision_vector={"source": 1}, memory_revision_vector={"goals": 2},
        policy_revision="policy:1", snapshot_revision=1, valid_at=10, producer_ts=10,
    )
    frame = CharacterMindFrame(
        actor_id="char_a", mind_turn_id="mind:1", producer_ts=10,
        provenance=MindFrameProvenance(source_refs=["outcome:1"]),
    ).bind_to_turn(turn)
    envelope = CapabilityEnvelope(
        actor_id="char_a", turn_id="turn:1", capability_revision="cap:1", envelope_revision="env:1",
        cognitive_limits=CognitiveLimits(), source_refs=("outcome:1",),
        revision_pins={"policy_revision": "policy:1"},
    )
    policy = CognitionPolicy.resolve(envelope=envelope, requested_tier="balanced")
    return dict(
        request_id="proposal:1", actor_id="char_a", trigger_kind="repeated_failure", trigger_source_ref="outcome:1",
        frame=frame.model_dump(mode="json"), current_goal_state={"primary_goal": "open_gate"},
        goal_state_history=[], interpretation_summary="The locked gate resisted repeated attempts.",
        evidence_refs=["outcome:1"], capability_envelope=envelope.model_dump(mode="json"),
        cognition_policy=policy.model_dump(mode="json"),
        goal_revision=2, expires_at=30,
    )


def prepare(gateway, context=None, contract="goal_proposal:v1", route="online_default"):
    return gateway.prepare_run_request(
        task_kind="l3_planning", context=context or proposal_context(),
        route_override=route, output_contract=contract,
    )


def test_proposal_roundtrip_preserves_frozen_input_without_an_action(monkeypatch):
    monkeypatch.setattr(settings, "character_model_provider_kind", "deepseek")
    provider = RecordingProvider({"active_goal_frame": {"primary_goal": "find_gate_key"}, "evidence_refs": ["outcome:1"]})
    gateway = CharacterModelGateway(provider=provider)
    context = proposal_context()
    request = prepare(gateway, context)
    frozen = gateway.freeze_prepared_request(request)
    context["current_goal_state"]["primary_goal"] = "mutated"
    output = gateway.complete_prepared_request(frozen)
    assert output["active_goal_frame"]["primary_goal"] == "find_gate_key"
    assert set(output) == {"active_goal_frame", "evidence_refs"}
    sent = provider.requests[0]
    assert sent["output_contract"] == "goal_proposal:v1"
    assert sent["context"]["current_goal_state"]["primary_goal"] == "open_gate"
    assert sent["prompt"]["required_output_keys"] == ["active_goal_frame", "evidence_refs"]
    assert json.loads(sent["prompt"]["user_instruction"])["frame"]["turn_id"] == "turn:1"
    assert "candidate_intents" not in sent["prompt"]["system_instruction"]


@pytest.mark.parametrize("route", ["local_only", "laya", "hybrid_ready"])
def test_proposal_rejects_non_generative_route_before_provider(route):
    provider = RecordingProvider({})
    with pytest.raises(ValueError, match="generative"):
        prepare(CharacterModelGateway(provider=provider), route=route)
    assert provider.requests == []


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(trigger_kind="confidence_low"),
    lambda c: c.update(trigger_source_ref="hidden:1"),
    lambda c: c.update(evidence_refs=["hidden:1"]),
    lambda c: c.update(evidence_refs=["outcome:1", "outcome:1"]),
    lambda c: c.update(raw_dossier={"secret": True}),
    lambda c: c["frame"].update(frame_digest="tampered"),
    lambda c: c.update(expires_at=10),
    lambda c: c.update(cognition_policy={}),
    lambda c: c["cognition_policy"].update(policy_digest=""),
    lambda c: c["capability_envelope"].update(envelope_digest=""),
    lambda c: c.update(actor_id="other"),
])
def test_proposal_rejects_malformed_context_before_provider(monkeypatch, mutation):
    monkeypatch.setattr(settings, "character_model_provider_kind", "deepseek")
    provider = RecordingProvider({})
    context = proposal_context()
    mutation(context)
    with pytest.raises(ValueError):
        prepare(CharacterModelGateway(provider=provider), context)
    assert provider.requests == []


@pytest.mark.parametrize("output", [
    {"active_goal_frame": {"primary_goal": " "}, "evidence_refs": []},
    {"active_goal_frame": {"primary_goal": 7}, "evidence_refs": []},
    {"active_goal_frame": {"primary_goal": "search", "actor_id": "other"}, "evidence_refs": []},
    {"active_goal_frame": {"primary_goal": "search"}, "evidence_refs": ["hidden:1"]},
    {"active_goal_frame": {"primary_goal": "search"}, "evidence_refs": ["outcome:1", "outcome:1"]},
    {"active_goal_frame": {"primary_goal": "search"}, "evidence_refs": [], "selected_intent": "attack"},
    {"active_goal_frame": {"primary_goal": "search"}, "evidence_refs": [], "request_id": "changed"},
    {"active_goal_frame": {"primary_goal": "search", "goal_portfolio": [{"goal_id": "g", "goal": "x", "source": "model", "horizon": "short", "status": "pending"}]}, "evidence_refs": []},
])
def test_proposal_output_rejected_without_action_coercion(monkeypatch, output):
    monkeypatch.setattr(settings, "character_model_provider_kind", "deepseek")
    provider = CharacterModelProvider(provider_kind="deepseek", endpoint_url="https://test.invalid", api_key="test")
    monkeypatch.setattr(provider, "_complete_via_deepseek", lambda request: output)
    gateway = CharacterModelGateway(provider=provider)
    with pytest.raises(ValueError):
        gateway.complete_prepared_request(gateway.freeze_prepared_request(prepare(gateway)))


def test_unknown_contract_rejected_on_prepare_and_restored_request(monkeypatch):
    monkeypatch.setattr(settings, "character_model_provider_kind", "deepseek")
    provider = RecordingProvider({})
    gateway = CharacterModelGateway(provider=provider)
    with pytest.raises(ValueError, match="contract"):
        prepare(gateway, contract="goal_proposal:v2")
    request = prepare(gateway)
    request["output_contract"] = "goal_proposal:v2"
    with pytest.raises(ValueError, match="contract"):
        gateway.complete_prepared_request(gateway.freeze_prepared_request(request))
    assert provider.requests == []


def test_real_provider_returns_goal_proposal_without_adding_action_defaults(monkeypatch):
    monkeypatch.setattr(settings, "character_model_provider_kind", "deepseek")
    output = {"active_goal_frame": {"primary_goal": "find_gate_key"}, "evidence_refs": ["outcome:1"]}
    provider = CharacterModelProvider(provider_kind="deepseek", endpoint_url="https://test.invalid", api_key="test")
    monkeypatch.setattr(provider, "_complete_via_deepseek", lambda request: copy.deepcopy(output))
    gateway = CharacterModelGateway(provider=provider)
    result = gateway.complete_prepared_request(gateway.freeze_prepared_request(prepare(gateway)))
    assert set(result) == {"active_goal_frame", "evidence_refs"}
    assert result["active_goal_frame"]["primary_goal"] == "find_gate_key"
    request = prepare(gateway)
    assert provider._build_deepseek_request(request)["max_tokens"] == 900


@pytest.mark.parametrize("patch", [
    {"goal_portfolio": [{"goal_id": "g", "goal": "search", "source": "model", "horizon": "short"}] * 2},
    {"dominant_goal_id": "missing"},
    {"preserved_goal_ids": ["g"], "suppressed_goal_ids": ["g"]},
    {"preserved_goal_ids": ["missing"]},
    {"suppressed_goal_ids": ["g", "g"]},
    {"goal_portfolio": [{"goal_id": "g", "goal": "search", "source": "model", "horizon": "short", "supporting_evidence": ["hidden:1"]}]},
])
def test_proposal_rejects_ambiguous_portfolio_references(monkeypatch, patch):
    monkeypatch.setattr(settings, "character_model_provider_kind", "deepseek")
    frame = {"primary_goal": "search", "goal_portfolio": [
        {"goal_id": "g", "goal": "search", "source": "model", "horizon": "short"},
    ], **patch}
    provider = RecordingProvider({"active_goal_frame": frame, "evidence_refs": ["outcome:1"]})
    gateway = CharacterModelGateway(provider=provider)
    with pytest.raises(ValueError):
        gateway.complete_prepared_request(gateway.freeze_prepared_request(prepare(gateway)))
