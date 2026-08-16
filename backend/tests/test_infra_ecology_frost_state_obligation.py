from __future__ import annotations

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ScheduledObligation
from app.world_runtime.obligations import (
    ObligationLifecycleProjection,
    ObligationLifecycleRegistration,
    ObligationSettlementCoordinator,
)
from app.world_runtime.simulation_clock import SimulationClock


REGION_REF = "region:valley"
CROP_REF = "crop:valley:wheat"
HAZARD_REF = "hazard:valley:frost"
STREAM = EcologyHazardAuthority.ecology_stream_id(region_ref=REGION_REF)
POLICY_REF = "policy:ecology_frost_crop_state_expiry@1"


def _bundle_command() -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id="command:ecology:valley:bundle",
        command_type="gameplay.ecology.region_bundle.record",
        command_version=1,
        principal_ref=EcologyHazardAuthority._PRINCIPAL,
        project_ref="project:demo",
        idempotency_key="ecology:valley:bundle",
        expected_revisions={STREAM: 0},
        causation_id="cause:ecology:valley:bundle",
        correlation_id="corr:ecology:valley:bundle",
        source_ref=EcologyHazardAuthority._PRINCIPAL,
        submitted_at="2026-08-14T00:00:00Z",
        payload={},
    )


def _apply_command(
    *,
    key: str = "ecology:frosted:apply:1",
    expected_revision: int = 5,
    scope: str = "project",
) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.ecology.apply_crop_state",
        command_version=1,
        principal_ref=EcologyHazardAuthority._PRINCIPAL,
        actor_ref=CROP_REF,
        project_ref="project:demo",
        idempotency_key=key,
        expected_revisions={STREAM: expected_revision},
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref=EcologyHazardAuthority._PRINCIPAL,
        submitted_at="2026-08-14T00:01:00Z",
        pinned_revisions={"ecology": expected_revision},
        payload={"visibility_scope": scope},
    )


def _region() -> EnvironmentRegion:
    return EnvironmentRegion(
        region_ref=REGION_REF,
        climate_profile_ref="climate:temperate",
        biome_tags=("biome:field",),
        jurisdiction_ref="jurisdiction:valley",
        revision=0,
    )


def _environment() -> EnvironmentalState:
    return EnvironmentalState(
        region_ref=REGION_REF,
        temperature_centi_c=-120,
        moisture_basis_points=5_200,
        weather_ref="weather:frost-front",
        revision=0,
    )


def _resource() -> ResourceNode:
    return ResourceNode(
        node_ref="resource:valley:water",
        region_ref=REGION_REF,
        substance_ref="substance:water",
        quantity=90,
        regeneration_per_tick=2,
        revision=0,
    )


def _crop() -> CropRecord:
    return CropRecord(
        crop_ref=CROP_REF,
        region_ref=REGION_REF,
        plot_ref="plot:valley:1",
        health=100,
        growth_basis_points=5_000,
        revision=0,
        owner_ref="authority:crop",
    )


def _hazard(*, privacy_scope: str = "project") -> HazardRecord:
    return HazardRecord(
        hazard_ref=HAZARD_REF,
        region_ref=REGION_REF,
        effect_ref="effect:frost",
        severity_basis_points=5_000,
        due_tick=4,
        duration_ticks=1,
        causal_parent_refs=("event:weather:valley",),
        semantic_revision="semantic:1",
        rule_revision="rule:1",
        policy_revision="rule:frost:1",
        revision=0,
        idempotency_key="ecology:frost:hazard:1",
        privacy_scope=privacy_scope,
    )


def _application(
    *,
    effect_ref: str = "effect:frost",
    magnitude: int = 50,
    expires_at_tick: int = 4,
) -> EffectApplication:
    return EffectApplication(
        effect_ref=effect_ref,
        target_component_ref=CROP_REF,
        magnitude=magnitude,
        stack_key="crop-state:frost",
        expires_at_tick=expires_at_tick,
        causal_chain_id=HAZARD_REF,
    )


def _resistance(*, effect_ref: str = "effect:frost") -> ResistanceProfile:
    return ResistanceProfile(
        effect_ref=effect_ref,
        source_ref=CROP_REF,
        modifier_basis_points=0,
        revision=1,
    )


