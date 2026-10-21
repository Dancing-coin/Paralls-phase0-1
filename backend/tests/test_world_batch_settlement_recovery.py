import pytest

from app.gameplay.econ1_economy_runtime import EconomyAuthority, OperatingWindow
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _setup(*, store=None):
    from app.world_runtime.batch_settlement import OrganizationWindowBatchAdapter, EconomyWageBatchAdapter

    store = store or GameplayEventStore()
    organization = OrganizationWindowBatchAdapter(owner=OrganizationAuthority(store=store), store=store)
    economy = EconomyWageBatchAdapter(owner=EconomyAuthority(store=store), store=store)
    first = organization.freeze(
        operation_ref="window", window=OperatingWindow(
            window_ref="window:1", organization_ref="org:bakery", opens_at_tick=1,
            closes_at_tick=5, policy_revision="policy:1", source_revision="source:1"),
        command_id="window:open", idempotency_key="window:open", causation_id="cause", correlation_id="corr",
        visibility_scope="project",
    )
    command = GameplayCommandEnvelope(
        command_id="wage:open", command_type="gameplay.economy.open_wage_obligation", command_version=1,
        principal_ref=EconomyAuthority._PRINCIPAL, actor_ref="character:char_b", idempotency_key="wage:open",
        expected_revisions={"gameplay:economy:wage:character:char_b": 0},
        read_set_revisions={"gameplay:organization:window:window:1": 1},
        causation_id="cause", correlation_id="corr", source_ref=EconomyAuthority._PRINCIPAL,
        submitted_at="tick:1", payload={"visibility_scope": "project"},
    )
    second = economy.freeze(operation_ref="wage", command=command, accrual_ref="accrual:1",
                            organization_ref="org:bakery", work_evidence_refs=("evidence:verified",),
                            wage_amount_minor=10, due_tick=5, policy_revision="policy:1")
    return store, organization, economy, first, second


def _plan(first, second, **changes):
    from app.world_runtime.batch_settlement import BatchSettlementPlan

    values = dict(batch_ref="batch:1", timeline_ref="legacy", window_ref="window:1", plan_revision="1",
                  frozen_read_set_ref="read:1", evidence_refs=("evidence:verified",),
                  definition_and_rule_pins=("policy:1",), operations=(first, second),
                  dependency_edges=(("window", "wage"),), ordering_policy_ref="dependency_then_ref",
                  consistency_scope="owner_atomic", failure_policy_ref="query_then_bounded_retry",
                  confirmation_boundary="window:1:end", recovery_cursor=0)
    values.update(changes)
    from dataclasses import replace
    from fractions import Fraction
    from app.world_runtime.batch_settlement import FrozenSettlementWindow
    from app.world_runtime.temporal_contracts import SettlementWindow, SimulationTime
    from test_temporal_mapping_contract import configured_clock
    clock, mapping = configured_clock()
    timeline = replace(clock.timeline, timeline_id=values["timeline_ref"], current_step=5)
    mapping = replace(mapping, target_timeline_ref=timeline.timeline_id, ratio=Fraction(1),
                      source_unit_ref="second", source_clock_ref=timeline.advancement_owner_ref)
    time = lambda tick: SimulationTime(timeline.timeline_id, tick, Fraction(tick))
    window = SettlementWindow(
        window_ref=values["window_ref"], timeline_id=timeline.timeline_id, from_time=time(1), to_time=time(5),
        participant_scope=tuple(op.owner_ref for op in values["operations"]), phase_ref=None,
        input_cutoff=time(5), late_input_policy_ref="reject_after_cutoff", confirmation_boundary=time(5),
        frozen_read_set=tuple(sorted({**first.command.expected_revisions, **second.command.expected_revisions}.items())),
        evidence_refs=values["evidence_refs"], ordering_policy_ref=values["ordering_policy_ref"],
        expected_authority_revisions=tuple(sorted({**first.command.expected_revisions, **second.command.expected_revisions}.items())),
        settlement_idempotency_key=values["batch_ref"])
    values["frozen_window"] = FrozenSettlementWindow(window, timeline, clock.temporal_profile, mapping)
    return BatchSettlementPlan(**values)


def test_real_owner_batch_replays_exact_receipts_without_duplicate_events():
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    plan = _plan(first, second)
    coordinator = BatchSettlementCoordinator(adapters=(org, econ))
    result = coordinator.execute(plan, budget=2)
    assert result.stage == "completed"
    assert result.confirmation_boundary == plan.confirmation_boundary
    assert [receipt.status for receipt in result.receipts] == ["committed", "committed"]
    assert result.receipts[1].owner_revision_before == (("gameplay:economy:wage:character:char_b", 0),)
    assert len(store.read_events()) == 2
    again = BatchSettlementCoordinator(adapters=(org, econ)).execute(plan, budget=0)
    assert again.stage == "completed"
    assert again.receipts == result.receipts
    assert len(store.read_events()) == 2


