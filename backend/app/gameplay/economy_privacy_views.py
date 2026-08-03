"""Principal-filtered backend views over authority-owned economy projections."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping

from app.gameplay.debt_runtime import DebtProjector
from app.gameplay.economy_runtime import EconomyProjector
from app.gameplay.event_store import GameplayEventStore


class EconomyPrivacyViewError(ValueError):
    pass


@dataclass(frozen=True)
class AccountBalanceView:
    account_id: str
    owner_ref: str
    currency_ref: str
    balance: int


@dataclass(frozen=True)
class DebtClaimView:
    debt_id: str
    contract_id: str
    creditor_ref: str
    debtor_ref: str
    currency_ref: str
    principal_amount: int
    outstanding_amount: int
    status: str


@dataclass(frozen=True)
class EconomyFieldRedactionPolicy:
    """Configured backend payload fields for already-authorized audiences."""

    account_owner_fields: frozenset[str] = field(default_factory=lambda: frozenset({"account_id", "currency_ref", "balance"}))
    account_authority_fields: frozenset[str] = field(default_factory=lambda: frozenset({"account_id", "owner_ref", "currency_ref", "balance"}))
    debt_party_fields: frozenset[str] = field(default_factory=lambda: frozenset({"debt_id", "currency_ref", "outstanding_amount", "status"}))
    debt_authority_fields: frozenset[str] = field(default_factory=lambda: frozenset({"debt_id", "contract_id", "creditor_ref", "debtor_ref", "currency_ref", "principal_amount", "outstanding_amount", "status"}))

    def __post_init__(self) -> None:
        _validate_fields(self.account_owner_fields, {"account_id", "owner_ref", "currency_ref", "balance"})
        _validate_fields(self.account_authority_fields, {"account_id", "owner_ref", "currency_ref", "balance"})
        _validate_fields(self.debt_party_fields, {"debt_id", "contract_id", "creditor_ref", "debtor_ref", "currency_ref", "principal_amount", "outstanding_amount", "status"})
        _validate_fields(self.debt_authority_fields, {"debt_id", "contract_id", "creditor_ref", "debtor_ref", "currency_ref", "principal_amount", "outstanding_amount", "status"})


class EconomyPrivacyQueryService:
    """Enforces principal visibility before exposing account or debt projection data."""

    def __init__(self, *, store: GameplayEventStore, authority_principals: Iterable[str], redaction_policy: EconomyFieldRedactionPolicy | None = None) -> None:
        self._store = store
        self._authority_principals = frozenset(value for value in authority_principals if value)
        self._redaction_policy = redaction_policy or EconomyFieldRedactionPolicy()
        self._economy_projector = EconomyProjector()
        self._debt_projector = DebtProjector()

    def account_balance_view(self, *, account_id: str, principal_ref: str) -> AccountBalanceView:
        account = self._economy_projector.rebuild(self._store.read_events()).accounts.get(account_id)
        if account is None:
            raise EconomyPrivacyViewError("economy_account_not_found")
        if not self._can_read(principal_ref, account.owner_ref):
            raise EconomyPrivacyViewError("economy_account_visibility_denied")
        return AccountBalanceView(
            account_id=account.account_id,
            owner_ref=account.owner_ref,
            currency_ref=account.currency_ref,
            balance=account.balance,
        )

    def debt_view(self, *, debt_id: str, principal_ref: str) -> DebtClaimView:
        claim = self._debt_projector.rebuild(self._store.read_events()).claims.get(debt_id)
        if claim is None:
            raise EconomyPrivacyViewError("economy_debt_not_found")
        if principal_ref not in {claim.creditor_ref, claim.debtor_ref} and principal_ref not in self._authority_principals:
            raise EconomyPrivacyViewError("economy_debt_visibility_denied")
        return DebtClaimView(
            debt_id=claim.debt_id,
            contract_id=claim.contract_id,
            creditor_ref=claim.creditor_ref,
            debtor_ref=claim.debtor_ref,
            currency_ref=claim.currency_ref,
            principal_amount=claim.principal_amount,
            outstanding_amount=claim.outstanding_amount,
            status=claim.status,
        )

    def account_redacted_payload(self, *, account_id: str, principal_ref: str) -> Mapping[str, object]:
        view = self.account_balance_view(account_id=account_id, principal_ref=principal_ref)
        fields = self._redaction_policy.account_authority_fields if principal_ref in self._authority_principals else self._redaction_policy.account_owner_fields
        return _redact({"account_id": view.account_id, "owner_ref": view.owner_ref, "currency_ref": view.currency_ref, "balance": view.balance}, fields)

    def debt_redacted_payload(self, *, debt_id: str, principal_ref: str) -> Mapping[str, object]:
        view = self.debt_view(debt_id=debt_id, principal_ref=principal_ref)
        fields = self._redaction_policy.debt_authority_fields if principal_ref in self._authority_principals else self._redaction_policy.debt_party_fields
        return _redact({"debt_id": view.debt_id, "contract_id": view.contract_id, "creditor_ref": view.creditor_ref, "debtor_ref": view.debtor_ref, "currency_ref": view.currency_ref, "principal_amount": view.principal_amount, "outstanding_amount": view.outstanding_amount, "status": view.status}, fields)

    def _can_read(self, principal_ref: str, owner_ref: str) -> bool:
        return bool(principal_ref) and (principal_ref == owner_ref or principal_ref in self._authority_principals)


def _validate_fields(fields: frozenset[str], allowed: set[str]) -> None:
    if not fields or not fields <= allowed:
        raise EconomyPrivacyViewError("economy_redaction_policy_invalid")


def _redact(values: Mapping[str, object], fields: frozenset[str]) -> Mapping[str, object]:
    return MappingProxyType({field: values[field] for field in sorted(fields)})


__all__ = ["AccountBalanceView", "DebtClaimView", "EconomyFieldRedactionPolicy", "EconomyPrivacyQueryService", "EconomyPrivacyViewError"]
