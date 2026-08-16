from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import ScheduledObligation
from app.world_runtime.obligations import ObligationLifecycleProjection, ObligationSettlementCoordinator


def _seed_applied_state() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Facility, str]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:maintenance:1",
        plot_ref="plot:maintenance:1",
        facility_kind="bakery",
        condition=1.0,
    )
    assert authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref=facility.plot_ref,
            jurisdiction_ref="jurisdiction:maintenance",
            owner_ref="org:maintenance",
        ),
        facility=facility,
        command_id="construction:maintenance:facility",
        idempotency_key="construction:maintenance:facility",
        causation_id="cause:maintenance:facility",
        correlation_id="corr:maintenance:facility",
    ).committed
    applied = authority.apply_maintenance_state(
        command_id="construction:maintenance:apply",
        idempotency_key="construction:maintenance:apply",
        facility_ref=facility.facility_ref,
        expected_revision=1,
        causation_id="cause:maintenance:apply",
        correlation_id="corr:maintenance:apply",
        source_ref="proposal:semantic:maintenance",
        submitted_at="2026-08-14T00:00:00Z",
        pinned_revisions={"semantic": 1},
        semantic_snapshot_digest="sha256:maintenance-state",
        application=EffectApplication(
            effect_ref="effect:maintenance_required",
            target_component_ref=facility.facility_ref,
            magnitude=10,
            stack_key="maintenance",
            expires_at_tick=None,
            causal_chain_id="chain:maintenance",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:maintenance_required",
            source_ref=facility.facility_ref,
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:maintenance_due",
            stack_policy="replace",
            stack_limit=1,
            expiry_policy="none",
        ),
    )
    assert applied.committed
    return store, authority, facility, store.read_events()[-1].event_id


def _snapshot(store: GameplayEventStore) -> dict[str, object]:
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def test_construction_maintenance_state_opens_event_derived_obligation_and_settles_due_expiry() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()

    opened = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:open",
        correlation_id="corr:maintenance:open",
    )

    assert opened.committed
    assert opened.obligation.policy_revision == "1"
    assert store.read_events()[-1].event_type == "gameplay.construction_production.maintenance_state_obligation_opened"
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(ConstructionProductionAuthority.maintenance_state_obligation_registration(),),
    )
    due_obligation = opened.obligation.model_copy(
        update={
            "status": "due",
            "expected_revisions": {"gameplay:construction_production:facility:maintenance:1": 3},
        }
    )
    plan = coordinator.plan_settle(
        obligation=due_obligation,
        fragments=(
            authority.build_maintenance_state_expiry_fragment(
                obligation=due_obligation,
                facility_ref=facility.facility_ref,
                expected_revision=3,
            ),
        ),
        principal_ref="world_runtime.caller",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    settled = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert settled.committed
    assert [event.event_type for event in store.read_events()[-2:]] == [
        "gameplay.construction_production.maintenance_state_expired",
        "gameplay.construction_production.maintenance_state_obligation_settled",
    ]
    assert facility.facility_ref not in authority.projector().maintenance_states


def test_construction_maintenance_state_obligation_rejects_unknown_source_without_write() -> None:
    store, authority, _facility, state_event_id = _seed_applied_state()
    before = _snapshot(store)

    with pytest.raises(ValueError, match="maintenance_state_source_unknown"):
        authority.open_maintenance_state_obligation(
            state_event_id="event:missing",
            due_tick=5,
            expected_revision=2,
            idempotency_key="construction:maintenance:missing",
            correlation_id="corr:maintenance:missing",
        )
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_duplicate_source_without_write() -> None:
    store, authority, _facility, state_event_id = _seed_applied_state()
    first = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:open",
        correlation_id="corr:maintenance:open",
    )
    assert first.committed
    before_duplicate = _snapshot(store)
    with pytest.raises(ValueError, match="maintenance_state_obligation_active"):
        authority.open_maintenance_state_obligation(
            state_event_id=state_event_id,
            due_tick=6,
            expected_revision=3,
            idempotency_key="construction:maintenance:open:changed",
            correlation_id="corr:maintenance:open:changed",
        )
    assert _snapshot(store) == before_duplicate


