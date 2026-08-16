from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import SemanticEffectCommand, SemanticSettlementAuthority
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry, TagAssignment, TagDefinition


def _registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:facility", category="type", version="1"))
    registry.assign_tag(
        TagAssignment(
            entity_ref="facility:bakery:1",
            tag_ref="type:facility",
            source_ref="fixture",
            revision=1,
        )
    )
    return registry


def _seed_construction_stream(store: GameplayEventStore) -> tuple[Facility, Recipe]:
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(
        plot_ref="plot:bakery:1",
        jurisdiction_ref="jurisdiction:demo",
        owner_ref="org:bakery",
    )
    facility = Facility(
        facility_ref="facility:bakery:1",
        plot_ref=plot.plot_ref,
        facility_kind="bakery",
        condition=1.0,
    )
    recipe = Recipe(
        recipe_ref="recipe:bread:1",
        inputs={},
        output_item="item:bread",
        duration_ticks=3,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="construction:facility:1",
        idempotency_key="construction:facility:1",
        causation_id="cause:facility:1",
        correlation_id="corr:facility:1",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:bakery:1",
        tick=0,
        command_id="construction:run:1",
        idempotency_key="construction:run:1",
        causation_id="cause:run:1",
        correlation_id="corr:run:1",
    ).committed
    return facility, recipe


def _seed_facility_only(store: GameplayEventStore) -> Facility:
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(
        plot_ref="plot:bakery:1",
        jurisdiction_ref="jurisdiction:demo",
        owner_ref="org:bakery",
    )
    facility = Facility(
        facility_ref="facility:bakery:1",
        plot_ref=plot.plot_ref,
        facility_kind="bakery",
        condition=1.0,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="construction:facility:1",
        idempotency_key="construction:facility:1",
        causation_id="cause:facility:1",
        correlation_id="corr:facility:1",
    ).committed
    return facility


def _submit(
    authority: SemanticSettlementAuthority,
    registry: SemanticRegistry,
    *,
    key: str = "construction-maintenance:1",
    expected_revision: int = 2,
    privacy_scope: str = "project",
    effect_ref: str = "effect:maintenance_required",
    state_ref: str = "state:maintenance_due",
    owner_ref: str = "actor_gameplay.construction_production_domain",
    target_ref: str = "facility:bakery:1",
    stream_id: str | None = None,
    magnitude: int = 120,
    source_revision_vector: dict[str, int] | None = None,
):
    target_stream_id = stream_id or f"gameplay:construction_production:{target_ref}"
    snapshot = registry.build_snapshot(
        target_ref,
        policy_context_ref="policy:construction:maintenance:1",
        source_revision_vector={"semantic": 1} if source_revision_vector is None else source_revision_vector,
    )
    return authority.settle_closed_construction_maintenance_state(
        SemanticEffectCommand(
            command_id=f"command:{key}",
            idempotency_key=key,
            principal_ref="authority:semantic",
            owner_ref=owner_ref,
            stream_id=target_stream_id,
            expected_revision=expected_revision,
            effect_ref=effect_ref,
            target_ref=target_ref,
            semantic_snapshot=snapshot,
            expected_snapshot_digest=snapshot.digest,
            privacy_scope=privacy_scope,
        ),
        application=EffectApplication(
            effect_ref=effect_ref,
            target_component_ref=target_ref,
            magnitude=magnitude,
            stack_key="maintenance",
            expires_at_tick=None,
            causal_chain_id="chain:construction-maintenance:1",
        ),
        resistance=ResistanceProfile(
            effect_ref=effect_ref,
            source_ref=target_ref,
            modifier_basis_points=2_500,
            revision=3,
        ),
        state=StateDefinition(
            state_ref=state_ref,
            stack_policy="replace",
            stack_limit=1,
            expiry_policy="none",
        ),
    )


def _zero_write_snapshot(store: GameplayEventStore) -> dict[str, object]:
    snapshot = store.export_snapshot()
    return {
        "events": snapshot["events"],
        "outbox": snapshot["outbox"],
        "idempotency": snapshot["idempotency"],
    }


def _assert_zero_write(before: dict[str, object], store: GameplayEventStore) -> None:
    assert _zero_write_snapshot(store) == before


