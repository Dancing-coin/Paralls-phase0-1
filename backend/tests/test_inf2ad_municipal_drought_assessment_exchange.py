from __future__ import annotations

from pathlib import Path

import pytest

from app.gameplay.contract_runtime import ContractRuntimeError
from app.gameplay.economy_runtime import EconomyAuthorityService, PackageDeclaredNegotiatedExchangeIntentV1, PartyConsentAttestationV1
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from test_inf3t_municipal_drought_assessment_fulfillment import (
    _create_assessment_contract,
    _request as _fulfillment_request,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-2" / "package-municipal-drought-services-v1.manifest.json"
PROVIDER = "organization:municipal-assessment-office"
RECEIVER = "organization:district-works"
OUTCOME = "outcome:municipal-drought-assessment-settlement@1"
SERVICE = "service:municipal-drought-assessment@1"
EVIDENCE = "evidence:municipal-drought-assessment@1"


def _setup(*, evidence_kind: str = EVIDENCE):
    store, contracts, source_event_id = _create_assessment_contract()
    completed = contracts.fulfill_municipal_drought_assessment_by_policy(
        _fulfillment_request(store, source_event_id)
    )
    manifest = GameplayPatchManifest.model_validate_json(MANIFEST_PATH.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(store=store, package_registry=registry, contract_authority=contracts)
    assert economy.open_account(command_id="account:provider", account_id="account:municipal-assessment", owner_ref=PROVIDER, currency_ref="currency:local", initial_balance=0, idempotency_key="account:provider", causation_id="cause:account", correlation_id="corr:account").committed
    assert economy.open_account(command_id="account:receiver", account_id="account:district-works", owner_ref=RECEIVER, currency_ref="currency:local", initial_balance=20, idempotency_key="account:receiver", causation_id="cause:account", correlation_id="corr:account").committed
    return store, economy, completed


def _intent(*, proposal_digest: str = "proposal:municipal-drought-assessment:1", amount: int | None = None):
    return PackageDeclaredNegotiatedExchangeIntentV1(
        capability_ref="capability:package-declared-negotiated-exchange@1",
        outcome_ref=OUTCOME,
        proposal_digest=proposal_digest,
        provider_consent=PartyConsentAttestationV1(party_ref=PROVIDER, proposal_digest=proposal_digest),
        receiver_consent=PartyConsentAttestationV1(party_ref=RECEIVER, proposal_digest=proposal_digest),
        proposed_amount=amount,
        command_id=f"command:{proposal_digest}",
        idempotency_key=f"package-negotiated-exchange:package:municipal-drought-services:v1:package_declared_negotiated_exchange@1:{proposal_digest}:v1",
        causation_id=f"cause:{proposal_digest}",
        correlation_id=f"corr:{proposal_digest}",
    )


def test_exact_completed_municipal_drought_assessment_settles_once_with_fixed_policy_and_replay() -> None:
    store, economy, completed = _setup()
    assert completed.committed
    result = economy.settle_package_declared_negotiated_exchange(_intent())

    assert result.committed, result.failure
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    assert [event.event_type for event in events] == ["gameplay.economy.account_debited", "gameplay.economy.account_credited", "gameplay.economy.package_declared_negotiated_exchange_settled"]
    settled = events[-1]
    assert settled.visibility_policy == "authority_only"
    assert settled.payload["amount_minor"] == 12
    assert settled.payload["source_evidence_mode"] == "completed_service@1"
    assert settled.payload["package_content_digest"] == "sha256:8ac0cc29e02707f8954953133533b61341fd0d60f0ddf994d7dd3a9a72ed975e"
    assert economy.package_declared_negotiated_exchange_receipt_for(result=result, scope="authority").committed_event_ids == tuple(result.committed_event_ids)
    assert economy.package_declared_negotiated_exchange_projection(scope="authority") == economy.package_declared_negotiated_exchange_projection(scope="authority", checkpoint_at=0)


def test_wrong_service_evidence_and_changed_or_price_mismatched_duplicate_are_zero_write() -> None:
    store, economy, completed = _setup()
    assert completed.committed
    first = economy.settle_package_declared_negotiated_exchange(_intent())
    before = store.export_snapshot()
    wrong_price = economy.settle_package_declared_negotiated_exchange(_intent(proposal_digest="proposal:municipal-drought-assessment:wrong-price", amount=13))
    changed = economy.settle_package_declared_negotiated_exchange(_intent(proposal_digest="proposal:municipal-drought-assessment:1").model_copy(update={"correlation_id": "corr:changed"}))

    assert first.committed
    assert not wrong_price.committed and wrong_price.failure is not None and wrong_price.failure.error_code == "package_exchange_price_invalid"
    assert not changed.committed and changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_multiple_same_currency_provider_accounts_are_zero_write() -> None:
    store, economy, completed = _setup()
    assert completed.committed
    assert economy.open_account(
        command_id="account:provider:duplicate",
        account_id="account:municipal-assessment:duplicate",
        owner_ref=PROVIDER,
        currency_ref="currency:local",
        initial_balance=0,
        idempotency_key="account:provider:duplicate",
        causation_id="cause:account",
        correlation_id="corr:account",
    ).committed
    before = store.export_snapshot()

    result = economy.settle_package_declared_negotiated_exchange(
        _intent(proposal_digest="proposal:municipal-drought-assessment:ambiguous-account")
    )

    assert not result.committed and result.failure is not None
    assert result.failure.error_code == "package_exchange_party_account_unavailable"
    assert store.export_snapshot() == before


def test_contract_owner_rejects_generic_municipal_assessment_evidence_before_exchange() -> None:
    store, contracts, source_event_id = _create_assessment_contract()
    contract_id = str(store.get_event(source_event_id).payload["contract_id"])
    before = store.export_snapshot()

    with pytest.raises(ContractRuntimeError, match="municipal_drought_fulfillment_row_required"):
        contracts.complete_simple_service_by_policy(command_id="wrong-evidence:complete", contract_id=contract_id, authority_ref="authority:municipal-assessment", completion_evidence_kind="evidence:other@1", completion_evidence_ref="evidence:other:1", idempotency_key="wrong-evidence:complete", causation_id=source_event_id, correlation_id="corr:wrong-evidence")

    assert store.export_snapshot() == before