def test_construction_maintenance_state_obligation_rejects_stale_revision_without_write() -> None:
    store, authority, _facility, state_event_id = _seed_applied_state()
    before = _snapshot(store)

    with pytest.raises(ValueError, match="revision_conflict"):
        authority.open_maintenance_state_obligation(
            state_event_id=state_event_id,
            due_tick=5,
            expected_revision=1,
            idempotency_key="construction:maintenance:stale-open",
            correlation_id="corr:maintenance:stale-open",
        )
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_wrong_source_without_write() -> None:
    store, authority, _facility, _state_event_id = _seed_applied_state()
    before = _snapshot(store)
    with pytest.raises(ValueError, match="maintenance_state_source_invalid"):
        authority.open_maintenance_state_obligation(
            state_event_id=store.read_events()[0].event_id,
            due_tick=5,
            expected_revision=2,
            idempotency_key="construction:maintenance:wrong-source",
            correlation_id="corr:maintenance:wrong-source",
        )
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_replays_exact_open_without_write() -> None:
    store, authority, _facility, state_event_id = _seed_applied_state()
    first = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:replay",
        correlation_id="corr:maintenance:replay",
    )
    assert first.committed
    after_first = _snapshot(store)
    replay = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:replay",
        correlation_id="corr:maintenance:replay",
    )
    assert replay.committed and replay.append_result.idempotency_status == "duplicate_replayed"
    assert _snapshot(store) == after_first


def test_construction_maintenance_state_obligation_rejects_duplicate_with_changed_revision_without_write() -> None:
    store, authority, _facility, state_event_id = _seed_applied_state()
    assert authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:replay",
        correlation_id="corr:maintenance:replay",
    ).committed
    before = _snapshot(store)
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        authority.open_maintenance_state_obligation(
            state_event_id=state_event_id,
            due_tick=5,
            expected_revision=3,
            idempotency_key="construction:maintenance:replay",
            correlation_id="corr:maintenance:replay",
        )
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_duplicate_with_changed_due_tick_without_write() -> None:
    store, authority, _facility, state_event_id = _seed_applied_state()
    assert authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:replay",
        correlation_id="corr:maintenance:replay",
    ).committed
    before = _snapshot(store)
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        authority.open_maintenance_state_obligation(
            state_event_id=state_event_id,
            due_tick=6,
            expected_revision=2,
            idempotency_key="construction:maintenance:replay",
            correlation_id="corr:maintenance:replay",
        )
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_settlement_without_committed_open() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()
    obligation = ScheduledObligation(
        obligation_id="obligation:construction-maintenance-state:forged",
        owner_ref="actor_gameplay.construction_production_domain",
        due_tick=5,
        policy_revision="1",
        status="due",
        idempotency_key="construction:maintenance:forged-settle",
        expected_revisions={f"gameplay:construction_production:{facility.facility_ref}": 2},
        visibility_scope="project",
        source_refs=("policy:construction_maintenance_state_expiry@1", f"state_event:{state_event_id}"),
    )
    before = _snapshot(store)

    settled = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(ConstructionProductionAuthority.maintenance_state_obligation_registration(),),
    ).plan_settle(
        obligation=obligation,
        fragments=(
            authority.build_maintenance_state_expiry_fragment(
                obligation=obligation,
                facility_ref=facility.facility_ref,
                expected_revision=2,
            ),
        ),
        principal_ref="world_runtime.caller",
    )

    assert settled.ready is False
    assert settled.error_code == "obligation_lifecycle_not_open"
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_settled_only_fragment_without_write() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()
    opened = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:settled-only-open",
        correlation_id="corr:maintenance:settled-only-open",
    )
    assert opened.committed and opened.obligation is not None
    obligation = opened.obligation.model_copy(
        update={
            "status": "due",
            "expected_revisions": {f"gameplay:construction_production:{facility.facility_ref}": 3},
        }
    )
    stream_id = f"gameplay:construction_production:{facility.facility_ref}"
    fragment = OwnerAuthorizedFragment(
        fragment_id="fragment:construction:maintenance-state:settled-only",
        owner_principal_ref=ConstructionProductionAuthority._PRINCIPAL,
        source_rule_ref="construction-production:maintenance-state-expiry",
        expected_revisions={stream_id: 3},
        pinned_revisions={"maintenance_state_policy": 1},
        event_specs={
            stream_id: (
                (
                    "gameplay.construction_production.maintenance_state_obligation_settled",
                    {
                        "obligation_id": obligation.obligation_id,
                        "prior_state": obligation.status,
                        "current_state": "settled",
                        "policy_ref": "policy:construction_maintenance_state_expiry@1",
                        "policy_revision": "1",
                        "due_tick": obligation.due_tick,
                    },
                ),
            )
        },
    )
    before = _snapshot(store)
    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(ConstructionProductionAuthority.maintenance_state_obligation_registration(),),
    ).plan_settle(obligation=obligation, fragments=(fragment,), principal_ref="world_runtime.caller")

    assert result.ready is False
    assert result.error_code == "obligation_lifecycle_event_missing"
    assert _snapshot(store) == before
    assert facility.facility_ref in authority.projector().maintenance_states


