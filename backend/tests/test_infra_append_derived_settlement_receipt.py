from __future__ import annotations

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.models import AppendBatchResult, GameplayFailure
from app.gameplay.phase4_commerce import CommerceAuthority
from app.gameplay.shared_contracts import SettlementReceipt
from app.world_runtime.obligations import ObligationSettlementCoordinator, ScheduledObligation
import pytest


def _committed_result() -> AppendBatchResult:
    return AppendBatchResult(
        committed=True,
        transaction_id="transaction:receipt:committed",
        command_id="command:receipt:committed",
        committed_event_ids=["event:one", "event:two"],
        resulting_stream_revisions={"gameplay:one": 3, "gameplay:two": 4},
        idempotency_status="new_commit",
    )


def _rejected_result() -> AppendBatchResult:
    return AppendBatchResult(
        committed=False,
        transaction_id="transaction:receipt:rejected",
        command_id="command:receipt:rejected",
        idempotency_status="rejected",
        failure=GameplayFailure(
            error_code="revision_conflict",
            message="revision_conflict",
            failed_stage="event_store",
        ),
    )


def test_settlement_receipt_is_derived_from_one_committed_append_result() -> None:
    result = _committed_result()

    receipt = SettlementReceipt.from_append_result(
        result=result,
        audit_refs=("audit:receipt",),
        pinned_revisions={"policy": 1},
        projection_digests={"projection:one": "sha256:one"},
    )

    assert receipt.transaction_id == result.transaction_id
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert receipt.stream_revisions == result.resulting_stream_revisions
    assert receipt.idempotency_status == "new_commit"
    assert receipt.zero_write is False
    assert receipt.error_code is None


def test_settlement_receipt_preserves_rejected_append_zero_write() -> None:
    result = _rejected_result()

    receipt = SettlementReceipt.from_append_result(result=result)

    assert receipt.transaction_id == result.transaction_id
    assert receipt.committed_event_ids == ()
    assert receipt.stream_revisions == {}
    assert receipt.idempotency_status == "rejected"
    assert receipt.zero_write is True
    assert receipt.error_code == "revision_conflict"


def test_economy_account_receipt_delegates_to_append_derived_factory() -> None:
    receipt = EconomyAuthorityService.account_settlement_receipt_for(
        result=_committed_result(), privacy_scope="authority"
    )

    assert receipt.audit_refs == ("economy_transaction:transaction:receipt:committed",)
    assert receipt.committed_event_ids == ("event:one", "event:two")


def test_economy_account_receipt_rejects_non_authority_scope() -> None:
    with pytest.raises(Exception, match="economy_account_receipt_scope_denied"):
        EconomyAuthorityService.account_settlement_receipt_for(
            result=_committed_result(), privacy_scope="project"
        )


def test_commerce_receipt_delegates_to_append_derived_factory() -> None:
    receipt = CommerceAuthority.commerce_settlement_receipt_for(
        result=_committed_result(), privacy_scope="authority"
    )

    assert receipt.audit_refs == ("commerce_transaction:transaction:receipt:committed",)
    assert receipt.stream_revisions == {"gameplay:one": 3, "gameplay:two": 4}


def test_commerce_receipt_rejects_non_authority_scope() -> None:
    with pytest.raises(ValueError, match="commerce_settlement_receipt_scope_denied"):
        CommerceAuthority.commerce_settlement_receipt_for(
            result=_committed_result(), privacy_scope="project"
        )


def test_obligation_receipt_delegates_to_append_derived_factory() -> None:
    obligation = ScheduledObligation(
        obligation_id="obligation:receipt",
        due_tick=3,
        owner_ref="actor_gameplay.survival_domain",
        expected_revisions={"gameplay:survival:character:ava": 2},
        idempotency_key="receipt:obligation",
        policy_revision="1",
        status="open",
    )

    receipt = ObligationSettlementCoordinator._receipt(_committed_result(), obligation)

    assert receipt.audit_refs == ("obligation:obligation:receipt",)
    assert receipt.pinned_revisions == {"policy": 1}
