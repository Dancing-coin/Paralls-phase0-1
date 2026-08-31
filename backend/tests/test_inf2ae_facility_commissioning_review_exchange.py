from __future__ import annotations

from pathlib import Path

from app.gameplay.economy_runtime import EconomyAuthorityService, PackageDeclaredNegotiatedExchangeIntentV1, PartyConsentAttestationV1
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from test_inf2ae_facility_commissioning_review_contract import _contracts, _request as contract_request, _source


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-2" / "package-industrial-facilities-v4-commissioning-review.manifest.json"
SERVICE = "service:industrial-facility-commissioning-review@1"
EVIDENCE = "evidence:industrial-facility-commissioning-review@1"
PROVIDER = "organization:municipal-assessment-office"
RECEIVER = "organization:mill"
OUTCOME = "outcome:industrial-facility-commissioning-review-settlement@1"


def _setup():
    store, construction, source_event_id = _source()
    contracts = _contracts(store)
    created = contracts.create_facility_commissioning_review_from_verification(
        contract_request(store, source_event_id)
    )
    assert created.committed
    created_event = store.get_event(created.committed_event_ids[0])
    fulfillment_type = __import__("app.gameplay.contract_runtime", fromlist=["FacilityCommissioningReviewFulfillmentIntentV1"]).FacilityCommissioningReviewFulfillmentIntentV1
    source = store.get_event(source_event_id)
    head = store.get_stream_head("gameplay:contracts")
    fulfilled = contracts.fulfill_facility_commissioning_review_by_policy(
        fulfillment_type(
            contract_created_event_id=created_event.event_id,
            expected_contract_created_revision=created_event.stream_revision,
            expected_operational_verification_revision=source.stream_revision,
            expected_contract_head=head,
            command_id="command:facility-commissioning-review:fulfill",
            idempotency_key=f"contract:facility-commissioning-review:fulfillment:{created_event.event_id}:{created_event.stream_revision}:{source.stream_revision}:{head}:v1",
            causation_id=created_event.event_id,
            correlation_id="corr:facility-commissioning-review",
            submitted_at="2026-08-27T00:00:00Z",
        )
    )
    assert fulfilled.committed
    manifest = GameplayPatchManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(store=store, package_registry=registry, contract_authority=contracts)
    assert economy.open_account(command_id="account:commissioning:provider", account_id="account:commissioning:provider", owner_ref=PROVIDER, currency_ref="currency:local", initial_balance=0, idempotency_key="account:commissioning:provider", causation_id=source_event_id, correlation_id="corr:accounts").committed
    assert economy.open_account(command_id="account:commissioning:receiver", account_id="account:commissioning:receiver", owner_ref=RECEIVER, currency_ref="currency:local", initial_balance=20, idempotency_key="account:commissioning:receiver", causation_id=source_event_id, correlation_id="corr:accounts").committed
    return store, economy, fulfilled


def _intent(proposal_digest: str = "proposal:facility-commissioning-review:1", amount: int | None = None) -> PackageDeclaredNegotiatedExchangeIntentV1:
    return PackageDeclaredNegotiatedExchangeIntentV1(
        capability_ref="capability:package-declared-negotiated-exchange@1",
        outcome_ref=OUTCOME,
        proposal_digest=proposal_digest,
        provider_consent=PartyConsentAttestationV1(party_ref=PROVIDER, proposal_digest=proposal_digest),
        receiver_consent=PartyConsentAttestationV1(party_ref=RECEIVER, proposal_digest=proposal_digest),
        proposed_amount=amount,
        command_id=f"command:{proposal_digest}",
        idempotency_key=f"package-negotiated-exchange:package:industrial-facilities:v4:package_declared_negotiated_exchange@1:{proposal_digest}:v1",
        causation_id=f"cause:{proposal_digest}",
        correlation_id=f"corr:{proposal_digest}",
    )


def test_facility_commissioning_review_package_settles_once_with_fixed_price_and_replay() -> None:
    store, economy, fulfilled = _setup()
    assert fulfilled.committed

    result = economy.settle_package_declared_negotiated_exchange(_intent())

    assert result.committed, result.failure
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    assert [event.event_type for event in events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.package_declared_negotiated_exchange_settled",
    ]
    assert events[-1].payload["outcome_ref"] == OUTCOME
    assert events[-1].payload["amount_minor"] == 12
    assert events[-1].payload["package_revision_id"] == "package:industrial-facilities:v4"
    assert events[-1].visibility_policy == "authority_only"
    assert economy.package_declared_negotiated_exchange_projection(scope="authority") == economy.package_declared_negotiated_exchange_projection(scope="authority", checkpoint_at=0)


def test_facility_commissioning_review_price_account_ambiguity_and_changed_duplicate_are_zero_write() -> None:
    store, economy, fulfilled = _setup()
    first = economy.settle_package_declared_negotiated_exchange(_intent())
    before = store.export_snapshot()
    changed = economy.settle_package_declared_negotiated_exchange(_intent(proposal_digest="proposal:facility-commissioning-review:1").model_copy(update={"correlation_id": "corr:changed"}))
    bad_price = economy.settle_package_declared_negotiated_exchange(_intent(proposal_digest="proposal:facility-commissioning-review:bad", amount=13))
    assert first.committed
    assert not changed.committed and changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert not bad_price.committed and bad_price.failure is not None and bad_price.failure.error_code == "package_exchange_price_invalid"
    assert store.export_snapshot() == before
