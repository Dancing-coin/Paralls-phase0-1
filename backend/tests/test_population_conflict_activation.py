"""B2 唤醒必须来自真实 Social Owner；唤醒本身不暴露项目事实。"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.organization_government_social_platform_runtime import SocialNormConflictIntent
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from app.gameplay.patch_runtime import GameplayPatchRegistry
from app.population_continuity.activation_policy import ActivationPolicy
from app.population_continuity.conflict_activation import prepare_conflict_activation
from test_organization_government_social_descriptor_binding import _manifest


def fixture(tmp_path):
    packages = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    packages.install(_manifest(family_ref="social_norm_conflict@1"))
    packages.activate(("package:social-conflict:v1",))
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    owner = SocialFactAuthority(registry=SimpleNamespace(registry_ref="registry:test",
        registry_revision="registry:test@1", registry_digest="sha256:" + "f" * 64), store=store, package_registry=packages)
    profiles = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets/characters/profiles")
    return store, owner, packages, profiles


def conflict(owner, state="opened", ordinal=0, subjects=("character:char_a", "character:char_b")):
    result = owner.record_admitted_platform_social_conflict(intent=SocialNormConflictIntent(
        case_ref="case:conflict@1", subject_refs=subjects, conflict_state=state,
        provenance_ref="provenance:conflict@1", source_revision_pin=ordinal),
        binding_ref="binding:social-conflict@1", command_id=f"command:conflict:{ordinal}",
        idempotency_key=f"key:conflict:{ordinal}", causation_id=f"cause:{ordinal}", correlation_id=f"corr:{ordinal}", expected_revision=ordinal)
    assert result.receipt is not None and result.receipt.committed_event_ids
    return result.receipt.committed_event_ids[0]


def prepare(store, packages, profiles, event_id, actor="char_a", budget=4):
    return prepare_conflict_activation(store=store, package_registry=packages, profiles=profiles,
        policy=ActivationPolicy(), source_event_id=event_id, actor_id=actor, budget=budget)


@pytest.mark.parametrize("state", ["opened", "appealed"])
def test_real_conflict_freezes_exact_wake_and_actor_identity_without_truth_payload(tmp_path, state):
    store, owner, packages, profiles = fixture(tmp_path)
    event_id = conflict(owner, state)
    before = store.get_last_global_sequence()
    wake = prepare(store, packages, profiles, event_id)
    assert wake.decision.state == "active" and wake.decision.requires_activation_lock
    assert wake.decision.load_private_memory and wake.decision.reason == "committed_social_conflict"
    assert wake.actor_id == "char_a" and wake.source_event_id == event_id
    assert wake.source_revision_vector == (("gameplay:social:case:case:conflict@1", 1),)
    assert wake.authored_identity_digest == profiles.authored_identity_digest("char_a")
    assert wake.source_kind == "run_background_cognition_tick"
    assert "subject_refs" not in repr(wake) and "conflict_state" not in repr(wake)
    assert store.get_last_global_sequence() == before
    reopened = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    assert prepare(reopened, packages, profiles, event_id) == wake
    assert prepare(store, packages, profiles, event_id, "char_b").candidate_key != wake.candidate_key


@pytest.mark.parametrize("state", ["mediated", "adjudicated", "final"])
def test_non_attention_conflict_state_cannot_wake(tmp_path, state):
    store, owner, packages, profiles = fixture(tmp_path)
    event_id = conflict(owner, state)
    with pytest.raises(ValueError, match="conflict_not_actionable"):
        prepare(store, packages, profiles, event_id)


def test_unknown_uninvolved_budget_and_stale_sources_rejected_before_any_activation(tmp_path):
    store, owner, packages, profiles = fixture(tmp_path)
    event_id = conflict(owner)
    for actor, budget, reason in [("resident_00001", 4, "unsupported_actor"), ("char_c", 4, "actor_not_subject"),
                                   ("char_a", 0, "activation_budget_exhausted")]:
        with pytest.raises(ValueError, match=reason):
            prepare(store, packages, profiles, event_id, actor, budget)
    conflict(owner, "final", 1)
    with pytest.raises(ValueError, match="conflict_source_stale"):
        prepare(store, packages, profiles, event_id)


def test_copied_social_payload_under_other_principal_cannot_authorize_wake(tmp_path):
    from app.gameplay.settlement_plan import build_atomic_event_batch
    store, owner, packages, profiles = fixture(tmp_path)
    original = store.get_event(conflict(owner))
    forged = build_atomic_event_batch(command_id="forged", principal_ref="untrusted", stream_id=original.stream_id,
        expected_revision=1, event_specs=[(original.event_type, original.payload)], idempotency_key="forged",
        causation_id="forged", correlation_id="forged")
    result = store.append_batch(forged)
    assert result.committed
    with pytest.raises(ValueError, match="conflict_owner_proof_invalid"):
        prepare(store, packages, profiles, result.committed_event_ids[0])


def test_revoked_package_cannot_reauthorize_old_wake(tmp_path):
    store, owner, packages, profiles = fixture(tmp_path)
    event_id = conflict(owner)
    other = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    other.install(_manifest())
    other.activate(("package:ogs-millers:v1",))
    with pytest.raises(ValueError, match="conflict_package_stale"):
        prepare(store, other, profiles, event_id)


def test_pending_seed_still_only_prewarms_without_verified_conflict():
    assert ActivationPolicy().evaluate(actor_id="char_a", distance_m=100, focused=False,
        interaction_type="conflict", pending_seed=True, budget=4).state == "prewarm"
