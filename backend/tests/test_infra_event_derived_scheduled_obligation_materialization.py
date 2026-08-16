from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import SemanticSettlementAuthority
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority
from app.world_runtime.obligations import (
    ObligationLifecycleContractRegistry,
    ObligationLifecycleProjection,
)


def _survival_command() -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id="command:survival:materialize",
        command_type="gameplay.survival.apply_state",
        command_version=1,
        principal_ref="actor_gameplay.survival_domain",
        actor_ref="character:ava",
        project_ref="project:demo",
        idempotency_key="survival:materialize",
        expected_revisions={"gameplay:survival:character:ava": 0},
        causation_id="cause:survival:materialize",
        correlation_id="corr:survival:materialize",
        source_ref="proposal:semantic:cold",
        submitted_at="2026-08-16T00:00:00Z",
    )


def _seed_two_owner_open_events() -> GameplayEventStore:
    store = GameplayEventStore()
    assert ConstructionProductionAuthority(store=store).settle_start_run(
        facility=Facility(
            facility_ref="facility:bakery",
            plot_ref="plot:bakery",
            facility_kind="bakery",
            condition=1,
        ),
        recipe=Recipe(
            recipe_ref="recipe:bread",
            inputs={},
            output_item="item:bread",
            duration_ticks=3,
        ),
        run_ref="run:bakery",
        tick=0,
        command_id="command:construction:materialize",
        idempotency_key="construction:materialize",
        causation_id="cause:construction:materialize",
        correlation_id="corr:construction:materialize",
    ).committed
    assert SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(
            effect_ref="effect:cold",
            target_component_ref="character:ava",
            magnitude=1,
            stack_key="cold",
            expires_at_tick=4,
            causal_chain_id="chain:cold",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:cold",
            source_ref="character:ava",
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:cold",
            stack_policy="add",
            stack_limit=1,
            expiry_policy="scheduled",
        ),
    ).committed
    return store


def test_event_derived_view_materializes_scheduled_obligations_for_two_existing_owners() -> None:
    store = _seed_two_owner_open_events()
    view = ObligationLifecycleProjection(
        ObligationLifecycleContractRegistry.closed_registrations()
    ).rebuild(store.read_events())

    obligations = view.to_scheduled_obligations()

    assert {item.owner_ref for item in obligations} == {
        "actor_gameplay.construction_production_domain",
        "actor_gameplay.survival_domain",
    }
    assert {item.status for item in obligations} == {"open"}
    assert all(item.idempotency_key.startswith("lifecycle:") for item in obligations)
    assert all(item.source_refs for item in obligations)
    for item in obligations:
        stream_ref = next(
            source_ref.removeprefix("stream:")
            for source_ref in item.source_refs
            if source_ref.startswith("stream:")
        )
        assert item.expected_revisions[stream_ref] >= 0


def test_event_derived_due_materialization_is_bounded_and_does_not_write() -> None:
    store = _seed_two_owner_open_events()
    projection = ObligationLifecycleProjection(
        ObligationLifecycleContractRegistry.closed_registrations()
    )
    before = store.export_snapshot()

    view = projection.replay_at(store.read_events(), tick=4, catch_up_limit=1)
    due = view.to_scheduled_obligations()

    assert sum(item.status == "due" for item in due) == 1
    assert store.export_snapshot() == before


def test_event_derived_materialization_reconstructs_from_checkpoint_tail() -> None:
    store = _seed_two_owner_open_events()
    projection = ObligationLifecycleProjection(
        ObligationLifecycleContractRegistry.closed_registrations()
    )
    events = store.read_events()
    full = projection.replay_at(events, tick=4, catch_up_limit=2)
    checkpoint = projection.create_checkpoint(events[:1])
    tail = projection.checkpoint_plus_tail_at(
        checkpoint,
        events[1:],
        tick=4,
        catch_up_limit=2,
    )

    assert tail.to_scheduled_obligations() == full.to_scheduled_obligations()
