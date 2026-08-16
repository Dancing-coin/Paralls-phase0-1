from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment
from app.gameplay.construction_production_runtime import (
    ConstructionDueCompletionPolicy,
    ProductionRun,
    Recipe,
)
from app.gameplay.shared_contracts import ScheduledObligation
from app.world_runtime.obligations import (
    ObligationLifecycleContractRegistry,
    ObligationLifecycleRegistration,
    ObligationSettlementCoordinator,
)


def _unknown_obligation() -> ScheduledObligation:
    return ScheduledObligation(
        obligation_id="obligation:farm:admission",
        owner_ref="authority:farm",
        due_tick=1,
        policy_revision="1",
        status="due",
        source_refs=("policy:farm_harvest",),
        idempotency_key="obligation:farm:admission",
        expected_revisions={"gameplay:farm:demo": 0},
        visibility_scope="project",
    )


def _unknown_fragment() -> OwnerAuthorizedFragment:
    return OwnerAuthorizedFragment(
        fragment_id="fragment:farm:admission",
        owner_principal_ref="authority:farm",
        source_rule_ref="policy:farm_harvest",
        expected_revisions={"gameplay:farm:demo": 0},
        event_specs={"gameplay:farm:demo": (("gameplay.farm.harvest_settled", {"obligation_id": "obligation:farm:admission"}),)},
        event_visibility_policies={"gameplay:farm:demo": ("project",)},
    )


def test_closed_lifecycle_registration_reader_contains_only_existing_owner_policies() -> None:
    registrations = ObligationLifecycleContractRegistry.closed_registrations()

    assert [(item.policy_ref, item.owner_ref, item.stream_pattern) for item in registrations] == [
        ("policy:construction_due_completion", "actor_gameplay.construction_production_domain", "gameplay:construction_production:{facility_ref}"),
        ("policy:construction_maintenance_state_expiry@1", "actor_gameplay.construction_production_domain", "gameplay:construction_production:{facility_ref}"),
        ("policy:ecology_drought_state_expiry@1", "authority:ecology", "gameplay:ecology:{region_ref}"),
        ("policy:ecology_frost_crop_state_expiry@1", "authority:ecology", "gameplay:ecology:{region_ref}"),
            ("policy:economy_scheduled_account_transfer@1", "actor_gameplay.economy_domain", "gameplay:economy"),
            ("policy:economy_tax_due@1", "actor_gameplay.economy_domain", "gameplay:economy"),
            ("policy:economy_wage_accrual", "actor_gameplay.econ1_economy_domain", "gameplay:economy:wage:{worker_ref}"),
        ("policy:survival_state_expiry", "actor_gameplay.survival_domain", "gameplay:survival:{actor_ref}"),
    ]


def test_policyless_generic_fragment_is_zero_write_rejected() -> None:
    store = GameplayEventStore()
    obligation = _unknown_obligation().model_copy(update={"source_refs": ()})

    result = ObligationSettlementCoordinator(store=store).settle(
        obligation=obligation,
        fragments=(_unknown_fragment(),),
        principal_ref="world_runtime.caller",
    )

    assert not result.committed
    assert result.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_unknown_policy_and_forged_registration_are_zero_write_rejected() -> None:
    store = GameplayEventStore()
    forged = ObligationLifecycleRegistration(
        policy_ref="policy:farm_harvest",
        policy_revision="1",
        owner_ref="authority:farm",
        stream_pattern="gameplay:farm:{farm_ref}",
        opened_event_type="gameplay.farm.harvest_opened",
        settled_event_type="gameplay.farm.harvest_settled",
        visibility_scope="project",
    )

    result = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(forged,)).settle(
        obligation=_unknown_obligation(),
        fragments=(_unknown_fragment(),),
        principal_ref="world_runtime.caller",
    )

    assert not result.committed
    assert result.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_closed_registration_rejects_a_widened_terminal_event_contract() -> None:
    canonical = ObligationLifecycleContractRegistry.require(
        policy_ref="policy:economy_wage_accrual",
        policy_revision="1",
    )
    widened = canonical.model_copy(update={"settled_event_type": "gameplay.economy.wage_paid"})

    assert not ObligationLifecycleContractRegistry.permits(widened)


