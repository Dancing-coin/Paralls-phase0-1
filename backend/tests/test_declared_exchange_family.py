from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.gameplay.closed_generic_gameplay_families import DeclaredExchangeIntent
from app.gameplay.economy_runtime import EconomyRuntimeError
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from test_inf2ad_municipal_drought_assessment_exchange import (
    OUTCOME as MUNICIPAL_OUTCOME,
    PROVIDER as MUNICIPAL_PROVIDER,
    RECEIVER as MUNICIPAL_RECEIVER,
    _setup as _municipal_setup,
)
from test_inf2ag_public_workshop_service_exchange import (
    OUTCOME as WORKSHOP_OUTCOME,
    PROVIDER as WORKSHOP_PROVIDER,
    _setup as _workshop_setup,
)
from test_inf2am_reinforced_mill_flour_output_purchase import (
    PROVIDER,
    PROVIDER_CONTAINER,
    RECEIVER,
    _certified_source,
    _economy_setup,
    _inventory_setup,
)

MANIFEST_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-2"
)
FAMILY_MANIFEST_DIR = MANIFEST_DIR.parent / "closed-generic" / "declared-exchange"


def _prepared_case():
    store, certification_event = _certified_source()
    inventory_registry, inventory = _inventory_setup(store)
    generic = inventory.record_output_receipt(
        command_id="declared-exchange:generic-output",
        actor_ref=PROVIDER,
        source_ref="source:declared-exchange:generic-output",
        item_ref="item:industrial-facilities:flour@1",
        item_id="item:declared-exchange:generic-output",
        definition_id="item:industrial-facilities:flour@1",
        container_id=PROVIDER_CONTAINER,
        quantity=10,
        idempotency_key="declared-exchange:generic-output",
        causation_id="cause:declared-exchange:bootstrap",
        correlation_id="corr:declared-exchange:bootstrap",
    )
    assert generic.committed, generic.failure
    source = inventory.record_reinforced_mill_flour_output_receipt(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(
            f"gameplay:inventory:{PROVIDER}"
        ),
        command_id="declared-exchange:source",
        idempotency_key=(
            "inventory:reinforced-mill-flour-output:"
            f"{certification_event.event_id}:{certification_event.stream_revision}:v1"
        ),
        causation_id=certification_event.event_id,
        correlation_id="corr:declared-exchange:source",
    )
    assert source.committed, source.failure
    source_event = store.get_event(source.committed_event_ids[0])
    economy = _economy_setup(
        store=store,
        inventory_registry=inventory_registry,
        inventory=inventory,
    )
    return store, economy, source_event


def _intent(source_event, **updates: object) -> DeclaredExchangeIntent:
    values: dict[str, object] = {
        "source_event_id": source_event.event_id,
        "expected_source_revision": source_event.stream_revision,
        "command_id": "declared-exchange:command",
        "causation_id": source_event.event_id,
        "correlation_id": "declared-exchange:correlation",
        "submitted_at": "2026-08-30T00:00:00Z",
    }
    values.update(updates)
    return DeclaredExchangeIntent.model_validate(values)


def _family_economy(source_economy, *, store, paths: tuple[Path, ...]) -> object:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifests = tuple(
        GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    )
    registry.install_many(manifests)
    registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    return source_economy.__class__(
        store=store,
        package_registry=registry,
        inventory_registry=getattr(source_economy, "_inventory_registry", None),
        inventory_authority=getattr(source_economy, "_inventory_authority", None),
        contract_authority=getattr(source_economy, "_contract_authority", None),
    )


