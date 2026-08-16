from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
)
from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import (
    RegisteredStateApplyCommand,
    RegisteredStateApplyConstructionProvenance,
    RegisteredStateApplyEcologyDroughtProvenance,
    RegisteredStateApplyEcologyFrostProvenance,
    RegisteredStateApplySurvivalProvenance,
    SemanticEffectCommand,
    SemanticSettlementAuthority,
)
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry, StateLifecyclePolicy
from test_infra_ecology_drought_state_obligation import (
    REGION_REF as DROUGHT_REGION_REF,
    STREAM as DROUGHT_STREAM,
    _seed_process,
)
from test_infra_ecology_frost_state_obligation import (
    CROP_REF as FROST_CROP_REF,
    HAZARD_REF as FROST_HAZARD_REF,
    REGION_REF as FROST_REGION_REF,
    STREAM as FROST_STREAM,
    _seed as _seed_frost,
)


def _survival_registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    for state_ref, effect_ref in (
        ("state:cold", "effect:cold_exposure"),
        ("state:overheated", "effect:heat_exposure"),
        ("state:dehydrated", "effect:dehydration_exposure"),
        ("state:fatigued", "effect:fatigue_exposure"),
    ):
        registry.register_state_lifecycle(
            StateLifecyclePolicy(
                state_ref=state_ref,
                effect_ref=effect_ref,
                lifecycle="scheduled",
                revision="1",
                owner_ref="actor_gameplay.survival_domain",
                stream_pattern="gameplay:survival:{actor_ref}",
                opened_event_type="gameplay.survival.obligation_opened",
                settled_event_type="gameplay.survival.obligation_settled",
                cancelled_event_type="gameplay.survival.obligation_cancelled",
                fragment_builder_ref="SurvivalAuthority.build_state_expiry_fragment",
                projection_scope="project",
            )
        )
    return registry


def _survival_registered_submission(
    *, stream_id: str = "gameplay:survival:character:ava"
) -> tuple[RegisteredStateApplyCommand, EffectApplication, ResistanceProfile, StateDefinition]:
    registry = _survival_registry()
    snapshot = registry.build_snapshot("character:ava", source_revision_vector={"semantic": 1})
    return (
        RegisteredStateApplyCommand(
            command_id="command:registered-survival",
            idempotency_key="registered-survival",
            principal_ref="authority:semantic",
            owner_ref="actor_gameplay.survival_domain",
            stream_id=stream_id,
            expected_revision=0,
            effect_ref="effect:cold_exposure",
            state_ref="state:cold",
            target_ref="character:ava",
            semantic_snapshot=snapshot,
            expected_snapshot_digest=snapshot.digest,
            privacy_scope="project",
            provenance=RegisteredStateApplySurvivalProvenance(),
        ),
        EffectApplication(
            effect_ref="effect:cold_exposure",
            target_component_ref="character:ava",
            magnitude=100,
            stack_key="cold",
            expires_at_tick=8,
            causal_chain_id="chain:registered-survival",
        ),
        ResistanceProfile(
            effect_ref="effect:cold_exposure",
            source_ref="character:ava",
            modifier_basis_points=0,
            revision=1,
        ),
        StateDefinition(
            state_ref="state:cold",
            stack_policy="add",
            stack_limit=2,
            expiry_policy="scheduled",
        ),
    )


def _survival_direct_submission(
    *, stream_id: str = "gameplay:survival:character:ava"
) -> tuple[SemanticEffectCommand, EffectApplication, ResistanceProfile, StateDefinition]:
    registry = _survival_registry()
    snapshot = registry.build_snapshot("character:ava", source_revision_vector={"semantic": 1})
    return (
        SemanticEffectCommand(
            command_id="command:closed-survival",
            idempotency_key="closed-survival",
            principal_ref="authority:semantic",
            owner_ref="actor_gameplay.survival_domain",
            stream_id=stream_id,
            expected_revision=0,
            effect_ref="effect:cold_exposure",
            target_ref="character:ava",
            semantic_snapshot=snapshot,
            expected_snapshot_digest=snapshot.digest,
            privacy_scope="project",
        ),
        EffectApplication(
            effect_ref="effect:cold_exposure",
            target_component_ref="character:ava",
            magnitude=100,
            stack_key="cold",
            expires_at_tick=8,
            causal_chain_id="chain:registered-survival",
        ),
        ResistanceProfile(
            effect_ref="effect:cold_exposure",
            source_ref="character:ava",
            modifier_basis_points=0,
            revision=1,
        ),
        StateDefinition(
            state_ref="state:cold",
            stack_policy="add",
            stack_limit=2,
            expiry_policy="scheduled",
        ),
    )


