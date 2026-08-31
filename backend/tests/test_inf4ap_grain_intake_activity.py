from __future__ import annotations

import pytest

from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.event_schema_registry import EventSchemaRegistry, register_inf4ap_grain_intake_event_schemas
from test_inf3ab_grain_harvest_inventory_custody import (
    PROVIDER,
    _inventory,
    _request,
    _source,
)


EVENT = "gameplay.organization.grain_intake_recorded@1"
ORG_STREAM = f"gameplay:organization:{PROVIDER}"


def _custody():
    store, harvest = _source()
    inventory = _inventory(store)
    receipt = inventory.record_grain_harvest_custody_receipt(**_request(store, harvest))
    assert receipt.committed, receipt.failure
    return store, store.get_event(receipt.committed_event_ids[0])


def _request_org(store, custody, **updates: object) -> dict[str, object]:
    inventory_revision = custody.stream_revision
    organization_revision = store.get_stream_head(ORG_STREAM)
    values: dict[str, object] = {
        "inventory_event_id": custody.event_id,
        "expected_inventory_revision": inventory_revision,
        "expected_organization_revision": organization_revision,
        "command_id": "inf4ap:grain-intake",
        "idempotency_key": f"organization:grain-intake:{custody.event_id}:{inventory_revision}:{organization_revision}:v1",
        "causation_id": custody.event_id,
        "correlation_id": "corr:inf4ap",
        "submitted_at": "2026-08-29T00:00:00Z",
    }
    values.update(updates)
    return values


def test_inf4ap_records_exact_project_grain_intake() -> None:
    store, custody = _custody()
    result = OrganizationAuthority(store=store).record_grain_intake_from_inventory(
        **_request_org(store, custody)
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == EVENT
    assert event.visibility_policy == "project"
    assert event.stream_id == ORG_STREAM
    assert event.payload["organization_ref"] == PROVIDER
    assert event.payload["project_ref"] == custody.payload["project_ref"]
    assert event.payload["item_ref"] == "grain:wheat@1"
    assert event.payload["quantity"] == 10
    assert event.payload["source_inventory_event_id"] == custody.event_id


def test_inf4ap_duplicate_and_changed_duplicate_are_zero_write() -> None:
    store, custody = _custody()
    authority = OrganizationAuthority(store=store)
    request = _request_org(store, custody)
    first = authority.record_grain_intake_from_inventory(**request)
    assert first.committed
    before = store.export_snapshot()

    duplicate = authority.record_grain_intake_from_inventory(**request)
    changed = authority.record_grain_intake_from_inventory(
        **{**request, "correlation_id": "corr:inf4ap:changed"}
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_inf4ap_rejects_private_or_stale_inventory_source() -> None:
    store, custody = _custody()
    authority = OrganizationAuthority(store=store)
    private = custody.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[custody.event_id] = private
    before = store.export_snapshot()
    rejected = authority.record_grain_intake_from_inventory(**_request_org(store, custody))
    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "organization_grain_intake_source_invalid"
    assert store.export_snapshot() == before

    store, custody = _custody()
    authority = OrganizationAuthority(store=store)
    store._stream_heads[custody.stream_id] = custody.stream_revision + 1
    before = store.export_snapshot()
    stale = authority.record_grain_intake_from_inventory(**_request_org(store, custody))
    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "organization_grain_intake_source_invalid"
    assert store.export_snapshot() == before


def test_inf4ap_unknown_source_and_wrong_key_are_zero_write() -> None:
    store, custody = _custody()
    authority = OrganizationAuthority(store=store)
    before = store.export_snapshot()
    missing = authority.record_grain_intake_from_inventory(
        **_request_org(store, custody, inventory_event_id="event:missing")
    )
    assert not missing.committed
    assert missing.failure is not None
    assert missing.failure.error_code == "organization_grain_intake_source_missing"
    wrong_key = authority.record_grain_intake_from_inventory(
        **_request_org(store, custody, idempotency_key="caller-selected")
    )
    assert not wrong_key.committed
    assert wrong_key.failure is not None
    assert wrong_key.failure.error_code == "organization_grain_intake_idempotency_key_invalid"
    assert store.export_snapshot() == before


def test_inf4ap_full_and_checkpoint_tail_replay_match() -> None:
    store, custody = _custody()
    authority = OrganizationAuthority(store=store)
    result = authority.record_grain_intake_from_inventory(**_request_org(store, custody))
    assert result.committed
    full = authority.grain_intake_view_for(organization_ref=PROVIDER)
    tail = authority.grain_intake_view_for(
        organization_ref=PROVIDER,
        checkpoint_at=custody.global_sequence,
    )
    assert full == tail
    assert custody.stream_id in full.source_revision_vector


def test_inf4ap_uses_separate_append_receipt_without_mutating_inventory() -> None:
    store, custody = _custody()
    authority = OrganizationAuthority(store=store)
    inventory_events_before = tuple(
        event.event_id
        for event in store.read_stream(custody.stream_id)
    )
    result = authority.record_grain_intake_from_inventory(**_request_org(store, custody))
    assert result.committed
    receipt = authority.grain_intake_receipt_for(result=result, scope="project")
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert tuple(event.event_id for event in store.read_stream(custody.stream_id)) == inventory_events_before
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["source_inventory_revision"] == custody.stream_revision


def test_inf4ap_catalog_row_is_exact() -> None:
    from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog

    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:organization-grain-intake@1",
        contract_kind="contract_admission",
    )
    assert contract.owner_ref == "actor_gameplay.organization_domain"
    assert contract.stream_patterns == ("gameplay:organization:{organization_ref}",)
    assert contract.event_types == (EVENT,)
    assert contract.projection_scope == "project"


def test_inf4ap_event_schema_is_registered_exactly() -> None:
    registry = EventSchemaRegistry()
    register_inf4ap_grain_intake_event_schemas(registry)
    assert registry.get(EVENT, 1).schema_digest.startswith("sha256:")