def test_commit_then_timeout_queries_actual_receipt_before_any_retry():
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    class LostReceiptStore(GameplayEventStore):
        lost = False

        def append_batch(self, batch):
            result = super().append_batch(batch)
            if batch.idempotency_record.principal_ref == EconomyAuthority._PRINCIPAL and not self.lost:
                self.lost = True
                raise TimeoutError("receipt lost after append")
            return result

    store, org, econ, first, second = _setup(store=LostReceiptStore())
    result = BatchSettlementCoordinator(adapters=(org, econ)).execute(_plan(first, second), budget=2)
    assert result.stage == "completed"
    assert len(store.read_events()) == 2


def test_budget_exhaustion_retains_owner_commit_and_does_not_confirm_window():
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    plan = _plan(first, second)
    coordinator = BatchSettlementCoordinator(adapters=(org, econ))
    partial = coordinator.execute(plan, budget=1)
    assert partial.stage == "pending_recovery"
    assert partial.recovery_cursor == 1
    assert partial.confirmation_boundary is None
    assert len(store.read_events()) == 1
    recovered = coordinator.execute(plan, budget=1)
    assert recovered.stage == "completed"
    assert len(store.read_events()) == 2


def test_second_owner_conflict_preserves_first_owner_event_and_receipt():
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    # Existing owner commits independently before this batch's frozen revision.
    assert econ.commit(second).committed is False  # prerequisite read revision has not committed
    # A conflicting wage revision can be produced through the real owner API.
    from app.gameplay.econ1_economy_runtime import WageAccrual
    assert econ.owner.accrue_wage(
        WageAccrual(accrual_ref="accrual:prior", organization_ref="org:bakery", payee_actor_ref="character:char_b",
                    work_evidence_refs=("evidence:verified",), wage_policy_revision="policy:1", amount=1),
        completed_evidence_refs={"evidence:verified"}, command_id="prior", idempotency_key="prior",
        causation_id="cause", correlation_id="corr").committed
    result = BatchSettlementCoordinator(adapters=(org, econ)).execute(_plan(first, second), budget=2)
    assert result.stage == "pending_recovery"
    assert [r.status for r in result.receipts] == ["committed", "rejected"]
    assert result.receipts[1].conflict_refs == ("revision_conflict",)
    assert len(store.read_events()) == 2
    assert result.confirmation_boundary is None


def test_changed_duplicate_is_rejected_before_second_append():
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    coordinator = BatchSettlementCoordinator(adapters=(org, econ))
    assert coordinator.execute(_plan(first, second), budget=2).stage == "completed"
    import json
    request = json.loads(second.request_json)
    request["wage_amount_minor"] = 20
    changed = econ.freeze(operation_ref=second.operation_ref, **request)
    with pytest.raises(ValueError, match="batch_input_identity_reused"):
        coordinator.execute(_plan(first, changed), budget=2)
    assert len(store.read_events()) == 2


def test_dependency_cycle_is_rejected_before_owner_calls():
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    with pytest.raises(ValueError, match="batch_dependency_cycle"):
        BatchSettlementCoordinator(adapters=(org, econ)).execute(
            _plan(first, second, dependency_edges=(("window", "wage"), ("wage", "window"))), budget=2)
    assert store.read_events() == []


def test_successor_keeps_original_committed_operation_identity():
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    original = _plan(first, second)
    coordinator = BatchSettlementCoordinator(adapters=(org, econ))
    assert coordinator.execute(original, budget=1).stage == "pending_recovery"
    successor = _plan(first, second, batch_ref="batch:2", predecessor_batch_ref="batch:1")
    assert coordinator.execute(successor, budget=1, predecessor=original).stage == "completed"
    assert len(store.read_events()) == 2


def test_dependency_actual_revision_must_match_frozen_read_set():
    import json
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    request = json.loads(second.request_json)
    request["command"]["read_set_revisions"] = {}
    second = econ.freeze(operation_ref="wage", **request)
    result = BatchSettlementCoordinator(adapters=(org, econ)).execute(_plan(first, second), budget=2)
    assert result.stage == "pending_recovery"
    assert result.receipts[-1].conflict_refs == ("dependency_revision_not_pinned",)
    assert len(store.read_events()) == 1