def _seed_construction_facility(
    *, suffix: str
) -> tuple[GameplayEventStore, Facility]:
    store = GameplayEventStore()
    construction = ConstructionProductionAuthority(store=store)
    plot = Plot(
        plot_ref=f"plot:{suffix}",
        jurisdiction_ref="jurisdiction:demo",
        owner_ref="org:demo",
    )
    facility = Facility(
        facility_ref=f"facility:{suffix}",
        plot_ref=plot.plot_ref,
        facility_kind="bakery",
        condition=1.0,
    )
    assert construction.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id=f"construction:{suffix}:acquire",
        idempotency_key=f"construction:{suffix}:acquire",
        causation_id=f"cause:{suffix}:acquire",
        correlation_id=f"corr:{suffix}:acquire",
    ).committed
    return store, facility


def _construction_submission(
    *, suffix: str = "dispatch:1"
) -> tuple[GameplayEventStore, RegisteredStateApplyCommand, EffectApplication, ResistanceProfile, StateDefinition]:
    store, facility = _seed_construction_facility(suffix=suffix)
    registry = SemanticRegistry()
    snapshot = registry.build_snapshot(facility.facility_ref, source_revision_vector={"semantic": 1})
    return (
        store,
        RegisteredStateApplyCommand(
            command_id=f"command:registered-construction:{suffix}",
            idempotency_key=f"registered-construction:{suffix}",
            principal_ref="authority:semantic",
            owner_ref="actor_gameplay.construction_production_domain",
            stream_id=f"gameplay:construction_production:{facility.facility_ref}",
            expected_revision=1,
            effect_ref="effect:maintenance_required",
            state_ref="state:maintenance_due",
            target_ref=facility.facility_ref,
            semantic_snapshot=snapshot,
            expected_snapshot_digest=snapshot.digest,
            privacy_scope="project",
            provenance=RegisteredStateApplyConstructionProvenance(),
        ),
        EffectApplication(
            effect_ref="effect:maintenance_required",
            target_component_ref=facility.facility_ref,
            magnitude=100,
            stack_key="maintenance",
            causal_chain_id=f"chain:registered-construction:{suffix}",
        ),
        ResistanceProfile(
            effect_ref="effect:maintenance_required",
            source_ref=facility.facility_ref,
            modifier_basis_points=0,
            revision=1,
        ),
        StateDefinition(
            state_ref="state:maintenance_due",
            stack_policy="replace",
            stack_limit=1,
            expiry_policy="none",
        ),
    )


def _frost_submission(
    *,
    key: str = "semantic:frost:registered",
    region_ref: str = FROST_REGION_REF,
    stream_id: str | None = None,
    expected_revision: int | None = None,
    magnitude: int = 50,
    digest: str = "sha256:frost",
) -> tuple[GameplayEventStore, RegisteredStateApplyCommand]:
    store, _authority = _seed_frost()
    registry = SemanticRegistry()
    snapshot = registry.build_snapshot(
        FROST_CROP_REF,
        source_revision_vector={"semantic": 1},
    ).model_copy(update={"digest": digest})
    return (
        store,
        RegisteredStateApplyCommand(
            command_id=key,
            idempotency_key=key,
            principal_ref="authority:semantic",
            owner_ref="authority:ecology",
            stream_id=stream_id or FROST_STREAM,
            expected_revision=store.get_stream_head(FROST_STREAM)
            if expected_revision is None
            else expected_revision,
            effect_ref="effect:frost",
            state_ref="state:frosted@1",
            target_ref=FROST_CROP_REF,
            semantic_snapshot=snapshot,
            expected_snapshot_digest=digest,
            privacy_scope="project",
            provenance=RegisteredStateApplyEcologyFrostProvenance(
                hazard_ref=FROST_HAZARD_REF,
                region_ref=region_ref,
                magnitude=magnitude,
                due_tick=4,
                resistance_revision=1,
            ),
        ),
    )


