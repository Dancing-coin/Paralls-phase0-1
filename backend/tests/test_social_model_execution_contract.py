from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.social_model import (DAILY_SUPPLY_DIMENSIONS, DailySupplyInput, DailySupplyReport,
    FactCard, FrozenModelInput, InputVersionVector, ModelComputation, ModelRunGrant, ModelRunReceipt,
    SocialModelDraft, SocialModelTemplate)
from app.population_continuity.simulation_contracts import simulation_digest
from app.services.social_model_execution import validate_model_run, validate_model_computation


def standard_inputs(**data_updates):
    cards = tuple(FactCard(card_ref=f"card:{kind}", fact_kind=kind, owner_ref=f"owner:{kind}",
        source_ref=f"source:{kind}", source_revision="1", source_revision_vector={f"source:{kind}":1},
        source_digest=simulation_digest({"original": kind}),
        reader_ref="siming:test", purpose="daily_supply_analysis", scope="cohort:1",
        valid_at=0, recorded_at=0, expiry_tick=100,
        content={"confirmed": True, "tags": [kind]}, content_digest="") for kind in DAILY_SUPPLY_DIMENSIONS)
    vector=InputVersionVector(source_revisions={f"source:{kind}":1 for kind in DAILY_SUPPLY_DIMENSIONS},
        query_pins={"query:members":"1"}, shard_revision="1",
        projection_digests={f"source:{kind}":simulation_digest({"original": kind}) for kind in DAILY_SUPPLY_DIMENSIONS},
        content_digests={card.card_ref:card.content_digest for card in cards},
        policy_revision="policy:daily:1", template_ref="daily-shard-supply@1", definition_version="1",
        operator_revision="daily-supply-operators@1", observed_at="2026-10-10T04:15:00Z",
        from_tick=0,to_tick=20,expiry_tick=100,input_digest="")
    data=dict(resource_unit="food-unit", custody_ref="custody:1", route_ref="route:1",
        demand_units=(120,140),confirmed_supply_units=100,window_capacity_units=100,
        capacity_factor_bps=10000,delivery_ratio_bps=(4800,6200),qualification_confirmed=True,
        route_open=True,process_open=True,arrival_delay_ticks=1,deadline_tick=20,
        protected_categories=("care_households",))
    data.update(data_updates)
    return FrozenModelInput(reader_ref="siming:test",purpose="daily_supply_analysis",scope="cohort:1",
        shard_ref="shard:1",cards=cards,vector=vector,data=DailySupplyInput(**data))


def grant(**updates):
    value=dict(grant_ref="grant:1",revision="1",reader_ref="siming:test",purpose="daily_supply_analysis",
        scope="cohort:1",mode="shadow",template_ref="daily-shard-supply@1",definition_version="1",
        operator_revision="daily-supply-operators@1",policy_revision="policy:daily:1",issued_tick=0,expiry_tick=100,
        budget_units=100,analysis_window=(0,20),correlation_ref="correlation:1")
    value.update(updates)
    return ModelRunGrant(**value)


def test_standard_frozen_contract_is_admitted_without_writing_any_authority():
    inputs=standard_inputs()
    assert validate_model_run(template=SocialModelTemplate(),grant=grant(),inputs=inputs,tick=1) is None
    assert inputs.vector.input_digest.startswith("sha256:")


@pytest.mark.parametrize("kind,updates", [(SocialModelTemplate,{"template_ref":"arbitrary"}),
    (SocialModelTemplate,{"ir":"eval('code')"}),(SocialModelTemplate,{"operator_revision":"untrusted"}),
    (SocialModelDraft,{"facts":{"supply":999}}),(SocialModelDraft,{"callable":"run"})])
def test_unknown_templates_code_and_request_facts_are_rejected(kind, updates):
    values={} if kind is SocialModelTemplate else dict(template_ref="daily-shard-supply@1",
        shard_ref="shard:1",window=(0,20),correlation_ref="correlation:1")
    with pytest.raises(ValidationError):
        kind(**{**values,**updates})


