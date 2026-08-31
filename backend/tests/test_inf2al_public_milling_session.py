from __future__ import annotations

from app.gameplay.construction_production_runtime import FacilityOperationalVerificationIntentV1, Recipe
from app.gameplay.contract_runtime import ContractAuthorityService, ContractTermsDefinition, ContractTermsRegistry, PublicMillingSessionContractIntentV1, PublicMillingSessionFulfillmentIntentV1
from app.gameplay.economy_runtime import EconomyAuthorityService, PackageDeclaredNegotiatedExchangeIntentV1, PartyConsentAttestationV1
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from pathlib import Path
import json
import pytest
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.event_store import GameplayEventStore
from test_infra_construction_mill_reinforcement import _intent, _setup


SERVICE = "service:industrial-facility-public-milling-session@1"
EVIDENCE = "evidence:industrial-facility-public-milling-session@1"
PROVIDER = "organization:district-milling-cooperative"
RECEIVER = "org:mill:1"
OUTCOME = "outcome:industrial-facility-public-milling-session-settlement@1"


def _source() -> tuple[GameplayEventStore, ConstructionProductionAuthority, object]:
    store, authority, _registry, acquisition_id = _setup()
    assert authority.reinforce_mill_from_package(_intent(acquisition_id)).committed
    facility = authority.projector().facilities["facility:mill-reinforcement:1"]
    recipe = Recipe(recipe_ref="recipe:inf2al", inputs={}, output_item="item:flour", duration_ticks=1)
    assert authority.settle_start_run(facility=facility, recipe=recipe, run_ref="run:inf2al", tick=10, command_id="inf2al:start", idempotency_key="inf2al:start", causation_id="cause:inf2al:start", correlation_id="corr:inf2al").committed
    run = authority.projector().runs["run:inf2al"]
    assert authority.settle_finish_run(run, tick=11, recipe=recipe, command_id="inf2al:finish", idempotency_key="inf2al:finish", causation_id="cause:inf2al:finish", correlation_id="corr:inf2al").committed
    stream = f"gameplay:construction_production:{facility.facility_ref}"
    events = store.read_stream(stream)
    started, finished = events[-2], events[-1]
    verified = authority.verify_facility_operationally(FacilityOperationalVerificationIntentV1(run_finished_event_id=finished.event_id, expected_run_finished_revision=finished.stream_revision, expected_run_started_revision=started.stream_revision, expected_facility_revision=1, expected_stream_revision=store.get_stream_head(stream), command_id="inf2al:verify", idempotency_key=f"construction:facility-operational-verification:{finished.event_id}:{finished.stream_revision}:1:{store.get_stream_head(stream)}:v1", causation_id=finished.event_id, correlation_id="corr:inf2al", submitted_at="2026-08-28T00:00:00Z"))
    assert verified.committed
    verification = store.get_event(verified.committed_event_ids[0])
    enabled = authority.enable_mill_reinforced_public_use(verification_event_id=verification.event_id, expected_verification_revision=verification.stream_revision, expected_facility_revision=1, expected_stream_revision=verification.stream_revision, command_id="inf2al:public-use", idempotency_key=f"construction:facility-mill-reinforced-public-use:{verification.event_id}:{verification.stream_revision}:1:{verification.stream_revision}:v1", causation_id=verification.event_id, correlation_id="corr:inf2al", submitted_at="2026-08-28T00:01:00Z")
    assert enabled.committed
    return store, authority, store.get_event(enabled.committed_event_ids[0])


def _contracts(store: GameplayEventStore) -> ContractAuthorityService:
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition(SERVICE, "simple_service", 2, EVIDENCE))
    return ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={"authority:district-milling"})


