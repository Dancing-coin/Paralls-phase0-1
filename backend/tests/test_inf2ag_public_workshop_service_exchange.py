from __future__ import annotations

from app.gameplay.economy_runtime import (
    EconomyAuthorityService,
    PackageDeclaredNegotiatedExchangeIntentV1,
    PartyConsentAttestationV1,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from test_inf2ag_public_workshop_service_contract import (
    EVIDENCE,
    PROVIDER,
    SERVICE,
    _contracts,
    _request,
    _source,
)


OUTCOME = "outcome:industrial-facility-public-workshop-session-settlement@1"
MANIFEST = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-2"
    / "package-industrial-facilities-v5-public-workshop-session.manifest.json"
)


def _setup() -> tuple[GameplayEventStore, EconomyAuthorityService]:
    store, _authority, source = _source()
    contracts = _contracts(store)
    created = contracts.create_public_workshop_session_from_public_use(_request(store, source.event_id))
    assert created.committed
    created_event = store.get_event(created.committed_event_ids[0])
    from app.gameplay.contract_runtime import PublicWorkshopSessionFulfillmentIntentV1

    source_event = store.get_event(source.event_id)
    head = store.get_stream_head("gameplay:contracts")
    fulfilled = contracts.fulfill_public_workshop_session_by_policy(
        PublicWorkshopSessionFulfillmentIntentV1(
            contract_created_event_id=created_event.event_id,
            expected_contract_created_revision=created_event.stream_revision,
            expected_public_use_revision=source_event.stream_revision,
            expected_contract_head=head,
            command_id="inf2ag:fulfill",
            idempotency_key=(
                f"contract:public-workshop-session:fulfillment:{created_event.event_id}:"
                f"{created_event.stream_revision}:{source_event.stream_revision}:{head}:v1"
            ),
            causation_id=created_event.event_id,
            correlation_id="corr:inf2ag",
            submitted_at="2026-08-27T13:02:00Z",
        )
    )
    assert fulfilled.committed
    manifest = GameplayPatchManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(store=store, package_registry=registry, contract_authority=contracts)
    assert economy.open_account(
        command_id="inf2ag:provider-account",
        account_id="account:inf2ag:provider",
        owner_ref=PROVIDER,
        currency_ref="currency:local",
        initial_balance=0,
        idempotency_key="inf2ag:provider-account",
        causation_id=source.event_id,
        correlation_id="corr:inf2ag",
    ).committed
    assert economy.open_account(
        command_id="inf2ag:receiver-account",
        account_id="account:inf2ag:receiver",
        owner_ref="organization:mill",
        currency_ref="currency:local",
        initial_balance=20,
        idempotency_key="inf2ag:receiver-account",
        causation_id=source.event_id,
        correlation_id="corr:inf2ag",
    ).committed
    return store, economy


def _intent(*, proposal_digest: str = "proposal:inf2ag:1", amount: int | None = None) -> PackageDeclaredNegotiatedExchangeIntentV1:
    return PackageDeclaredNegotiatedExchangeIntentV1(
        capability_ref="capability:package-declared-negotiated-exchange@1",
        outcome_ref=OUTCOME,
        proposal_digest=proposal_digest,
        provider_consent=PartyConsentAttestationV1(party_ref=PROVIDER, proposal_digest=proposal_digest),
        receiver_consent=PartyConsentAttestationV1(party_ref="organization:mill", proposal_digest=proposal_digest),
        proposed_amount=amount,
        command_id=f"command:{proposal_digest}",
        idempotency_key=(
            f"package-negotiated-exchange:package:industrial-facilities:v5:"
            f"package_declared_negotiated_exchange@1:{proposal_digest}:v1"
        ),
        causation_id=f"cause:{proposal_digest}",
        correlation_id=f"corr:{proposal_digest}",
    )


def test_public_workshop_package_settles_once_with_fixed_price_and_replay() -> None:
    store, economy = _setup()
    result = economy.settle_package_declared_negotiated_exchange(_intent())
    assert result.committed, result.failure
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    assert [event.event_type for event in events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.package_declared_negotiated_exchange_settled",
    ]
    assert events[-1].payload["package_revision_id"] == "package:industrial-facilities:v5"
    assert events[-1].payload["outcome_ref"] == OUTCOME
    assert events[-1].payload["amount_minor"] == 12
    full = economy.package_declared_negotiated_exchange_projection(scope="authority")
    tail = economy.package_declared_negotiated_exchange_projection(scope="authority", checkpoint_at=events[-1].global_sequence)
    assert full == tail


def test_public_workshop_exchange_price_and_changed_duplicate_are_zero_write() -> None:
    store, economy = _setup()
    first = economy.settle_package_declared_negotiated_exchange(_intent())
    assert first.committed
    before = store.export_snapshot()
    changed = economy.settle_package_declared_negotiated_exchange(_intent().model_copy(update={"correlation_id": "corr:changed"}))
    bad_price = economy.settle_package_declared_negotiated_exchange(_intent(proposal_digest="proposal:inf2ag:bad", amount=13))
    assert not changed.committed
    assert not bad_price.committed
    assert store.export_snapshot() == before


def test_public_workshop_exchange_rejects_caller_selected_idempotency_key() -> None:
    store, economy = _setup()
    before = store.export_snapshot()
    result = economy.settle_package_declared_negotiated_exchange(
        _intent().model_copy(update={"idempotency_key": "caller-selected"})
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "package_exchange_idempotency_key_invalid"
    assert store.export_snapshot() == before
