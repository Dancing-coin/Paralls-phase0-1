from __future__ import annotations

from pathlib import Path


from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.batch import ContinuityMergeAuthority
from app.population_continuity.models import (
    ActivationGrant,
    PendingChange,
    BatchIntentCandidate,
    PopulationBatchPlan,
    WorldModeProfile,
)
from app.population_continuity.world import WorldContinuityRuntime
from app.population_continuity.vertical import BakeryDistrictPopulationFixture
from app.world_runtime.scheduling import RuntimePopulationPolicy, RuntimeWakeUpCandidate


PROFILE_DIR = (
    Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"
)


def registry() -> CharacterProfileRegistry:
    return CharacterProfileRegistry.from_directory(PROFILE_DIR)


def proposal(**overrides: object):
    values = {
        "proposal_id": "proposal:1",
        "profile_ref": "character:char_a",
        "world_ref": "world:bakery",
        "package_revision": "package:bakery-authored-agents:v1",
        "policy_revision": "policy:population:v1",
        "activation_reason": "bakery-district",
        "scope_grant": ("actor:self", "organization:summary"),
        "cadence_class": "simulation",
        "expected_revisions": {"population:world:bakery": 0},
        "idempotency_key": "activation:1",
        "correlation_id": "corr:activation:1",
        "source_ref": "population:planner",
    }
    values.update(overrides)
    from app.population_continuity.models import ActivationProposal

    return ActivationProposal(**values)


def mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="simulation",
        revision="mode:simulation:v1",
        cadence_class="daily",
        batch_limit=3,
        wake_budget=5,
        catch_up_limit=2,
        allowed_intent_kinds=("work", "supply", "inspection"),
        survival_mode="narrative",
        degraded_threshold=2,
    )


def candidate(actor: str, *, claim: str = "slot:bakery:1", key: str | None = None):
    return BatchIntentCandidate(
        intent_ref=f"intent:{actor}:{key or '1'}",
        profile_ref=actor,
        intent_kind="work",
        payload={
            "stream_ref": f"population:{actor}",
            "event_type": "population.intent.proposed",
        },
        priority=1,
        claim_refs=(claim,),
        expected_revisions={f"population:{actor}": 0},
        policy_revision=mode().revision,
        package_revision="package:bakery-authored-agents:v1",
        idempotency_key=key or f"intent:{actor}:1",
        correlation_id="corr:batch:1",
        source_ref="population:planner",
        privacy_scope="actor:self",
    )


def test_p3a_activation_uses_existing_profile_and_zero_writes_denials() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    receipt = authority.commit(proposal())
    assert receipt.committed and receipt.profile_ref == "character:char_a"
    assert receipt.identity_digest.startswith("sha256:")
    assert (
        authority.projection("world:bakery")["character:char_a"]["status"] == "active"
    )
    before = len(store.read_events())
    denied = authority.commit(
        proposal(
            proposal_id="proposal:unknown",
            profile_ref="character:npc:1",
            idempotency_key="activation:unknown",
        )
    )
    assert (
        not denied.committed
        and denied.zero_write
        and len(store.read_events()) == before
    )


def test_p3a_suspend_requeue_and_duplicate_are_replayable() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    authority.commit(proposal())
    suspended = authority.suspend(
        "world:bakery", "character:char_a", expected_revision=1
    )
    assert suspended.committed
    requeued = authority.requeue(
        "world:bakery", "character:char_a", expected_revision=2
    )
    assert requeued.committed
    duplicate = authority.commit(proposal())
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"


def test_activation_lock_records_replayable_schedule_pending_then_releases() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    locked = authority.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0)
    assert locked.committed
    pending = authority.record_pending(
        PendingChange(
            change_ref="pending:1", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=0,
            payload={"kind": "schedule_gated_supply", "plan_digest": "sha256:pending-plan"}, privacy_scope="actor:self",
        )
    )
    assert pending.committed and pending.zero_write is False
    assert authority.pending_projection("world:bakery")["pending:1"]["status"] == "recorded"
    released = authority.release_lock(lock_ref="lock:world:bakery:character:char_a", expected_revision=2)
    assert released.committed
    assert store.read_events()[-1].payload["pending_change_refs"] == ["pending:1"]
    assert authority.pending_projection("world:bakery")["pending:1"]["status"] == "released"