def _economy_setup() -> tuple[GameplayEventStore, EconomyAuthorityService, object]:
    store, _authority, source = _source()
    contracts = _contracts(store)
    created = contracts.create_public_milling_session_from_public_use(
        PublicMillingSessionContractIntentV1(
            public_use_event_id=source.event_id,
            expected_public_use_revision=source.stream_revision,
            expected_contract_revision=0,
            command_id="inf2al:economy:create",
            idempotency_key=f"contract:public-milling-session:{source.event_id}:{source.stream_revision}:0:v1",
            causation_id=source.event_id,
            correlation_id="corr:inf2al:economy",
            submitted_at="2026-08-28T00:02:00Z",
        )
    )
    assert created.committed
    created_event = store.get_event(created.committed_event_ids[0])
    head = store.get_stream_head("gameplay:contracts")
    fulfilled = contracts.fulfill_public_milling_session_by_policy(
        PublicMillingSessionFulfillmentIntentV1(
            contract_created_event_id=created_event.event_id,
            expected_contract_created_revision=created_event.stream_revision,
            expected_public_use_revision=source.stream_revision,
            expected_contract_head=head,
            command_id="inf2al:economy:fulfill",
            idempotency_key=f"contract:public-milling-session:fulfillment:{created_event.event_id}:{created_event.stream_revision}:{source.stream_revision}:{head}:v1",
            causation_id=created_event.event_id,
            correlation_id="corr:inf2al:economy",
            submitted_at="2026-08-28T00:03:00Z",
        )
    )
    assert fulfilled.committed
    manifest_path = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-2" / "package-industrial-facilities-v6-public-milling-session.manifest.json"
    manifest = GameplayPatchManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(store=store, package_registry=registry, contract_authority=contracts)
    assert economy.open_account(command_id="inf2al:economy:provider", account_id="account:inf2al:provider", owner_ref=PROVIDER, currency_ref="currency:local", initial_balance=0, idempotency_key="inf2al:economy:provider", causation_id=source.event_id, correlation_id="corr:inf2al:economy").committed
    assert economy.open_account(command_id="inf2al:economy:receiver", account_id="account:inf2al:receiver", owner_ref=RECEIVER, currency_ref="currency:local", initial_balance=12, idempotency_key="inf2al:economy:receiver", causation_id=source.event_id, correlation_id="corr:inf2al:economy").committed
    return store, economy, fulfilled


