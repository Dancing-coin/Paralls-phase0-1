from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalState, SurvivalStateExpiryPolicy
from app.world_runtime.obligations import ObligationLifecycleRegistration, ObligationSettlementCoordinator
from app.world_runtime.simulation_clock import SimulationClock


def _command(*, expected_revision: int = 0, key: str = "survival-state:apply:1") -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.survival.apply_state",
        command_version=1,
        principal_ref="actor_gameplay.survival_domain",
        actor_ref="character:ava",
        project_ref="project:demo",
        idempotency_key=key,
        expected_revisions={"gameplay:survival:character:ava": expected_revision},
        causation_id="cause:survival-state:1",
        correlation_id="corr:survival-state:1",
        source_ref="proposal:semantic:frost:1",
        submitted_at="2026-08-13T00:00:00Z",
        pinned_revisions={"semantic": 1},
        payload={},
    )


def _application() -> EffectApplication:
    return EffectApplication(
        effect_ref="effect:cold_exposure",
        target_component_ref="character:ava",
        magnitude=100,
        stack_key="cold",
        expires_at_tick=8,
        causal_chain_id="chain:cold:1",
    )


def _resistance() -> ResistanceProfile:
    return ResistanceProfile(
        effect_ref="effect:cold_exposure",
        source_ref="character:ava",
        modifier_basis_points=2_500,
        revision=1,
    )


def _state(*, policy: str = "add", limit: int = 2) -> StateDefinition:
    return StateDefinition(
        state_ref="state:cold",
        stack_policy=policy,
        stack_limit=limit,
        expiry_policy="scheduled",
    )


def test_survival_scheduled_state_application_commits_state_and_open_obligation() -> None:
    store = GameplayEventStore()

    result = SurvivalAuthority(store=store).apply_effect_state(
        command=_command(),
        application=_application(),
        resistance=_resistance(),
        definition=_state(),
    )

    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    projection = SurvivalAuthority(store=store).projector()
    assert projection.states[("character:ava", "state:cold")].stacks == 1
    assert projection.open_obligations["obligation:survival:state:character:ava:state:cold"] == 8


def test_survival_fatigue_owner_row_commits_through_the_existing_state_obligation_spine() -> None:
    store = GameplayEventStore()
    application = _application().model_copy(
        update={"effect_ref": "effect:fatigue_exposure", "stack_key": "fatigue"}
    )
    definition = StateDefinition(
        state_ref="state:fatigued",
        stack_policy="refresh",
        stack_limit=1,
        expiry_policy="scheduled",
        transform_targets=("state:recovering",),
    )

    result = SurvivalAuthority(store=store).apply_effect_state(
        command=_command(key="survival-fatigue:apply:1"),
        application=application,
        resistance=_resistance().model_copy(update={"effect_ref": "effect:fatigue_exposure"}),
        definition=definition,
    )

    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    projection = SurvivalAuthority(store=store).projector()
    assert projection.states[("character:ava", "state:fatigued")].stacks == 1
    assert projection.open_obligations["obligation:survival:state:character:ava:state:fatigued"] == 8


def test_survival_fatigue_owner_row_replays_duplicate_and_rejects_changed_input() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    definition = StateDefinition(
        state_ref="state:fatigued", stack_policy="refresh", stack_limit=1,
        expiry_policy="scheduled", transform_targets=("state:recovering",),
    )
    application = _application().model_copy(update={"effect_ref": "effect:fatigue_exposure", "stack_key": "fatigue"})
    resistance = _resistance().model_copy(update={"effect_ref": "effect:fatigue_exposure"})
    command = _command(key="survival-fatigue:duplicate")

    assert authority.apply_effect_state(command=command, application=application, resistance=resistance, definition=definition).committed
    duplicate = authority.apply_effect_state(command=command, application=application, resistance=resistance, definition=definition)
    changed = authority.apply_effect_state(
        command=command,
        application=application.model_copy(update={"magnitude": 101}),
        resistance=resistance,
        definition=definition,
    )

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed and changed.failure and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 2


