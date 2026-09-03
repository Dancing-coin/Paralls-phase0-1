"""Owner-local Economy financial-family runtime.

This slice adds four exact Economy-owned financial event families through the
existing append spine only. It does not introduce a generic settlement router,
coordinator, or cross-owner writer.
"""

from __future__ import annotations

from typing import Literal, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import (
    AppendBatchResult,
    AtomicEventBatch,
    GameplayEvent,
    OwnerAuthorizedFragment,
    StrictGameplayModel,
)
from app.gameplay.settlement_plan import build_atomic_event_batch


class EconomyFinancialPlatformError(ValueError):
    pass


class _FinancialModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _AuthorityCommand(_FinancialModel):
    command_id: str = Field(min_length=1, strict=True)
    idempotency_key: str = Field(min_length=1, strict=True)
    expected_revision: int = Field(ge=0, strict=True)
    causation_id: str = Field(min_length=1, strict=True)
    correlation_id: str = Field(min_length=1, strict=True)


class CreditFacilityRecord(_FinancialModel):
    facility_ref: str = Field(pattern=r"^credit:", min_length=1, strict=True)
    lender_ref: str = Field(min_length=1, strict=True)
    borrower_ref: str = Field(min_length=1, strict=True)
    currency_ref: str = Field(pattern=r"^currency:", strict=True)
    principal_limit_minor: int = Field(gt=0, strict=True)
    collateral_ref: str = Field(min_length=1, strict=True)
    policy_revision: str = Field(min_length=1, strict=True)

    @model_validator(mode="after")
    def validate_parties(self) -> "CreditFacilityRecord":
        if self.lender_ref == self.borrower_ref:
            raise ValueError("economy_credit_facility_invalid")
        return self


class InsurancePolicyRecord(_FinancialModel):
    policy_ref: str = Field(pattern=r"^policy:", strict=True)
    insurer_ref: str = Field(min_length=1, strict=True)
    insured_ref: str = Field(min_length=1, strict=True)
    covered_risk_ref: str = Field(min_length=1, strict=True)
    premium_currency_ref: str = Field(pattern=r"^currency:", strict=True)
    claim_policy_ref: str = Field(pattern=r"^policy:", strict=True)

    @model_validator(mode="after")
    def validate_parties(self) -> "InsurancePolicyRecord":
        if self.insurer_ref == self.insured_ref:
            raise ValueError("economy_insurance_policy_invalid")
        return self


class SecurityHoldingRecord(_FinancialModel):
    holding_ref: str = Field(pattern=r"^holding:", min_length=1, strict=True)
    security_ref: str = Field(pattern=r"^security:", min_length=1, strict=True)
    holder_ref: str = Field(min_length=1, strict=True)
    custody_ref: str = Field(min_length=1, strict=True)
    units: int = Field(gt=0, strict=True)
    denomination_currency_ref: str = Field(pattern=r"^currency:", strict=True)


class InsolvencyResolutionRecord(_FinancialModel):
    case_ref: str = Field(pattern=r"^insolvency:", min_length=1, strict=True)
    subject_ref: str = Field(min_length=1, strict=True)
    jurisdiction_ref: str = Field(min_length=1, strict=True)
    trigger_ref: str = Field(min_length=1, strict=True)
    waterfall_ref: str = Field(min_length=1, strict=True)
    resolution_kind: Literal["restructured", "liquidated", "discharged"]
    policy_revision: str = Field(min_length=1, strict=True)


class CreditFacilityCommand(_AuthorityCommand):
    record: CreditFacilityRecord


class InsurancePolicyCommand(_AuthorityCommand):
    record: InsurancePolicyRecord


class SecurityHoldingCommand(_AuthorityCommand):
    record: SecurityHoldingRecord


class InsolvencyResolutionCommand(_AuthorityCommand):
    record: InsolvencyResolutionRecord


class EconomyFinancialPlatformProjection(_FinancialModel):
    credit_facilities: dict[str, CreditFacilityRecord] = Field(default_factory=dict)
    insurance_policies: dict[str, InsurancePolicyRecord] = Field(default_factory=dict)
    security_holdings: dict[str, SecurityHoldingRecord] = Field(default_factory=dict)
    insolvency_resolutions: dict[str, InsolvencyResolutionRecord] = Field(default_factory=dict)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)