def _drought_submission(
    *,
    key: str = "semantic:drought:registered",
    target_ref: str = DROUGHT_REGION_REF,
    stream_id: str | None = None,
    expected_revision: int | None = None,
    source_event_id: str | None = None,
    source_event_revision: int | None = None,
    digest: str = "sha256:drought",
) -> tuple[GameplayEventStore, RegisteredStateApplyCommand, str, int]:
    store, _authority, seeded_event_id, seeded_event_revision = _seed_process()
    registry = SemanticRegistry()
    snapshot = registry.build_snapshot(
        target_ref,
        source_revision_vector={"semantic": 1},
    ).model_copy(update={"digest": digest})
    return (
        store,
        RegisteredStateApplyCommand(
            command_id=key,
            idempotency_key=key,
            principal_ref="authority:semantic",
            owner_ref="authority:ecology",
            stream_id=stream_id or DROUGHT_STREAM,
            expected_revision=store.get_stream_head(DROUGHT_STREAM)
            if expected_revision is None
            else expected_revision,
            effect_ref="effect:drought",
            state_ref="state:drought@1",
            target_ref=target_ref,
            semantic_snapshot=snapshot,
            expected_snapshot_digest=digest,
            privacy_scope="project",
            provenance=RegisteredStateApplyEcologyDroughtProvenance(
                source_event_id=source_event_id or seeded_event_id,
                source_event_revision=source_event_revision or seeded_event_revision,
                due_tick=6,
                resistance_revision=1,
            ),
        ),
        seeded_event_id,
        seeded_event_revision,
    )


def test_registered_state_dispatch_routes_survival_to_existing_owner() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, state = _survival_registered_submission()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]


def test_registered_state_dispatch_routes_fatigue_to_existing_owner() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, _ = _survival_registered_submission()
    command = command.model_copy(
        update={
            "command_id": "command:registered-fatigue",
            "idempotency_key": "registered-fatigue",
            "effect_ref": "effect:fatigue_exposure",
            "state_ref": "state:fatigued",
        }
    )
    application = application.model_copy(
        update={"effect_ref": "effect:fatigue_exposure", "stack_key": "fatigue"}
    )
    resistance = resistance.model_copy(update={"effect_ref": "effect:fatigue_exposure"})
    state = StateDefinition(
        state_ref="state:fatigued",
        stack_policy="refresh",
        stack_limit=1,
        expiry_policy="scheduled",
        transform_targets=("state:recovering",),
    )

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]


def test_registered_state_owner_matrix_contains_exact_seven_apply_rows() -> None:
    registry = _survival_registry()
    rows = registry.registered_state_owner_rows()

    assert [(row.state_ref, row.effect_ref, row.owner_ref) for row in rows] == [
        ("state:cold", "effect:cold_exposure", "actor_gameplay.survival_domain"),
        ("state:dehydrated", "effect:dehydration_exposure", "actor_gameplay.survival_domain"),
        ("state:drought@1", "effect:drought", "authority:ecology"),
        ("state:fatigued", "effect:fatigue_exposure", "actor_gameplay.survival_domain"),
        ("state:frosted@1", "effect:frost", "authority:ecology"),
        (
            "state:maintenance_due",
            "effect:maintenance_required",
            "actor_gameplay.construction_production_domain",
        ),
        ("state:overheated", "effect:heat_exposure", "actor_gameplay.survival_domain"),
    ]
    assert all(row.projection_scope == "project" for row in rows)
    assert all(row.revision == "1" for row in rows)


def test_registered_state_dispatch_routes_construction_to_existing_owner() -> None:
    store, command, application, resistance, state = _construction_submission()

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )

    assert result.committed
    assert store.read_events()[-1].event_type == "gameplay.construction_production.maintenance_state_applied"


def test_registered_state_dispatch_routes_ecology_frost_to_existing_owner() -> None:
    store, command = _frost_submission()

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_registered_state(
        command
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.crop_state_applied",
        "gameplay.ecology.crop_state_obligation_opened",
    ]


def test_registered_state_dispatch_routes_ecology_drought_to_existing_owner() -> None:
    store, command, _source_event_id, _source_event_revision = _drought_submission()

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_registered_state(
        command
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.drought_state_applied",
        "gameplay.ecology.drought_state_obligation_opened",
    ]


def test_registered_state_dispatch_rejects_unknown_row_without_write() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, state = _survival_registered_submission()
    command = command.model_copy(update={"effect_ref": "effect:unknown"})
    application = application.model_copy(update={"effect_ref": "effect:unknown"})
    resistance = resistance.model_copy(update={"effect_ref": "effect:unknown"})
    state = state.model_copy(update={"state_ref": "state:unknown"})

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "semantic_registered_state_route_unknown"
    assert store.read_events() == []


def test_registered_state_dispatch_rejects_wrong_route_without_write() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, state = _survival_registered_submission(
        stream_id="gameplay:construction_production:forged"
    )

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "semantic_registered_state_route_mismatch"
    assert store.read_events() == []