def test_survival_fatigue_owner_row_rejects_stale_revision_and_forged_contract_without_write(monkeypatch) -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    definition = StateDefinition(
        state_ref="state:fatigued", stack_policy="refresh", stack_limit=1,
        expiry_policy="scheduled", transform_targets=("state:recovering",),
    )
    application = _application().model_copy(update={"effect_ref": "effect:fatigue_exposure", "stack_key": "fatigue"})
    resistance = _resistance().model_copy(update={"effect_ref": "effect:fatigue_exposure"})
    assert authority.apply_effect_state(
        command=_command(key="survival-fatigue:one"), application=application, resistance=resistance, definition=definition
    ).committed
    stale = authority.apply_effect_state(
        command=_command(expected_revision=0, key="survival-fatigue:stale"), application=application, resistance=resistance, definition=definition
    )
    original = SemanticRegistry.require_closed_state_owner_contract
    monkeypatch.setattr(
        SemanticRegistry,
        "require_closed_state_owner_contract",
        classmethod(lambda cls, *, effect_ref, state_ref: original(effect_ref=effect_ref, state_ref=state_ref).model_copy(update={"projection_scope": "authority_only"})),
    )
    forged = authority.apply_effect_state(
        command=_command(expected_revision=2, key="survival-fatigue:forged"), application=application, resistance=resistance, definition=definition
    )

    assert stale.failure and stale.failure.error_code == "revision_conflict"
    assert forged.failure and forged.failure.error_code == "survival_state_owner_mapping_unregistered"
    assert len(store.read_events()) == 2


def test_survival_fatigue_owner_row_replays_full_and_checkpoint_tail() -> None:
    store = GameplayEventStore()
    checkpoint_events = store.read_events()
    definition = StateDefinition(
        state_ref="state:fatigued", stack_policy="refresh", stack_limit=1,
        expiry_policy="scheduled", transform_targets=("state:recovering",),
    )
    assert SurvivalAuthority(store=store).apply_effect_state(
        command=_command(key="survival-fatigue:replay"),
        application=_application().model_copy(update={"effect_ref": "effect:fatigue_exposure", "stack_key": "fatigue"}),
        resistance=_resistance().model_copy(update={"effect_ref": "effect:fatigue_exposure"}),
        definition=definition,
    ).committed
    replay = GameplayProjectionReplay(projector_id="inf1s-fatigue", projector_version="1")

    full = replay.full_replay(store.read_events())
    tail = replay.checkpoint_plus_tail_replay(replay.create_checkpoint(checkpoint_events), store.read_events())

    assert full.succeeded and tail.succeeded and full.projection_hash == tail.projection_hash


def test_due_survival_state_expiry_is_selected_by_clock_and_settled_by_existing_coordinator() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state())
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=8, expected_revision=2, status="due")
    due = SimulationClock(world_ref="world:demo", catch_up_budget=1).advance(8, (obligation,)).due
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(
            ObligationLifecycleRegistration(
                policy_ref=policy.policy_ref,
                policy_revision=policy.policy_revision,
                owner_ref="actor_gameplay.survival_domain",
                stream_pattern="gameplay:survival:{actor_ref}",
                opened_event_type="gameplay.survival.obligation_opened",
                settled_event_type="gameplay.survival.obligation_settled",
                cancelled_event_type="gameplay.survival.obligation_cancelled",
                visibility_scope="project",
            ),
        ),
    )

    plan = coordinator.plan_settle(
        obligation=due[0],
        fragments=(
            SurvivalAuthority.build_state_expiry_fragment(
                obligation=due[0],
                actor_ref="character:ava",
                state_ref="state:cold",
                expected_revision=2,
            ),
        ),
        principal_ref="world_runtime.caller",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.survival.state_expired",
        "gameplay.survival.obligation_settled",
    ]


def _apply_twice(*, policy: str, limit: int) -> SurvivalAuthority:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state(policy=policy, limit=limit))
    result = authority.apply_effect_state(
        command=_command(expected_revision=2, key=f"survival-state:{policy}:2"),
        application=_application().model_copy(update={"expires_at_tick": 9}),
        resistance=_resistance(),
        definition=_state(policy=policy, limit=limit),
    )
    assert result.committed is True
    return authority


def test_survival_state_add_policy_increments_stacks() -> None:
    assert _apply_twice(policy="add", limit=2).projector().states[("character:ava", "state:cold")].stacks == 2


def test_survival_state_replace_policy_resets_stacks() -> None:
    assert _apply_twice(policy="replace", limit=1).projector().states[("character:ava", "state:cold")].stacks == 1


def test_survival_state_refresh_policy_retains_stacks() -> None:
    assert _apply_twice(policy="refresh", limit=2).projector().states[("character:ava", "state:cold")].stacks == 1


def test_survival_state_reject_policy_is_zero_write_at_limit() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state(policy="reject", limit=1))
    rejected = authority.apply_effect_state(
        command=_command(expected_revision=2, key="survival-state:reject:2"),
        application=_application(),
        resistance=_resistance(),
        definition=_state(policy="reject", limit=1),
    )
    assert rejected.committed is False
    assert rejected.failure is not None and rejected.failure.error_code == "state_stack_limit"
    assert len(store.read_events()) == 2