def _state(*, state_ref: str = "state:frosted@1") -> StateDefinition:
    return StateDefinition(
        state_ref=state_ref,
        stack_policy="refresh",
        stack_limit=1,
        expiry_policy="scheduled",
    )


def _registration() -> ObligationLifecycleRegistration:
    return ObligationLifecycleRegistration(
        policy_ref=POLICY_REF,
        policy_revision="1",
        owner_ref=EcologyHazardAuthority._PRINCIPAL,
        stream_pattern="gameplay:ecology:{region_ref}",
        opened_event_type="gameplay.ecology.crop_state_obligation_opened",
        settled_event_type="gameplay.ecology.crop_state_obligation_settled",
        cancelled_event_type="gameplay.ecology.crop_state_obligation_cancelled",
        expired_event_type="gameplay.ecology.crop_state_expired",
        visibility_scope="project",
    )


def _seed() -> tuple[GameplayEventStore, EcologyHazardAuthority]:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    result = authority.record_region_bundle(
        envelope=_bundle_command(),
        region=_region(),
        environment=_environment(),
        resource=_resource(),
        crop=_crop(),
        hazard=_hazard(),
    )
    assert result.committed is True
    return store, authority


def _seed_with_hazard_privacy(*, privacy_scope: str) -> tuple[GameplayEventStore, EcologyHazardAuthority]:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    result = authority.record_region_bundle(
        envelope=_bundle_command(),
        region=_region(),
        environment=_environment(),
        resource=_resource(),
        crop=_crop(),
        hazard=_hazard(privacy_scope=privacy_scope),
    )
    assert result.committed is True
    return store, authority


def _apply(
    authority: EcologyHazardAuthority,
    *,
    key: str = "ecology:frosted:apply:1",
    expected_revision: int = 5,
    scope: str = "project",
    effect_ref: str = "effect:frost",
    magnitude: int = 50,
    expires_at_tick: int = 4,
    state_ref: str = "state:frosted@1",
):
    return authority.apply_crop_state(
        command=_apply_command(key=key, expected_revision=expected_revision, scope=scope),
        hazard_ref=HAZARD_REF,
        crop_ref=CROP_REF,
        application=_application(effect_ref=effect_ref, magnitude=magnitude, expires_at_tick=expires_at_tick),
        resistance=_resistance(effect_ref=effect_ref),
        definition=_state(state_ref=state_ref),
    )


def _open_obligation(store: GameplayEventStore):
    lifecycle = ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events())
    assert len(lifecycle.open) == 1
    return next(iter(lifecycle.open.values()))


def _due_obligation(store: GameplayEventStore, *, status: str = "due") -> ScheduledObligation:
    open_record = _open_obligation(store)
    return ScheduledObligation(
        obligation_id=open_record.obligation_id,
        owner_ref=open_record.owner_ref,
        due_tick=open_record.due_tick,
        policy_revision=open_record.policy_revision,
        status=status,
        source_refs=(POLICY_REF,),
        idempotency_key=f"ecology:frosted:settle:{open_record.obligation_id}",
        expected_revisions={STREAM: store.get_stream_head(STREAM)},
        visibility_scope=open_record.visibility_scope,
    )


def _settle_due(store: GameplayEventStore, authority: EcologyHazardAuthority):
    due = SimulationClock(world_ref="world:demo", catch_up_budget=1).advance(
        _due_obligation(store).due_tick,
        (_due_obligation(store),),
    ).due[0]
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(_registration(),),
    )
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(
            authority.build_frost_crop_state_fragment(
                obligation=due,
                region_ref=REGION_REF,
                hazard_ref=HAZARD_REF,
                crop_ref=CROP_REF,
                expected_revision=store.get_stream_head(STREAM),
            ),
        ),
        principal_ref="world_runtime.caller",
    )
    assert plan.ready and plan.owner_commit_batch is not None
    return authority.commit_obligation_batch(plan.owner_commit_batch)


def test_ecology_frost_crop_state_apply_commits_on_existing_ecology_stream() -> None:
    store, authority = _seed()

    result = _apply(authority)

    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.crop_state_applied",
        "gameplay.ecology.crop_state_obligation_opened",
    ]
    assert _open_obligation(store).due_tick == 4


