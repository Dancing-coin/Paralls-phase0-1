from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionDueCompletionPolicy, ConstructionProductionAuthority, Facility, ProductionRun, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.obligations import ObligationLifecycleRegistration, ObligationSettlementCoordinator


def _run() -> ProductionRun:
    return ProductionRun(run_ref="run:bakery:1", facility_ref="facility:bakery:1", recipe_ref="recipe:bread:1", started_tick=0, finish_tick=3, output_item="item:bread")


def _recipe() -> Recipe:
    return Recipe(recipe_ref="recipe:bread:1", inputs={}, output_item="item:bread", duration_ticks=3)


def _registration() -> ObligationLifecycleRegistration:
    return ObligationLifecycleRegistration(
        policy_ref="policy:construction_due_completion",
        policy_revision="1",
        owner_ref="actor_gameplay.construction_production_domain",
        stream_pattern="gameplay:construction_production:{facility_ref}",
        opened_event_type="gameplay.construction_production.run_started",
        settled_event_type="gameplay.construction_production.obligation_settled",
        cancelled_event_type="gameplay.construction_production.obligation_cancelled",
        visibility_scope="project",
    )


def _committed_open_obligation(store: GameplayEventStore):
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    ConstructionProductionAuthority(store=store).settle_start_run(
        facility=Facility(facility_ref=run.facility_ref, plot_ref="plot:bakery:1", facility_kind="bakery", condition=1),
        recipe=_recipe(),
        run_ref=run.run_ref,
        tick=0,
        command_id="command:production:start:1",
        idempotency_key="idem:production:start:1",
        causation_id="cause:production:start:1",
        correlation_id="corr:production:1",
    )
    obligation = policy.build_obligation(run=run, expected_revision=1, status="open")
    fragment = ConstructionProductionAuthority.build_obligation_cancellation_fragment(
        obligation=obligation,
        cancelled_event_type="gameplay.construction_production.obligation_cancelled",
        reason_ref="reason:operator",
    )
    return obligation, fragment


def _start_due_run(store: GameplayEventStore, run: ProductionRun) -> None:
    assert ConstructionProductionAuthority(store=store).settle_start_run(
        facility=Facility(
            facility_ref=run.facility_ref,
            plot_ref="plot:bakery:1",
            facility_kind="bakery",
            condition=1,
        ),
        recipe=_recipe(),
        run_ref=run.run_ref,
        tick=0,
        command_id=f"command:production:start:{run.run_ref}",
        idempotency_key=f"idem:production:start:{run.run_ref}",
        causation_id=f"cause:production:start:{run.run_ref}",
        correlation_id=f"corr:production:{run.run_ref}",
    ).committed


def test_registered_construction_settlement_commits_owner_and_lifecycle_events() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    _start_due_run(store, run)
    obligation = policy.build_obligation(run=run, expected_revision=1)

    plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(policy.build_fragment(run=run, recipe=_recipe(), tick=3, expected_revision=1, obligation=obligation, settled_event_type="gameplay.construction_production.obligation_settled"),),
        principal_ref="world_runtime.caller",
    )
    assert plan.ready is True
    assert plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == ["gameplay.construction_production.run_started", "gameplay.construction_production.run_finished", "gameplay.construction_production.obligation_settled"]
    assert store.read_events()[2].payload["prior_state"] == "due"
    assert store.read_events()[2].payload["current_state"] == "settled"


def test_registered_settlement_rejects_changed_duplicate_without_append() -> None:
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    _start_due_run(store, run)
    obligation = policy.build_obligation(run=run, expected_revision=1)
    fragment = policy.build_fragment(
        run=run, recipe=_recipe(), tick=3, expected_revision=1, obligation=obligation,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )
    first = coordinator.plan_settle(obligation=obligation, fragments=(fragment,), principal_ref="world_runtime.caller")
    assert first.ready is True and first.owner_commit_batch is not None
    assert ConstructionProductionAuthority(store=store).commit_obligation_batch(first.owner_commit_batch).committed

    changed = obligation.model_copy(update={"due_tick": 4})
    changed_fragment = policy.build_fragment(
        run=run, recipe=_recipe(), tick=3, expected_revision=1, obligation=changed,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )
    rejected = coordinator.plan_settle(obligation=changed, fragments=(changed_fragment,), principal_ref="world_runtime.caller")

    assert rejected.ready is False and rejected.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 3