@pytest.mark.parametrize("updates,reason", [({"reader_ref":"wrong"},"policy_denied"),
    ({"scope":"other"},"policy_denied"),({"expiry_tick":1},"stale_input"),
    ({"issued_tick":2},"policy_denied"),({"budget_units":7},"budget_exhausted"),
    ({"policy_revision":"policy:wrong"},"policy_denied"),
    ({"analysis_window":(0,21)},"policy_denied")])
def test_grant_cannot_expand_scope_time_or_budget(updates,reason):
    with pytest.raises(ValueError,match=reason):
        validate_model_run(template=SocialModelTemplate(),grant=grant(**updates),inputs=standard_inputs(),tick=1)


def test_active_mode_is_not_admitted_by_unmet_gate():
    with pytest.raises(ValidationError):
        grant(mode="active")


def test_analysis_window_cannot_exceed_the_original_game_day():
    with pytest.raises(ValidationError):
        grant(analysis_window=(0,86401))
    with pytest.raises(ValidationError):
        SocialModelDraft(template_ref="daily-shard-supply@1",shard_ref="shard:1",
            window=(0,86401),correlation_ref="correlation:1")


def test_expired_card_is_stale_even_when_the_vector_and_grant_have_not_expired():
    inputs=standard_inputs()
    card=inputs.cards[0].model_copy(update={"expiry_tick":1})
    vector=inputs.vector.model_copy(update={"input_digest":""})
    stale=FrozenModelInput.model_validate({**inputs.model_dump(),"vector":vector,"cards":(card,*inputs.cards[1:])})
    with pytest.raises(ValueError,match="stale_input"):
        validate_model_run(template=SocialModelTemplate(),grant=grant(),inputs=stale,tick=1)


def test_model_copy_cannot_replace_the_fixed_dimension_order():
    changed=SocialModelTemplate().model_copy(update={"dimensions":tuple(reversed(DAILY_SUPPLY_DIMENSIONS))})
    with pytest.raises(ValueError):
        validate_model_run(template=changed,grant=grant(),inputs=standard_inputs(),tick=1)


def test_missing_card_is_context_insufficient_not_zero_supply():
    inputs=standard_inputs()
    reduced=inputs.model_copy(update={"cards":inputs.cards[:-1]})
    with pytest.raises(ValueError,match="context_insufficient|digest"):
        validate_model_run(template=SocialModelTemplate(),grant=grant(),inputs=reduced,tick=1)


def test_unknown_route_cannot_produce_complete_coverage():
    with pytest.raises(ValueError,match="context_insufficient"):
        validate_model_run(template=SocialModelTemplate(),grant=grant(),inputs=standard_inputs(route_open=None),tick=1)


def test_off_grant_cannot_enter_calculation_admission():
    with pytest.raises(ValueError,match="policy_denied"):
        validate_model_run(template=SocialModelTemplate(),grant=grant(mode="off"),inputs=standard_inputs(),tick=1)


@pytest.mark.parametrize("tick", [True,-1,1.0])
def test_clock_cannot_be_coerced_at_admission(tick):
    with pytest.raises(ValueError):
        validate_model_run(template=SocialModelTemplate(),grant=grant(),inputs=standard_inputs(),tick=tick)


@pytest.mark.parametrize("updates", [{"budget_units":True},{"mode":"active"},{"reader_ref":"forged"}])
def test_model_copy_cannot_bypass_run_admission(updates):
    with pytest.raises(ValueError):
        validate_model_run(template=SocialModelTemplate(),grant=grant().model_copy(update=updates),inputs=standard_inputs(),tick=1)