def test_ecology_frost_crop_state_refresh_updates_due_without_reopening_the_row() -> None:
    store, authority = _seed()
    assert _apply(authority).committed is True

    refreshed = _apply(
        authority,
        key="ecology:frosted:refresh:2",
        expected_revision=7,
        expires_at_tick=6,
    )

    assert refreshed.committed is True
    assert _open_obligation(store).due_tick == 6
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.crop_state_applied",
        "gameplay.ecology.crop_state_obligation_opened",
    ]


def test_ecology_frost_crop_state_duplicate_replays_without_second_append() -> None:
    store, authority = _seed()
    first = _apply(authority)
    duplicate = _apply(authority)

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 7


def test_ecology_frost_crop_state_changed_duplicate_is_zero_write() -> None:
    store, authority = _seed()
    assert _apply(authority).committed is True

    changed = _apply(authority, magnitude=55)

    assert changed.committed is False
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 7


def test_ecology_frost_crop_state_revision_conflict_is_zero_write() -> None:
    store, authority = _seed()

    stale = _apply(authority, key="ecology:frosted:stale", expected_revision=4)

    assert stale.committed is False
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == 5


def test_ecology_frost_crop_state_nonproject_privacy_is_zero_write() -> None:
    store, authority = _seed()

    private = _apply(
        authority,
        key="ecology:frosted:private",
        scope="authority_only",
    )

    assert private.committed is False
    assert private.failure is not None and private.failure.error_code == "ecology_crop_state_privacy_scope_denied"
    assert len(store.read_events()) == 5


def test_ecology_frost_crop_state_authority_only_source_is_zero_write() -> None:
    store, authority = _seed_with_hazard_privacy(privacy_scope="authority_only")

    result = _apply(authority, key="ecology:frosted:authority-source")

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_crop_state_source_privacy_denied"
    assert len(store.read_events()) == 5


def test_ecology_frost_crop_state_unknown_row_is_zero_write() -> None:
    store, authority = _seed()

    unknown = _apply(
        authority,
        key="ecology:frosted:unknown-row",
        state_ref="state:blighted@1",
    )

    assert unknown.committed is False
    assert unknown.failure is not None and unknown.failure.error_code == "ecology_crop_state_row_unregistered"
    assert len(store.read_events()) == 5


def test_ecology_frost_crop_state_rejects_forged_shared_owner_contract_without_write(monkeypatch) -> None:
    store, authority = _seed()
    original = SemanticRegistry.require_closed_state_owner_contract

    def forged(cls, *, effect_ref: str, state_ref: str):
        return original(effect_ref=effect_ref, state_ref=state_ref).model_copy(
            update={"settled_event_type": "gameplay.ecology.forged_settled"}
        )

    monkeypatch.setattr(SemanticRegistry, "require_closed_state_owner_contract", classmethod(forged))
    result = _apply(authority, key="ecology:frosted:forged-contract")

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "ecology_crop_state_row_unregistered"
    assert len(store.read_events()) == 5


def test_ecology_frost_crop_state_due_expiry_settles_through_existing_coordinator() -> None:
    store, authority = _seed()
    assert _apply(authority).committed is True

    result = _settle_due(store, authority)

    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.crop_state_expired",
        "gameplay.ecology.crop_state_obligation_settled",
    ]


def test_ecology_frost_crop_state_outbox_is_project_scoped() -> None:
    store, authority = _seed()
    assert _apply(authority).committed is True
    assert _settle_due(store, authority).committed is True

    assert {entry.audience for entry in store.list_outbox()} == {"project"}
    assert {entry.topic for entry in store.list_outbox()} >= {
        "world.ecology.scoped_projection",
        "world.obligation.scoped_projection",
    }


def test_ecology_frost_crop_state_full_replay_rebuilds_committed_history() -> None:
    store, authority = _seed()
    assert _apply(authority).committed is True
    assert _settle_due(store, authority).committed is True

    replay = authority.crop_state_replay()

    assert replay.succeeded is True
    assert replay.state[STREAM]["last_event_type"] == "gameplay.ecology.crop_state_obligation_settled"


def test_ecology_frost_crop_state_checkpoint_tail_replay_matches_full_replay() -> None:
    store, authority = _seed()
    assert _apply(authority).committed is True
    assert _settle_due(store, authority).committed is True

    assert authority.crop_state_replay().projection_hash == authority.crop_state_replay(checkpoint_at=7).projection_hash