def test_construction_maintenance_owner_row_appends_fixed_state_event() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)

    result = _submit(SemanticSettlementAuthority(store=store, registry=registry), registry)

    assert result.committed is True
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.construction_production.maintenance_state_applied"
    assert event.visibility_policy == "project"
    assert event.payload["facility_ref"] == "facility:bakery:1"
    assert event.payload["state_ref"] == "state:maintenance_due"
    assert event.payload["effect_ref"] == "effect:maintenance_required"
    assert event.payload["effective_magnitude"] == 90
    assert event.payload["next_stacks"] == 1
    assert event.payload["resistance_revision"] == 3
    assert event.payload["semantic_snapshot_digest"] == registry.build_snapshot(
        "facility:bakery:1",
        policy_context_ref="policy:construction:maintenance:1",
        source_revision_vector={"semantic": 1},
    ).digest


def test_construction_maintenance_owner_row_replays_exact_duplicate_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _submit(authority, registry).committed

    before = _zero_write_snapshot(store)
    duplicate = _submit(authority, registry)

    assert duplicate.idempotency_status == "duplicate_replayed"
    _assert_zero_write(before, store)


def test_construction_maintenance_owner_row_rejects_changed_duplicate_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _submit(authority, registry).committed

    before = _zero_write_snapshot(store)
    changed = _submit(authority, registry, magnitude=121)

    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    _assert_zero_write(before, store)


def test_construction_maintenance_owner_row_rejects_stale_revision_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _submit(authority, registry).committed

    before = _zero_write_snapshot(store)
    stale = _submit(authority, registry, key="construction-maintenance:stale", expected_revision=2)

    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "revision_conflict"
    _assert_zero_write(before, store)


def test_construction_maintenance_owner_row_rejects_nonproject_privacy_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)

    before = _zero_write_snapshot(store)
    rejected = _submit(
        SemanticSettlementAuthority(store=store, registry=registry),
        registry,
        privacy_scope="authority_only",
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "semantic_construction_privacy_scope_denied"
    _assert_zero_write(before, store)


def test_construction_maintenance_rejects_forged_shared_owner_contract_without_append(monkeypatch) -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)
    original = SemanticRegistry.require_closed_state_owner_contract

    def forged(cls, *, effect_ref: str, state_ref: str):
        return original(effect_ref=effect_ref, state_ref=state_ref).model_copy(
            update={"apply_event_type": "gameplay.forged.state_applied"}
        )

    monkeypatch.setattr(SemanticRegistry, "require_closed_state_owner_contract", classmethod(forged))
    before = _zero_write_snapshot(store)
    result = _submit(SemanticSettlementAuthority(store=store, registry=registry), registry)

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "construction_maintenance_owner_mapping_unregistered"
    _assert_zero_write(before, store)