def test_construction_maintenance_state_obligation_rejects_non_owner_fragment_without_write() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()
    opened = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:foreign-owner-open",
        correlation_id="corr:maintenance:foreign-owner-open",
    )
    assert opened.committed and opened.obligation is not None
    obligation = opened.obligation.model_copy(
        update={
            "status": "due",
            "expected_revisions": {f"gameplay:construction_production:{facility.facility_ref}": 3},
        }
    )
    fragment = authority.build_maintenance_state_expiry_fragment(
        obligation=obligation,
        facility_ref=facility.facility_ref,
        expected_revision=3,
    ).model_copy(update={"owner_principal_ref": "authority:foreign"}, deep=True)
    before = _snapshot(store)
    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(ConstructionProductionAuthority.maintenance_state_obligation_registration(),),
    ).plan_settle(obligation=obligation, fragments=(fragment,), principal_ref="world_runtime.caller")

    assert result.ready is False
    assert result.error_code == "owner_fragment_mismatch"
    assert _snapshot(store) == before


def test_construction_maintenance_state_reapply_cannot_open_a_second_active_obligation() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()
    assert authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:first-open",
        correlation_id="corr:maintenance:first-open",
    ).committed

    reapplied = authority.apply_maintenance_state(
        command_id="construction:maintenance:reapply",
        idempotency_key="construction:maintenance:reapply",
        facility_ref=facility.facility_ref,
        expected_revision=3,
        causation_id="cause:maintenance:reapply",
        correlation_id="corr:maintenance:reapply",
        source_ref="proposal:semantic:maintenance",
        submitted_at="2026-08-14T00:00:00Z",
        pinned_revisions={"semantic": 1},
        semantic_snapshot_digest="sha256:maintenance-state-reapply",
        application=EffectApplication(
            effect_ref="effect:maintenance_required",
            target_component_ref=facility.facility_ref,
            magnitude=10,
            stack_key="maintenance",
            expires_at_tick=None,
            causal_chain_id="chain:maintenance:reapply",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:maintenance_required",
            source_ref=facility.facility_ref,
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:maintenance_due",
            stack_policy="replace",
            stack_limit=1,
            expiry_policy="none",
        ),
    )
    assert reapplied.committed
    before = _snapshot(store)

    with pytest.raises(ValueError, match="maintenance_state_obligation_active"):
        authority.open_maintenance_state_obligation(
            state_event_id=store.read_events()[-1].event_id,
            due_tick=6,
            expected_revision=4,
            idempotency_key="construction:maintenance:second-open",
            correlation_id="corr:maintenance:second-open",
        )

    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_cancel_without_write() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()
    opened = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:cancel-open",
        correlation_id="corr:maintenance:cancel-open",
    )
    assert opened.committed and opened.obligation is not None
    active = opened.obligation.model_copy(
        update={
            "expected_revisions": {f"gameplay:construction_production:{facility.facility_ref}": 3},
        }
    )
    before = _snapshot(store)

    cancelled = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(ConstructionProductionAuthority.maintenance_state_obligation_registration(),),
    ).plan_cancel(
        obligation=active,
        fragment=OwnerAuthorizedFragment(
            fragment_id="fragment:construction:maintenance-state:cancel",
            owner_principal_ref="actor_gameplay.construction_production_domain",
            source_rule_ref="forged-cancel",
            expected_revisions=active.expected_revisions,
            event_specs={
                f"gameplay:construction_production:{facility.facility_ref}": (
                    (
                        "gameplay.construction_production.maintenance_state_obligation_cancelled",
                        {"obligation_id": active.obligation_id, "reason_ref": "reason:test"},
                    ),
                ),
            },
        ),
        principal_ref="world_runtime.caller",
        reason_ref="reason:test",
    )

    assert cancelled.ready is False
    assert cancelled.error_code == "obligation_cancel_unsupported"
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_retry_without_write() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()
    opened = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:retry-open",
        correlation_id="corr:maintenance:retry-open",
    )
    assert opened.committed and opened.obligation is not None
    before = _snapshot(store)

    retried = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(ConstructionProductionAuthority.maintenance_state_obligation_registration(),),
    ).retry(
        obligation=opened.obligation.model_copy(
            update={"retry_policy": {"attempt": 1, "max_attempts": 2}}
        ),
        fragment=OwnerAuthorizedFragment(
            fragment_id="fragment:construction:maintenance-state:retry",
            owner_principal_ref="actor_gameplay.construction_production_domain",
            source_rule_ref="forged-retry",
            expected_revisions=opened.obligation.expected_revisions,
            event_specs={
                f"gameplay:construction_production:{facility.facility_ref}": (
                    ("gameplay.construction_production.maintenance_state_obligation_retried", {}),
                ),
            },
        ),
        principal_ref="world_runtime.caller",
    )

    assert retried.error_code == "obligation_retry_unsupported"
    assert _snapshot(store) == before