def test_inf2al_mill_public_use_creates_exact_service_contract() -> None:
    store, _authority, source = _source()
    contracts = _contracts(store)
    result = contracts.create_public_milling_session_from_public_use(
        PublicMillingSessionContractIntentV1(
            public_use_event_id=source.event_id,
            expected_public_use_revision=source.stream_revision,
            expected_contract_revision=store.get_stream_head("gameplay:contracts"),
            command_id="inf2al:create",
            idempotency_key=f"contract:public-milling-session:{source.event_id}:{source.stream_revision}:0:v1",
            causation_id=source.event_id,
            correlation_id="corr:inf2al",
            submitted_at="2026-08-28T00:02:00Z",
        )
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["terms_ref"] == SERVICE
    assert event.payload["party_refs"] == [PROVIDER, RECEIVER]
    assert event.payload["facility_kind"] == "mill_reinforced"

    head = store.get_stream_head("gameplay:contracts")
    fulfilled = contracts.fulfill_public_milling_session_by_policy(
        PublicMillingSessionFulfillmentIntentV1(
            contract_created_event_id=event.event_id,
            expected_contract_created_revision=event.stream_revision,
            expected_public_use_revision=source.stream_revision,
            expected_contract_head=head,
            command_id="inf2al:fulfill",
            idempotency_key=(
                f"contract:public-milling-session:fulfillment:{event.event_id}:"
                f"{event.stream_revision}:{source.stream_revision}:{head}:v1"
            ),
            causation_id=event.event_id,
            correlation_id="corr:inf2al",
            submitted_at="2026-08-28T00:03:00Z",
        )
    )
    assert fulfilled.committed
    assert [store.get_event(item).event_type for item in fulfilled.committed_event_ids] == [
        "gameplay.contract.service_completion_recorded",
        "gameplay.contract.record_fulfilled",
    ]


def test_inf2al_public_milling_exchange_uses_frozen_v6_and_fixed_price() -> None:
    store, _authority, source = _source()
    contracts = _contracts(store)
    created = contracts.create_public_milling_session_from_public_use(
        PublicMillingSessionContractIntentV1(
            public_use_event_id=source.event_id,
            expected_public_use_revision=source.stream_revision,
            expected_contract_revision=0,
            command_id="inf2al:exchange:create",
            idempotency_key=f"contract:public-milling-session:{source.event_id}:{source.stream_revision}:0:v1",
            causation_id=source.event_id,
            correlation_id="corr:inf2al:exchange",
            submitted_at="2026-08-28T00:02:00Z",
        )
    )
    assert created.committed
    created_event = store.get_event(created.committed_event_ids[0])
    head = store.get_stream_head("gameplay:contracts")
    fulfilled = contracts.fulfill_public_milling_session_by_policy(
        PublicMillingSessionFulfillmentIntentV1(
            contract_created_event_id=created_event.event_id,
            expected_contract_created_revision=created_event.stream_revision,
            expected_public_use_revision=source.stream_revision,
            expected_contract_head=head,
            command_id="inf2al:exchange:fulfill",
            idempotency_key=f"contract:public-milling-session:fulfillment:{created_event.event_id}:{created_event.stream_revision}:{source.stream_revision}:{head}:v1",
            causation_id=created_event.event_id,
            correlation_id="corr:inf2al:exchange",
            submitted_at="2026-08-28T00:03:00Z",
        )
    )
    assert fulfilled.committed
    manifest_path = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-2" / "package-industrial-facilities-v6-public-milling-session.manifest.json"
    manifest = GameplayPatchManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(store=store, package_registry=registry, contract_authority=contracts)
    assert economy.open_account(command_id="inf2al:provider-account", account_id="account:inf2al:provider", owner_ref=PROVIDER, currency_ref="currency:local", initial_balance=0, idempotency_key="inf2al:provider-account", causation_id=source.event_id, correlation_id="corr:inf2al").committed
    assert economy.open_account(command_id="inf2al:receiver-account", account_id="account:inf2al:receiver", owner_ref=RECEIVER, currency_ref="currency:local", initial_balance=12, idempotency_key="inf2al:receiver-account", causation_id=source.event_id, correlation_id="corr:inf2al").committed
    proposal = "proposal:inf2al:1"
    result = economy.settle_package_declared_negotiated_exchange(
        PackageDeclaredNegotiatedExchangeIntentV1(
            capability_ref="capability:package-declared-negotiated-exchange@1",
            outcome_ref=OUTCOME,
            proposal_digest=proposal,
            provider_consent=PartyConsentAttestationV1(party_ref=PROVIDER, proposal_digest=proposal),
            receiver_consent=PartyConsentAttestationV1(party_ref=RECEIVER, proposal_digest=proposal),
            proposed_amount=8,
            command_id="inf2al:exchange:settle",
            idempotency_key=f"package-negotiated-exchange:{manifest.patch_revision_id}:package_declared_negotiated_exchange@1:{proposal}:v1",
            causation_id=fulfilled.committed_event_ids[0],
            correlation_id="corr:inf2al:exchange",
        )
    )
    assert result.committed, result.failure
    events = [store.get_event(item) for item in result.committed_event_ids]
    assert events[-1].payload["package_revision_id"] == "package:industrial-facilities:v6"
    assert events[-1].payload["amount_minor"] == 8


def test_inf2al_exchange_duplicate_price_and_replay_are_zero_write_or_equal() -> None:
    store, economy, fulfilled = _economy_setup()
    proposal = "proposal:inf2al:replay"
    def request(*, proposal_digest: str = proposal, amount: int | None = 8, key: str | None = None, correlation: str = "corr:inf2al:replay"):
        return PackageDeclaredNegotiatedExchangeIntentV1(
            capability_ref="capability:package-declared-negotiated-exchange@1",
            outcome_ref=OUTCOME,
            proposal_digest=proposal_digest,
            provider_consent=PartyConsentAttestationV1(party_ref=PROVIDER, proposal_digest=proposal_digest),
            receiver_consent=PartyConsentAttestationV1(party_ref=RECEIVER, proposal_digest=proposal_digest),
            proposed_amount=amount,
            command_id="inf2al:replay:settle",
            idempotency_key=key or f"package-negotiated-exchange:package:industrial-facilities:v6:package_declared_negotiated_exchange@1:{proposal_digest}:v1",
            causation_id=fulfilled.committed_event_ids[0],
            correlation_id=correlation,
        )
    first = economy.settle_package_declared_negotiated_exchange(request())
    assert first.committed
    before = store.export_snapshot()
    duplicate = economy.settle_package_declared_negotiated_exchange(request())
    changed = economy.settle_package_declared_negotiated_exchange(request(correlation="corr:changed"))
    bad_price = economy.settle_package_declared_negotiated_exchange(request(proposal_digest="proposal:inf2al:bad", amount=9))
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed and not bad_price.committed
    assert store.export_snapshot() == before
    full = economy.package_declared_negotiated_exchange_projection(scope="authority")
    tail = economy.package_declared_negotiated_exchange_projection(scope="authority", checkpoint_at=first.global_sequence_range[-1])
    assert full == tail


def test_inf2al_exchange_rejects_caller_selected_party_bindings() -> None:
    store, economy, fulfilled = _economy_setup()
    proposal = "proposal:inf2al:party"
    result = economy.settle_package_declared_negotiated_exchange(
        PackageDeclaredNegotiatedExchangeIntentV1(
            capability_ref="capability:package-declared-negotiated-exchange@1",
            outcome_ref=OUTCOME,
            proposal_digest=proposal,
            provider_consent=PartyConsentAttestationV1(party_ref="organization:other", proposal_digest=proposal),
            receiver_consent=PartyConsentAttestationV1(party_ref=RECEIVER, proposal_digest=proposal),
            proposed_amount=8,
            command_id="inf2al:party:provider",
            idempotency_key=f"package-negotiated-exchange:package:industrial-facilities:v6:package_declared_negotiated_exchange@1:{proposal}:v1",
            causation_id=fulfilled.committed_event_ids[0],
            correlation_id="corr:inf2al:party",
        )
    )
    assert not result.committed
    assert result.failure and result.failure.error_code == "public_milling_provider_binding_invalid"
    assert store.read_stream("gameplay:economy") == [] or all(event.event_type == "gameplay.economy.account_opened" for event in store.read_stream("gameplay:economy"))


def test_inf2al_generic_contract_creation_and_caller_key_are_rejected() -> None:
    store, economy, _fulfilled = _economy_setup()
    contracts = economy._contract_authority
    assert contracts is not None
    with pytest.raises(Exception, match="public_milling_session_row_required"):
        contracts.create_contract(command_id="inf2al:generic", contract_id="contract:generic", contract_type="simple_service", terms_ref=SERVICE, party_refs=(PROVIDER, RECEIVER), idempotency_key="generic", causation_id="cause", correlation_id="corr")
    proposal = "proposal:inf2al:key"
    result = economy.settle_package_declared_negotiated_exchange(PackageDeclaredNegotiatedExchangeIntentV1(capability_ref="capability:package-declared-negotiated-exchange@1", outcome_ref=OUTCOME, proposal_digest=proposal, provider_consent=PartyConsentAttestationV1(party_ref=PROVIDER, proposal_digest=proposal), receiver_consent=PartyConsentAttestationV1(party_ref=RECEIVER, proposal_digest=proposal), proposed_amount=8, command_id="inf2al:key", idempotency_key="caller-selected", causation_id="cause", correlation_id="corr"))
    assert not result.committed and result.failure is not None
    assert store.read_stream("gameplay:economy") == [] or all(event.event_type == "gameplay.economy.account_opened" for event in store.read_stream("gameplay:economy"))
