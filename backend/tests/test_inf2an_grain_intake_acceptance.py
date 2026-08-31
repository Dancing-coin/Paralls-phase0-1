from __future__ import annotations

import pytest

from app.gameplay.event_schema_registry import (
    EventSchemaRegistry,
    register_inf2an_grain_intake_acceptance_event_schemas,
)
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.organization_government_runtime import OrganizationAuthority
from test_inf4ap_grain_intake_activity import PROVIDER, _custody, _request_org


EVENT = "gameplay.economy.grain_intake_accepted@1"


def _intake():
    store, custody = _custody()
    result = OrganizationAuthority(store=store).record_grain_intake_from_inventory(
        **_request_org(store, custody)
    )
    assert result.committed, result.failure
    return store, store.get_event(result.committed_event_ids[0])


def test_inf2an_records_exact_authority_only_grain_intake_acceptance() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)

    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:accept",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an",
        submitted_at="2026-08-29T00:00:00Z",
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == EVENT
    assert event.visibility_policy == "authority_only"
    assert event.stream_id == "gameplay:economy"
    assert event.payload["organization_ref"] == PROVIDER
    assert event.payload["project_ref"] == intake.payload["project_ref"]
    assert event.payload["item_ref"] == "grain:wheat@1"
    assert event.payload["quantity"] == 10
    assert event.payload["status"] == "accepted"