def test_registered_state_dispatch_preserves_survival_duplicate_idempotency() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, state = _survival_registered_submission()
    authority = SemanticSettlementAuthority(store=store, registry=registry)

    first = authority.settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )
    before = tuple(store.read_events())
    duplicate = authority.settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )

    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert tuple(store.read_events()) == before


def test_registered_state_dispatch_rejects_changed_duplicate_without_write() -> None:
    store, command = _frost_submission(key="semantic:frost:changed-duplicate")
    authority = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())

    first = authority.settle_registered_state(command)
    duplicate = authority.settle_registered_state(
        command.model_copy(
            update={
                "provenance": command.provenance.model_copy(update={"magnitude": 55}),
            }
        )
    )

    assert first.committed
    assert not duplicate.committed
    assert duplicate.failure is not None
    assert duplicate.failure.error_code == "idempotency_key_reused"


def test_registered_state_dispatch_preserves_survival_revision_and_privacy_zero_write() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, state = _survival_registered_submission()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    ).committed

    stale = authority.settle_registered_state(
        command.model_copy(
            update={
                "command_id": "command:registered-survival-stale",
                "idempotency_key": "registered-survival-stale",
            }
        ),
        application=application,
        resistance=resistance,
        state=state,
    )
    private = authority.settle_registered_state(
        command.model_copy(
            update={
                "command_id": "command:registered-survival-private",
                "idempotency_key": "registered-survival-private",
                "privacy_scope": "private_evidence",
            }
        ),
        application=application,
        resistance=resistance,
        state=state,
    )

    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert private.failure is not None and private.failure.error_code == "semantic_registered_state_route_mismatch"
    assert len(store.read_events()) == 2


def test_registered_state_dispatch_rejects_forged_drought_provenance_without_write() -> None:
    store, command, source_event_id, source_event_revision = _drought_submission(
        key="semantic:drought:forged-provenance",
        target_ref="region:forged",
        stream_id="gameplay:ecology:region:forged",
        expected_revision=0,
    )
    command = command.model_copy(
        update={
            "provenance": RegisteredStateApplyEcologyDroughtProvenance(
                source_event_id=source_event_id,
                source_event_revision=source_event_revision,
                due_tick=6,
                resistance_revision=1,
            )
        }
    )

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_registered_state(
        command
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "ecology_drought_state_source_invalid"
    assert store.read_events()[-1].event_type == "gameplay.ecology.drought_process_advanced"


def test_registered_state_dispatch_project_scope_outbox_is_preserved() -> None:
    store, command = _frost_submission(key="semantic:frost:privacy-scope")

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_registered_state(
        command
    )

    assert result.committed
    assert store.list_outbox()[-1].audience == "project"


def test_direct_survival_helper_rejects_stale_semantic_vector_without_write() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, state = _survival_direct_submission()
    stale_snapshot = registry.build_snapshot("character:ava", source_revision_vector={"semantic": 2})
    command = command.model_copy(
        update={
            "semantic_snapshot": stale_snapshot,
            "expected_snapshot_digest": stale_snapshot.digest,
        }
    )

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_closed_survival_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "semantic_closed_registry_revision_mismatch"
    assert store.read_events() == []


def test_registered_survival_dispatch_rejects_noncanonical_state_definition_without_write() -> None:
    store = GameplayEventStore()
    registry = _survival_registry()
    command, application, resistance, state = _survival_registered_submission()
    altered_state = state.model_copy(update={"stack_limit": 99})

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=altered_state,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "semantic_survival_owner_mapping_unregistered"
    assert store.read_events() == []


def test_registered_construction_dispatch_replays_full_and_checkpoint_tail() -> None:
    store, command, application, resistance, state = _construction_submission(
        suffix="dispatch:replay"
    )

    assert SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_registered_state(
        command,
        application=application,
        resistance=resistance,
        state=state,
    ).committed

    construction = ConstructionProductionAuthority(store=store)
    full = construction.projector()
    tail = construction.projector(checkpoint_at=1)
    assert full.maintenance_states == tail.maintenance_states
    assert full.source_revision_vector == tail.source_revision_vector


def test_registered_ecology_frost_dispatch_replays_full_and_checkpoint_tail() -> None:
    store, command = _frost_submission(key="semantic:frost:replay")

    assert SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_registered_state(
        command
    ).committed

    authority = EcologyHazardAuthority(store=store)
    assert authority.crop_state_replay().projection_hash == authority.crop_state_replay(
        checkpoint_at=5
    ).projection_hash
