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


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="simulation",
        revision="mode:inf2b:1",
        cadence_class="daily",
        batch_limit=1,
        wake_budget=1,
        catch_up_limit=1,
        allowed_intent_kinds=(),
        degraded_threshold=1,
    )


def _prepare(*, state_ref: str = "state:cold", effect_ref: str = "effect:cold_exposure") -> tuple[GameplayEventStore, ProfileActivationAuthority, ContinuityMergeAuthority, object]:
    store = GameplayEventStore()
    survival = SurvivalAuthority(store=store)
    applied = survival.apply_effect_state(
        command=GameplayCommandEnvelope(
            command_id=f"command:inf2b:{state_ref}",
            command_type="gameplay.survival.apply_state",
            command_version=1,
            principal_ref="actor_gameplay.survival_domain",
            actor_ref="character:char_a",
            idempotency_key=f"inf2b:{state_ref}",
            expected_revisions={"gameplay:survival:character:char_a": 0},
            causation_id=f"cause:inf2b:{state_ref}",
            correlation_id=f"corr:inf2b:{state_ref}",
            source_ref="test",
            submitted_at="2026-08-14T00:00:00Z",
            pinned_revisions={},
            payload={},
        ),
        application=EffectApplication(effect_ref=effect_ref, target_component_ref="character:char_a", magnitude=1, stack_key=state_ref, expires_at_tick=4, causal_chain_id=f"chain:inf2b:{state_ref}"),
        resistance=ResistanceProfile(effect_ref=effect_ref, source_ref="character:char_a", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref=state_ref, stack_policy="refresh" if state_ref == "state:fatigued" else "add", stack_limit=1, expiry_policy="scheduled"),
    )
    assert applied.committed
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:char_a", state_ref=state_ref, due_tick=4, expected_revision=2, status="due")
    activation = ProfileActivationAuthority(registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), store=store)
    assert activation.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0).committed
    pending = PendingChange(
        change_ref="pending:inf2b:expiry",
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
    assert activation.release_lock(lock_ref=pending.lock_ref, expected_revision=2).committed
    merger = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), mode=_mode())
    return store, activation, merger, obligation


def test_released_survival_expiry_pending_settles_only_through_existing_survival_fragment() -> None:
    store, activation, merger, obligation = _prepare()

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2b:expiry",
        obligation=obligation,
    )

    assert result.committed is True
    assert [event.event_type for event in store.read_stream("gameplay:survival:character:char_a")][-2:] == [
        "gameplay.survival.state_expired",
        "gameplay.survival.obligation_settled",
    ]
    assert activation.pending_projection("world:bakery")["pending:inf2b:expiry"]["status"] == "released"


def test_released_fatigue_expiry_pending_settles_through_existing_survival_fragment() -> None:
    store, _, merger, obligation = _prepare(state_ref="state:fatigued", effect_ref="effect:fatigue_exposure")

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation
    )

    assert result.committed
    assert [event.event_type for event in store.read_stream("gameplay:survival:character:char_a")][-2:] == [
        "gameplay.survival.state_expired", "gameplay.survival.obligation_settled"
    ]


def test_released_fatigue_expiry_pending_replays_duplicate_and_rejects_stale_revision() -> None:
    store, _, merger, obligation = _prepare(state_ref="state:fatigued", effect_ref="effect:fatigue_exposure")
    first = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation)
    duplicate = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation)
    stale = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation.model_copy(update={"expected_revisions": {"gameplay:survival:character:char_a": 3}}))

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not stale.committed and stale.error_code == "released_survival_pending_invalid"


def test_released_fatigue_expiry_pending_rejects_nonproject_privacy_and_replays_tail() -> None:
    store, activation, merger, obligation = _prepare(state_ref="state:fatigued", effect_ref="effect:fatigue_exposure")
    private = PendingChange(
        change_ref="pending:inf2b:fatigue-private", lock_ref="lock:world:bakery:character:char_a",
        profile_ref="character:char_a", expected_revision=0,
        payload={"kind": "survival_state_expiry", "obligation_id": obligation.obligation_id, "policy_revision": "1", "expected_survival_revision": 2},
        privacy_scope="actor:self",
    )
    before = len(store.read_events())
    assert activation.record_pending(private).zero_write
    rejected = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref=private.change_ref, obligation=obligation)
    assert not rejected.committed and len(store.read_events()) == before
    assert merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="inf2n-fatigue", projector_version="1")
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(replay.create_checkpoint(events[:3]), events[3:]).projection_hash


def test_released_survival_expiry_pending_replays_duplicate_without_second_write() -> None:
    store, _, merger, obligation = _prepare()
    first = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation)
    before = len(store.read_events())
    duplicate = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation)

    assert first.committed is True
    assert duplicate.committed is True and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before


def test_released_survival_expiry_pending_keeps_activation_and_survival_receipts_separate() -> None:
    store, _, merger, obligation = _prepare()

    result = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2b:expiry",
        obligation=obligation,
    )

    assert result.committed is True
    assert result.receipt is not None
    assert result.receipt.committed_event_ids == result.committed_event_ids
    assert all(
        store.get_event(event_id).stream_id == "gameplay:survival:character:char_a"
        for event_id in result.receipt.committed_event_ids
    )
    assert all(
        event_id not in result.receipt.committed_event_ids
        for event_id in (
            event.event_id
            for event in store.read_stream("population:world:bakery")
        )
    )


def test_released_survival_expiry_pending_rejects_changed_survival_revision_without_writes() -> None:
    store, _, merger, obligation = _prepare()
    before = len(store.read_events())
    changed = obligation.model_copy(update={"expected_revisions": {"gameplay:survival:character:char_a": 3}})

    result = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=changed)

    assert result.committed is False and result.error_code == "released_survival_pending_invalid"
    assert len(store.read_events()) == before


def test_released_survival_expiry_pending_rejects_nonproject_privacy_without_target_write() -> None:
    store, activation, merger, obligation = _prepare()
    pending = PendingChange(
        change_ref="pending:inf2b:private",
        lock_ref="lock:world:bakery:character:char_a",
        profile_ref="character:char_a",
        expected_revision=0,
        payload={"kind": "survival_state_expiry", "obligation_id": obligation.obligation_id, "policy_revision": "1", "expected_survival_revision": 2},
        privacy_scope="actor:self",
    )
    before = len(store.read_events())
    assert activation.record_pending(pending).zero_write is True
    result = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:private", obligation=obligation)

    assert result.committed is False
    assert len(store.read_events()) == before


def test_released_survival_expiry_pending_rejects_terminal_obligation_without_writes() -> None:
    store, _, merger, obligation = _prepare()
    before = len(store.read_events())
    terminal = obligation.model_copy(update={"status": "settled"})

    result = merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=terminal)

    assert result.committed is False and result.error_code == "released_survival_pending_invalid"
    assert len(store.read_events()) == before


def test_released_survival_expiry_pending_checkpoint_tail_replay_matches_full() -> None:
    store, _, merger, obligation = _prepare()
    assert merger.merge_released_survival_state_expiry(world_ref="world:bakery", profile_ref="character:char_a", pending_change_ref="pending:inf2b:expiry", obligation=obligation).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="infra-activation-survival-expiry", projector_version="1")
    checkpoint = replay.create_checkpoint(events[:3])

    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[3:]).projection_hash
