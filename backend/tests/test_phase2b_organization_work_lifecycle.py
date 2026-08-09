from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import AttendanceEvidence, OrganizationAuthority, RoleAssignment, ShiftOffer, WorkOrder
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch


def test_role_assignment_work_lifecycle_keeps_profile_reference_and_verified_evidence() -> None:
    assignment = RoleAssignment(
        assignment_ref="assignment:baker", organization_ref="org:bakery", character_ref="character:char_b",
        role="baker", permitted_role_ref="baker/production", authorization_revision=1,
    )
    offer = ShiftOffer(shift_ref="shift:1", assignment_ref=assignment.assignment_ref, work_kind="production", operating_window_ref="window:1")
    order = WorkOrder(work_order_ref="work:1", shift_ref=offer.shift_ref, evidence_kind="production-completed")
    evidence = AttendanceEvidence(
        evidence_ref="evidence:1", actor_ref=assignment.character_ref, assignment_ref=assignment.assignment_ref,
        work_order_ref=order.work_order_ref, source_ref="run:1", issuer_principal_ref="actor_gameplay.production_domain",
        evidence_kind="production-completed", observed_at="tick:1", outcome="completed", verification_state="verified", source_digest="sha256:1",
    )
    assert OrganizationAuthority.completed_evidence(evidence) is evidence
    with pytest.raises(ValueError, match="work_evidence_issuer_unauthorized"):
        OrganizationAuthority.completed_evidence(evidence.model_copy(update={"issuer_principal_ref": "actor_gameplay.unknown_domain"}))


def test_multi_stream_settlement_is_atomic_on_stale_revision() -> None:
    store = GameplayEventStore()
    batch = build_multi_stream_atomic_event_batch(
        command_id="work:start:1", principal_ref="actor_gameplay.organization_domain",
        expected_revisions={"gameplay:organization:org:bakery": 0, "gameplay:construction_production:facility:1": 1},
        event_specs={
            "gameplay:organization:org:bakery": [("gameplay.organization.work_started", {"work_order_ref": "work:1"})],
            "gameplay:construction_production:facility:1": [("gameplay.construction_production.work_started", {"run_ref": "run:1"})],
        },
        idempotency_key="work:start:1", causation_id="cause:1", correlation_id="corr:1",
    )
    result = store.append_batch(batch)
    assert result.committed is False
    assert result.failure and result.failure.error_code == "revision_conflict"
    assert store.read_events() == []
