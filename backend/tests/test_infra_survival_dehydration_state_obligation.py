from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import SemanticEffectCommand, SemanticSettlementAuthority
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry, StateLifecyclePolicy, TagAssignment, TagDefinition
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalStateExpiryPolicy
from app.world_runtime.obligations import ObligationLifecycleRegistration, ObligationSettlementCoordinator


def _registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:character", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="character:ava", tag_ref="type:character", source_ref="fixture", revision=1))
    registry.register_state_lifecycle(
        StateLifecyclePolicy(
            state_ref="state:dehydrated", effect_ref="effect:dehydration_exposure", lifecycle="scheduled", revision="1",
            owner_ref="actor_gameplay.survival_domain", stream_pattern="gameplay:survival:{actor_ref}",
            opened_event_type="gameplay.survival.obligation_opened", settled_event_type="gameplay.survival.obligation_settled",
            cancelled_event_type="gameplay.survival.obligation_cancelled", fragment_builder_ref="SurvivalAuthority.build_state_expiry_fragment",
            projection_scope="project",
        )
    )
    return registry


def _submit(
    authority: SemanticSettlementAuthority,
    registry: SemanticRegistry,
    *,
    key: str = "dehydration:one",
    expected_revision: int = 0,
    privacy_scope: str = "project",
    effect_ref: str = "effect:dehydration_exposure",
    magnitude: int = 100,
):
    snapshot = registry.build_snapshot("character:ava", source_revision_vector={"semantic": 1})
    return authority.settle_closed_survival_state(
        SemanticEffectCommand(
            command_id=f"command:{key}", idempotency_key=key, principal_ref="authority:semantic",
            owner_ref="actor_gameplay.survival_domain", stream_id="gameplay:survival:character:ava",
            expected_revision=expected_revision, effect_ref=effect_ref, target_ref="character:ava",
            semantic_snapshot=snapshot, expected_snapshot_digest=snapshot.digest, privacy_scope=privacy_scope,
        ),
        application=EffectApplication(effect_ref=effect_ref, target_component_ref="character:ava", magnitude=magnitude, stack_key="dehydration", expires_at_tick=8, causal_chain_id="chain:dehydration:1"),
        resistance=ResistanceProfile(effect_ref=effect_ref, source_ref="character:ava", modifier_basis_points=2_500, revision=1),
        state=StateDefinition(state_ref="state:dehydrated", stack_policy="add", stack_limit=2, expiry_policy="scheduled"),
    )


def test_dehydration_owner_row_opens_existing_survival_obligation() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = _submit(SemanticSettlementAuthority(store=store, registry=registry), registry)

    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == ["gameplay.survival.state_applied", "gameplay.survival.obligation_opened"]


def test_dehydration_owner_row_replays_duplicate_without_second_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _submit(authority, registry).committed

    duplicate = _submit(authority, registry)

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 2


def test_dehydration_owner_row_rejects_changed_duplicate_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _submit(authority, registry).committed

    changed = _submit(authority, registry, magnitude=101)

    assert not changed.committed and changed.failure and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 2


def test_dehydration_owner_row_rejects_stale_revision_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _submit(authority, registry).committed

    stale = _submit(authority, registry, key="dehydration:stale", expected_revision=0)

    assert not stale.committed and stale.failure and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == 2


def test_dehydration_owner_row_rejects_nonproject_privacy_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()

    rejected = _submit(SemanticSettlementAuthority(store=store, registry=registry), registry, privacy_scope="authority_only")

    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "semantic_survival_privacy_scope_denied"
    assert store.read_events() == []


def test_dehydration_owner_row_rejects_unpaired_effect_without_append() -> None:
    store = GameplayEventStore()
    registry = _registry()

    rejected = _submit(SemanticSettlementAuthority(store=store, registry=registry), registry, effect_ref="effect:heat_exposure")

    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "semantic_survival_owner_mapping_unregistered"
    assert store.read_events() == []


def test_dehydration_expiry_settles_with_checkpoint_tail_replay() -> None:
    store = GameplayEventStore()
    registry = _registry()
    assert _submit(SemanticSettlementAuthority(store=store, registry=registry), registry).committed
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:dehydrated", due_tick=8, expected_revision=2, status="due")
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(
            ObligationLifecycleRegistration(
                policy_ref=policy.policy_ref, policy_revision=policy.policy_revision,
                owner_ref="actor_gameplay.survival_domain", stream_pattern="gameplay:survival:{actor_ref}",
                opened_event_type="gameplay.survival.obligation_opened", settled_event_type="gameplay.survival.obligation_settled",
                cancelled_event_type="gameplay.survival.obligation_cancelled", visibility_scope="project",
            ),
        ),
    )

    plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(SurvivalAuthority.build_state_expiry_fragment(obligation=obligation, actor_ref="character:ava", state_ref="state:dehydrated", expected_revision=2),),
        principal_ref="world_runtime.caller",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = SurvivalAuthority(store=store).commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed and coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=2).projection_hash


def test_dehydration_owner_row_emits_project_scoped_outbox() -> None:
    store = GameplayEventStore()
    registry = _registry()
    assert _submit(SemanticSettlementAuthority(store=store, registry=registry), registry).committed

    assert {entry.audience for entry in store.list_outbox()} == {"project"}
