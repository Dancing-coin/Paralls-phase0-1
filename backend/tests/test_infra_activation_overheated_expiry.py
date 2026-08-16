from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalStateExpiryPolicy
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.batch import ContinuityMergeAuthority
from app.population_continuity.models import PendingChange, WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"
SURVIVAL_STREAM = "gameplay:survival:character:char_a"
ACTIVATION_STREAM = "population:world:bakery"


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="simulation",
        revision="mode:inf2f:1",
        cadence_class="daily",
        batch_limit=1,
        wake_budget=1,
        catch_up_limit=1,
        allowed_intent_kinds=(),
        degraded_threshold=1,
    )


def _prepare(
    *,
    state_ref: str = "state:overheated",
    effect_ref: str = "effect:heat_exposure",
    release_lock: bool = True,
) -> tuple[GameplayEventStore, ProfileActivationAuthority, ContinuityMergeAuthority, object]:
    store = GameplayEventStore()
    survival = SurvivalAuthority(store=store)
    applied = survival.apply_effect_state(
        command=GameplayCommandEnvelope(
            command_id="command:inf2f:overheated",
            command_type="gameplay.survival.apply_state",
            command_version=1,
            principal_ref="actor_gameplay.survival_domain",
            actor_ref="character:char_a",
            idempotency_key="inf2f:overheated",
            expected_revisions={SURVIVAL_STREAM: 0},
            causation_id="cause:inf2f",
            correlation_id="corr:inf2f",
            source_ref="test",
            submitted_at="2026-08-14T00:00:00Z",
            pinned_revisions={},
            payload={},
        ),
        application=EffectApplication(
            effect_ref=effect_ref,
            target_component_ref="character:char_a",
            magnitude=1,
            stack_key="heat",
            expires_at_tick=4,
            causal_chain_id="chain:inf2f",
        ),
        resistance=ResistanceProfile(
            effect_ref=effect_ref,
            source_ref="character:char_a",
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref=state_ref,
            stack_policy="add",
            stack_limit=1,
            expiry_policy="scheduled",
        ),
    )
    assert applied.committed
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(
        actor_ref="character:char_a",
        state_ref=state_ref,
        due_tick=4,
        expected_revision=2,
        status="due",
    )
    activation = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        store=store,
    )
    assert activation.lock(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        expected_revision=0,
    ).committed
    pending = PendingChange(
        change_ref="pending:inf2f:expiry",
        lock_ref="lock:world:bakery:character:char_a",
        profile_ref="character:char_a",
        expected_revision=0,
        payload={
            "kind": "survival_state_expiry",
            "obligation_id": obligation.obligation_id,
            "policy_revision": obligation.policy_revision,
            "expected_survival_revision": 2,
        },
        privacy_scope="project",
    )
    assert activation.record_pending(pending).committed
    if release_lock:
        assert activation.release_lock(
            lock_ref=pending.lock_ref,
            expected_revision=2,
        ).committed
    merger = ContinuityMergeAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        mode=_mode(),
    )
    return store, activation, merger, obligation


def test_released_overheated_pending_settles_through_existing_survival_fragment() -> None:
    store, activation, merger, obligation = _prepare()

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    )

    settlement_batch = next(
        batch
        for batch in store.read_transactions()
        if batch.transaction_id == result.receipt.transaction_id
    )

    assert result.committed
    assert [event.event_type for event in store.read_stream(SURVIVAL_STREAM)][-2:] == [
        "gameplay.survival.state_expired",
        "gameplay.survival.obligation_settled",
    ]
    assert activation.pending_projection("world:bakery")["pending:inf2f:expiry"]["status"] == "released"
    assert tuple(entry.audience for entry in settlement_batch.outbox_entries) == ("project", "project")


def test_released_overheated_pending_replays_exact_duplicate_without_second_target_write() -> None:
    store, _, merger, obligation = _prepare()
    assert merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    ).committed
    before = len(store.read_stream(SURVIVAL_STREAM))

    duplicate = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    )

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_stream(SURVIVAL_STREAM)) == before


def test_released_overheated_pending_rejects_changed_duplicate_without_second_target_write() -> None:
    store, _, merger, obligation = _prepare()
    assert merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    ).committed
    before = len(store.read_stream(SURVIVAL_STREAM))
    changed = obligation.model_copy(update={"due_tick": obligation.due_tick + 1})

    rejected = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=changed,
    )

    assert not rejected.committed and rejected.error_code == "idempotency_key_reused"
    assert len(store.read_stream(SURVIVAL_STREAM)) == before


