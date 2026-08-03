from __future__ import annotations

import pytest

from app.gameplay.debt_runtime import DebtAuthorityService
from app.gameplay.economy_privacy_views import EconomyFieldRedactionPolicy, EconomyPrivacyQueryService, EconomyPrivacyViewError
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore


def _setup(*, redaction_policy: EconomyFieldRedactionPolicy | None = None) -> EconomyPrivacyQueryService:
    store = GameplayEventStore()
    economy = EconomyAuthorityService(store=store)
    economy.open_account(command_id="cmd:alice", account_id="account:alice", owner_ref="actor:alice", currency_ref="coin", initial_balance=20, idempotency_key="alice", causation_id="cause", correlation_id="corr")
    economy.open_account(command_id="cmd:bob", account_id="account:bob", owner_ref="actor:bob", currency_ref="coin", initial_balance=0, idempotency_key="bob", causation_id="cause", correlation_id="corr")
    DebtAuthorityService(store=store).issue_simple_debt(command_id="cmd:issue", contract_id="contract:loan", debt_id="debt:loan", creditor_ref="actor:alice", debtor_ref="actor:bob", creditor_account_id="account:alice", debtor_account_id="account:bob", currency_ref="coin", principal_amount=5, idempotency_key="issue", causation_id="cause", correlation_id="corr")
    return EconomyPrivacyQueryService(store=store, authority_principals={"authority:economy"}, redaction_policy=redaction_policy)


def test_account_balance_is_visible_only_to_owner_or_authority() -> None:
    query = _setup()
    assert query.account_balance_view(account_id="account:alice", principal_ref="actor:alice").balance == 15
    assert query.account_balance_view(account_id="account:alice", principal_ref="authority:economy").balance == 15
    with pytest.raises(EconomyPrivacyViewError, match="economy_account_visibility_denied") as error:
        query.account_balance_view(account_id="account:alice", principal_ref="actor:eve")
    assert "15" not in str(error.value)
    assert "actor:alice" not in str(error.value)


def test_debt_is_visible_only_to_parties_or_authority() -> None:
    query = _setup()
    assert query.debt_view(debt_id="debt:loan", principal_ref="actor:alice").outstanding_amount == 5
    assert query.debt_view(debt_id="debt:loan", principal_ref="actor:bob").status == "active"
    assert query.debt_view(debt_id="debt:loan", principal_ref="authority:economy").creditor_ref == "actor:alice"
    with pytest.raises(EconomyPrivacyViewError, match="economy_debt_visibility_denied") as error:
        query.debt_view(debt_id="debt:loan", principal_ref="actor:eve")
    assert "5" not in str(error.value)
    assert "actor:alice" not in str(error.value)


def test_redacted_payloads_apply_audience_field_allowlists_after_visibility_check() -> None:
    query = _setup()

    owner_account = query.account_redacted_payload(account_id="account:alice", principal_ref="actor:alice")
    assert owner_account == {
        "account_id": "account:alice",
        "currency_ref": "coin",
        "balance": 15,
    }
    authority_account = query.account_redacted_payload(account_id="account:alice", principal_ref="authority:economy")
    assert authority_account["owner_ref"] == "actor:alice"

    debtor_debt = query.debt_redacted_payload(debt_id="debt:loan", principal_ref="actor:bob")
    assert debtor_debt == {
        "debt_id": "debt:loan",
        "currency_ref": "coin",
        "outstanding_amount": 5,
        "status": "active",
    }
    authority_debt = query.debt_redacted_payload(debt_id="debt:loan", principal_ref="authority:economy")
    assert authority_debt["contract_id"] == "contract:loan"
    assert authority_debt["creditor_ref"] == "actor:alice"
    assert authority_debt["principal_amount"] == 5

    with pytest.raises(EconomyPrivacyViewError, match="economy_debt_visibility_denied") as error:
        query.debt_redacted_payload(debt_id="debt:loan", principal_ref="actor:eve")
    assert "contract:loan" not in str(error.value)
    assert "actor:alice" not in str(error.value)


def test_redaction_policy_is_configurable_and_rejects_unknown_fields() -> None:
    policy = EconomyFieldRedactionPolicy(
        account_owner_fields=frozenset({"account_id"}),
        account_authority_fields=frozenset({"account_id", "balance"}),
        debt_party_fields=frozenset({"debt_id", "status"}),
        debt_authority_fields=frozenset({"debt_id", "principal_amount"}),
    )
    query = _setup(redaction_policy=policy)
    assert query.account_redacted_payload(account_id="account:alice", principal_ref="actor:alice") == {"account_id": "account:alice"}
    assert query.debt_redacted_payload(debt_id="debt:loan", principal_ref="actor:bob") == {"debt_id": "debt:loan", "status": "active"}

    with pytest.raises(EconomyPrivacyViewError, match="economy_redaction_policy_invalid"):
        EconomyFieldRedactionPolicy(
            account_owner_fields=frozenset({"owner_secret"}),
            account_authority_fields=frozenset({"account_id"}),
            debt_party_fields=frozenset({"debt_id"}),
            debt_authority_fields=frozenset({"debt_id"}),
        )
