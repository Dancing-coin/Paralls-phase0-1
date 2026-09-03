import pytest

from app.gameplay.economy_financial_platform import (
    CreditFacilityCommand,
    CreditFacilityRecord,
    EconomyFinancialPlatformAuthority,
    EconomyFinancialPlatformError,
    EconomyFinancialPlatformProjector,
    InsurancePolicyCommand,
    InsurancePolicyRecord,
    InsolvencyResolutionCommand,
    InsolvencyResolutionRecord,
    SecurityHoldingCommand,
    SecurityHoldingRecord,
)
from app.gameplay.event_store import GameplayEventStore


def _credit_command(*, command_id: str = "cmd:credit", idempotency_key: str = "idem:credit", expected_revision: int = 0, principal_limit_minor: int = 120) -> CreditFacilityCommand:
    return CreditFacilityCommand(
        command_id=command_id,
        idempotency_key=idempotency_key,
        expected_revision=expected_revision,
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        record=CreditFacilityRecord(
            facility_ref="credit:facility:mill-upgrade",
            lender_ref="organization:lender",
            borrower_ref="organization:borrower",
            currency_ref="currency:local",
            principal_limit_minor=principal_limit_minor,
            collateral_ref="ownership:mill-title",
            policy_revision="policy:credit:mill@1",
        ),
    )


def _insurance_command(*, command_id: str = "cmd:insurance", idempotency_key: str = "idem:insurance", expected_revision: int = 0) -> InsurancePolicyCommand:
    return InsurancePolicyCommand(
        command_id=command_id,
        idempotency_key=idempotency_key,
        expected_revision=expected_revision,
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        record=InsurancePolicyRecord(
            policy_ref="policy:insurance:mill-fire",
            insurer_ref="organization:mutual",
            insured_ref="organization:borrower",
            covered_risk_ref="risk:fire",
            premium_currency_ref="currency:local",
            claim_policy_ref="policy:claim:mill-fire@1",
        ),
    )


def _security_command(*, command_id: str = "cmd:security", idempotency_key: str = "idem:security", expected_revision: int = 0, units: int = 15) -> SecurityHoldingCommand:
    return SecurityHoldingCommand(
        command_id=command_id,
        idempotency_key=idempotency_key,
        expected_revision=expected_revision,
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        record=SecurityHoldingRecord(
            holding_ref="holding:workshop-bond",
            security_ref="security:workshop-bond",
            holder_ref="organization:borrower",
            custody_ref="custody:vault-a",
            units=units,
            denomination_currency_ref="currency:local",
        ),
    )


def _insolvency_command(*, command_id: str = "cmd:insolvency", idempotency_key: str = "idem:insolvency", expected_revision: int = 0) -> InsolvencyResolutionCommand:
    return InsolvencyResolutionCommand(
        command_id=command_id,
        idempotency_key=idempotency_key,
        expected_revision=expected_revision,
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        record=InsolvencyResolutionRecord(
            case_ref="insolvency:borrower:1",
            subject_ref="organization:borrower",
            jurisdiction_ref="jurisdiction:district",
            trigger_ref="trigger:payment-default",
            waterfall_ref="waterfall:district-standard",
            resolution_kind="restructured",
            policy_revision="policy:insolvency:district@1",
        ),
    )


def test_financial_families_append_one_authority_only_event_each_and_replay_from_checkpoint_tail() -> None:
    store = GameplayEventStore()
    authority = EconomyFinancialPlatformAuthority(store=store)

    results = (
        authority.record_credit_facility(_credit_command()),
        authority.record_insurance_policy(_insurance_command()),
        authority.record_security_holding(_security_command()),
        authority.record_insolvency_resolution(_insolvency_command()),
    )

    assert all(result.committed for result in results)
    events = store.read_events()
    assert [event.event_type for event in events] == [
        "gameplay.economy.credit_facility_recorded@1",
        "gameplay.economy.insurance_policy_recorded@1",
        "gameplay.economy.security_holding_recorded@1",
        "gameplay.economy.insolvency_resolution_recorded@1",
    ]
    assert {event.visibility_policy for event in events} == {"authority_only"}

    transactions = store.read_transactions()
    assert len(transactions) == 4
    assert all(transaction.owner_fragments for transaction in transactions)
    assert all(
        tuple(policies) == ("authority_only",)
        for transaction in transactions
        for policies in transaction.owner_fragments[0].event_visibility_policies.values()
    )

    projector = EconomyFinancialPlatformProjector()
    full = projector.rebuild(events)
    checkpoint = projector.rebuild(events[:2])
    tail = projector.rebuild(events[2:], checkpoint=checkpoint)

    assert full == tail
    assert full.source_revision_vector == {
        "gameplay:economy:credit:facility:mill-upgrade": 1,
        "gameplay:economy:holding:workshop-bond": 1,
        "gameplay:economy:insolvency:borrower:1": 1,
        "gameplay:economy:policy:insurance:mill-fire": 1,
    }


def test_credit_facility_duplicate_replay_is_idempotent_and_does_not_write_twice() -> None:
    store = GameplayEventStore()
    authority = EconomyFinancialPlatformAuthority(store=store)
    command = _credit_command()

    first = authority.record_credit_facility(command)
    replay = authority.record_credit_facility(command)

    assert first.committed
    assert replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1


def test_reused_idempotency_key_with_changed_payload_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = EconomyFinancialPlatformAuthority(store=store)

    authority.record_credit_facility(_credit_command())

    with pytest.raises(EconomyFinancialPlatformError, match="economy_financial_idempotency_key_reused"):
        authority.record_credit_facility(
            _credit_command(command_id="cmd:credit:changed", principal_limit_minor=240),
        )

    assert len(store.read_events()) == 1


def test_credit_revision_conflict_rejects_before_append() -> None:
    store = GameplayEventStore()
    authority = EconomyFinancialPlatformAuthority(store=store)

    authority.record_credit_facility(_credit_command())

    with pytest.raises(EconomyFinancialPlatformError, match="economy_financial_revision_conflict"):
        authority.record_credit_facility(
            _credit_command(
                command_id="cmd:credit:stale",
                idempotency_key="idem:credit:stale",
                expected_revision=0,
            )
        )

    assert len(store.read_events()) == 1


def test_security_holding_model_rejects_zero_units_before_write() -> None:
    store = GameplayEventStore()

    with pytest.raises(ValueError):
        _security_command(units=0)

    assert store.read_events() == []