def test_registered_lifecycle_fragment_cannot_smuggle_an_unregistered_event() -> None:
    store = GameplayEventStore()
    policy = ConstructionDueCompletionPolicy(
        policy_ref="policy:construction_due_completion",
        policy_revision="1",
    )
    run = ProductionRun(
        run_ref="run:admission",
        facility_ref="facility:admission",
        recipe_ref="recipe:admission",
        started_tick=0,
        finish_tick=2,
    )
    obligation = policy.build_obligation(run=run, expected_revision=0)
    fragment = policy.build_fragment(
        run=run,
        recipe=Recipe(
            recipe_ref="recipe:admission",
            inputs={},
            output_item="item:bread",
            duration_ticks=2,
        ),
        tick=2,
        expected_revision=0,
        obligation=obligation,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )
    stream_id = next(iter(fragment.event_specs))
    smuggled = fragment.model_copy(
        update={
            "event_specs": {
                stream_id: fragment.event_specs[stream_id]
                + (("gameplay.construction_production.unregistered_write", {"obligation_id": obligation.obligation_id}),)
            }
        },
        deep=True,
    )

    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(
            ObligationLifecycleContractRegistry.require(
                policy_ref="policy:construction_due_completion",
                policy_revision="1",
            ),
        ),
    ).settle(
        obligation=obligation,
        fragments=(smuggled,),
        principal_ref="world_runtime.caller",
    )

    assert not result.committed
    assert result.error_code == "obligation_fragment_event_unregistered"
    assert store.read_events() == []


def test_registered_lifecycle_fragment_cannot_override_the_owner_privacy_scope() -> None:
    store = GameplayEventStore()
    policy = ConstructionDueCompletionPolicy(
        policy_ref="policy:construction_due_completion",
        policy_revision="1",
    )
    run = ProductionRun(
        run_ref="run:privacy",
        facility_ref="facility:privacy",
        recipe_ref="recipe:privacy",
        started_tick=0,
        finish_tick=2,
    )
    obligation = policy.build_obligation(run=run, expected_revision=0)
    fragment = policy.build_fragment(
        run=run,
        recipe=Recipe(
            recipe_ref="recipe:privacy",
            inputs={},
            output_item="item:bread",
            duration_ticks=2,
        ),
        tick=2,
        expected_revision=0,
        obligation=obligation,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )
    stream_id = next(iter(fragment.event_specs))
    private = fragment.model_copy(
        update={"event_visibility_policies": {stream_id: ("authority_only", "authority_only")}},
        deep=True,
    )

    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(
            ObligationLifecycleContractRegistry.require(
                policy_ref="policy:construction_due_completion",
                policy_revision="1",
            ),
        ),
    ).settle(
        obligation=obligation,
        fragments=(private,),
        principal_ref="world_runtime.caller",
    )

    assert not result.committed
    assert result.error_code == "obligation_fragment_visibility_mismatch"
    assert store.read_events() == []


def test_construction_due_completion_requires_its_committed_run_open_event() -> None:
    store = GameplayEventStore()
    policy = ConstructionDueCompletionPolicy(
        policy_ref="policy:construction_due_completion",
        policy_revision="1",
    )
    run = ProductionRun(
        run_ref="run:open-required",
        facility_ref="facility:open-required",
        recipe_ref="recipe:open-required",
        started_tick=0,
        finish_tick=2,
    )
    obligation = policy.build_obligation(run=run, expected_revision=0)
    fragment = policy.build_fragment(
        run=run,
        recipe=Recipe(
            recipe_ref="recipe:open-required",
            inputs={},
            output_item="item:bread",
            duration_ticks=2,
        ),
        tick=2,
        expected_revision=0,
        obligation=obligation,
        settled_event_type="gameplay.construction_production.obligation_settled",
    )

    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(
            ObligationLifecycleContractRegistry.require(
                policy_ref="policy:construction_due_completion",
                policy_revision="1",
            ),
        ),
    ).settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )

    assert not result.committed
    assert result.error_code == "obligation_lifecycle_not_open"
    assert store.read_events() == []