def test_activation_schedule_pending_rejects_free_form_payload_without_writes() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    assert authority.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0).committed
    before = len(store.read_events())
    denied = authority.record_pending(
        PendingChange(
            change_ref="pending:free-form", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=0,
            payload={"kind": "free_form_world_write"}, privacy_scope="actor:self",
        )
    )
    assert denied.zero_write and denied.stop_reason == "pending_change_kind_unsupported"
    assert len(store.read_events()) == before


def test_activation_schedule_pending_duplicate_is_idempotent() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    assert authority.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0).committed
    change = PendingChange(
        change_ref="pending:replay", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=0,
        payload={"kind": "schedule_gated_supply", "plan_digest": "sha256:replay-plan"}, privacy_scope="actor:self",
    )
    first = authority.record_pending(change)
    duplicate = authority.record_pending(change)
    assert first.committed and duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"


def test_activation_schedule_pending_privacy_scope_filters_view() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    assert authority.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0).committed
    assert authority.record_pending(PendingChange(
        change_ref="pending:scope", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=0,
        payload={"kind": "schedule_gated_supply", "plan_digest": "sha256:scope-plan"}, privacy_scope="actor:self",
    )).committed
    assert authority.pending_view_for(world_ref="world:bakery", reader_scope="public") == {}
    assert authority.pending_view_for(world_ref="world:bakery", reader_scope="actor:self")["pending:scope"]["plan_digest"] == "sha256:scope-plan"


def test_activation_schedule_pending_checkpoint_tail_replay_matches_full() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    assert authority.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0).committed
    assert authority.record_pending(PendingChange(
        change_ref="pending:replay", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=0,
        payload={"kind": "schedule_gated_supply", "plan_digest": "sha256:replay-plan"}, privacy_scope="actor:self",
    )).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="population-activation", projector_version="1")
    checkpoint = replay.create_checkpoint(events[:1])
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[1:]).projection_hash


def test_activation_lock_stale_pending_or_release_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    authority.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0)
    pending = authority.record_pending(
        PendingChange(change_ref="pending:stale", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=1, payload={}, privacy_scope="actor:self")
    )
    assert pending.zero_write and pending.stop_reason == "revision_conflict"
    released = authority.release_lock(lock_ref="lock:world:bakery:character:char_a", expected_revision=2)
    assert released.zero_write and released.stop_reason == "revision_conflict"


def test_p3a_requires_an_explicit_matching_package_scope_grant_when_configured() -> (
    None
):
    store = GameplayEventStore()
    grant = ActivationGrant(
        profile_ref="character:char_a",
        world_ref="world:bakery",
        package_revision="package:bakery-authored-agents:v1",
        policy_revision="policy:population:v1",
        scope_grant=("actor:self",),
    )
    authority = ProfileActivationAuthority(
        registry=registry(), store=store, grants=(grant,)
    )
    denied = authority.commit(proposal())
    assert (
        not denied.committed
        and denied.zero_write
        and denied.stop_reason == "package_scope_grant_denied"
    )
    allowed = authority.commit(proposal(scope_grant=("actor:self",)))
    assert allowed.committed


def test_p3b_mode_pause_resume_due_and_catch_up_without_implicit_tick() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry(), store=store)
    authority.commit(proposal())
    runtime = WorldContinuityRuntime(store=store, mode=mode())
    assert runtime.pause(reason="maintenance").committed
    assert runtime.resume().committed
    due = runtime.evaluate_due(
        actor_ref="character:char_a", obligation_refs=("obligation:wage:1",)
    )
    assert (
        due.zero_write
        and due.envelopes[0].command_type == "population.obligation.evaluate"
    )
    full, tail = runtime.replay_equivalence()
    assert full == tail


def test_p3b_budget_degrades_only_selection_through_existing_policy() -> None:
    runtime = WorldContinuityRuntime(
        store=GameplayEventStore(),
        mode=mode().model_copy(update={"wake_budget": 1, "degraded_threshold": 2}),
    )
    policy = RuntimePopulationPolicy(
        max_active_actors_per_tick=3,
        wake_up_batch_size=2,
        degraded_population_threshold=2,
    )
    selected = runtime.select_actors(
        candidates=[
            RuntimeWakeUpCandidate(actor_id="char_b", continuity_priority=2),
            RuntimeWakeUpCandidate(actor_id="char_a", continuity_priority=1),
        ],
        policy=policy,
    )
    assert selected == ("char_b",)