def test_inf2an_duplicate_changed_duplicate_and_replay_are_bounded() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    request = {
        "source_event_id": intake.event_id,
        "expected_source_revision": intake.stream_revision,
        "expected_economy_stream_revision": store.get_stream_head("gameplay:economy"),
        "command_id": "inf2an:accept:first",
        "idempotency_key": (
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        "causation_id": intake.event_id,
        "correlation_id": "corr:inf2an",
        "submitted_at": "2026-08-29T00:00:00Z",
    }
    first = economy.record_grain_intake_acceptance(**request)
    assert first.committed
    before = store.export_snapshot()

    duplicate = economy.record_grain_intake_acceptance(**request)
    changed = economy.record_grain_intake_acceptance(
        **{**request, "correlation_id": "corr:inf2an:changed"}
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "economy_grain_intake_acceptance_idempotency_key_reused"
    assert store.export_snapshot() == before
    receipt = economy.grain_intake_acceptance_receipt_for(result=first, scope="authority")
    assert receipt.committed_event_ids == tuple(first.committed_event_ids)


def test_inf2an_private_or_stale_organization_source_is_zero_write() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    private = intake.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[intake.event_id] = private
    before = store.export_snapshot()
    rejected = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:private",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:private",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "economy_grain_intake_acceptance_source_invalid"
    assert store.export_snapshot() == before


def test_inf2an_wrong_source_owner_stream_is_zero_write() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    forged = intake.model_copy(
        update={"stream_id": "gameplay:organization:organization:forged"},
        deep=True,
    )
    store._events_by_id[intake.event_id] = forged
    store._events = [forged if event.event_id == intake.event_id else event for event in store._events]
    before = store.export_snapshot()

    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:wrong-source-stream",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:wrong-source-stream",
        submitted_at="2026-08-29T00:00:00Z",
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "economy_grain_intake_acceptance_source_invalid"
    assert store.export_snapshot() == before


def test_inf2an_boolean_revision_pins_are_zero_write() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    before = store.export_snapshot()
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=True,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:boolean-revision",
        idempotency_key="inf2an:boolean-revision",
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:boolean-revision",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "economy_grain_intake_acceptance_reference_invalid"
    assert store.export_snapshot() == before


def test_inf2an_stale_inventory_source_is_zero_write() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    inventory_event_id = intake.payload["source_inventory_event_id"]
    inventory_event = store.get_event(inventory_event_id)
    store._events_by_id[inventory_event_id] = inventory_event.model_copy(
        update={"stream_revision": inventory_event.stream_revision - 1}, deep=True
    )
    store._events = [
        store._events_by_id.get(event.event_id, event) for event in store._events
    ]
    before = store.export_snapshot()
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:stale-inventory",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:stale-inventory",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "economy_grain_intake_acceptance_source_invalid"
    assert store.export_snapshot() == before

    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    before = store.export_snapshot()
    stale = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision - 1,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:stale",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision - 1}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:stale",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "economy_grain_intake_acceptance_reference_invalid"
    assert store.export_snapshot() == before


def test_inf2an_full_and_checkpoint_tail_replay_match() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:replay",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:replay",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    full = economy.grain_intake_acceptance_projection(scope="authority")
    tail = economy.grain_intake_acceptance_projection(
        scope="authority",
        checkpoint_at=event.global_sequence,
    )
    assert full == tail
    assert full["acceptance_refs"] == (event.payload["acceptance_ref"],)


def test_inf2an_acceptance_marker_does_not_mutate_economy_accounts() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    before_events = tuple(
        event.event_id
        for event in store.read_stream("gameplay:economy")
        if event.event_type.startswith("gameplay.economy.account_")
    )
    before_accounts = dict(economy._projector.rebuild(store.read_events()).accounts)

    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:no-account-mutation",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:no-account-mutation",
        submitted_at="2026-08-29T00:00:00Z",
    )

    assert result.committed, result.failure
    after_events = tuple(
        event.event_id
        for event in store.read_stream("gameplay:economy")
        if event.event_type.startswith("gameplay.economy.account_")
    )
    after_accounts = dict(economy._projector.rebuild(store.read_events()).accounts)
    assert after_events == before_events
    assert after_accounts == before_accounts


def test_inf2an_projector_rejects_forged_source_or_payload() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:forged",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:forged",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert result.committed
    event_id = result.committed_event_ids[0]
    forged = store.get_event(event_id).model_copy(
        update={"payload": {**store.get_event(event_id).payload, "quantity": 9}},
        deep=True,
    )
    store._events_by_id[event_id] = forged
    store._events = [forged if event.event_id == event_id else event for event in store._events]
    with pytest.raises(ValueError, match="grain_intake_acceptance_projection_source_invalid"):
        economy.grain_intake_acceptance_projection(scope="authority")


def test_inf2an_projector_rejects_target_revision_pin_mismatch() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:forged-target-revision",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:forged-target-revision",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert result.committed
    event_id = result.committed_event_ids[0]
    original = store.get_event(event_id)
    forged = original.model_copy(
        update={"payload": {**original.payload, "economy_stream_head": original.stream_revision + 1}},
        deep=True,
    )
    store._events_by_id[event_id] = forged
    store._events = [forged if event.event_id == event_id else event for event in store._events]
    with pytest.raises(ValueError, match="grain_intake_acceptance_projection_source_invalid"):
        economy.grain_intake_acceptance_projection(scope="authority")


def test_inf2an_nested_boolean_source_revision_is_zero_write_and_replay_rejects() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    source_org_id = intake.event_id
    source_org = store.get_event(source_org_id)
    source_org_forged = source_org.model_copy(
        update={"payload": {**source_org.payload, "source_inventory_revision": True}},
        deep=True,
    )
    store._events_by_id[source_org_id] = source_org_forged
    store._events = [
        source_org_forged if event.event_id == source_org_id else event
        for event in store._events
    ]
    before = store.export_snapshot()
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:nested-bool-source-revision",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:nested-bool-source-revision",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "economy_grain_intake_acceptance_source_invalid"
    assert store.export_snapshot() == before

    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:nested-bool-source-revision-replay",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:nested-bool-source-revision-replay",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert result.committed
    event_id = result.committed_event_ids[0]
    original = store.get_event(event_id)
    forged = original.model_copy(
        update={"payload": {**original.payload, "source_inventory_revision": True}},
        deep=True,
    )
    store._events_by_id[event_id] = forged
    store._events = [forged if event.event_id == event_id else event for event in store._events]
    with pytest.raises(ValueError, match="grain_intake_acceptance_projection_source_invalid"):
        economy.grain_intake_acceptance_projection(scope="authority")


def test_inf2an_replay_rejects_forged_causation_binding() -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2an:forged-causation",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id="corr:inf2an:forged-causation",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert result.committed
    event_id = result.committed_event_ids[0]
    original = store.get_event(event_id)
    forged = original.model_copy(update={"causation_id": "event:forged"}, deep=True)
    store._events_by_id[event_id] = forged
    store._events = [forged if event.event_id == event_id else event for event in store._events]
    with pytest.raises(ValueError, match="grain_intake_acceptance_projection_source_invalid"):
        economy.grain_intake_acceptance_projection(scope="authority")


@pytest.mark.parametrize(
    "field,value",
    [
        ("acceptance_ref", ""),
        ("project_ref", "plot:forged"),
        ("source_inventory_revision", True),
    ],
)
def test_inf2an_replay_rejects_forged_binding_fields(field: str, value: object) -> None:
    store, intake = _intake()
    economy = EconomyAuthorityService(store=store)
    result = economy.record_grain_intake_acceptance(
        source_event_id=intake.event_id,
        expected_source_revision=intake.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id=f"inf2an:forged:{field}",
        idempotency_key=(
            f"economy:grain-intake-acceptance:{intake.event_id}:"
            f"{intake.stream_revision}:{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id=intake.event_id,
        correlation_id=f"corr:inf2an:forged:{field}",
        submitted_at="2026-08-29T00:00:00Z",
    )
    assert result.committed
    event_id = result.committed_event_ids[0]
    original = store.get_event(event_id)
    forged = original.model_copy(
        update={"payload": {**original.payload, field: value}},
        deep=True,
    )
    store._events_by_id[event_id] = forged
    store._events = [forged if event.event_id == event_id else event for event in store._events]
    with pytest.raises(ValueError, match="grain_intake_acceptance_projection_source_invalid"):
        economy.grain_intake_acceptance_projection(scope="authority")


def test_inf2an_catalog_row_and_event_schema_are_exact() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:economy-grain-intake-acceptance@1",
        contract_kind="lifecycle",
    )
    assert contract.owner_ref == "actor_gameplay.economy_domain"
    assert contract.stream_patterns == ("gameplay:economy",)
    assert contract.event_types == ("gameplay.economy.grain_intake_accepted@1",)
    assert contract.projection_scope == "authority_only"
    assert contract.replay_reader_ref == "EconomyAuthorityService.grain_intake_acceptance_projection"

    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref == "descriptor:economy-grain-intake-acceptance@1"
    )
    assert descriptor.capability_ref == "capability:economy-grain-intake-acceptance@1"
    assert descriptor.outcome_family_ref == "outcome:economy-grain-intake-accepted@1"
    assert descriptor.allowed_predicate_family_refs == (
        "predicate:organization-grain-intake-recorded@1",
    )
    assert descriptor.allowed_proposal_effect_types == (
        "effect:economy-grain-intake-accepted@1",
    )

    registry = EventSchemaRegistry()
    register_inf2an_grain_intake_acceptance_event_schemas(registry)
    assert registry.get(EVENT, 1).schema_digest.startswith("sha256:")
