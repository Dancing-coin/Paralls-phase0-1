from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.ecology_hazard_platform import (
    EcologyHazardIntent,
    EcologyHazardPlatformAuthority,
)
from app.gameplay.event_store import GameplayEventStore


_TOPOLOGY = {
    "region:a": ("region:b",),
    "region:b": ("region:a", "region:c"),
    "region:c": ("region:b",),
}


def _authority() -> tuple[GameplayEventStore, EcologyHazardPlatformAuthority]:
    store = GameplayEventStore()
    return store, EcologyHazardPlatformAuthority(store=store, topology=_TOPOLOGY)


def _intent(
    *,
    hazard_ref: str,
    hazard_kind: str,
    region_ref: str,
    chain_budget: int = 2,
    visibility_scope: str = "project",
) -> EcologyHazardIntent:
    return EcologyHazardIntent(
        hazard_ref=hazard_ref,
        hazard_kind=hazard_kind,
        region_ref=region_ref,
        severity_basis_points=6_000,
        created_tick=3,
        duration_ticks=4,
        policy_revision="policy:ecology-hazard@1",
        chain_budget=chain_budget,
        visibility_scope=visibility_scope,
        causal_parent_refs=("event:weather:seed",),
    )


def _operate(authority: EcologyHazardPlatformAuthority, method: str, *, hazard_ref: str, suffix: str):
    return getattr(authority, method)(
        hazard_ref=hazard_ref,
        command_id=f"command:{suffix}",
        idempotency_key=f"idempotency:{suffix}",
        causation_id=f"cause:{suffix}",
        correlation_id=f"corr:{suffix}",
    )


def _seed_active_hazard(
    authority: EcologyHazardPlatformAuthority,
    *,
    hazard_ref: str,
    hazard_kind: str,
    region_ref: str,
    chain_budget: int = 2,
) -> None:
    proposed = authority.propose_hazard(
        intent=_intent(
            hazard_ref=hazard_ref,
            hazard_kind=hazard_kind,
            region_ref=region_ref,
            chain_budget=chain_budget,
        )
    )
    assert proposed.accepted is True
    assert proposed.proposal is not None
    admitted = authority.admit_hazard(
        proposal=proposed.proposal,
        command_id=f"command:{hazard_ref}:admit",
        idempotency_key=f"idempotency:{hazard_ref}:admit",
        causation_id=f"cause:{hazard_ref}:admit",
        correlation_id=f"corr:{hazard_ref}:admit",
    )
    assert admitted.committed is True
    activated = _operate(
        authority,
        "activate_hazard",
        hazard_ref=hazard_ref,
        suffix=f"{hazard_ref}:activate",
    )
    assert activated.committed is True


def test_closed_hazard_kind_set_has_explicit_recovery_policies() -> None:
    _, authority = _authority()

    assert set(authority.recovery_policies()) == {
        "frost",
        "drought",
        "rain",
        "flood",
        "fire",
        "pollution",
        "disease",
    }
    assert authority.recovery_policy_for("fire").recovery_action == "extinguish"
    assert authority.recovery_policy_for("flood").required_stage == "decay"

    with pytest.raises(ValidationError, match="literal_error"):
        _intent(
            hazard_ref="hazard:invalid",
            hazard_kind="ash",
            region_ref="region:a",
        )


def test_hazard_lifecycle_commits_owner_local_events_and_replays_from_checkpoint_tail() -> None:
    store, authority = _authority()

    proposed = authority.propose_hazard(
        intent=_intent(
            hazard_ref="hazard:fire:1",
            hazard_kind="fire",
            region_ref="region:a",
        )
    )
    assert proposed.accepted is True
    assert proposed.proposal is not None
    assert proposed.proposal.lifecycle_stage == "proposed"
    assert store.read_events() == []

    admitted = authority.admit_hazard(
        proposal=proposed.proposal,
        command_id="command:fire:admit",
        idempotency_key="idempotency:fire:admit",
        causation_id="cause:fire:admit",
        correlation_id="corr:fire:admit",
    )
    activated = _operate(authority, "activate_hazard", hazard_ref="hazard:fire:1", suffix="fire:activate")
    decayed = _operate(authority, "decay_hazard", hazard_ref="hazard:fire:1", suffix="fire:decay")
    recovered = authority.recover_hazard(
        hazard_ref="hazard:fire:1",
        recovery_policy_ref=authority.recovery_policy_for("fire").policy_ref,
        command_id="command:fire:recover",
        idempotency_key="idempotency:fire:recover",
        causation_id="cause:fire:recover",
        correlation_id="corr:fire:recover",
    )
    terminal = _operate(authority, "terminate_hazard", hazard_ref="hazard:fire:1", suffix="fire:terminal")

    assert all(result.committed for result in (admitted, activated, decayed, recovered, terminal))

    events = store.read_stream(authority.hazard_stream_id(region_ref="region:a"))
    assert [event.event_type for event in events] == [
        "gameplay.ecology_hazard.hazard_admitted@1",
        "gameplay.ecology_hazard.hazard_activated@1",
        "gameplay.ecology_hazard.hazard_decayed@1",
        "gameplay.ecology_hazard.hazard_recovered@1",
        "gameplay.ecology_hazard.hazard_terminal@1",
    ]
    assert all(
        batch.owner_fragments[0].owner_principal_ref == authority.principal_ref
        for batch in store.read_transactions()
    )

    projection = authority.project(scope="authority")
    assert projection.hazards["hazard:fire:1"]["lifecycle_stage"] == "terminal"
    assert projection.hazards["hazard:fire:1"]["recovery_policy_ref"] == authority.recovery_policy_for("fire").policy_ref

    full = authority.replay()
    tail = authority.replay(checkpoint_at=2)
    assert full == tail