def test_p3c_shuffled_determinism_contention_and_atomic_failure() -> None:
    store_a = GameplayEventStore()
    store_b = GameplayEventStore()
    plan = PopulationBatchPlan(
        batch_ref="batch:1",
        world_ref="world:bakery",
        policy_revision=mode().revision,
        package_revision="package:bakery-authored-agents:v1",
        deterministic_seed="seed:1",
        input_digest="sha256:input",
        budget=3,
        candidates=(candidate("character:char_b"), candidate("character:char_a")),
    )
    first = ContinuityMergeAuthority(
        store=store_a, registry=registry(), mode=mode()
    ).merge(plan)
    shuffled = plan.model_copy(update={"candidates": tuple(reversed(plan.candidates))})
    second = ContinuityMergeAuthority(
        store=store_b, registry=registry(), mode=mode()
    ).merge(shuffled)
    assert first.replay_hash == second.replay_hash == ""
    assert first.zero_write and second.zero_write
    assert first.stop_reason == second.stop_reason == "legacy_population_merge_retired"
    assert store_a.read_events() == store_b.read_events() == []
    stale = plan.model_copy(
        update={
            "candidates": (
                candidate("character:char_a").model_copy(
                    update={"expected_revisions": {"population:character:char_a": 9}}
                ),
            )
        }
    )
    before = len(store_a.read_events())
    failed = ContinuityMergeAuthority(
        store=store_a, registry=registry(), mode=mode()
    ).merge(stale)
    assert (
            not failed.committed
            and failed.zero_write
            and failed.stop_reason == "legacy_population_merge_retired"
            and len(store_a.read_events()) == before
    )


def test_p3b_survival_modes_are_explicit() -> None:
    for survival_mode in ("disabled", "narrative", "simulation"):
        profile = mode().model_copy(update={"survival_mode": survival_mode})
        assert (
            WorldContinuityRuntime(
                store=GameplayEventStore(), mode=profile
            ).mode.survival_mode
            == survival_mode
        )


def test_p3c_privacy_denial_is_atomic_and_zero_write() -> None:
    store = GameplayEventStore()
    invalid = candidate("character:char_a").model_copy(
        update={"privacy_scope": "private:memory"}
    )
    plan = PopulationBatchPlan(
        batch_ref="batch:private",
        world_ref="world:bakery",
        policy_revision=mode().revision,
        package_revision="package:bakery-authored-agents:v1",
        deterministic_seed="seed",
        input_digest="sha256:input",
        budget=1,
        candidates=(invalid,),
    )
    receipt = ContinuityMergeAuthority(
        store=store, registry=registry(), mode=mode()
    ).merge(plan)
    assert (
        not receipt.committed
        and receipt.zero_write
            and receipt.stop_reason == "legacy_population_merge_retired"
        and store.read_events() == []
    )


def test_p3d_bakery_district_fixture_uses_existing_profiles_and_replays(
    tmp_path: Path,
) -> None:
    result = BakeryDistrictPopulationFixture.create(profile_dir=PROFILE_DIR).run()
    assert result["replay_equal"]
    assert result["batch"]["committed"] is True
    assert result["batch"]["owner_receipt_ref"] == "actor_gameplay.organization_domain"
    assert result["batch_duplicate"]["committed"] is True
    assert result["batch_duplicate"]["idempotency_status"] == "duplicate_replayed"
    assert result["revision_conflict"]["zero_write"] is True
    assert result["revision_conflict"]["stop_reason"] == "source_revision_stale"
    assert result["privacy_denial"]["zero_write"] is True
    assert result["privacy_denial"]["stop_reason"] == "schedule_privacy_denied"
    assert result["rejected_input"]["accepted"] is False
    assert result["rejected_input"]["error_code"] == "schedule_work_order_missing"
    assert result["zero_write"] is True
    assert result["scope_redaction"]["public"]["active_profiles"] == [
        "character:char_a",
        "character:char_b",
        "character:char_c",
    ]
    assert result["restricted_market"]["supplier_quote"] == "fixed-quote"