def test_construction_maintenance_state_obligation_rejects_compensation_without_write() -> None:
    store, authority, facility, state_event_id = _seed_applied_state()
    opened = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:compensation-open",
        correlation_id="corr:maintenance:compensation-open",
    )
    assert opened.committed and opened.obligation is not None
    before = _snapshot(store)

    compensated = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(ConstructionProductionAuthority.maintenance_state_obligation_registration(),),
    ).compensate(
        obligation=opened.obligation.model_copy(
            update={"compensation_policy": {"reason_ref": "reason:test"}}
        ),
        fragment=OwnerAuthorizedFragment(
            fragment_id="fragment:construction:maintenance-state:compensation",
            owner_principal_ref="actor_gameplay.construction_production_domain",
            source_rule_ref="forged-compensation",
            expected_revisions=opened.obligation.expected_revisions,
            event_specs={
                f"gameplay:construction_production:{facility.facility_ref}": (
                    ("gameplay.construction_production.maintenance_state_obligation_compensated", {}),
                ),
            },
        ),
        principal_ref="world_runtime.caller",
    )

    assert compensated.error_code == "obligation_compensation_unsupported"
    assert _snapshot(store) == before


def _settle_maintenance_state_obligation() -> tuple[
    GameplayEventStore,
    ConstructionProductionAuthority,
    ObligationSettlementCoordinator,
    str,
]:
    store, authority, facility, state_event_id = _seed_applied_state()
    opened = authority.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=5,
        expected_revision=2,
        idempotency_key="construction:maintenance:lifecycle",
        correlation_id="corr:maintenance:lifecycle",
    )
    assert opened.committed and opened.obligation is not None
    registration = ConstructionProductionAuthority.maintenance_state_obligation_registration()
    due = opened.obligation.model_copy(
        update={
            "status": "due",
            "expected_revisions": {f"gameplay:construction_production:{facility.facility_ref}": 3},
        }
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(registration,))
    fragments = (
        authority.build_maintenance_state_expiry_fragment(
            obligation=due,
            facility_ref=facility.facility_ref,
            expected_revision=3,
        ),
    )
    settled = coordinator.plan_settle(
        obligation=due,
        fragments=fragments,
        principal_ref="world_runtime.caller",
    )
    assert settled.ready and settled.owner_commit_batch is not None
    append_result = authority.commit_obligation_batch(settled.owner_commit_batch)
    assert append_result.committed
    duplicate = coordinator.plan_settle(
        obligation=due,
        fragments=fragments,
        principal_ref="world_runtime.caller",
    )
    assert duplicate.receipt is not None
    coordinator._receipts[due.idempotency_key] = duplicate.receipt
    return store, authority, coordinator, opened.obligation.obligation_id


def test_construction_maintenance_state_obligation_projects_open_then_settled_lifecycle() -> None:
    store, _authority, _coordinator, obligation_id = _settle_maintenance_state_obligation()
    registration = ConstructionProductionAuthority.maintenance_state_obligation_registration()
    lifecycle = ObligationLifecycleProjection((registration,)).rebuild(store.read_events())

    assert obligation_id not in lifecycle.open
    assert lifecycle.terminal[obligation_id].status == "settled"


def test_construction_maintenance_state_obligation_emits_project_scoped_outbox() -> None:
    store, _authority, _coordinator, _obligation_id = _settle_maintenance_state_obligation()

    assert {entry.audience for entry in store.list_outbox()} == {"project"}


def test_construction_maintenance_state_obligation_receipt_is_append_derived() -> None:
    store, _authority, coordinator, _obligation_id = _settle_maintenance_state_obligation()

    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()
    assert coordinator.project_receipt(scope="authority")["committed_event_ids"] == tuple(
        event.event_id for event in store.read_events()[-2:]
    )


def test_construction_maintenance_state_obligation_replays_full_and_checkpoint_tail() -> None:
    store, authority, coordinator, _obligation_id = _settle_maintenance_state_obligation()

    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=3).projection_hash
    full = authority.projector()
    checkpoint_tail = authority.projector(checkpoint_at=3)
    assert full.maintenance_states == checkpoint_tail.maintenance_states == {}
    assert full.source_revision_vector == checkpoint_tail.source_revision_vector