def test_receipt_query_cannot_accept_changed_privacy_or_owner_identity():
    import json
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    assert BatchSettlementCoordinator(adapters=(org, econ)).execute(_plan(first, second), budget=2).stage == "completed"
    for field, value in (("payload", {"visibility_scope": "authority_only"}), ("principal_ref", "character:char_b")):
        request = json.loads(second.request_json)
        request["command"][field] = value
        with pytest.raises(ValueError, match="batch_wage_request_not_admitted"):
            econ.freeze(operation_ref="wage", **request)
    assert len(store.read_events()) == 2


def test_faulted_adapter_blocks_owner_commit_and_batch_confirmation():
    from app.world_runtime.adapter_admission import admit_adapters
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator
    from test_world_adapter_admission import _descriptor, _requirement

    store, org, econ, first, second = _setup()
    descriptor = _descriptor()
    admission = admit_adapters((descriptor,), requirement=_requirement())
    fault = admission.invalidate(adapter_ref=descriptor.adapter_ref, reason="capability_lost")
    result = BatchSettlementCoordinator(adapters=(org, econ)).execute(
        _plan(first, second), budget=2, adapter_admission=fault, current_descriptors=(descriptor,))
    assert result.stage == "pending_recovery"
    assert result.confirmation_boundary is None
    assert result.receipts[0].conflict_refs == ("adapter_confirmation_blocked",)
    assert store.read_events() == []


def test_successor_cannot_change_existing_operation_or_skip_it_with_cursor():
    from dataclasses import replace
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator

    store, org, econ, first, second = _setup()
    plan = _plan(first, second, recovery_cursor=2)
    coordinator = BatchSettlementCoordinator(adapters=(org, econ))
    result = coordinator.execute(plan, budget=0)
    assert result.stage == "pending_recovery"
    assert result.recovery_cursor == 0
    successor = _plan(replace(first, operation_ref="changed"), second,
                      batch_ref="batch:2", predecessor_batch_ref="batch:1", dependency_edges=())
    with pytest.raises(ValueError, match="batch_successor_operation_changed"):
        coordinator.execute(successor, budget=2, predecessor=plan)
    assert store.read_events() == []


def test_recovery_cursor_is_not_input_identity():
    from dataclasses import replace
    _, _, _, first, second = _setup()
    plan = _plan(first, second)
    assert replace(plan, recovery_cursor=2).input_digest == plan.input_digest


@pytest.mark.parametrize("field", ["mapping", "profile", "timeline", "rules", "ordering", "dependencies"])
def test_original_batch_identity_includes_frozen_versions_and_dependencies(field):
    from dataclasses import replace
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator
    store, org, econ, first, second = _setup()
    coordinator = BatchSettlementCoordinator(adapters=(org, econ))
    plan = _plan(first, second)
    coordinator.execute(plan, budget=1)
    frozen = plan.frozen_window
    if field == "mapping": changed = replace(plan, frozen_window=replace(frozen, mapping=replace(frozen.mapping, revision="2")))
    if field == "profile": changed = replace(plan, frozen_window=replace(frozen, profile=replace(frozen.profile, revision="2")))
    if field == "timeline": changed = replace(plan, frozen_window=replace(frozen, timeline=replace(frozen.timeline, authoritative_revision=2)))
    if field == "rules": changed = replace(plan, definition_and_rule_pins=("policy:2",))
    if field == "ordering": changed = replace(plan, operations=(second, first))
    if field == "dependencies": changed = replace(plan, dependency_edges=())
    with pytest.raises(ValueError, match="batch_input_identity_reused"):
        coordinator.execute(changed, budget=2)
    assert len(store.read_events()) == 1


def test_unbound_window_strings_are_rejected_before_owner_call():
    from dataclasses import replace
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator
    store, org, econ, first, second = _setup()
    with pytest.raises(ValueError, match="batch_window_required"):
        BatchSettlementCoordinator(adapters=(org, econ)).execute(
            replace(_plan(first, second), frozen_window=None), budget=2)
    assert store.read_events() == []


def test_batch_recovery_rejects_owner_receipt_with_corrupt_event_refs() -> None:
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator
    store, org, econ, first, second = _setup()
    plan = _plan(first, second)
    coordinator = BatchSettlementCoordinator(adapters=(org, econ))
    partial = coordinator.execute(plan, budget=1)
    assert partial.stage == "pending_recovery"
    key = (org.owner_ref, "window:open")
    stored = store._idempotency_results[key]
    store._idempotency_results[key] = stored.model_copy(update={"committed_event_ids": ["missing:event"]}, deep=True)
    recovered = coordinator.execute(plan, budget=1)
    assert recovered.stage == "pending_recovery"
    assert recovered.receipts[0].status == "rejected"
    assert recovered.receipts[0].conflict_refs == ("owner_receipt_event_refs_invalid",)
    assert len(store.read_events()) == 1