def report(inputs,**updates):
    values=dict(shard_ref=inputs.shard_ref,from_tick=0,to_tick=20,demand_units=(120,140),
        confirmed_supply_units=100,reachable_supply_units=(48,62),coverage_bps=(3428,5167),
        blocking_reasons=(),upgrade_categories=("care_households",),input_digest=inputs.vector.input_digest,
        source_revisions=dict(inputs.vector.source_revisions),expiry_tick=100)
    values.update(updates)
    return DailySupplyReport(**values)


def test_report_contract_has_no_actor_allocation_and_failed_result_has_no_report():
    inputs=standard_inputs()
    valid=report(inputs)
    assert validate_model_computation(computation=ModelComputation(status="ok",report=valid,work_units=8),
        inputs=inputs,grant=grant()) is None
    with pytest.raises(ValidationError):
        report(inputs,actor_allocations={"char_a":62})
    with pytest.raises(ValidationError):
        ModelComputation(status="budget_exhausted",report=valid,work_units=8)


@pytest.mark.parametrize("changes", [{"input_digest":"sha256:"+"0"*64},
    {"shard_ref":"shard:other"},{"expiry_tick":101},{"source_revisions":{"source:new":1}}])
def test_report_must_reference_the_exact_frozen_input(changes):
    inputs=standard_inputs()
    with pytest.raises(ValueError):
        validate_model_computation(computation=ModelComputation(status="ok",report=report(inputs,**changes),work_units=8),
            inputs=inputs,grant=grant())


def test_report_zero_demand_requires_not_required_and_empty_coverage():
    inputs=standard_inputs(demand_units=(0,0))
    with pytest.raises(ValidationError):
        report(inputs,demand_units=(0,0))
    zero=report(inputs,demand_units=(0,0),coverage_bps=None,blocking_reasons=("not_required",))
    assert zero.coverage_bps is None


@pytest.mark.parametrize("value", [(2,1),(-1,1),(0,10001),(True,10)])
def test_report_coverage_is_strict_bounded_and_ordered(value):
    with pytest.raises(ValidationError):
        report(standard_inputs(),coverage_bps=value)


def test_success_report_cannot_exceed_grant_work_budget():
    inputs=standard_inputs()
    with pytest.raises(ValueError,match="budget_exhausted"):
        validate_model_computation(computation=ModelComputation(status="ok",report=report(inputs),work_units=101),
            inputs=inputs,grant=grant())


def test_unknown_or_known_closed_route_cannot_report_positive_reachability():
    for route in (None,False):
        inputs=standard_inputs(route_open=route)
        with pytest.raises(ValueError):
            validate_model_computation(computation=ModelComputation(status="ok",report=report(inputs),work_units=8),
                inputs=inputs,grant=grant())


def test_zero_reachable_supply_cannot_claim_positive_coverage():
    with pytest.raises(ValidationError):
        report(standard_inputs(),reachable_supply_units=(0,0))


def test_failure_receipt_records_pins_without_fact_bodies_or_fake_output():
    inputs=standard_inputs()
    values=dict(receipt_ref="run:1",correlation_ref="correlation:1",grant_ref="grant:1",grant_revision="1",
        reader_ref=inputs.reader_ref,purpose=inputs.purpose,scope=inputs.scope,mode="shadow",status="stale_input",
        template_ref="daily-shard-supply@1",definition_version="1",operator_revision="daily-supply-operators@1",
        policy_revision="policy:daily:1",input_digest=inputs.vector.input_digest,output_digest=None,
        read_card_refs=tuple(card.card_ref for card in inputs.cards),source_revisions=inputs.vector.source_revisions,
        work_units=0,budget_units=100,source_validation="stale")
    receipt=ModelRunReceipt(**values)
    assert ModelRunReceipt.model_validate_json(receipt.model_dump_json())==receipt
    for extra in ({"content":{"private":"body"}},{"output_digest":inputs.vector.input_digest},{"mode":"active"}):
        with pytest.raises(ValidationError):
            ModelRunReceipt(**{**values,**extra})
