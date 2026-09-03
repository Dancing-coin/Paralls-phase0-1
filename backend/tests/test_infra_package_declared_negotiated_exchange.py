from __future__ import annotations

import pytest

from app.gameplay.contract_runtime import ContractAuthorityService, ContractTermsDefinition, ContractTermsRegistry
from app.gameplay.economy_runtime import (
    EconomyAuthorityService,
    EconomyRuntimeError,
    PackageDeclaredNegotiatedExchangeIntentV1,
    PartyConsentAttestationV1,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.ownership_runtime import OwnershipAuthorityService
from app.gameplay.patch_runtime import (
    GameplayPatchManifest,
    GameplayPatchRegistry,
    PackageDeclaredNegotiatedExchangeDefinition,
    PackageExchangePricePolicy,
    RequestedCapability,
)


SELLER = "actor:provider"
BUYER = "actor:receiver"
CURRENCY = "currency:local"
PACKAGE_REVISION = "patch:negotiated-exchange:v1"


def _manifest(*, outcome_ref: str, tradeable_ref: str | None, typed_service_ref: str | None, source_mode: str, amount: int = 7) -> GameplayPatchManifest:
    definition = PackageDeclaredNegotiatedExchangeDefinition(
        economic_outcome_id="package_declared_negotiated_exchange@1",
        outcome_ref=outcome_ref,
        tradeable_ref=tradeable_ref,
        typed_service_ref=typed_service_ref,
        source_evidence_mode=source_mode,
        source_owner_ref={
            "inventory_custody@1": "actor_gameplay.inventory_domain",
            "ownership_right@1": "actor_gameplay.ownership_domain",
            "completed_service@1": "actor_gameplay.contract_domain",
        }[source_mode],
        source_evidence_kind=source_mode,
        price_policy=PackageExchangePricePolicy(
            price_policy_revision="price:package-exchange:v1",
            currency_ref=CURRENCY,
            fixed_amount=amount,
        ),
        consent_rule_ref="consent:mutual@1",
        eligibility_refs=(),
        privacy_policy_ref="authority_only",
        compensation_policy_ref="none",
        source_selection_rule_ref="exchange:unique-owned-source@1",
        capability_ref="capability:package-declared-negotiated-exchange@1",
    )
    draft = GameplayPatchManifest(
        manifest_schema_version=1,
        patch_id="package:negotiated-exchange",
        patch_version="1.0.0",
        patch_revision_id=PACKAGE_REVISION,
        content_digest="pending",
        author_id="author:trusted",
        trust_policy_ref="trust:gameplay-package@1",
        requested_capabilities=(
            RequestedCapability(
                capability_id="capability:package-declared-negotiated-exchange",
                capability_version="1",
                call_sites=("need-resolution",),
                reason="admitted package exchange outcome",
            ),
        ),
        economic_outcomes=(definition,),
    )
    return draft.model_copy(update={"content_digest": draft.expected_content_digest()})


@pytest.mark.parametrize(
    "field",
    ("privacy_policy_ref", "compensation_policy_ref", "source_selection_rule_ref", "capability_ref"),
)
def test_package_exchange_policy_and_capability_fields_cannot_be_omitted(field: str) -> None:
    definition = _manifest(
        outcome_ref="outcome:package-explicit-fields",
        tradeable_ref="item:package-explicit-fields@1",
        typed_service_ref=None,
        source_mode="inventory_custody@1",
    ).economic_outcomes[0]
    payload = definition.model_dump(mode="json")
    payload.pop(field)

    with pytest.raises(Exception):
        PackageDeclaredNegotiatedExchangeDefinition.model_validate(payload)


def test_package_exchange_eligibility_refs_cannot_be_omitted() -> None:
    definition = _manifest(
        outcome_ref="outcome:package-explicit-eligibility",
        tradeable_ref="item:package-explicit-eligibility@1",
        typed_service_ref=None,
        source_mode="inventory_custody@1",
    ).economic_outcomes[0]
    payload = definition.model_dump(mode="json")
    payload.pop("eligibility_refs")

    with pytest.raises(Exception):
        PackageDeclaredNegotiatedExchangeDefinition.model_validate(payload)


def _intent(*, outcome_ref: str, proposal_digest: str = "proposal:exchange:1", amount: int | None = None) -> PackageDeclaredNegotiatedExchangeIntentV1:
    return PackageDeclaredNegotiatedExchangeIntentV1(
        capability_ref="capability:package-declared-negotiated-exchange@1",
        outcome_ref=outcome_ref,
        proposal_digest=proposal_digest,
        provider_consent=PartyConsentAttestationV1(party_ref=SELLER, proposal_digest=proposal_digest),
        receiver_consent=PartyConsentAttestationV1(party_ref=BUYER, proposal_digest=proposal_digest),
        proposed_amount=amount,
        command_id=f"command:{proposal_digest}",
        idempotency_key=(
            f"package-negotiated-exchange:{PACKAGE_REVISION}:"
            f"package_declared_negotiated_exchange@1:{proposal_digest}:v1"
        ),
        causation_id=f"cause:{proposal_digest}",
        correlation_id=f"corr:{proposal_digest}",
    )


def _setup(*, source_mode: str = "inventory_custody@1", amount: int = 7) -> tuple[GameplayEventStore, EconomyAuthorityService, InventoryAuthorityService, OwnershipAuthorityService, ContractAuthorityService]:
    store = GameplayEventStore()
    inventory_registry = InventoryDefinitionRegistry()
    inventory_registry.register_item(ItemDefinition("item:package-compass", "1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=inventory_registry)
    for actor in (SELLER, BUYER):
        assert inventory.create_container(
            command_id=f"command:container:{actor}",
            actor_ref=actor,
            spec=ContainerSpec(f"container:{actor}", 10, 10, 3),
            idempotency_key=f"idem:container:{actor}",
            causation_id="cause:bootstrap",
            correlation_id="corr:bootstrap",
        ).committed
    assert inventory.instantiate(
        command_id="command:item:provider",
        actor_ref=SELLER,
        item_id="item:provider:compass",
        definition_id="item:package-compass",
        quantity=1,
        container_id=f"container:{SELLER}",
        idempotency_key="idem:item:provider",
        causation_id="cause:bootstrap",
        correlation_id="corr:bootstrap",
    ).committed
    ownership = OwnershipAuthorityService(store=store)
    assert ownership.grant_initial_title(
        command_id="command:right:provider",
        asset_ref="asset:package-estate",
        holder_ref=SELLER,
        right_id="right:provider:estate",
        idempotency_key="idem:right:provider",
        causation_id="cause:bootstrap",
        correlation_id="corr:bootstrap",
    ).committed
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition("service:package-tutoring", "simple_service", 2, "evidence:package-tutoring@1"))
    contracts = ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={"authority:provider"})
    assert contracts.create_contract(
        command_id="command:service:contract",
        contract_id="contract:package-tutoring:1",
        contract_type="simple_service",
        terms_ref="service:package-tutoring",
        party_refs=(SELLER, BUYER),
        idempotency_key="idem:service:contract",
        causation_id="cause:bootstrap",
        correlation_id="corr:bootstrap",
    ).committed
    assert contracts.complete_simple_service_by_policy(
        command_id="command:service:complete",
        contract_id="contract:package-tutoring:1",
        authority_ref="authority:provider",
        completion_evidence_kind="evidence:package-tutoring@1",
        completion_evidence_ref="evidence:package-tutoring:completed:1",
        idempotency_key="idem:service:complete",
        causation_id="cause:bootstrap",
        correlation_id="corr:bootstrap",
    ).committed
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:trusted"}))
    if source_mode == "inventory_custody@1":
        manifest = _manifest(outcome_ref="outcome:package-compass", tradeable_ref="item:package-compass", typed_service_ref=None, source_mode=source_mode, amount=amount)
    elif source_mode == "ownership_right@1":
        manifest = _manifest(outcome_ref="outcome:package-estate", tradeable_ref="asset:package-estate", typed_service_ref=None, source_mode=source_mode, amount=amount)
    else:
        manifest = _manifest(outcome_ref="outcome:package-tutoring", tradeable_ref=None, typed_service_ref="service:package-tutoring", source_mode=source_mode, amount=amount)
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(
        store=store,
        package_registry=registry,
        inventory_registry=inventory_registry,
        inventory_authority=inventory,
        ownership_authority=ownership,
        contract_authority=contracts,
    )
    assert economy.open_account(
        command_id="command:account:provider", account_id="account:provider", owner_ref=SELLER,
        currency_ref=CURRENCY, initial_balance=0, idempotency_key="idem:account:provider",
        causation_id="cause:bootstrap", correlation_id="corr:bootstrap",
    ).committed
    assert economy.open_account(
        command_id="command:account:receiver", account_id="account:receiver", owner_ref=BUYER,
        currency_ref=CURRENCY, initial_balance=20, idempotency_key="idem:account:receiver",
        causation_id="cause:bootstrap", correlation_id="corr:bootstrap",
    ).committed
    return store, economy, inventory, ownership, contracts


@pytest.mark.parametrize(
    ("source_mode", "outcome_ref", "expected_source_events"),
    (
        ("inventory_custody@1", "outcome:package-compass", {"gameplay.inventory.item_transferred_out", "gameplay.inventory.item_transferred_in"}),
        ("ownership_right@1", "outcome:package-estate", {"gameplay.ownership.right_transferred"}),
        ("completed_service@1", "outcome:package-tutoring", set()),
    ),
    ids=("inventory_success", "ownership_success", "completed_service_success"),
)
def test_package_declared_exchange_commits_one_fixed_owner_vector_for_each_admitted_source_mode(source_mode: str, outcome_ref: str, expected_source_events: set[str]) -> None:
    store, economy, _inventory, _ownership, _contracts = _setup(source_mode=source_mode)

    result = economy.settle_package_declared_negotiated_exchange(_intent(outcome_ref=outcome_ref))

    assert result.committed, result.failure
    event_types = {store.get_event(event_id).event_type for event_id in result.committed_event_ids}
    assert event_types == {
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.package_declared_negotiated_exchange_settled",
        *expected_source_events,
    }
    assert len({store.get_event(event_id).transaction_id for event_id in result.committed_event_ids}) == 1
    assert all(store.get_event(event_id).visibility_policy == "authority_only" for event_id in result.committed_event_ids)


def test_package_exchange_rejects_price_outside_fixed_policy_without_writes() -> None:
    store, economy, inventory, _ownership, _contracts = _setup()
    before_events, before_outbox = store.read_events(), store.list_outbox()
    invalid_price = economy.settle_package_declared_negotiated_exchange(_intent(outcome_ref="outcome:package-compass", amount=8))
    assert not invalid_price.committed
    assert invalid_price.failure is not None and invalid_price.failure.error_code == "package_exchange_price_invalid"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_package_exchange_rejects_ambiguous_package_source_without_writes() -> None:
    store, economy, inventory, _ownership, _contracts = _setup()
    assert inventory.instantiate(
        command_id="command:item:provider:second", actor_ref=SELLER,
        item_id="item:provider:compass:second", definition_id="item:package-compass", quantity=1,
        container_id=f"container:{SELLER}", idempotency_key="idem:item:provider:second",
        causation_id="cause:mutation", correlation_id="corr:mutation",
    ).committed
    before_events, before_outbox = store.read_events(), store.list_outbox()
    ambiguous = economy.settle_package_declared_negotiated_exchange(_intent(outcome_ref="outcome:package-compass", proposal_digest="proposal:ambiguous"))
    assert not ambiguous.committed
    assert ambiguous.failure is not None and ambiguous.failure.error_code == "package_exchange_source_ambiguous"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_package_exchange_rejects_capability_mismatch_without_writes() -> None:
    store, economy, _inventory, _ownership, _contracts = _setup()
    before_events, before_outbox = store.read_events(), store.list_outbox()
    denied = economy.settle_package_declared_negotiated_exchange(_intent(outcome_ref="outcome:package-compass", proposal_digest="proposal:denied").model_copy(update={"capability_ref": "capability:package-declared-negotiated-exchange@2"}))
    assert not denied.committed
    assert denied.failure is not None and denied.failure.error_code == "package_exchange_capability_denied"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_package_exchange_rejects_inactive_package_revision_without_writes() -> None:
    store, economy, _inventory, _ownership, _contracts = _setup()
    before_events, before_outbox = store.read_events(), store.list_outbox()
    economy._package_registry.replace_active_set(())
    rejected = economy.settle_package_declared_negotiated_exchange(
        _intent(outcome_ref="outcome:package-compass", proposal_digest="proposal:inactive")
    )
    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "package_exchange_package_inactive"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_package_exchange_receipt_is_authority_only_and_append_derived() -> None:
    store, economy, _inventory, _ownership, _contracts = _setup()
    intent = _intent(outcome_ref="outcome:package-compass")
    result = economy.settle_package_declared_negotiated_exchange(intent)
    assert result.committed
    receipt = economy.package_declared_negotiated_exchange_receipt_for(result=result, scope="authority")
    assert receipt.transaction_id == result.transaction_id
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    with pytest.raises(EconomyRuntimeError, match="package_exchange_receipt_scope_denied"):
        economy.package_declared_negotiated_exchange_receipt_for(result=result, scope="public")


def test_package_exchange_projection_is_authority_only_and_full_replay_is_fixed() -> None:
    store, economy, _inventory, _ownership, _contracts = _setup()
    result = economy.settle_package_declared_negotiated_exchange(_intent(outcome_ref="outcome:package-compass"))
    assert result.committed
    full = economy.package_declared_negotiated_exchange_projection(scope="authority")
    assert full["settlements"]["proposal:exchange:1"]["status"] == "settled"
    with pytest.raises(EconomyRuntimeError, match="package_exchange_projection_scope_denied"):
        economy.package_declared_negotiated_exchange_projection(scope="project")


def test_package_exchange_checkpoint_tail_replay_matches_full_replay() -> None:
    store, economy, _inventory, _ownership, _contracts = _setup()
    result = economy.settle_package_declared_negotiated_exchange(_intent(outcome_ref="outcome:package-compass"))
    assert result.committed
    full = economy.package_declared_negotiated_exchange_projection(scope="authority")
    tail = economy.package_declared_negotiated_exchange_projection(scope="authority", checkpoint_at=result.global_sequence_range[-1])
    assert tail == full


def test_package_exchange_exact_duplicate_replays_and_changed_duplicate_is_zero_write() -> None:
    store, economy, _inventory, _ownership, _contracts = _setup()
    intent = _intent(outcome_ref="outcome:package-compass")
    result = economy.settle_package_declared_negotiated_exchange(intent)
    assert result.committed
    before_events, before_outbox = store.read_events(), store.list_outbox()
    duplicate = economy.settle_package_declared_negotiated_exchange(intent)
    changed = economy.settle_package_declared_negotiated_exchange(intent.model_copy(update={"command_id": "command:changed"}))
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox
