from __future__ import annotations

from pathlib import Path

import pytest

from app.gameplay.economy_random_registry import EconomyRandomPolicyRegistry, EconomyRandomRegistryError
from app.gameplay.economy_random_policy import SUPPORTED_ALGORITHM_REVISION, SUPPORTED_SEED_POLICY_REVISION
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.random_business_admission import (
    RandomBusinessAdmission,
    RandomBusinessAdmissionError,
    RandomBusinessRequest,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "assets" / "gameplay" / "economy_random"


def test_published_policy_is_consumable_by_declared_economy_owner(tmp_path: Path) -> None:
    registry = EconomyRandomPolicyRegistry.from_directory(POLICY_DIR)
    store = DurableGameplayEventStore(tmp_path / "published-policy.db")
    try:
        owner = EconomyAuthorityService(store=store)
        for ref in registry.policy_refs():
            source = registry.source(ref)
            actor_ref = source.actor_scope[0]
            world_ref = source.world_scope[0]
            timeline_ref = source.timeline_scope[0]
            result = owner.settle_random_business(
                operation_ref=f"published:{ref}", kind=source.kind,
                target_ref=actor_ref, world_ref=world_ref, timeline_ref=timeline_ref,
                source=source, policy=registry.policy(ref), world_tick=1,
                idempotency_key=f"published:{ref}", command_id=f"cmd:published:{ref}",
            )
            assert result.committed, result.failure
    finally:
        store.close()


def test_authored_registry_loads_each_random_business_kind_and_freezes_source() -> None:
    registry = EconomyRandomPolicyRegistry.from_directory(POLICY_DIR)
    assert {registry.policy(ref).kind for ref in registry.policy_refs()} == {
        "lottery", "loot", "event_choice"
    }
    for ref in registry.policy_refs():
        policy = registry.policy(ref)
        source = registry.source(ref)
        assert source.candidate_registry_ref == policy.policy_ref
        assert source.candidate_registry_revision == policy.policy_revision
        assert source.fact_owner_ref == "actor_gameplay.economy_domain"
        assert source.source_digest.startswith("sha256:")
        assert source.read_principals == ("actor_gameplay.economy_domain", "gameplay_scheduler")
        assert source.receipt_lookup_ref == "gameplay.receipts.economy_random"
        assert source.revocation_owner_ref == source.fact_owner_ref


def test_registry_digest_is_stable_and_revalidation_detects_changed_frozen_source() -> None:
    first = EconomyRandomPolicyRegistry.from_directory(POLICY_DIR)
    second = EconomyRandomPolicyRegistry.from_directory(POLICY_DIR)
    ref = "policy:economy_lottery@1"
    source = first.source(ref)
    policy = first.policy(ref)
    assert source == second.source(ref)

    request = RandomBusinessRequest(
        operation_ref="operation:draw-1", effect_ref="effect:lottery",
        target_ref="char_a", draw_index=0, seed="frozen-seed",
        source_digest=source.source_digest,
    )
    admission = RandomBusinessAdmission()
    frozen = admission.admit(
        source, request, actor_ref="char_a", world_ref="world:main",
        timeline_ref="timeline:main", now_world_tick=1,
        caller_principal="actor_gameplay.economy_domain",
    )
    admission.revalidate(frozen, second.source(ref), now_world_tick=1)

    changed = source.model_copy(update={"algorithm_revision": "algorithm:changed"})
    with pytest.raises(RandomBusinessAdmissionError, match="source_changed"):
        admission.revalidate(frozen, changed, now_world_tick=1)
    assert policy.candidate_registry_digest.startswith("sha256:")


def test_registry_rejects_unknown_fields_and_duplicate_candidate_refs(tmp_path: Path) -> None:
    source = (POLICY_DIR / "lottery.yaml").read_text(encoding="utf-8")
    unknown = tmp_path / "unknown.yaml"
    unknown.write_text(source + "unexpected: true\n", encoding="utf-8")
    with pytest.raises(EconomyRandomRegistryError, match="fields_invalid"):
        EconomyRandomPolicyRegistry.from_directory(tmp_path)

    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        source.replace("candidate_ref: lottery:rare", "candidate_ref: lottery:common"),
        encoding="utf-8",
    )
    with pytest.raises(EconomyRandomRegistryError, match="invalid"):
        EconomyRandomPolicyRegistry.from_directory(tmp_path)


@pytest.mark.parametrize("field,value,error", [
    ("algorithm_revision", "algorithm:unsupported-v9", "algorithm_revision_unsupported"),
    ("seed_policy_revision", "seed:operation-world-tick-v1", "seed_policy_revision_unsupported"),
])
def test_registry_rejects_unsupported_random_revision(field: str, value: str, error: str, tmp_path: Path) -> None:
    source = (POLICY_DIR / "lottery.yaml").read_text(encoding="utf-8")
    rejected = tmp_path / "rejected.yaml"
    rejected.write_text(source.replace(
        f"{field}: {SUPPORTED_ALGORITHM_REVISION if field == 'algorithm_revision' else SUPPORTED_SEED_POLICY_REVISION}",
        f"{field}: {value}",
    ), encoding="utf-8")
    with pytest.raises(EconomyRandomRegistryError, match=error):
        EconomyRandomPolicyRegistry.from_directory(tmp_path)


def test_registry_reload_uses_original_directory_and_fails_closed_when_unavailable(tmp_path: Path) -> None:
    registry = EconomyRandomPolicyRegistry.from_directory(POLICY_DIR)
    assert registry.reload().source("policy:economy_lottery@1") == registry.source("policy:economy_lottery@1")
    detached = EconomyRandomPolicyRegistry({})
    with pytest.raises(EconomyRandomRegistryError, match="reload_unavailable"):
        detached.reload()
