from __future__ import annotations

from pathlib import Path


from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.batch import ContinuityMergeAuthority
from app.population_continuity.models import (
    ActivationGrant,
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
    assert first.replay_hash == second.replay_hash
    assert first.committed and first.rejections
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
        and receipt.stop_reason == "privacy_denial"
        and store.read_events() == []
    )


def test_p3d_bakery_district_fixture_uses_existing_profiles_and_replays(
    tmp_path: Path,
) -> None:
    result = BakeryDistrictPopulationFixture.create(profile_dir=PROFILE_DIR).run()
    assert result["replay_equal"]
    assert result["batch"]["committed"]
    assert result["scope_redaction"]["public"]["active_profiles"] == [
        "character:char_a",
        "character:char_b",
        "character:char_c",
    ]
    assert result["restricted_market"]["supplier_quote"] == "fixed-quote"