class EconomyFinancialPlatformProjector:
    _EVENT_TYPES = frozenset(
        {
            "gameplay.economy.credit_facility_recorded@1",
            "gameplay.economy.insurance_policy_recorded@1",
            "gameplay.economy.security_holding_recorded@1",
            "gameplay.economy.insolvency_resolution_recorded@1",
        }
    )

    def rebuild(
        self,
        events: Sequence[GameplayEvent],
        *,
        checkpoint: EconomyFinancialPlatformProjection | None = None,
    ) -> EconomyFinancialPlatformProjection:
        credit_facilities = dict(checkpoint.credit_facilities) if checkpoint else {}
        insurance_policies = dict(checkpoint.insurance_policies) if checkpoint else {}
        security_holdings = dict(checkpoint.security_holdings) if checkpoint else {}
        insolvency_resolutions = dict(checkpoint.insolvency_resolutions) if checkpoint else {}
        source_revision_vector = dict(checkpoint.source_revision_vector) if checkpoint else {}

        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            source_revision_vector[event.stream_id] = max(
                source_revision_vector.get(event.stream_id, 0),
                event.stream_revision,
            )
            if event.visibility_policy != "authority_only":
                raise EconomyFinancialPlatformError("economy_financial_visibility_invalid")
            if event.event_type == "gameplay.economy.credit_facility_recorded@1":
                record = _validate_record(CreditFacilityRecord, event.payload, "economy_credit_facility_replay_invalid")
                if record.facility_ref in credit_facilities:
                    raise EconomyFinancialPlatformError("economy_credit_facility_duplicate")
                credit_facilities[record.facility_ref] = record
            elif event.event_type == "gameplay.economy.insurance_policy_recorded@1":
                record = _validate_record(InsurancePolicyRecord, event.payload, "economy_insurance_policy_replay_invalid")
                if record.policy_ref in insurance_policies:
                    raise EconomyFinancialPlatformError("economy_insurance_policy_duplicate")
                insurance_policies[record.policy_ref] = record
            elif event.event_type == "gameplay.economy.security_holding_recorded@1":
                record = _validate_record(SecurityHoldingRecord, event.payload, "economy_security_holding_replay_invalid")
                if record.holding_ref in security_holdings:
                    raise EconomyFinancialPlatformError("economy_security_holding_duplicate")
                security_holdings[record.holding_ref] = record
            elif event.event_type == "gameplay.economy.insolvency_resolution_recorded@1":
                record = _validate_record(InsolvencyResolutionRecord, event.payload, "economy_insolvency_resolution_replay_invalid")
                if record.case_ref in insolvency_resolutions:
                    raise EconomyFinancialPlatformError("economy_insolvency_resolution_duplicate")
                insolvency_resolutions[record.case_ref] = record

        return EconomyFinancialPlatformProjection(
            credit_facilities=dict(sorted(credit_facilities.items())),
            insurance_policies=dict(sorted(insurance_policies.items())),
            security_holdings=dict(sorted(security_holdings.items())),
            insolvency_resolutions=dict(sorted(insolvency_resolutions.items())),
            source_revision_vector=dict(sorted(source_revision_vector.items())),
        )


