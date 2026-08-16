from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractError, GovernedAuthorityContractCatalog
from app.gameplay.organization_government_runtime import (
    GovernmentAuthority,
    GovernmentCommercialInspectionPolicy,
)


ORGANIZATION = "organization:policy-registration"
STREAM = f"gameplay:government:{ORGANIZATION}"


def _policy(*, revision: str = "1") -> GovernmentCommercialInspectionPolicy:
    return GovernmentCommercialInspectionPolicy(
        policy_ref="policy:commercial-inspection-window@1",
        policy_revision=revision,
        organization_ref=ORGANIZATION,
        jurisdiction_ref="jurisdiction:policy-registration",
        inspection_window_ticks=8,
    )


def _snapshot(store: GameplayEventStore) -> dict[str, object]:
    exported = store.export_snapshot()
    return {key: exported[key] for key in ("events", "outbox", "idempotency")}


def _register(authority: GovernmentAuthority, *, key: str = "policy:register", revision: int = 0):
    return authority.register_commercial_inspection_policy(
        policy=_policy(),
        command_id=f"command:{key}",
        idempotency_key=key,
        causation_id="cause:policy-registration",
        correlation_id="corr:policy-registration",
        expected_revision=revision,
        privacy_scope="project",
    )


def test_government_registers_a_fixed_policy_on_its_existing_stream_through_one_append_batch() -> None:
    store = GameplayEventStore()

    result = _register(GovernmentAuthority(store=store))

    assert result.committed
    assert result.resulting_stream_revisions == {STREAM: 1}
    assert [event.event_type for event in store.read_stream(STREAM)] == [
        "gameplay.government.commercial_inspection_policy_registered"
    ]
    assert GovernmentAuthority(store=store).commercial_inspection_policy_view_for(
        organization_ref=ORGANIZATION,
        scope="project",
    ).active_policy_refs == ("policy:commercial-inspection-window@1",)


def test_government_policy_registration_replays_an_exact_duplicate_without_writing() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    first = _register(authority)
    before = _snapshot(store)

    replayed = _register(authority)

    assert first.committed and replayed.committed
    assert replayed.idempotency_status == "duplicate_replayed"
    assert _snapshot(store) == before


def test_government_policy_registration_rejects_changed_duplicate_without_writing() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    assert _register(authority).committed
    before = _snapshot(store)

    rejected = authority.register_commercial_inspection_policy(
        policy=_policy(revision="2"),
        command_id="command:policy:register",
        idempotency_key="policy:register",
        causation_id="cause:policy-registration",
        correlation_id="corr:policy-registration",
        expected_revision=1,
        privacy_scope="project",
    )

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "idempotency_key_reused"
    assert _snapshot(store) == before


def test_government_policy_registration_rejects_stale_revision_without_writing() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    before = _snapshot(store)

    stale = _register(authority, key="policy:stale", revision=1)
    assert not stale.committed and stale.failure is not None
    assert stale.failure.error_code == "revision_conflict"
    assert _snapshot(store) == before


def test_government_policy_registration_rejects_nonproject_scope_without_writing() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    before = _snapshot(store)

    private = authority.register_commercial_inspection_policy(
        policy=_policy(), command_id="command:policy:private", idempotency_key="policy:private",
        causation_id="cause:policy-registration", correlation_id="corr:policy-registration",
        expected_revision=0, privacy_scope="authority_only",
    )

    assert not private.committed and private.failure is not None
    assert private.failure.error_code == "government_policy_privacy_denied"
    assert _snapshot(store) == before


def test_government_policy_registration_rejects_catalog_admission_failure_before_append(monkeypatch) -> None:
    store = GameplayEventStore()
    before = _snapshot(store)

    def reject_catalog(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_stream_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_catalog)
    rejected = _register(GovernmentAuthority(store=store), key="policy:catalog-rejected")

    assert not rejected.committed and rejected.failure is not None
    assert rejected.failure.error_code == "governed_authority_contract_stream_mismatch"
    assert _snapshot(store) == before


def test_government_policy_registration_rejects_unknown_policy_kind_before_authority_write() -> None:
    store = GameplayEventStore()
    before = _snapshot(store)

    with pytest.raises(ValidationError):
        GovernmentCommercialInspectionPolicy(**(_policy().model_dump() | {"policy_kind": "policy:other@1"}))

    assert _snapshot(store) == before


def test_government_revokes_the_fixed_policy_on_its_existing_stream_through_one_append_batch() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    assert _register(authority).committed

    result = authority.revoke_commercial_inspection_policy(
        organization_ref=ORGANIZATION,
        policy_ref="policy:commercial-inspection-window@1",
        policy_revision="1",
        command_id="command:policy:revoke",
        idempotency_key="policy:revoke",
        causation_id="cause:policy-revocation",
        correlation_id="corr:policy-revocation",
        expected_revision=1,
        privacy_scope="project",
    )

    assert result.committed
    assert result.resulting_stream_revisions == {STREAM: 2}
    assert [event.event_type for event in store.read_stream(STREAM)] == [
        "gameplay.government.commercial_inspection_policy_registered",
        "gameplay.government.commercial_inspection_policy_revoked",
    ]
    assert authority.commercial_inspection_policy_view_for(
        organization_ref=ORGANIZATION,
        scope="project",
    ).active_policy_refs == ()


def test_government_policy_registration_replays_full_and_checkpoint_tail_view() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    assert _register(authority).committed
    assert authority.revoke_commercial_inspection_policy(
        organization_ref=ORGANIZATION,
        policy_ref="policy:commercial-inspection-window@1",
        policy_revision="1",
        command_id="command:policy:revoke",
        idempotency_key="policy:revoke",
        causation_id="cause:policy-revocation",
        correlation_id="corr:policy-revocation",
        expected_revision=1,
        privacy_scope="project",
    ).committed

    full = authority.commercial_inspection_policy_view_for(organization_ref=ORGANIZATION, scope="project")
    tail = authority.commercial_inspection_policy_view_for(
        organization_ref=ORGANIZATION, scope="project", checkpoint_at=1
    )

    assert full.active_policy_refs == ()
    assert full.projection_hash == tail.projection_hash
