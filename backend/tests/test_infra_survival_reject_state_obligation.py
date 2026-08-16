from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority


def _command(*, revision: int, key: str) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}", command_type="gameplay.survival.apply_state", command_version=1,
        principal_ref="actor_gameplay.survival_domain", actor_ref="character:ava", project_ref="project:demo",
        idempotency_key=key, expected_revisions={"gameplay:survival:character:ava": revision},
        causation_id="cause:overload", correlation_id="corr:overload", source_ref="proposal:semantic:overload",
        submitted_at="2026-08-15T00:00:00Z", pinned_revisions={"semantic": 1}, payload={},
    )


def _apply(authority: SurvivalAuthority, *, revision: int, key: str):
    return authority.apply_effect_state(
        command=_command(revision=revision, key=key),
        application=EffectApplication(effect_ref="effect:overload_exposure", target_component_ref="character:ava", magnitude=100, stack_key="overload", expires_at_tick=8, causal_chain_id="chain:overload"),
        resistance=ResistanceProfile(effect_ref="effect:overload_exposure", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:overloaded", stack_policy="reject", stack_limit=1, expiry_policy="scheduled"),
    )


def test_unregistered_survival_reject_state_is_zero_write_before_any_owner_append() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)

    first = _apply(authority, revision=0, key="overload:first")
    before = store.export_snapshot()
    rejected = _apply(authority, revision=2, key="overload:second")

    assert not first.committed and first.failure is not None
    assert first.failure.error_code == "survival_state_owner_mapping_unregistered"
    assert not rejected.committed and rejected.failure is not None
    assert rejected.failure.error_code == "survival_state_owner_mapping_unregistered"
    assert store.export_snapshot() == before
