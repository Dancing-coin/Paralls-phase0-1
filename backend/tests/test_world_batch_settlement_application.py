"""Actual internal caller, serialized runtime and original durable owners."""
import asyncio
import json
from dataclasses import asdict, replace
from fractions import Fraction

import pytest

from app.world_runtime.temporal_contracts import SettlementWindow, SimulationTime
from test_status_application_lifecycle import application
from test_temporal_profile_migration import request as migration_request
from test_world_batch_settlement_recovery import _setup, _plan


def inputs(main, suffix="1"):
    _, _, _, first, second = _setup(store=main.gameplay_event_store)
    driver = main._population_runtime_driver
    end = driver.current_tick
    start = end - driver.window_size
    def time(tick):
        return SimulationTime(driver.clock.timeline.timeline_id,
                              int(Fraction(tick) / driver.clock.temporal_profile.step_duration), Fraction(tick))
    window = SettlementWindow(
        window_ref=f"settlement:{suffix}", timeline_id=driver.clock.timeline.timeline_id,
        from_time=time(start), to_time=time(end), participant_scope=(first.owner_ref, second.owner_ref),
        phase_ref=None, input_cutoff=time(end), late_input_policy_ref="reject_after_cutoff",
        confirmation_boundary=time(end), frozen_read_set=tuple(sorted({**first.command.expected_revisions, **second.command.expected_revisions}.items())),
        evidence_refs=("evidence:verified",), ordering_policy_ref="dependency_then_ref",
        expected_authority_revisions=tuple(sorted({**first.command.expected_revisions, **second.command.expected_revisions}.items())),
        settlement_idempotency_key=f"batch:{suffix}")
    # Existing owners use canonical population seconds, never new profile steps.
    org = main._settlement_batch_coordinator.adapters[(first.owner_ref, first.owner_contract_ref)]
    econ = main._settlement_batch_coordinator.adapters[(second.owner_ref, second.owner_contract_ref)]
    a = json.loads(first.request_json)
    a["window"].update(opens_at_tick=start, closes_at_tick=end)
    first = org.freeze(operation_ref=first.operation_ref, **a)
    b = json.loads(second.request_json)
    b["due_tick"] = end
    second = econ.freeze(operation_ref=second.operation_ref, **b)
    plan = _plan(first, second, batch_ref=f"batch:{suffix}", timeline_ref=window.timeline_id,
                 window_ref=window.window_ref, confirmation_boundary=f"{window.window_ref}:end", frozen_window=None)
    plan = replace(plan, frozen_window=None)
    return plan, window


async def submit(main, *, plan=None, window=None, budget=0, batch_ref="batch:1", **kw):
    return await asyncio.wrap_future(main.submit_settlement_batch(
        plan=plan, window=window, batch_ref=batch_ref, budget=budget,
        advancement_owner_ref=main._population_runtime_driver.clock.timeline.advancement_owner_ref, **kw))


@pytest.mark.asyncio
async def test_real_caller_new_store_owner_runtime_receipts_and_frozen_pins(application, record_property):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    result = await submit(main, plan=plan, window=window, budget=1)
    assert result.stage == "pending_recovery" and result.recovery_cursor == 1
    assert result.confirmation_boundary is None
    old_store, old_runtime, old_owners = main.gameplay_event_store, main.runtime_execution, main._settlement_batch_coordinator
    await advance(86400)
    await asyncio.wrap_future(main.submit_temporal_profile_migration(**migration_request(main)))
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main.gameplay_event_store is not old_store and main.runtime_execution is not old_runtime
    assert main._settlement_batch_coordinator is not old_owners
    recovered = await submit(main, budget=1)
    assert recovered.stage == "completed" and recovered.input_digest == result.input_digest
    assert recovered.receipts[0] == result.receipts[0]
    assert recovered.receipts[1].input_digest == plan.operations[1].input_digest
    assert await submit(main) == recovered
    frozen = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.get_projection_checkpoint("batch-input:batch:1")))
    assert frozen.state["plan"]["frozen_window"]["profile"]["revision"] == "population-seconds:v1"
    assert main._population_runtime_driver.clock.temporal_profile.revision == "population-thirds:v2"
    record_property("frozen_batch", json.dumps(frozen.state))
    record_property("owner_receipts", json.dumps(asdict(recovered)))
    await advance(172800)
    new_plan, new_window = inputs(main, "2")
    # Even with a new batch ref, an old owner key cannot be rebound to another window.
    with pytest.raises(ValueError, match="batch_operation_identity_reused"):
        await submit(main, plan=new_plan, window=new_window, batch_ref="batch:2")
    org = main._settlement_batch_coordinator.adapters[(new_plan.operations[0].owner_ref, new_plan.operations[0].owner_contract_ref)]
    econ = main._settlement_batch_coordinator.adapters[(new_plan.operations[1].owner_ref, new_plan.operations[1].owner_contract_ref)]
    a = json.loads(new_plan.operations[0].request_json)
    a.update(command_id="window:new", idempotency_key="window:new")
    a["window"]["window_ref"] = "window:new"
    first = org.freeze(operation_ref="window", **a)
    b = json.loads(new_plan.operations[1].request_json)
    b["command"].update(command_id="wage:new", idempotency_key="wage:new",
        expected_revisions={"gameplay:economy:wage:character:char_b": 1},
        read_set_revisions={"gameplay:organization:window:window:new": 1})
    b["accrual_ref"] = "accrual:new"
    second = econ.freeze(operation_ref="wage", **b)
    revisions = tuple(sorted({**first.command.expected_revisions, **second.command.expected_revisions}.items()))
    new_plan = replace(new_plan, operations=(first, second))
    new_window = replace(new_window, frozen_read_set=revisions, expected_authority_revisions=revisions)
    assert (await submit(main, plan=new_plan, window=new_window, batch_ref="batch:2", budget=2)).stage == "completed"
    new_frozen = main.gameplay_event_store.get_projection_checkpoint("batch-input:batch:2")
    assert new_frozen.state["plan"]["frozen_window"]["profile"]["revision"] == "population-thirds:v2"
    assert new_frozen.state["plan"]["frozen_window"]["window"]["to_time"]["step_index"] == 259200
    record_property("new_version_frozen_batch", json.dumps(new_frozen.state))


