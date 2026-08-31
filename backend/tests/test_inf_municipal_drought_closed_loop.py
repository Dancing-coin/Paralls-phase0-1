from __future__ import annotations

from pathlib import Path

from app.gameplay.contract_runtime import (
    ContractAuthorityService,
    ContractProjector,
    ContractTermsDefinition,
    ContractTermsRegistry,
    GovernmentDroughtAssessmentContractIntentV1,
    MunicipalDroughtAssessmentFulfillmentIntentV1,
)
from app.gameplay.economy_runtime import (
    EconomyAuthorityService,
    PackageDeclaredNegotiatedExchangeIntentV1,
    PartyConsentAttestationV1,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import (
    MunicipalDroughtAssessmentCertificateIntentV1,
    OwnershipAuthorityService,
    OwnershipProjector,
)
from test_inf3u_municipal_certificate_government_acknowledgment import _request as _acknowledgment_request
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from test_infra_weather_front_government_drought_advisory import JURISDICTION, _intent, _setup


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-2" / "package-municipal-drought-services-v1.manifest.json"
TERMS = "service:municipal-drought-assessment@1"
EVIDENCE = "evidence:municipal-drought-assessment@1"
PROVIDER = "organization:municipal-assessment-office"
RECEIVER = "organization:district-works"
OUTCOME = "outcome:municipal-drought-assessment-settlement@1"


def _contracts(store: GameplayEventStore) -> ContractAuthorityService:
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(TERMS, "simple_service", 2, EVIDENCE))
    return ContractAuthorityService(
        store=store,
        terms_registry=terms,
        policy_authorities={"authority:municipal-assessment"},
    )