def test_survival_state_duplicate_revision_and_forged_owner_are_zero_write() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    first = authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state())
    duplicate = authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state())
    stale = authority.apply_effect_state(
        command=_command(expected_revision=0, key="survival-state:stale"),
        application=_application(),
        resistance=_resistance(),
        definition=_state(),
    )
    forged = authority.apply_effect_state(
        command=_command(key="survival-state:forged").model_copy(update={"principal_ref": "client:forged"}),
        application=_application(),
        resistance=_resistance(),
        definition=_state(),
    )
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert forged.failure is not None and forged.failure.error_code == "survival_state_owner_required"
    assert len(store.read_events()) == 2


def test_survival_state_rejects_forged_shared_owner_contract_without_write(monkeypatch) -> None:
    store = GameplayEventStore()
    original = SemanticRegistry.require_closed_state_owner_contract

    def forged(cls, *, effect_ref: str, state_ref: str):
        return original(effect_ref=effect_ref, state_ref=state_ref).model_copy(
            update={"stream_pattern": "gameplay:forged:{actor_ref}"}
        )

    monkeypatch.setattr(SemanticRegistry, "require_closed_state_owner_contract", classmethod(forged))
    result = SurvivalAuthority(store=store).apply_effect_state(
        command=_command(), application=_application(), resistance=_resistance(), definition=_state()
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "survival_state_owner_mapping_unregistered"
    assert store.read_events() == []


def test_survival_state_dispel_cancels_only_committed_open_obligation() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state())
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=8, expected_revision=2, status="open")
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(
            ObligationLifecycleRegistration(
                policy_ref=policy.policy_ref,
                policy_revision=policy.policy_revision,
                owner_ref="actor_gameplay.survival_domain",
                stream_pattern="gameplay:survival:{actor_ref}",
                opened_event_type="gameplay.survival.obligation_opened",
                settled_event_type="gameplay.survival.obligation_settled",
                cancelled_event_type="gameplay.survival.obligation_cancelled",
                visibility_scope="project",
            ),
        ),
    )

    plan = coordinator.plan_cancel(
        obligation=obligation,
        fragment=SurvivalAuthority.build_state_dispel_fragment(
            obligation=obligation,
            actor_ref="character:ava",
            state_ref="state:cold",
            expected_revision=2,
            reason_ref="reason:remedy",
        ),
        principal_ref="world_runtime.caller",
        reason_ref="reason:remedy",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.survival.state_dispelled",
        "gameplay.survival.obligation_cancelled",
    ]
    assert ("character:ava", "state:cold") not in authority.projector().states


def test_survival_state_transform_cancels_prior_expiry_and_rebuilds_from_checkpoint_tail() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state())
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=8, expected_revision=2, status="open")
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(
            ObligationLifecycleRegistration(
                policy_ref=policy.policy_ref,
                policy_revision=policy.policy_revision,
                owner_ref="actor_gameplay.survival_domain",
                stream_pattern="gameplay:survival:{actor_ref}",
                opened_event_type="gameplay.survival.obligation_opened",
                settled_event_type="gameplay.survival.obligation_settled",
                cancelled_event_type="gameplay.survival.obligation_cancelled",
                visibility_scope="project",
            ),
        ),
    )
    replacement = SurvivalState(state_ref="state:recovering", effect_ref="effect:remedy", stacks=1, effective_magnitude=50)
    plan = coordinator.plan_cancel(
        obligation=obligation,
        fragment=SurvivalAuthority.build_state_transform_fragment(
            obligation=obligation,
            actor_ref="character:ava",
            state_ref="state:cold",
            replacement=replacement,
            expected_revision=2,
            reason_ref="reason:remedy",
        ),
        principal_ref="world_runtime.caller",
        reason_ref="reason:remedy",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed is True
    assert authority.projector().states[("character:ava", "state:recovering")] == replacement
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=2).projection_hash
    assert {entry.audience for entry in store.list_outbox()} == {"project"}


def test_survival_state_public_projection_redacts_effect_and_obligation_details() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(command=_command(), application=_application(), resistance=_resistance(), definition=_state())

    public = authority.project_states(scope="public")
    authority_only = authority.project_states(scope="authority")

    assert public == {"character:ava": ({"state_ref": "state:cold", "stacks": 1},)}
    assert authority_only["character:ava"][0]["effect_ref"] == "effect:cold_exposure"
    assert authority_only["character:ava"][0]["expiry_obligation_id"] == "obligation:survival:state:character:ava:state:cold"