class EconomyFinancialPlatformAuthority:
    _PRINCIPAL = "actor_gameplay.economy_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def record_credit_facility(self, command: CreditFacilityCommand) -> AppendBatchResult:
        command = _validate_command(CreditFacilityCommand, command, "economy_credit_facility_invalid")
        return self._commit(
            command=command,
            event_type="gameplay.economy.credit_facility_recorded@1",
            subject_ref=command.record.facility_ref,
            payload=command.record.model_dump(mode="json"),
        )

    def record_insurance_policy(self, command: InsurancePolicyCommand) -> AppendBatchResult:
        command = _validate_command(InsurancePolicyCommand, command, "economy_insurance_policy_invalid")
        return self._commit(
            command=command,
            event_type="gameplay.economy.insurance_policy_recorded@1",
            subject_ref=command.record.policy_ref,
            payload=command.record.model_dump(mode="json"),
        )

    def record_security_holding(self, command: SecurityHoldingCommand) -> AppendBatchResult:
        command = _validate_command(SecurityHoldingCommand, command, "economy_security_holding_invalid")
        return self._commit(
            command=command,
            event_type="gameplay.economy.security_holding_recorded@1",
            subject_ref=command.record.holding_ref,
            payload=command.record.model_dump(mode="json"),
        )

    def record_insolvency_resolution(self, command: InsolvencyResolutionCommand) -> AppendBatchResult:
        command = _validate_command(InsolvencyResolutionCommand, command, "economy_insolvency_resolution_invalid")
        return self._commit(
            command=command,
            event_type="gameplay.economy.insolvency_resolution_recorded@1",
            subject_ref=command.record.case_ref,
            payload=command.record.model_dump(mode="json"),
        )

    def _commit(
        self,
        *,
        command: CreditFacilityCommand | InsurancePolicyCommand | SecurityHoldingCommand | InsolvencyResolutionCommand,
        event_type: str,
        subject_ref: str,
        payload: dict[str, object],
    ) -> AppendBatchResult:
        stream_id = f"gameplay:economy:{subject_ref}"
        batch = build_atomic_event_batch(
            command_id=command.command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=command.expected_revision,
            event_specs=((event_type, payload),),
            idempotency_key=command.idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            read_stream_revisions={stream_id: command.expected_revision},
            pinned_revisions={stream_id: command.expected_revision},
        )
        batch = batch.model_copy(
            update={
                "events": [
                    event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
                    for event in batch.events
                ],
                "owner_fragments": [
                    OwnerAuthorizedFragment(
                        fragment_id=f"fragment:economy-financial:{command.command_id}",
                        owner_principal_ref=self._PRINCIPAL,
                        source_rule_ref="economy-financial-platform:owner-local-financial-family@1",
                        expected_revisions={stream_id: command.expected_revision},
                        read_set_revisions={stream_id: command.expected_revision},
                        pinned_revisions={stream_id: command.expected_revision},
                        event_specs={stream_id: ((event_type, payload),)},
                        event_visibility_policies={stream_id: ("authority_only",)},
                    )
                ],
            },
            deep=True,
        )
        duplicate = self._duplicate_result(batch)
        if duplicate is not None:
            return duplicate
        if self._store.get_stream_head(stream_id) != command.expected_revision:
            raise EconomyFinancialPlatformError("economy_financial_revision_conflict")
        return self._store.append_batch(batch)

    def _duplicate_result(self, batch: AtomicEventBatch) -> AppendBatchResult | None:
        principal_ref = self._PRINCIPAL
        idempotency_record = batch.idempotency_record
        existing = self._store.get_idempotency_record(
            principal_ref,
            idempotency_record.idempotency_key,
        )
        if existing is None:
            return None
        if existing.payload_digest != idempotency_record.payload_digest:
            raise EconomyFinancialPlatformError("economy_financial_idempotency_key_reused")
        result = self._store.get_by_idempotency(principal_ref, idempotency_record.idempotency_key)
        if result is None:
            raise EconomyFinancialPlatformError("economy_financial_idempotency_result_missing")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)


def _validate_record(model: type[_FinancialModel], payload: dict[str, object], error_code: str) -> _FinancialModel:
    try:
        return model.model_validate(payload)
    except Exception as exc:  # pragma: no cover - fail-closed adapter guard
        raise EconomyFinancialPlatformError(error_code) from exc


def _validate_command(model: type[_AuthorityCommand], value: _AuthorityCommand, error_code: str) -> _AuthorityCommand:
    try:
        return model.model_validate(value.model_dump(mode="json"))
    except Exception as exc:  # pragma: no cover - fail-closed adapter guard
        raise EconomyFinancialPlatformError(error_code) from exc


__all__ = [
    "CreditFacilityCommand",
    "CreditFacilityRecord",
    "EconomyFinancialPlatformAuthority",
    "EconomyFinancialPlatformError",
    "EconomyFinancialPlatformProjection",
    "EconomyFinancialPlatformProjector",
    "InsurancePolicyCommand",
    "InsurancePolicyRecord",
    "InsolvencyResolutionCommand",
    "InsolvencyResolutionRecord",
    "SecurityHoldingCommand",
    "SecurityHoldingRecord",
]