def test_municipal_drought_assessment_closed_loop_uses_only_admitted_owner_rows() -> None:
    store, _ecology, government, weather_event_id = _setup()
    advisory = government.issue_drought_advisory(_intent(store, weather_event_id))
    assert advisory.committed
    advisory_event_id = advisory.committed_event_ids[0]
    advisory_event = store.get_event(advisory_event_id)

    contracts = _contracts(store)
    creation = contracts.create_municipal_drought_assessment_from_advisory(
        GovernmentDroughtAssessmentContractIntentV1(
            advisory_event_id=advisory_event_id,
            expected_advisory_revision=advisory_event.stream_revision,
            expected_contract_revision=store.get_stream_head("gameplay:contracts"),
            command_id="command:municipal-loop:contract",
            idempotency_key=(
                f"contract:municipal-drought-assessment:{advisory_event_id}:"
                f"{advisory_event.stream_revision}:{JURISDICTION}:0:v1"
            ),
            causation_id=advisory_event_id,
            correlation_id="corr:municipal-loop",
            submitted_at="2026-08-26T00:00:00Z",
        )
    )
    assert creation.committed
    creation_event_id = creation.committed_event_ids[0]
    creation_event = store.get_event(creation_event_id)
    fulfillment = contracts.fulfill_municipal_drought_assessment_by_policy(
        MunicipalDroughtAssessmentFulfillmentIntentV1(
            contract_created_event_id=creation_event_id,
            expected_contract_created_revision=creation_event.stream_revision,
            expected_advisory_revision=advisory_event.stream_revision,
            expected_contract_head=store.get_stream_head("gameplay:contracts"),
            command_id="command:municipal-loop:fulfillment",
            idempotency_key=(
                f"contract:municipal-drought-assessment:fulfillment:{creation_event_id}:"
                f"{creation_event.stream_revision}:{advisory_event.stream_revision}:"
                f"{store.get_stream_head('gameplay:contracts')}:v1"
            ),
            causation_id=creation_event_id,
            correlation_id="corr:municipal-loop",
            submitted_at="2026-08-26T00:00:00Z",
        )
    )
    assert fulfillment.committed

    manifest = GameplayPatchManifest.model_validate_json(MANIFEST_PATH.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(store=store, package_registry=registry, contract_authority=contracts)
    assert economy.open_account(
        command_id="command:municipal-loop:provider-account",
        account_id="account:municipal-assessment",
        owner_ref=PROVIDER,
        currency_ref="currency:local",
        initial_balance=0,
        idempotency_key="municipal-loop:provider-account",
        causation_id=creation_event_id,
        correlation_id="corr:municipal-loop",
    ).committed
    assert economy.open_account(
        command_id="command:municipal-loop:receiver-account",
        account_id="account:district-works",
        owner_ref=RECEIVER,
        currency_ref="currency:local",
        initial_balance=20,
        idempotency_key="municipal-loop:receiver-account",
        causation_id=creation_event_id,
        correlation_id="corr:municipal-loop",
    ).committed
    proposal_digest = "proposal:municipal-drought-loop:1"
    settlement = economy.settle_package_declared_negotiated_exchange(
        PackageDeclaredNegotiatedExchangeIntentV1(
            capability_ref="capability:package-declared-negotiated-exchange@1",
            outcome_ref=OUTCOME,
            proposal_digest=proposal_digest,
            provider_consent=PartyConsentAttestationV1(party_ref=PROVIDER, proposal_digest=proposal_digest),
            receiver_consent=PartyConsentAttestationV1(party_ref=RECEIVER, proposal_digest=proposal_digest),
            command_id="command:municipal-loop:settlement",
            idempotency_key=(
                "package-negotiated-exchange:package:municipal-drought-services:v1:"
                f"package_declared_negotiated_exchange@1:{proposal_digest}:v1"
            ),
            causation_id=fulfillment.committed_event_ids[-1],
            correlation_id="corr:municipal-loop",
        )
    )
    assert settlement.committed

    ownership = OwnershipAuthorityService(store=store)
    contract_id = f"contract:municipal-drought-assessment:{JURISDICTION}:{advisory_event_id}"
    certificate = ownership.grant_municipal_drought_assessment_certificate(
        MunicipalDroughtAssessmentCertificateIntentV1(
            advisory_event_id=advisory_event_id,
            expected_contract_revision=store.get_stream_head("gameplay:contracts"),
            expected_ownership_revision=store.get_stream_head("gameplay:ownership"),
            command_id="command:municipal-loop:certificate",
            idempotency_key=(
                f"ownership:municipal-drought-assessment-certificate:{contract_id}:"
                f"{store.get_stream_head('gameplay:contracts')}:"
                f"{store.get_stream_head('gameplay:ownership')}:v1"
            ),
            causation_id=fulfillment.committed_event_ids[-1],
            correlation_id="corr:municipal-loop",
            submitted_at="2026-08-26T00:00:00Z",
        )
    )
    assert certificate.committed
    project_advisory_before_acknowledgment = government.drought_advisory_view_for(
        jurisdiction_ref=advisory_event.payload["jurisdiction_ref"]
    )
    acknowledgment = government.acknowledge_municipal_drought_assessment_certificate(
        _acknowledgment_request(store, certificate.committed_event_ids[0], advisory_event_id)
    )
    assert acknowledgment.committed

    fulfillment_events = [store.get_event(event_id) for event_id in fulfillment.committed_event_ids]
    settlement_events = [store.get_event(event_id) for event_id in settlement.committed_event_ids]
    certificate_event = store.get_event(certificate.committed_event_ids[0])
    acknowledgment_event = store.get_event(acknowledgment.committed_event_ids[0])
    assert [event.event_type for event in fulfillment_events] == [
        "gameplay.contract.service_completion_recorded",
        "gameplay.contract.record_fulfilled",
    ]
    assert [event.event_type for event in settlement_events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.package_declared_negotiated_exchange_settled",
    ]
    assert certificate_event.event_type == "gameplay.ownership.right_granted"
    assert acknowledgment_event.event_type == "gameplay.government.drought_assessment_acknowledged"
    assert len({creation.transaction_id, fulfillment.transaction_id, settlement.transaction_id, certificate.transaction_id, acknowledgment.transaction_id}) == 5
    assert all(event.visibility_policy == "authority_only" for event in fulfillment_events + settlement_events + [certificate_event, acknowledgment_event])
    assert project_advisory_before_acknowledgment == government.drought_advisory_view_for(
        jurisdiction_ref=advisory_event.payload["jurisdiction_ref"]
    )
    assert ContractProjector().rebuild(store.read_events()) == ContractProjector().rebuild(
        store.read_events(), checkpoint_at=fulfillment_events[0].global_sequence - 1
    )
    assert OwnershipProjector().rebuild(store.read_events()) == OwnershipProjector().rebuild(
        store.read_events(), checkpoint_at=certificate_event.global_sequence
    )
