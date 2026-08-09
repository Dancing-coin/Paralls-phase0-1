"""P1E heterogeneous ownership/contract/debt fixture with fixed terms."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from pydantic import ConfigDict, Field, model_validator

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.debt_runtime import DebtAuthorityService
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector
from app.gameplay.shared_contracts import GameplayCommandEnvelope


class OwnershipContractDebtSample(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    applicant_ref: str = Field(min_length=1)
    collateral_ref: str = Field(min_length=1)
    principal: float = Field(gt=0)
    term_ticks: int = Field(ge=0)
    contract_ref: str = "contract:ownership-debt:1"
    debt_obligation_ref: str = "debt:ownership-debt:1"
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_fixed_terms(self) -> "OwnershipContractDebtSample":
        if self.applicant_ref not in self.existing_character_refs():
            raise ValueError("character_record_required")
        if not self.collateral_ref.startswith("ownership:"):
            raise ValueError("custody_missing")
        if self.term_ticks <= 0:
            raise ValueError("fixed_terms_required")
        return self

    @staticmethod
    def existing_character_refs() -> frozenset[str]:
        profile_dir = Path(__file__).resolve().parents[3] / "assets" / "characters" / "profiles"
        registry = CharacterProfileRegistry.from_directory(profile_dir)
        return frozenset(f"character:{actor_id}" for actor_id in registry.actor_ids())

    @property
    def result_digest(self) -> str:
        return "sha256:" + sha256(json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def settle(self, *, custody_ref: str, permission_scope: str) -> dict[str, object]:
        if permission_scope != self.applicant_ref:
            raise ValueError("permission_denied")
        if custody_ref != self.collateral_ref:
            raise ValueError("custody_missing")
        return {"contract_ref": self.contract_ref, "debt_obligation_ref": self.debt_obligation_ref, "result_digest": self.result_digest}

    def settle_authorities(
        self,
        *,
        store: GameplayEventStore,
        custody_ref: str,
        permission_scope: str,
    ) -> dict[str, object]:
        """Compose existing ownership, account, and debt authorities for P1E.

        The sample verifies its typed input before authority writes, then keeps
        collateral custody, account balances, contract, and debt facts with
        their respective owners.
        """
        settled = self.settle(custody_ref=custody_ref, permission_scope=permission_scope)
        if int(self.principal) != self.principal:
            raise ValueError("principal_precision_invalid")
        principal = int(self.principal)
        creditor_ref = "organization:p1e-creditor"
        currency_ref = "currency:coin"
        creditor_account_id = "account:p1e-creditor"
        debtor_account_id = "account:p1e-applicant"
        account_authority = EconomyAuthorityService(store=store)
        accounts = EconomyProjector().rebuild(store.read_events()).accounts
        if creditor_account_id not in accounts:
            account_authority.open_account(
                command_id="p1e:open-creditor-account",
                account_id=creditor_account_id,
                owner_ref=creditor_ref,
                currency_ref=currency_ref,
                initial_balance=principal,
                idempotency_key="p1e:open-creditor-account",
                causation_id=f"causation:{self.contract_ref}",
                correlation_id=f"correlation:{self.applicant_ref}",
            )
        if debtor_account_id not in accounts:
            account_authority.open_account(
                command_id="p1e:open-debtor-account",
                account_id=debtor_account_id,
                owner_ref=self.applicant_ref,
                currency_ref=currency_ref,
                initial_balance=0,
                idempotency_key="p1e:open-debtor-account",
                causation_id=f"causation:{self.contract_ref}",
                correlation_id=f"correlation:{self.applicant_ref}",
            )
        ownership_authority = OwnershipAuthorityService(store=store)
        rights = OwnershipProjector().rebuild(store.read_events()).rights
        if self.collateral_ref not in rights:
            ownership_authority.grant_initial_title(
                command_id=f"p1e:grant:{self.collateral_ref}",
                asset_ref=f"asset:{self.collateral_ref}",
                holder_ref=self.applicant_ref,
                right_id=self.collateral_ref,
                idempotency_key=f"p1e:grant:{self.collateral_ref}",
                causation_id=f"causation:{self.contract_ref}",
                correlation_id=f"correlation:{self.applicant_ref}",
            )
        right = OwnershipProjector().rebuild(store.read_events()).rights.get(self.collateral_ref)
        if right is None or right.holder_ref != self.applicant_ref:
            raise ValueError("custody_missing")
        receipt = DebtAuthorityService(store=store).issue_simple_debt(
            command_id=f"p1e:issue:{self.contract_ref}",
            contract_id=self.contract_ref,
            debt_id=self.debt_obligation_ref,
            creditor_ref=creditor_ref,
            debtor_ref=self.applicant_ref,
            creditor_account_id=creditor_account_id,
            debtor_account_id=debtor_account_id,
            currency_ref=currency_ref,
            principal_amount=principal,
            idempotency_key=f"p1e:issue:{self.contract_ref}",
            causation_id=f"causation:{self.contract_ref}",
            correlation_id=f"correlation:{self.applicant_ref}",
        )
        return {**settled, "receipt": receipt, "collateral_right_ref": right.right_id}

    def to_command(self, *, custody_ref: str, permission_scope: str) -> GameplayCommandEnvelope:
        """Return the sample's typed settlement input without owning any write path."""
        settled = self.settle(custody_ref=custody_ref, permission_scope=permission_scope)
        stream_ref = f"stream:ownership-contract-debt:{self.applicant_ref}"
        return GameplayCommandEnvelope(
            command_id=f"command:{self.contract_ref}",
            command_type="ownership-contract-debt.settle",
            command_version=1,
            principal_ref=self.applicant_ref,
            actor_ref=self.applicant_ref,
            project_ref="project:p1e",
            transaction_id=f"transaction:{self.contract_ref}",
            idempotency_key=f"idempotency:{self.contract_ref}",
            expected_revisions={stream_ref: 0},
            causation_id=f"causation:{self.contract_ref}",
            correlation_id=f"correlation:{self.applicant_ref}",
            source_ref=self.collateral_ref,
            submitted_at="p1e",
            pinned_revisions={"ownership": self.revision, "contract": self.revision, "debt": self.revision},
            payload={
                "stream_ref": stream_ref,
                "event_type": "gameplay.ownership_contract_debt.settled",
                "contract_ref": settled["contract_ref"],
                "debt_obligation_ref": settled["debt_obligation_ref"],
                "collateral_ref": self.collateral_ref,
                "principal": self.principal,
                "term_ticks": self.term_ticks,
            },
        )


__all__ = ["OwnershipContractDebtSample"]