def test_overheated_pending_rejects_changed_pending_duplicate_without_activation_write() -> None:
    store, activation, _, obligation = _prepare(release_lock=False)
    before = len(store.read_stream(ACTIVATION_STREAM))
    changed = PendingChange(
        change_ref="pending:inf2f:expiry",
        lock_ref="lock:world:bakery:character:char_a",
        profile_ref="character:char_a",
        expected_revision=0,
        payload={
            "kind": "survival_state_expiry",
            "obligation_id": obligation.obligation_id,
            "policy_revision": "1",
            "expected_survival_revision": 3,
        },
        privacy_scope="project",
    )

    receipt = activation.record_pending(changed)

    assert not receipt.committed and receipt.zero_write and receipt.stop_reason == "idempotency_key_reused"
    assert len(store.read_stream(ACTIVATION_STREAM)) == before


def test_released_overheated_pending_rejects_target_revision_conflict_without_target_write() -> None:
    store, _, merger, obligation = _prepare()
    survival = SurvivalAuthority(store=store)
    assert survival.apply_effect_state(
        command=GameplayCommandEnvelope(
            command_id="command:inf2f:revision-shift",
            command_type="gameplay.survival.apply_state",
            command_version=1,
            principal_ref="actor_gameplay.survival_domain",
            actor_ref="character:char_a",
            idempotency_key="inf2f:revision-shift",
            expected_revisions={SURVIVAL_STREAM: 2},
            causation_id="cause:inf2f:revision-shift",
            correlation_id="corr:inf2f:revision-shift",
            source_ref="test",
            submitted_at="2026-08-14T00:00:00Z",
            pinned_revisions={},
            payload={},
        ),
        application=EffectApplication(
            effect_ref="effect:heat_exposure",
            target_component_ref="character:char_a",
            magnitude=1,
            stack_key="heat",
            expires_at_tick=6,
            causal_chain_id="chain:inf2f:revision-shift",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:heat_exposure",
            source_ref="character:char_a",
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:overheated",
            stack_policy="add",
            stack_limit=2,
            expiry_policy="scheduled",
        ),
    ).committed
    before = len(store.read_stream(SURVIVAL_STREAM))

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    )

    assert not result.committed and result.error_code == "released_survival_obligation_invalid"
    assert len(store.read_stream(SURVIVAL_STREAM)) == before


def test_released_overheated_pending_rejects_nonproject_privacy_without_target_write() -> None:
    store, activation, merger, obligation = _prepare()
    pending = PendingChange(
        change_ref="pending:inf2f:private",
        lock_ref="lock:world:bakery:character:char_a",
        profile_ref="character:char_a",
        expected_revision=0,
        payload={
            "kind": "survival_state_expiry",
            "obligation_id": obligation.obligation_id,
            "policy_revision": "1",
            "expected_survival_revision": 2,
        },
        privacy_scope="actor:self",
    )
    before = len(store.read_stream(SURVIVAL_STREAM))

    assert activation.record_pending(pending).zero_write
    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:private",
        obligation=obligation,
    )

    assert not result.committed
    assert len(store.read_stream(SURVIVAL_STREAM)) == before


def test_released_overheated_pending_rejects_unsupported_state_without_target_write() -> None:
    store, _, merger, obligation = _prepare(state_ref="state:unsupported")
    before = len(store.read_stream(SURVIVAL_STREAM))

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    )

    assert not result.committed and result.error_code == "released_survival_obligation_invalid"
    assert len(store.read_stream(SURVIVAL_STREAM)) == before


def test_released_overheated_pending_rejects_terminal_obligation_without_target_write() -> None:
    store, _, merger, obligation = _prepare()
    before = len(store.read_stream(SURVIVAL_STREAM))

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation.model_copy(update={"status": "settled"}),
    )

    assert not result.committed and result.error_code == "released_survival_pending_invalid"
    assert len(store.read_stream(SURVIVAL_STREAM)) == before


def test_released_overheated_pending_full_and_checkpoint_tail_replay_match() -> None:
    store, _, merger, obligation = _prepare()
    assert merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    ).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(
        projector_id="infra-activation-overheated-expiry",
        projector_version="1",
    )
    checkpoint = replay.create_checkpoint(events[:3])

    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(
        checkpoint,
        events[3:],
    ).projection_hash


def test_overheated_release_and_survival_settlement_have_distinct_append_receipts() -> None:
    store, _, merger, obligation = _prepare()

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2f:expiry",
        obligation=obligation,
    )
    activation_batches = [
        batch
        for batch in store.read_transactions()
        if any(event.event_type == "population.activation.released" for event in batch.events)
    ]

    assert result.committed and result.receipt is not None
    assert len(activation_batches) == 1
    assert result.receipt.transaction_id != activation_batches[0].transaction_id