def test_unregistered_and_retry_or_compensation_policy_are_zero_write() -> None:
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    fragment = policy.build_fragment(run=run, recipe=_recipe(), tick=3, expected_revision=0)
    store = GameplayEventStore()

    unregistered = ObligationSettlementCoordinator(store=store).plan_settle(obligation=policy.build_obligation(run=run, expected_revision=0), fragments=(fragment,), principal_ref="world_runtime.caller")
    retry = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).plan_settle(obligation=policy.build_obligation(run=run, expected_revision=0, retry_policy={"attempt": 1}), fragments=(fragment,), principal_ref="world_runtime.caller")
    compensation = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).plan_settle(obligation=policy.build_obligation(run=run, expected_revision=0, compensation_policy={"inverse": "unknown"}), fragments=(fragment,), principal_ref="world_runtime.caller")

    assert unregistered.error_code == "obligation_policy_unregistered"
    assert retry.error_code == "obligation_retry_unsupported"
    assert compensation.error_code == "obligation_compensation_unsupported"
    assert store.read_events() == []


def test_registration_owner_mismatch_is_zero_write() -> None:
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    obligation = policy.build_obligation(run=run, expected_revision=0)
    fragment = policy.build_fragment(
        run=run,
        recipe=_recipe(),
        tick=3,
        expected_revision=0,
        obligation=obligation,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )
    owner_mismatch = obligation.model_copy(update={"owner_ref": "actor_gameplay.unknown"})
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))

    assert coordinator.plan_settle(obligation=owner_mismatch, fragments=(fragment,), principal_ref="world_runtime.caller").error_code == "obligation_registration_owner_mismatch"
    assert store.read_events() == []


def test_registration_stream_mismatch_is_zero_write() -> None:
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    obligation = policy.build_obligation(run=run, expected_revision=0)
    fragment = policy.build_fragment(
        run=run,
        recipe=_recipe(),
        tick=3,
        expected_revision=0,
        obligation=obligation,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )
    stream_mismatch = obligation.model_copy(update={"expected_revisions": {"gameplay:survival:bakery:1": 0}})
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))

    assert coordinator.plan_settle(obligation=stream_mismatch, fragments=(fragment,), principal_ref="world_runtime.caller").error_code == "obligation_registration_stream_mismatch"
    assert store.read_events() == []


def test_fragment_stream_or_revision_mismatch_is_zero_write() -> None:
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    obligation = policy.build_obligation(run=run, expected_revision=0)
    fragment = policy.build_fragment(
        run=run,
        recipe=_recipe(),
        tick=3,
        expected_revision=0,
        obligation=obligation,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )
    stream_id = next(iter(obligation.expected_revisions))
    crafted = fragment.model_copy(
        update={
            "expected_revisions": {stream_id: 1},
            "event_specs": {stream_id: fragment.event_specs[stream_id]},
        },
        deep=True,
    )
    store = GameplayEventStore()

    result = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).plan_settle(
        obligation=obligation,
        fragments=(crafted,),
        principal_ref="world_runtime.caller",
    )

    assert result.error_code == "obligation_fragment_revision_mismatch"
    assert store.read_events() == []


def test_registered_settlement_requires_lifecycle_correlation_event_without_write() -> None:
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    store = GameplayEventStore()
    result = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).plan_settle(
        obligation=policy.build_obligation(run=run, expected_revision=0),
        fragments=(policy.build_fragment(run=run, recipe=_recipe(), tick=3, expected_revision=0),),
        principal_ref="world_runtime.caller",
    )

    assert result.error_code == "obligation_lifecycle_event_missing"
    assert store.read_events() == []


