from __future__ import annotations

import pytest

from app.gameplay.organization_government_runtime import GovernmentAuthority, Inspection, Permit
from app.gameplay.event_store import GameplayEventStore


def test_permit_policy_and_tax_are_typed_decisions() -> None:
    permit = Permit(permit_ref="permit:1", organization_ref="org:1", policy_revision="policy:v1", expires_tick=3)
    GovernmentAuthority.require_permit(permit, tick=3, policy_revision="policy:v1")
    with pytest.raises(ValueError, match="permit_expired"):
        GovernmentAuthority.require_permit(permit, tick=4, policy_revision="policy:v1")
    tax = GovernmentAuthority.assess_tax("period:1", "org:1", revenue=100, rate=0.1, policy_revision="policy:v1")
    assert tax.amount == 10
    assert GovernmentAuthority.inspection_obligation(Inspection(inspection_ref="inspection:1", organization_ref="org:1", tick=1, passed=False, policy_revision="policy:v1"))


def test_settle_permit_tax_and_failed_inspection_append_government_events() -> None:
    store = GameplayEventStore()
    authority = GovernmentAuthority(store=store)
    permit = Permit(permit_ref="permit:1", organization_ref="org:1", policy_revision="policy:v1", expires_tick=3)
    permit_result = authority.settle_permit_activation(
        permit, command_id="command:government:permit:1", idempotency_key="idem:government:permit:1",
        causation_id="cause:government:permit:1", correlation_id="corr:government:1",
    )
    inspection = Inspection(inspection_ref="inspection:1", organization_ref="org:1", tick=1, passed=False, policy_revision="policy:v1")
    inspection_result = authority.settle_inspection(
        inspection, command_id="command:government:inspection:1", idempotency_key="idem:government:inspection:1",
        causation_id="cause:government:inspection:1", correlation_id="corr:government:1",
    )
    tax_result = authority.settle_tax(
        authority.assess_tax("period:1", "org:1", revenue=100, rate=0.1, policy_revision="policy:v1"),
        command_id="command:government:tax:1", idempotency_key="idem:government:tax:1",
        causation_id="cause:government:tax:1", correlation_id="corr:government:1",
    )
    assert permit_result.committed and inspection_result.committed and tax_result.committed
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.government.permit_activated", "gameplay.government.inspection_recorded",
        "gameplay.government.inspection_obligation_created", "gameplay.government.tax_assessed",
    ]