@pytest.mark.parametrize(
    ("effect_ref", "state_ref", "owner_ref", "stream_id"),
    [
        ("effect:wrong", "state:maintenance_due", "actor_gameplay.construction_production_domain", "gameplay:construction_production:facility:bakery:1"),
        ("effect:maintenance_required", "state:wrong", "actor_gameplay.construction_production_domain", "gameplay:construction_production:facility:bakery:1"),
        ("effect:maintenance_required", "state:maintenance_due", "actor_gameplay.survival_domain", "gameplay:construction_production:facility:bakery:1"),
        ("effect:maintenance_required", "state:maintenance_due", "actor_gameplay.construction_production_domain", "gameplay:survival:facility:bakery:1"),
    ],
)
def test_construction_maintenance_owner_row_rejects_mismatched_pair_owner_or_stream_without_append(
    effect_ref: str,
    state_ref: str,
    owner_ref: str,
    stream_id: str,
) -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)

    before = _zero_write_snapshot(store)
    rejected = _submit(
        SemanticSettlementAuthority(store=store, registry=registry),
        registry,
        effect_ref=effect_ref,
        state_ref=state_ref,
        owner_ref=owner_ref,
        stream_id=stream_id,
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "semantic_construction_owner_mapping_unregistered"
    _assert_zero_write(before, store)


@pytest.mark.parametrize("source_revision_vector", [{}, {"semantic": 0}, {"semantic": 2}])
def test_construction_maintenance_owner_row_rejects_nonexact_semantic_vector_without_append(
    source_revision_vector: dict[str, int],
) -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)

    before = _zero_write_snapshot(store)
    rejected = _submit(
        SemanticSettlementAuthority(store=store, registry=registry),
        registry,
        source_revision_vector=source_revision_vector,
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "semantic_closed_registry_revision_mismatch"
    _assert_zero_write(before, store)


def test_construction_owner_rejects_direct_nonregistered_maintenance_effect_without_append() -> None:
    store = GameplayEventStore()
    _seed_construction_stream(store)
    owner = ConstructionProductionAuthority(store=store)
    before = _zero_write_snapshot(store)

    rejected = owner.apply_maintenance_state(
        command_id="command:direct-wrong-maintenance",
        idempotency_key="direct-wrong-maintenance",
        facility_ref="facility:bakery:1",
        expected_revision=2,
        causation_id="cause:direct-wrong-maintenance",
        correlation_id="corr:direct-wrong-maintenance",
        source_ref="direct-test",
        submitted_at="test",
        pinned_revisions={"semantic": 1},
        semantic_snapshot_digest="digest:direct-wrong-maintenance",
        application=EffectApplication(
            effect_ref="effect:foreign",
            target_component_ref="facility:bakery:1",
            magnitude=120,
            stack_key="foreign",
            expires_at_tick=None,
            causal_chain_id="chain:direct-wrong-maintenance",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:foreign",
            source_ref="facility:bakery:1",
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:foreign",
            stack_policy="replace",
            stack_limit=1,
            expiry_policy="none",
        ),
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "construction_maintenance_owner_mapping_unregistered"
    _assert_zero_write(before, store)


def test_construction_owner_rejects_direct_stale_semantic_vector_without_append() -> None:
    store = GameplayEventStore()
    _seed_construction_stream(store)
    owner = ConstructionProductionAuthority(store=store)
    before = _zero_write_snapshot(store)

    rejected = owner.apply_maintenance_state(
        command_id="command:direct-stale-maintenance",
        idempotency_key="direct-stale-maintenance",
        facility_ref="facility:bakery:1",
        expected_revision=2,
        causation_id="cause:direct-stale-maintenance",
        correlation_id="corr:direct-stale-maintenance",
        source_ref="direct-test",
        submitted_at="test",
        pinned_revisions={"semantic": 0},
        semantic_snapshot_digest="digest:direct-stale-maintenance",
        application=EffectApplication(
            effect_ref="effect:maintenance_required",
            target_component_ref="facility:bakery:1",
            magnitude=120,
            stack_key="maintenance",
            expires_at_tick=None,
            causal_chain_id="chain:direct-stale-maintenance",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:maintenance_required",
            source_ref="facility:bakery:1",
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

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "semantic_closed_registry_revision_mismatch"
    _assert_zero_write(before, store)


def test_construction_maintenance_owner_row_rejects_unacquired_facility_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    before = _zero_write_snapshot(store)

    rejected = _submit(
        SemanticSettlementAuthority(store=store, registry=registry),
        registry,
        key="construction-maintenance:ghost",
        expected_revision=0,
        target_ref="facility:ghost:1",
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "construction_maintenance_facility_unknown"
    _assert_zero_write(before, store)


def test_construction_maintenance_owner_row_settles_facility_without_started_run() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_facility_only(store)

    result = _submit(
        SemanticSettlementAuthority(store=store, registry=registry),
        registry,
        expected_revision=1,
    )

    assert result.committed
    assert "run_ref" not in store.read_events()[-1].payload


def test_construction_maintenance_owner_row_emits_project_scoped_outbox_and_projection() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)
    assert _submit(SemanticSettlementAuthority(store=store, registry=registry), registry).committed

    outbox = store.list_outbox()
    projection = ConstructionProductionAuthority(store=store).projector()

    assert outbox[-1].audience == "project"
    assert outbox[-1].topic == "construction_production.scoped_projection"
    state = projection.maintenance_states["facility:bakery:1"]
    assert state.state_ref == "state:maintenance_due"
    assert state.effect_ref == "effect:maintenance_required"
    assert state.stacks == 1
    assert state.effective_magnitude == 90


def test_construction_maintenance_owner_row_full_and_checkpoint_tail_projection_match() -> None:
    store = GameplayEventStore()
    registry = _registry()
    _seed_construction_stream(store)
    assert _submit(SemanticSettlementAuthority(store=store, registry=registry), registry).committed

    authority = ConstructionProductionAuthority(store=store)
    full = authority.projector()
    checkpoint = authority.projector(checkpoint_at=2)

    assert full.maintenance_states == checkpoint.maintenance_states
    assert full.source_revision_vector == checkpoint.source_revision_vector