@pytest.mark.asyncio
async def test_changed_window_rules_payload_and_untrusted_cursor(application):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    partial = await submit(main, plan=replace(plan, recovery_cursor=2), window=window)
    assert partial.recovery_cursor == 0 and partial.stage == "pending_recovery"
    for changed, changed_window in (
        (replace(plan, definition_and_rule_pins=("policy:2",)), window),
        (plan, replace(window, evidence_refs=("changed",))),
        (replace(plan, window_ref="changed"), replace(window, window_ref="changed")),
    ):
        with pytest.raises(ValueError, match="batch_input_identity_reused"):
            await submit(main, plan=changed, window=changed_window, budget=2)
    completed = await submit(main, plan=replace(plan, recovery_cursor=1), window=window, budget=2)
    assert completed.stage == "completed" and completed.input_digest == partial.input_digest
    original = main._settlement_batch_coordinator.load(plan.batch_ref).frozen_window
    changed_pins = replace(original, mapping=replace(original.mapping, revision="changed"))
    with pytest.raises(ValueError, match="batch_input_identity_reused"):
        await submit(main, plan=replace(plan, frozen_window=changed_pins), window=window)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["cutoff", "boundary", "timeline", "evidence", "revisions", "read_set", "participant", "range"])
async def test_illegal_window_zero_owner_events(application, fault):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    if fault == "cutoff": window = replace(window, input_cutoff=window.from_time)
    if fault == "boundary": window = replace(window, confirmation_boundary=window.from_time)
    if fault == "timeline": plan = replace(plan, timeline_ref="other")
    if fault == "evidence": window = replace(window, evidence_refs=())
    if fault == "revisions": window = replace(window, expected_authority_revisions=())
    if fault == "read_set": window = replace(window, frozen_read_set=())
    if fault == "participant": window = replace(window, participant_scope=(plan.operations[0].owner_ref,))
    if fault == "range":
        with pytest.raises(ValueError, match="settlement_window_cutoff_out_of_bounds"):
            replace(window, to_time=window.from_time)
        return
    with pytest.raises(ValueError, match="batch_window"):
        await submit(main, plan=plan, window=window, budget=2)
    assert not main.gameplay_event_store.read_stream("gameplay:organization:window:window:1")


@pytest.mark.asyncio
async def test_durable_conflict_preserves_a_and_original_b_across_restart(application, record_property):
    from app.gameplay.econ1_economy_runtime import WageAccrual
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    econ = main._settlement_batch_coordinator.adapters[(plan.operations[1].owner_ref, plan.operations[1].owner_contract_ref)]
    def prior():
        return econ.owner.accrue_wage(WageAccrual(accrual_ref="prior", organization_ref="org:bakery",
            payee_actor_ref="character:char_b", work_evidence_refs=("evidence:verified",),
            wage_policy_revision="policy:1", amount=1), completed_evidence_refs={"evidence:verified"},
            command_id="prior", idempotency_key="prior", causation_id="cause", correlation_id="corr")
    assert (await asyncio.wrap_future(main.runtime_execution.submit(prior))).committed
    result = await submit(main, plan=plan, window=window, budget=2)
    assert result.stage == "pending_recovery" and result.receipts[1].conflict_refs == ("revision_conflict",)
    assert result.confirmation_boundary is None
    await main._stop_population_runtime_on_shutdown()
    await start()
    again = await submit(main, budget=2)
    assert again == result
    assert len(main.gameplay_event_store.read_stream("gameplay:organization:window:window:1")) == 1
    assert len(main.gameplay_event_store.read_stream("gameplay:economy:wage:character:char_b")) == 1
    record_property("conflict_receipts", json.dumps(asdict(again)))


@pytest.mark.asyncio
@pytest.mark.parametrize("committed", [True, False])
async def test_durable_timeout_queries_receipt_before_retry_and_rebuilds_after_restart(application, monkeypatch, committed):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    store = main.gameplay_event_store
    append, query = store.append_batch, store.get_by_idempotency
    calls = []
    def lost(batch):
        if batch.idempotency_record.principal_ref == plan.operations[0].owner_ref:
            calls.append("commit")
            if committed:
                append(batch)
            raise TimeoutError("lost response")
        return append(batch)
    def queried(owner, key):
        if owner == plan.operations[0].owner_ref:
            calls.append("query")
        return query(owner, key)
    monkeypatch.setattr(store, "append_batch", lost)
    monkeypatch.setattr(store, "get_by_idempotency", queried)
    result = await submit(main, plan=plan, window=window, budget=2)
    assert calls == ["query", "commit", "query"]
    assert result.stage == ("completed" if committed else "pending_recovery")
    if not committed:
        assert result.receipts[1].conflict_refs == ("dependency_not_committed",)
        assert result.recovery_cursor == 0
    await main._stop_population_runtime_on_shutdown()
    await start()
    recovered = await submit(main, budget=2)
    assert recovered.stage == "completed" and recovered.input_digest == result.input_digest
    assert len(main.gameplay_event_store.read_stream("gameplay:organization:window:window:1")) == 1
    assert len(main.gameplay_event_store.read_stream("gameplay:economy:wage:character:char_b")) == 1