def test_registered_future_cancellation_is_event_derived_and_idempotent() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    obligation, fragment = _committed_open_obligation(store)
    first = coordinator.plan_cancel(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:operator")
    assert first.ready is True and first.owner_commit_batch is not None
    assert authority.commit_obligation_batch(first.owner_commit_batch).committed
    duplicate = coordinator.plan_cancel(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:operator")

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert [event.event_type for event in store.read_events()] == ["gameplay.construction_production.run_started", "gameplay.construction_production.obligation_cancelled"]


def test_registered_cancellation_rejects_changed_duplicate_without_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    obligation, fragment = _committed_open_obligation(store)
    first = coordinator.plan_cancel(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:operator")
    assert first.ready is True and first.owner_commit_batch is not None
    assert authority.commit_obligation_batch(first.owner_commit_batch).committed
    before = len(store.read_events())
    changed = fragment.model_copy(update={"fragment_id": f"{fragment.fragment_id}:changed"})

    rejected = coordinator.plan_cancel(obligation=obligation, fragment=changed, principal_ref="world_runtime.caller", reason_ref="reason:operator")

    assert rejected.ready is False and rejected.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before


def test_cancellation_revision_conflict_and_terminal_state_are_zero_write() -> None:
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    obligation, fragment = _committed_open_obligation(store)
    obligation = obligation.model_copy(update={"expected_revisions": {next(iter(obligation.expected_revisions)): 2}})
    fragment = fragment.model_copy(update={"expected_revisions": dict(obligation.expected_revisions)})
    conflict = coordinator.plan_cancel(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:operator")
    terminal = coordinator.plan_cancel(
        obligation=obligation.model_copy(update={"status": "cancelled"}),
        fragment=fragment,
        principal_ref="world_runtime.caller",
        reason_ref="reason:operator",
    )

    assert conflict.error_code == "revision_conflict"
    assert terminal.error_code == "obligation_not_cancellable"
    assert len(store.read_events()) == 1


def test_cancellation_without_committed_open_source_or_registered_scope_is_zero_write() -> None:
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    uncommitted = policy.build_obligation(run=_run(), expected_revision=0, status="open")
    fragment = ConstructionProductionAuthority.build_obligation_cancellation_fragment(
        obligation=uncommitted,
        cancelled_event_type="gameplay.construction_production.obligation_cancelled",
        reason_ref="reason:operator",
    )
    no_source = coordinator.plan_cancel(obligation=uncommitted, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:operator")
    scope_mismatch = coordinator.plan_cancel(
        obligation=uncommitted.model_copy(update={"visibility_scope": "authority_only"}),
        fragment=fragment,
        principal_ref="world_runtime.caller",
        reason_ref="reason:operator",
    )

    assert no_source.error_code == "obligation_lifecycle_not_open"
    assert scope_mismatch.error_code == "obligation_registration_visibility_mismatch"
    assert store.read_events() == []


def test_cancellation_rejects_uncommitted_obligation_id_for_a_committed_run() -> None:
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    obligation, _fragment = _committed_open_obligation(store)
    forged = obligation.model_copy(
        update={
            "obligation_id": "obligation:construction-production:finish:forged",
            "idempotency_key": "obligation:construction-production:finish:forged:1",
        }
    )
    fragment = ConstructionProductionAuthority.build_obligation_cancellation_fragment(
        obligation=forged,
        cancelled_event_type="gameplay.construction_production.obligation_cancelled",
        reason_ref="reason:operator",
    )

    result = coordinator.plan_cancel(
        obligation=forged,
        fragment=fragment,
        principal_ref="world_runtime.caller",
        reason_ref="reason:operator",
    )

    assert result.error_code == "obligation_lifecycle_not_open"
    assert [event.event_type for event in store.read_events()] == ["gameplay.construction_production.run_started"]


def test_lifecycle_public_receipt_is_redacted_and_replay_matches() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    policy = ConstructionDueCompletionPolicy(policy_ref="policy:construction_due_completion", policy_revision="1")
    run = _run()
    _start_due_run(store, run)
    obligation = policy.build_obligation(run=run, expected_revision=1)
    plan = coordinator.plan_settle(obligation=obligation, fragments=(policy.build_fragment(run=run, recipe=_recipe(), tick=3, expected_revision=1, obligation=obligation, settled_event_type="gameplay.construction_production.obligation_settled"),), principal_ref="world_runtime.caller")
    assert plan.ready is True and plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(plan.owner_commit_batch).committed
    duplicate = coordinator.plan_settle(obligation=obligation, fragments=(policy.build_fragment(run=run, recipe=_recipe(), tick=3, expected_revision=1, obligation=obligation, settled_event_type="gameplay.construction_production.obligation_settled"),), principal_ref="world_runtime.caller")
    assert duplicate.receipt is not None
    coordinator._receipts[obligation.idempotency_key] = duplicate.receipt

    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=1).projection_hash


def test_cancellation_uses_registered_project_scope_and_filters_public_receipt() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    obligation, fragment = _committed_open_obligation(store)

    plan = coordinator.plan_cancel(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:operator")
    assert plan.ready is True and plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    duplicate = coordinator.plan_cancel(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:operator")
    assert duplicate.receipt is not None
    coordinator._receipts[f"{obligation.idempotency_key}:cancel:reason:operator"] = duplicate.receipt

    assert result.committed is True
    assert store.list_outbox()[0].audience == "project"
    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()
