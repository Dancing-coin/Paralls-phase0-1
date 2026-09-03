from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_schema_registry import EventSchemaRegistry, register_inf2ao_production_output_market_eligibility_event_schemas
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.patch_runtime import GameplayPatchRegistry
from app.gameplay import inf2ao_market_eligibility as inf2ao
from closed_generic_manifest_fixtures import load_manifest
from test_production_output_certification_family import _intent as cert_intent, _setup
from test_production_output_custody_family import (
    _custody_manifest,
    _family_registry,
    _inventory_for_certification,
)


def _prepared() -> tuple[object, EconomyAuthorityService, object]:
    store, construction, finished_id = _setup()
    certification_manifest = load_manifest("production-output-certification-demo-v1")
    custody_manifest = _custody_manifest(
        package_id="production-output-custody-bread",
        package_revision="package:production-output-custody:bread@1",
        definition_ref="definition:production-output-custody-bread@1",
        output_item_ref="item:bread@1",
        holder_binding_ref="binding:holder:organization:bakery@1",
        container_binding_ref="binding:container:container:organization:bakery:production-output@1",
        policy_revision="policy:inventory-production-output-custody@1",
    )
    registry = _family_registry(certification_manifest, custody_manifest)
    finished = store.get_event(finished_id)
    certification = construction.settle_production_output_certification(
        intent=cert_intent(finished.event_id)
    )
    assert certification.committed, certification.failure
    certification_event = store.get_event(certification.committed_event_ids[0])
    inventory = _inventory_for_certification(
        store,
        package_registry=registry,
        holder_ref="organization:bakery",
        item_ref="item:bread@1",
        container_id="container:organization:bakery:production-output",
    )
    custody = inventory.settle_production_output_custody(
        intent={
            "certification_event_id": certification_event.event_id,
            "expected_certification_revision": certification_event.stream_revision,
            "expected_inventory_stream_revision": store.get_stream_head("gameplay:inventory:organization:bakery"),
            "command_id": "inf2ao:custody",
            "correlation_id": "inf2ao:custody",
            "submitted_at": "2026-08-31T00:00:00Z",
        }
    )
    assert custody.committed, custody.failure
    source = store.get_event(custody.committed_event_ids[0])
    economy = EconomyAuthorityService(store=store)
    return store, economy, source


def _intent(source: object, **updates: object) -> inf2ao.ProductionOutputMarketEligibilityIntent:
    values: dict[str, object] = {
        "source_event_id": source.event_id,
        "expected_source_revision": source.stream_revision,
        "expected_economy_stream_revision": 0,
        "command_id": "inf2ao:eligibility",
        "causation_id": source.event_id,
        "correlation_id": "corr:inf2ao",
        "submitted_at": "2026-08-31T00:00:00Z",
    }
    values.update(updates)
    return inf2ao.ProductionOutputMarketEligibilityIntent.model_validate(values)


def test_inf2ao_records_account_neutral_market_eligibility_marker() -> None:
    store, economy, source = _prepared()

    result = economy.record_production_output_market_eligibility(intent=_intent(source))

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.economy.production_output_market_eligible@1"
    assert event.visibility_policy == "authority_only"
    assert event.payload["source_event_id"] == source.event_id
    assert event.payload["item_ref"] == "item:bread@1"
    assert event.payload["quantity"] == source.payload["quantity"]
    assert event.payload["status"] == "eligible"
    assert not any(item.event_type.startswith("gameplay.economy.account_") for item in store.read_events())


def test_inf2ao_replays_duplicate_and_rejects_changed_duplicate() -> None:
    store, economy, source = _prepared()
    first = economy.record_production_output_market_eligibility(intent=_intent(source))
    before = tuple(store.read_events())

    duplicate = economy.record_production_output_market_eligibility(intent=_intent(source))
    changed = economy.record_production_output_market_eligibility(
        intent=_intent(source, correlation_id="corr:inf2ao:changed")
    )

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert tuple(store.read_events()) == before


def test_inf2ao_rejects_private_or_forged_source_without_write() -> None:
    store, economy, source = _prepared()
    private = source.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    forged = private.model_copy(update={"payload": {**private.payload, "family_ref": "forged@1"}}, deep=True)
    store._events_by_id[source.event_id] = forged
    before = tuple(store.read_events())

    result = economy.record_production_output_market_eligibility(intent=_intent(source))

    assert not result.committed
    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_inf2ao_rejects_source_stream_not_bound_to_holder_without_write() -> None:
    store, economy, source = _prepared()
    forged = source.model_copy(
        update={"payload": {**source.payload, "holder_ref": "organization:other-holder"}},
        deep=True,
    )
    store._events_by_id[source.event_id] = forged
    store._events = [forged if event.event_id == source.event_id else event for event in store._events]
    before = tuple(store.read_events())

    result = economy.record_production_output_market_eligibility(intent=_intent(source))

    assert not result.committed
    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_inf2ao_receipt_and_full_tail_projection_match() -> None:
    store, economy, source = _prepared()
    result = economy.record_production_output_market_eligibility(intent=_intent(source))
    assert result.committed

    receipt = economy.production_output_market_eligibility_receipt_for(result=result, scope="authority")
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    full = economy.production_output_market_eligibility_projection(scope="authority")
    tail = economy.production_output_market_eligibility_projection(
        scope="authority", checkpoint_at=source.global_sequence
    )
    assert full == tail


