from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalStateExpiryPolicy
from app.population_continuity import activation
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import PendingChange


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _activation() -> tuple[GameplayEventStore, ProfileActivationAuthority]:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), store=store
    )
    assert authority.lock(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        expected_revision=0,
    ).committed
    return store, authority


def _schedule_pending(*, binding_ref: str | None = None) -> PendingChange:
    payload: dict[str, object] = {
        "kind": "schedule_gated_supply",
        "plan_digest": "sha256:activation-obligation-binding-contract",
    }
    if binding_ref is not None:
        payload["binding_ref"] = binding_ref
    return PendingChange(
        change_ref="pending:inf2g:schedule",
        lock_ref="lock:world:bakery:character:char_a",
        profile_ref="character:char_a",
        expected_revision=0,
        payload=payload,
        privacy_scope="actor:self",
    )


def test_activation_obligation_binding_contract_has_exact_four_existing_owner_rows() -> None:
    contract = getattr(activation, "ActivationObligationBindingContract", None)
    assert contract is not None
    rows = contract.closed_rows()

    assert [
        (row.binding_ref, row.pending_kind, row.target_owner_ref, row.privacy_scope)
        for row in rows
    ] == [
        (
            "activation-binding:survival-state-expiry:cold:v1",
            "survival_state_expiry",
            "actor_gameplay.survival_domain",
            "project",
        ),
        (
            "activation-binding:survival-state-expiry:dehydrated:v1",
            "survival_state_expiry",
            "actor_gameplay.survival_domain",
            "project",
        ),
        (
            "activation-binding:survival-state-expiry:overheated:v1",
            "survival_state_expiry",
            "actor_gameplay.survival_domain",
            "project",
        ),
        (
            "activation-binding:survival-state-expiry:fatigued:v1",
            "survival_state_expiry",
            "actor_gameplay.survival_domain",
            "project",
        ),
        (
            "activation-binding:schedule-gated-supply:v1",
            "schedule_gated_supply",
            "actor_gameplay.organization_domain",
            "plan_report_scope",
        ),
    ]


def test_unknown_pending_kind_has_no_activation_obligation_binding() -> None:
    contract = getattr(activation, "ActivationObligationBindingContract", None)
    assert contract is not None
    unknown = _schedule_pending().model_copy(
        update={"payload": {"kind": "unregistered_pending", "plan_digest": "sha256:x"}}
    )

    assert contract.resolve(unknown) is None


def test_pending_event_persists_contract_derived_binding_ref() -> None:
    store, authority = _activation()

    receipt = authority.record_pending(_schedule_pending())

    assert receipt.committed
    event = store.read_stream("population:world:bakery")[-1]
    assert event.event_type == "population.activation.pending_recorded"
    assert event.payload["binding_ref"] == "activation-binding:schedule-gated-supply:v1"
    assert authority.pending_projection("world:bakery")["pending:inf2g:schedule"]["binding_ref"] == event.payload["binding_ref"]


def test_forged_pending_binding_ref_is_zero_write() -> None:
    store, authority = _activation()
    before = len(store.read_stream("population:world:bakery"))

    receipt = authority.record_pending(
        _schedule_pending(
            binding_ref="activation-binding:survival-state-expiry:cold:v1"
        )
    )

    assert not receipt.committed
    assert receipt.zero_write
    assert receipt.stop_reason == "pending_binding_forged"
    assert len(store.read_stream("population:world:bakery")) == before