def test_neighbor_propagation_uses_precompiled_neighbors_and_budget_guards() -> None:
    store, authority = _authority()
    _seed_active_hazard(
        authority,
        hazard_ref="hazard:drought:root",
        hazard_kind="drought",
        region_ref="region:a",
        chain_budget=1,
    )

    proposed = authority.propose_neighbor_propagation(
        hazard_ref="hazard:drought:root",
        propagated_hazard_ref="hazard:drought:child",
        target_region_ref="region:b",
    )
    assert proposed.accepted is True
    assert proposed.proposal is not None
    committed = authority.admit_neighbor_propagation(
        proposal=proposed.proposal,
        command_id="command:drought:propagate",
        idempotency_key="idempotency:drought:propagate",
        causation_id="cause:drought:propagate",
        correlation_id="corr:drought:propagate",
    )
    assert committed.committed is True

    projection = authority.project(scope="authority")
    child = projection.hazards["hazard:drought:child"]
    assert child["region_ref"] == "region:b"
    assert child["hazard_kind"] == "drought"
    assert child["chain_depth"] == 1
    assert child["lineage_hazard_refs"][-1] == "hazard:drought:root"

    before = store.export_snapshot()
    rejected = authority.propose_neighbor_propagation(
        hazard_ref="hazard:drought:child",
        propagated_hazard_ref="hazard:drought:grandchild",
        target_region_ref="region:c",
    )
    assert rejected.accepted is False
    assert rejected.error_code == "ecology_hazard_budget_exhausted"
    assert store.export_snapshot() == before


def test_hazard_conflict_fences_are_zero_write_for_private_missing_policy_cycle_and_stale_cases() -> None:
    store, authority = _authority()

    before_private = store.export_snapshot()
    private = authority.propose_hazard(
        intent=_intent(
            hazard_ref="hazard:rain:private",
            hazard_kind="rain",
            region_ref="region:a",
            visibility_scope="authority_only",
        )
    )
    assert private.accepted is False
    assert private.error_code == "ecology_hazard_private_scope_denied"
    assert store.export_snapshot() == before_private

    missing_before = store.export_snapshot()
    missing = _operate(authority, "activate_hazard", hazard_ref="hazard:missing", suffix="missing:activate")
    assert missing.committed is False
    assert missing.failure is not None
    assert missing.failure.error_code == "ecology_hazard_missing"
    assert store.export_snapshot() == missing_before

    _seed_active_hazard(
        authority,
        hazard_ref="hazard:flood:root",
        hazard_kind="flood",
        region_ref="region:a",
        chain_budget=2,
    )
    _operate(authority, "decay_hazard", hazard_ref="hazard:flood:root", suffix="flood:decay")
    policy_before = store.export_snapshot()
    wrong_policy = authority.recover_hazard(
        hazard_ref="hazard:flood:root",
        recovery_policy_ref="policy:ecology-hazard-recover:wrong@1",
        command_id="command:flood:wrong-policy",
        idempotency_key="idempotency:flood:wrong-policy",
        causation_id="cause:flood:wrong-policy",
        correlation_id="corr:flood:wrong-policy",
    )
    assert wrong_policy.committed is False
    assert wrong_policy.failure is not None
    assert wrong_policy.failure.error_code == "ecology_hazard_recovery_policy_mismatch"
    assert store.export_snapshot() == policy_before

    propagated = authority.propose_neighbor_propagation(
        hazard_ref="hazard:flood:root",
        propagated_hazard_ref="hazard:flood:child",
        target_region_ref="region:b",
    )
    assert propagated.accepted is True
    assert propagated.proposal is not None
    assert authority.admit_neighbor_propagation(
        proposal=propagated.proposal,
        command_id="command:flood:propagate",
        idempotency_key="idempotency:flood:propagate",
        causation_id="cause:flood:propagate",
        correlation_id="corr:flood:propagate",
    ).committed is True
    cycle_before = store.export_snapshot()
    cycle = authority.propose_neighbor_propagation(
        hazard_ref="hazard:flood:child",
        propagated_hazard_ref="hazard:flood:cycle",
        target_region_ref="region:a",
    )
    assert cycle.accepted is False
    assert cycle.error_code == "ecology_hazard_cycle_denied"
    assert store.export_snapshot() == cycle_before

    stale = authority.propose_hazard(
        intent=_intent(
            hazard_ref="hazard:frost:stale",
            hazard_kind="frost",
            region_ref="region:c",
        )
    )
    assert stale.accepted is True
    assert stale.proposal is not None
    current = authority.propose_hazard(
        intent=_intent(
            hazard_ref="hazard:frost:current",
            hazard_kind="frost",
            region_ref="region:c",
        )
    )
    assert current.accepted is True
    assert current.proposal is not None
    assert authority.admit_hazard(
        proposal=current.proposal,
        command_id="command:frost:current",
        idempotency_key="idempotency:frost:current",
        causation_id="cause:frost:current",
        correlation_id="corr:frost:current",
    ).committed is True
    stale_before = store.export_snapshot()
    stale_result = authority.admit_hazard(
        proposal=stale.proposal,
        command_id="command:frost:stale",
        idempotency_key="idempotency:frost:stale",
        causation_id="cause:frost:stale",
        correlation_id="corr:frost:stale",
    )
    assert stale_result.committed is False
    assert stale_result.failure is not None
    assert stale_result.failure.error_code == "ecology_hazard_stale_proposal"
    assert store.export_snapshot() == stale_before
