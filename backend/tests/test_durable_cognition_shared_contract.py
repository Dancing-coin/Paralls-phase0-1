import json

import pytest

from app.character_agent.cognition.capability_envelope import CapabilityEnvelope
from app.character_agent.cognition.cognition_policy import CognitionPolicy
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.planning.l3_planner import PreparedCharacterIntentPlan
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation, CharacterPrivateWorldSnapshot

from test_character_cognition_coordinator import setup
from test_character_cognition_admission import request


def _pending(tmp_path, *, background=False):
    runtime, admissions, coordinator, child, handle = setup(tmp_path)
    if background:
        runtime._l1.apply_siming_output(runtime._plan_siming_entry(child.payload)['normalized_payload'])
        runtime.set_background_cognition_enabled(True)
        runtime.set_background_mode('char_a', 'active')
        runtime._refresh_weak_supervision_state(
            actor_id='char_a', producer_ts=9999, reason_summary='background enabled')
        child = admissions.admit(**{**request(), 'delivery_id': 'wake',
            'source_kind': 'run_background_cognition_tick', 'payload': {}, 'producer_ts': 10000})
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    return runtime, admissions, coordinator, child, handle, pending


def test_durable_l2_and_l3_use_one_frozen_source_contract(tmp_path):
    rt, _, coordinator, child, handle, pending = _pending(tmp_path)
    try:
        context = json.loads(pending.request_json)["context"]
        envelope = context["capability_envelope"]
        policy = context["cognition_policy"]
        assert policy["envelope_digest"] == envelope["envelope_digest"]
        assert envelope["turn_id"] == policy["turn_id"] == pending.frame["turn_id"]
        stable = rt._cognition_frame_value(pending.frame, "context")["stable_ability_snapshot"]
        assert stable["registry_revision"] != "skills:unknown"
        assert stable["skills"]
        coordinator.accept_l2(child.child_key, activation=handle, now=113., output={
            "interpreted_summary": "unexpected pressure", "interpretation_type": "observation",
            "ambiguity_level": "high", "risk_level": "high", "salience_score": .9,
        })
        coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
        coordinator.resume_l2(child.child_key, activation=handle, now=115.)
        l3 = coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
        prepared = rt._cognition_frame_value(l3.frame, "l3_prepared")["prepared"]
        assert prepared["capability_envelope"] == envelope
        assert prepared["cognition_policy"] == policy
        assert l3.frame["envelope_digest"] == envelope["envelope_digest"]
        assert l3.frame["policy_digest"] == policy["policy_digest"]
        decision = CharacterIntentDecision(
            actor_id="char_a", selected_intent="observe", persona_passed=True,
            logic_passed=True, gain_loss_passed=True, rationale="watch",
        )
        execution_turn = rt._durable_execution_turn_context(dict(
            l3.frame, decision=decision.model_dump(mode="json"),
        ))
        snapshot = CharacterPrivateWorldSnapshot.model_validate(l3.frame["entry_after"]["private_snapshot"])
        interpretation = CharacterInterpretation.model_validate(l3.frame["interpretation"])
        contract = rt._l4_executor.build_execution_contract(snapshot, interpretation, decision, execution_turn)
        frozen_turn = CharacterTurnContext.model_validate(rt._cognition_frame_value(l3.frame, "context")["turn_context"])
        assert contract.turn_id == execution_turn.turn_id == frozen_turn.turn_id == envelope["turn_id"]
        assert execution_turn.actor_id == frozen_turn.actor_id
        assert execution_turn.source_event_ref == frozen_turn.source_event_ref
        assert execution_turn.policy_revision == frozen_turn.policy_revision
    finally:
        rt.close()


@pytest.mark.parametrize('background', [False, True])
def test_provider_pending_reopen_does_not_recompile_contract(tmp_path, monkeypatch, background):
    rt, _, _, child, _, pending = _pending(tmp_path, background=background)
    rt.close()
    rt, _, coordinator, _, handle = setup(tmp_path)
    try:
        if background:
            rt.set_background_cognition_enabled(True)
            rt.set_background_mode('char_a', 'active')
            rt._refresh_weak_supervision_state(
                actor_id='char_a', producer_ts=9999, reason_summary='background enabled')
        monkeypatch.setattr(rt._skill_service, "compile_stable_snapshot", lambda **_: pytest.fail("must read frozen contract"))
        restored = coordinator.prepare_l2(child.child_key, activation=handle, now=113.)
        assert restored.request_json == pending.request_json
        assert restored.frame["envelope_digest"] == pending.frame["envelope_digest"]
    finally:
        rt.close()