def test_released_unbound_historical_pending_cannot_replay_existing_survival_settlement() -> None:
    store, activation = _activation()
    survival_stream = "gameplay:survival:character:char_a"
    applied = SurvivalAuthority(store=store).apply_effect_state(
        command=GameplayCommandEnvelope(
            command_id="command:inf2g:cold",
            command_type="gameplay.survival.apply_state",
            command_version=1,
            principal_ref="actor_gameplay.survival_domain",
            actor_ref="character:char_a",
            idempotency_key="inf2g:cold",
            expected_revisions={survival_stream: 0},
            causation_id="cause:inf2g:cold",
            correlation_id="corr:inf2g:cold",
            source_ref="test",
            submitted_at="2026-08-14T00:00:00Z",
            pinned_revisions={},
            payload={},
        ),
        application=EffectApplication(
            effect_ref="effect:cold_exposure",
            target_component_ref="character:char_a",
            magnitude=1,
            stack_key="cold",
            expires_at_tick=4,
            causal_chain_id="chain:inf2g:cold",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:cold_exposure",
            source_ref="character:char_a",
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:cold",
            stack_policy="add",
            stack_limit=1,
            expiry_policy="scheduled",
        ),
    )
    assert applied.committed
    obligation = SurvivalStateExpiryPolicy().build_obligation(
        actor_ref="character:char_a",
        state_ref="state:cold",
        due_tick=4,
        expected_revision=2,
        status="due",
    )
    valid = PendingChange(
        change_ref="pending:inf2g:valid",
        lock_ref="lock:world:bakery:character:char_a",
        profile_ref="character:char_a",
        expected_revision=0,
        payload={
            "kind": "survival_state_expiry",
            "obligation_id": obligation.obligation_id,
            "policy_revision": "1",
            "expected_survival_revision": 2,
        },
        privacy_scope="project",
    )
    assert activation.record_pending(valid).committed
    assert activation.release_lock(lock_ref=valid.lock_ref, expected_revision=2).committed

    from app.population_continuity.batch import ContinuityMergeAuthority
    from app.population_continuity.models import WorldModeProfile

    merger = ContinuityMergeAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        mode=WorldModeProfile(
            world_ref="world:bakery",
            mode="simulation",
            revision="mode:inf2g:1",
            cadence_class="daily",
            batch_limit=1,
            wake_budget=1,
            catch_up_limit=1,
            allowed_intent_kinds=(),
            degraded_threshold=1,
        ),
    )
    assert merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref="pending:inf2g:valid",
        obligation=obligation,
    ).committed

    activation_stream = "population:world:bakery"
    historical_ref = "pending:inf2g:unbound"
    pending_payload = {
        "profile_ref": "character:char_a",
        "identity_digest": CharacterProfileRegistry.from_directory(PROFILE_DIR).authored_identity_digest("character:char_a"),
        "world_ref": "world:bakery",
        "lock_ref": valid.lock_ref,
        "change_ref": historical_ref,
        "kind": "survival_state_expiry",
        "plan_digest": None,
        "privacy_scope": "project",
        "obligation_id": obligation.obligation_id,
        "policy_revision": "1",
        "expected_survival_revision": 2,
        "binding_ref": "",
    }
    assert store.append_batch(build_atomic_event_batch(
        command_id="historical:inf2g:unbound-pending",
        principal_ref="world_runtime.activation_authority",
        stream_id=activation_stream,
        expected_revision=store.get_stream_head(activation_stream),
        event_specs=[("population.activation.pending_recorded", pending_payload)],
        idempotency_key="historical:inf2g:unbound-pending",
        causation_id=valid.lock_ref,
        correlation_id="corr:inf2g:historical",
    )).committed
    assert store.append_batch(build_atomic_event_batch(
        command_id="historical:inf2g:unbound-release",
        principal_ref="world_runtime.activation_authority",
        stream_id=activation_stream,
        expected_revision=store.get_stream_head(activation_stream),
        event_specs=[("population.activation.released", {
            "profile_ref": "character:char_a",
            "identity_digest": pending_payload["identity_digest"],
            "lock_ref": valid.lock_ref,
            "pending_change_refs": [historical_ref],
        })],
        idempotency_key="historical:inf2g:unbound-release",
        causation_id=valid.lock_ref,
        correlation_id="corr:inf2g:historical",
    )).committed
    before = len(store.read_stream(survival_stream))

    rejected = merger.merge_released_survival_state_expiry(
        world_ref="world:bakery",
        profile_ref="character:char_a",
        pending_change_ref=historical_ref,
        obligation=obligation,
    )

    assert not rejected.committed
    assert rejected.error_code == "released_survival_obligation_invalid"
    assert len(store.read_stream(survival_stream)) == before