def test_inf2ao_replay_rejects_holder_stream_mismatch() -> None:
    store, economy, source = _prepared()
    result = economy.record_production_output_market_eligibility(intent=_intent(source))
    assert result.committed
    target_id = result.committed_event_ids[0]
    forged_source = source.model_copy(
        update={"payload": {**source.payload, "holder_ref": "organization:other-holder"}},
        deep=True,
    )
    forged_target = store.get_event(target_id).model_copy(
        update={"payload": {**store.get_event(target_id).payload, "holder_ref": "organization:other-holder"}},
        deep=True,
    )
    store._events_by_id[source.event_id] = forged_source
    store._events_by_id[target_id] = forged_target
    store._events = [
        forged_source if event.event_id == source.event_id else forged_target if event.event_id == target_id else event
        for event in store._events
    ]

    with pytest.raises(Exception, match="production_output_market_eligibility_projection_source_invalid"):
        economy.production_output_market_eligibility_projection(scope="authority")


def test_inf2ao_replay_rejects_mapping_and_subject_pin_mismatch() -> None:
    store, economy, source = _prepared()
    result = economy.record_production_output_market_eligibility(intent=_intent(source))
    assert result.committed
    target_id = result.committed_event_ids[0]
    forged_source = source.model_copy(
        update={
            "payload": {
                **source.payload,
                "facility_ref": "facility:forged",
                "project_ref": "plot:forged",
                "recipe_ref": "recipe:forged@1",
                "mapping_revision": "mapping:forged@1",
            }
        },
        deep=True,
    )
    forged_target = store.get_event(target_id).model_copy(
        update={
            "payload": {
                **store.get_event(target_id).payload,
                "facility_ref": "facility:forged",
                "project_ref": "plot:forged",
                "recipe_ref": "recipe:forged@1",
                "mapping_revision": "mapping:forged@1",
            }
        },
        deep=True,
    )
    store._events_by_id[source.event_id] = forged_source
    store._events_by_id[target_id] = forged_target
    store._events = [
        forged_source if event.event_id == source.event_id else forged_target if event.event_id == target_id else event
        for event in store._events
    ]

    with pytest.raises(Exception, match="production_output_market_eligibility_projection_source_invalid"):
        economy.production_output_market_eligibility_projection(scope="authority")


def test_inf2ao_replay_rejects_forged_target_contract_pins() -> None:
    store, economy, source = _prepared()
    result = economy.record_production_output_market_eligibility(intent=_intent(source))
    assert result.committed
    target_id = result.committed_event_ids[0]
    target = store.get_event(target_id)
    forged = target.model_copy(
        update={
            "payload": {
                **target.payload,
                "source_stream_id": "gameplay:inventory:forged",
                "source_stream_head": 999,
                "policy_revision": "policy:forged@1",
                "descriptor_ref": "descriptor:forged@1",
                "descriptor_revision": "descriptor:forged@1",
                "catalog_ref": "inf:forged@1",
                "terminal": "retryable",
            }
        },
        deep=True,
    )
    store._events_by_id[target_id] = forged
    store._events = [forged if event.event_id == target_id else event for event in store._events]

    with pytest.raises(Exception, match="production_output_market_eligibility_projection_source_invalid"):
        economy.production_output_market_eligibility_projection(scope="authority")


def test_inf2ao_replay_rejects_certification_revision_pin_mismatch() -> None:
    store, economy, source = _prepared()
    result = economy.record_production_output_market_eligibility(intent=_intent(source))
    assert result.committed
    target_id = result.committed_event_ids[0]
    forged_source = source.model_copy(
        update={"payload": {**source.payload, "source_certification_revision": 999}},
        deep=True,
    )
    forged_target = store.get_event(target_id).model_copy(
        update={"payload": {**store.get_event(target_id).payload, "source_certification_revision": 999}},
        deep=True,
    )
    store._events_by_id[source.event_id] = forged_source
    store._events_by_id[target_id] = forged_target
    store._events = [
        forged_source if event.event_id == source.event_id else forged_target if event.event_id == target_id else event
        for event in store._events
    ]

    with pytest.raises(Exception, match="production_output_market_eligibility_projection_source_invalid"):
        economy.production_output_market_eligibility_projection(scope="authority")


def test_inf2ao_intent_rejects_caller_payment_coordinates() -> None:
    with pytest.raises(ValidationError):
        inf2ao.ProductionOutputMarketEligibilityIntent.model_validate(
            {
                "source_event_id": "event:source",
                "expected_source_revision": 1,
                "expected_economy_stream_revision": 0,
                "command_id": "command:eligibility",
                "causation_id": "cause",
                "correlation_id": "corr",
                "submitted_at": "2026-08-31T00:00:00Z",
                "account_id": "account:caller",
                "amount": 1,
                "currency_ref": "currency:caller",
            }
        )


def test_inf2ao_catalog_and_event_schema_are_exact() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:economy-production-output-market-eligibility@1",
        contract_kind="lifecycle",
    )
    assert contract.owner_ref == "actor_gameplay.economy_domain"
    assert contract.stream_patterns == ("gameplay:economy",)
    assert contract.event_types == ("gameplay.economy.production_output_market_eligible@1",)
    assert contract.projection_scope == "authority_only"
    descriptor = GovernedAuthorityContractCatalog.require_descriptor(
        "descriptor:economy-production-output-market-eligibility@1"
    )
    assert descriptor.capability_ref == "capability:economy-production-output-market-eligibility@1"
    assert descriptor.target_event_types == ("gameplay.economy.production_output_market_eligible@1",)

    schemas = EventSchemaRegistry()
    register_inf2ao_production_output_market_eligibility_event_schemas(schemas)
    assert schemas.get("gameplay.economy.production_output_market_eligible@1", 1).schema_digest.startswith("sha256:")