def test_legacy_prepared_plan_remains_recoverable(tmp_path):
    rt, _, _, _, _, pending = _pending(tmp_path)
    try:
        snapshot = CharacterPrivateWorldSnapshot.model_validate(pending.frame["entry_after"]["private_snapshot"])
        interpretation = CharacterInterpretation(
            actor_id="char_a", interpreted_summary="observe", interpretation_type="observation",
            salience_score=.5, ambiguity_level="low", risk_level="low", opportunity_level="low",
        )
        prepared = rt._l3.prepare_intent_plan(
            interpretation=interpretation, control_mode="agent_full_auto", snapshot=snapshot.model_dump(mode="json"),
        )
        raw = prepared.to_json_value()
        for field in ("frozen_candidates", "candidate_mapping", "candidate_digest", "capability_envelope", "cognition_policy"):
            raw["prepared"].pop(field)
        legacy = PreparedCharacterIntentPlan.from_json_value(raw)
        assert legacy.request_json == prepared.request_json
        assert legacy.candidate_mapping == {}
        assert legacy.capability_envelope == {}
        raw["prepared"]["unknown_field"] = "foreign"
        with pytest.raises(ValueError, match="character_intent_frame_fields_invalid"):
            PreparedCharacterIntentPlan.from_json_value(raw)
    finally:
        rt.close()


@pytest.mark.parametrize("layer", ["l2", "l3"])
@pytest.mark.parametrize("mismatch", ["actor", "turn", "policy", "missing", "turn_actor", "turn_policy", "turn_source"])
def test_foreign_or_incomplete_pair_never_reaches_gateway(tmp_path, monkeypatch, layer, mismatch):
    rt, _, _, _, _, pending = _pending(tmp_path)
    try:
        context = rt._cognition_frame_value(pending.frame, "context")
        turn = CharacterTurnContext.model_validate(context["turn_context"])
        if mismatch.startswith("turn_"):
            field = {"turn_actor": "actor_id", "turn_policy": "policy_revision",
                     "turn_source": "source_event_ref"}[mismatch]
            raw_turn = dict(context["turn_context"], **{field: "foreign"})
            turn = CharacterTurnContext.model_validate(raw_turn)
        raw = dict(context["capability_envelope"])
        raw.pop("envelope_digest")
        if mismatch in {"actor", "turn"}:
            raw[{"actor": "actor_id", "turn": "turn_id"}[mismatch]] = "foreign"
        envelope = CapabilityEnvelope.model_validate(raw)
        policy = CognitionPolicy.resolve(envelope=envelope)
        if mismatch == "policy":
            raw_policy = policy.model_dump(mode="json", exclude={"policy_digest"})
            raw_policy["envelope_digest"] = "different"
            policy = CognitionPolicy.model_validate(raw_policy)
        args = dict(turn_context=turn, capability_envelope=envelope.model_dump(mode="json"),
                    cognition_policy=None if mismatch == "missing" else policy.model_dump(mode="json"))
        snapshot = CharacterPrivateWorldSnapshot.model_validate(pending.frame["entry_after"]["private_snapshot"])
        service = rt._l2 if layer == "l2" else rt._l3
        monkeypatch.setattr(service._gateway, "prepare_run_request", lambda **_: pytest.fail("foreign pair reached gateway"))
        with pytest.raises(ValueError, match="cognition_contract_"):
            if layer == "l2":
                service.prepare_reasoning_request(snapshot=snapshot, event={}, **args)
            else:
                interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="observe",
                    interpretation_type="observation", salience_score=.5, ambiguity_level="low",
                    risk_level="low", opportunity_level="low")
                service.prepare_intent_plan(interpretation=interpretation, control_mode="agent_full_auto",
                    snapshot=snapshot.model_dump(mode="json"), **args)
    finally:
        rt.close()