def _family_manifest(*, binding_requests: list[dict[str, object]]) -> GameplayPatchManifest:
    package_revision = "package:declared-exchange-admission-test@1"
    definition_ref = "definition:declared-exchange-admission-test@1"
    declaration_ref = "declaration:declared-exchange-admission-test@1"
    declaration = {
        "declaration_ref": declaration_ref,
        "outcome_family_ref": "outcome:declared-exchange@1",
        "definition_refs": [definition_ref],
        "eligibility_refs": ["eligibility:declared-exchange@1"],
        "policy_revision_ref": "policy:declared-exchange@1",
        "source_package_revision": package_revision,
    }
    declaration["declaration_digest"] = "sha256:" + sha256(
        json.dumps(
            {key: value for key, value in declaration.items() if key != "declaration_digest"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    raw = {
        "manifest_schema_version": 2,
        "patch_id": "package:declared-exchange-admission-test",
        "patch_version": "1.0.0",
        "patch_revision_id": package_revision,
        "content_digest": "sha256:" + "0" * 64,
        "author_id": "author:repo",
        "trust_policy_ref": "trust:repo",
        "dependencies": [],
        "state_group_ids": [],
        "state_group_migrations": [],
        "event_schemas": [],
        "rules": [],
        "requested_capabilities": [],
        "economic_outcomes": [],
        "granted_effect_types": [],
        "verification_profiles": [],
        "platform_extension": {
            "platform_schema_version": "1.0",
            "package_identity": {
                "package_id": "package:declared-exchange-admission-test",
                "package_version": "1.0.0",
                "package_revision": package_revision,
            },
            "package_definitions": [
                {
                    "definition_ref": definition_ref,
                    "definition_schema_ref": "schema:declared-exchange@1",
                    "source_package_revision": package_revision,
                    "typed_content": {
                        "outcome_ref": "outcome:declared-exchange-item@1",
                        "tradeable_definition_ref": "definition:industrial-facilities-flour@1",
                        "policy_revision_ref": "policy:declared-exchange@1",
                        "eligibility_refs": ["eligibility:declared-exchange@1"],
                    },
                }
            ],
            "outcome_declarations": [declaration],
            "capability_binding_requests": binding_requests,
            "dependency_and_conflict_refs": [],
            "replay_reader_refs": [],
            "verification_profile_refs": [],
        },
    }
    manifest = GameplayPatchManifest.model_validate(raw)
    return manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})


@pytest.mark.parametrize(
    "binding_requests",
    [
        [],
        [
            {
                "binding_ref": "binding:declared-exchange-admission-test@1",
                "capability_ref": "capability:package-declared-negotiated-exchange@1",
                "source_package_revision": "package:declared-exchange-admission-test@1",
                "declaration_ref": "declaration:declared-exchange-admission-test@1",
                "typed_read_requirements": [
                    {
                        "requirement_ref": "requirement:declared-exchange-source@1",
                        "predicate_family_ref": "predicate:declared-source-evidence@1",
                        "subject_slot_ref": "slot:tradeable-or-service@1",
                    }
                ],
                "proposal_effect_types": ["effect:declared-exchange@1"],
            }
        ],
    ],
    ids=("missing_family_binding", "legacy_capability_mismatch"),
)
def test_declared_exchange_activation_rejects_missing_or_mismatched_family_binding(
    binding_requests: list[dict[str, object]],
) -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _family_manifest(binding_requests=binding_requests)
    registry.install(manifest)

    with pytest.raises(ValueError, match="patch_capability_binding_(missing|mismatch|unknown)"):
        registry.activate((manifest.patch_revision_id,))


def test_declared_exchange_derives_item_parties_and_price_from_committed_source() -> None:
    store, economy, source = _prepared_case()

    result = economy.settle_declared_exchange(intent=_intent(source))

    assert result.committed, result.failure
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    settlement = next(
        event
        for event in events
        if event.event_type
        == "gameplay.economy.package_declared_negotiated_exchange_settled"
    )
    assert settlement.visibility_policy == "authority_only"
    assert settlement.payload["family_ref"] == "declared_exchange@1"
    assert settlement.payload["provider_ref"] == PROVIDER
    assert settlement.payload["receiver_ref"] == RECEIVER
    assert settlement.payload["amount_minor"] == 8
    assert settlement.payload["currency_ref"] == "currency:local"
    assert settlement.payload["source_event_ids"] == [source.event_id]
    assert settlement.payload["package_revision_id"] == "package:industrial-facilities:v7"


@pytest.mark.parametrize(
    (
        "setup",
        "expected_package_revision",
        "expected_outcome_ref",
        "expected_provider_ref",
        "expected_receiver_ref",
        "expected_amount_minor",
    ),
    [
        (
            _prepared_case,
            "package:industrial-facilities:v7",
            "outcome:industrial-facility-reinforced-mill-flour-output-purchase@1",
            PROVIDER,
            RECEIVER,
            8,
        ),
        (
            _workshop_setup,
            "package:industrial-facilities:v5",
            WORKSHOP_OUTCOME,
            WORKSHOP_PROVIDER,
            "organization:mill",
            12,
        ),
        (
            _municipal_setup,
            "package:municipal-drought-services:v1",
            MUNICIPAL_OUTCOME,
            MUNICIPAL_PROVIDER,
            MUNICIPAL_RECEIVER,
            12,
        ),
    ],
    ids=("inventory_item_v7", "completed_service_v5", "completed_service_municipal_v1"),
)
def test_declared_exchange_uses_same_adapter_for_distinct_committed_item_and_service_rows(
    setup,
    expected_package_revision: str,
    expected_outcome_ref: str,
    expected_provider_ref: str,
    expected_receiver_ref: str,
    expected_amount_minor: int,
) -> None:
    prepared = setup()
    if setup is _prepared_case:
        store, economy, source = prepared
        expected_source_event_ids = [source.event_id]
    else:
        store, economy, *_rest = prepared
        contract_events = store.read_stream("gameplay:contracts")
        expected_source_event_ids = [contract_events[-2].event_id, contract_events[-1].event_id]
        source = store.read_stream("gameplay:contracts")[-1]
        assert source.event_type == "gameplay.contract.record_fulfilled"
        assert source.visibility_policy == "authority_only"

    result = economy.settle_declared_exchange(intent=_intent(source))

    assert result.committed, result.failure
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    settlement = next(
        event
        for event in events
        if event.event_type
        == "gameplay.economy.package_declared_negotiated_exchange_settled"
    )
    assert settlement.payload["family_ref"] == "declared_exchange@1"
    assert settlement.payload["package_revision_id"] == expected_package_revision
    assert settlement.payload["outcome_ref"] == expected_outcome_ref
    assert settlement.payload["provider_ref"] == expected_provider_ref
    assert settlement.payload["receiver_ref"] == expected_receiver_ref
    assert settlement.payload["amount_minor"] == expected_amount_minor
    assert settlement.payload["source_event_ids"] == expected_source_event_ids


@pytest.mark.parametrize(
    ("setup", "family_manifest", "expected_package_revision", "expected_source_mode"),
    [
        (
            _prepared_case,
            FAMILY_MANIFEST_DIR / "package-declared-exchange-item-v7.manifest.json",
            "package:declared-exchange:item-v7@1",
            "inventory_custody@1",
        ),
        (
            _workshop_setup,
            FAMILY_MANIFEST_DIR / "package-declared-exchange-service-v5.manifest.json",
            "package:declared-exchange:service-v5@1",
            "completed_service@1",
        ),
    ],
    ids=("admitted_item_content", "admitted_service_content"),
)
def test_declared_exchange_family_admits_distinct_content_and_replays_through_one_adapter(
    setup,
    family_manifest: Path,
    expected_package_revision: str,
    expected_source_mode: str,
) -> None:
    prepared = setup()
    if setup is _prepared_case:
        store, source_economy, source = prepared
    else:
        store, source_economy, *_rest = prepared
        source = store.read_stream("gameplay:contracts")[-1]
        assert source.event_type == "gameplay.contract.record_fulfilled"
    economy = _family_economy(
        source_economy,
        store=store,
        paths=(
            FAMILY_MANIFEST_DIR / "package-declared-exchange-item-v7.manifest.json",
            FAMILY_MANIFEST_DIR / "package-declared-exchange-service-v5.manifest.json",
        ),
    )

    first = economy.settle_declared_exchange(intent=_intent(source))
    assert first.committed, first.failure
    settlement = next(
        store.get_event(event_id)
        for event_id in first.committed_event_ids
        if store.get_event(event_id).event_type
        == "gameplay.economy.package_declared_negotiated_exchange_settled"
    )
    assert settlement.payload["family_ref"] == "declared_exchange@1"
    assert settlement.payload["package_revision_id"] == expected_package_revision
    assert settlement.payload["source_evidence_mode"] == expected_source_mode

    before = store.export_snapshot()
    replay = economy.settle_declared_exchange(intent=_intent(source))
    assert replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before


def test_declared_exchange_is_caller_minimal_and_rejects_authority_coordinates() -> None:
    with pytest.raises(Exception):
        DeclaredExchangeIntent.model_validate(
            {
                "source_event_id": "event:source",
                "expected_source_revision": 1,
                "command_id": "command:declared-exchange",
                "causation_id": "cause:declared-exchange",
                "correlation_id": "corr:declared-exchange",
                "submitted_at": "2026-08-30T00:00:00Z",
                "provider_ref": "caller-provider",
                "receiver_ref": "caller-receiver",
                "amount_minor": 99,
                "currency_ref": "currency:caller",
                "idempotency_key": "caller-idempotency",
            }
        )


def test_declared_exchange_replays_duplicate_and_changed_duplicate_without_writes() -> None:
    store, economy, source = _prepared_case()
    intent = _intent(source)

    first = economy.settle_declared_exchange(intent=intent)
    assert first.committed, first.failure
    before = store.export_snapshot()

    duplicate = economy.settle_declared_exchange(intent=intent)
    changed = economy.settle_declared_exchange(
        intent=intent.model_copy(update={"correlation_id": "declared-exchange:changed"})
    )

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_declared_exchange_source_privacy_and_revision_fail_before_append() -> None:
    store, economy, source = _prepared_case()
    private = store.get_event(source.event_id).model_copy(
        update={"visibility_policy": "authority_only"}, deep=True
    )
    store._events_by_id[source.event_id] = private
    store._events = [
        private if event.event_id == source.event_id else event
        for event in store._events
    ]
    before = store.export_snapshot()

    rejected = economy.settle_declared_exchange(intent=_intent(source))

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "declared_exchange_source_invalid"
    assert store.export_snapshot() == before

    store, economy, source = _prepared_case()
    before = store.export_snapshot()
    stale = economy.settle_declared_exchange(
        intent=_intent(source, expected_source_revision=source.stream_revision - 1)
    )

    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "declared_exchange_source_revision_invalid"
    assert store.export_snapshot() == before


def test_declared_exchange_receipt_and_checkpoint_tail_replay_are_append_derived() -> None:
    store, economy, source = _prepared_case()
    result = economy.settle_declared_exchange(intent=_intent(source))
    assert result.committed, result.failure

    receipt = economy.declared_exchange_receipt_for(result=result, scope="authority")
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    full = economy.declared_exchange_projection(scope="authority")
    tail = economy.declared_exchange_projection(
        scope="authority", checkpoint_at=result.global_sequence_range[-1]
    )
    assert full == tail
    with pytest.raises(EconomyRuntimeError, match="declared_exchange_receipt_scope_denied"):
        economy.declared_exchange_receipt_for(result=result, scope="project")


def test_declared_exchange_generic_output_received_remains_zero_write_blocker() -> None:
    store, economy, source = _prepared_case()
    generic_source = next(
        event for event in store.read_events() if event.event_type == "gameplay.inventory.output_received"
    )
    before = store.export_snapshot()

    result = economy.settle_declared_exchange(intent=_intent(generic_source))

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "declared_exchange_source_invalid"
    assert store.export_snapshot() == before


def test_declared_exchange_family_manifests_are_exactly_bound_and_digest_valid() -> None:
    manifests = [
        GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(FAMILY_MANIFEST_DIR.glob("*.manifest.json"))
    ]
    assert [manifest.patch_revision_id for manifest in manifests] == [
        "package:declared-exchange:item-v7@1",
        "package:declared-exchange:service-v5@1",
    ]
    assert all(manifest.content_digest == manifest.expected_content_digest() for manifest in manifests)
    assert all(
        len(manifest.platform_extension.capability_binding_requests) == 1
        and manifest.platform_extension.capability_binding_requests[0].capability_ref
        == "capability:declared-exchange@1"
        for manifest in manifests
    )
