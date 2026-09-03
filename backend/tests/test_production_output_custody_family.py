from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.gameplay.closed_generic_gameplay_families import (
    ProductionOutputCustodyIntent,
)
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    ItemDefinition,
    InventoryRuntimeError,
)
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from closed_generic_manifest_fixtures import load_manifest
from test_production_output_certification_family import (
    _intent as certification_intent,
    _kiln_intent,
    _kiln_setup,
    _mill_intent,
    _mill_setup,
    _setup,
)


def _digest(value: object) -> str:
    return "sha256:" + sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _custody_manifest(
    *,
    package_id: str,
    package_revision: str,
    definition_ref: str,
    output_item_ref: str,
    holder_binding_ref: str,
    container_binding_ref: str,
    policy_revision: str,
) -> GameplayPatchManifest:
    declaration_ref = f"declaration:{package_id}@1"
    definition = {
        "definition_ref": definition_ref,
        "definition_schema_ref": "schema:production-output-custody@1",
        "source_package_revision": package_revision,
        "typed_content": {
            "output_item_definition_ref": output_item_ref,
            "holder_binding_ref": holder_binding_ref,
            "container_binding_ref": container_binding_ref,
            "policy_revision_ref": policy_revision,
        },
    }
    declaration = {
        "declaration_ref": declaration_ref,
        "outcome_family_ref": "outcome:production-output-custody@1",
        "definition_refs": [definition_ref],
        "eligibility_refs": ["predicate:construction-production-output-certified@1"],
        "policy_revision_ref": policy_revision,
        "source_package_revision": package_revision,
    }
    declaration["declaration_digest"] = _digest(declaration)
    raw = {
        "manifest_schema_version": 2,
        "patch_id": package_id,
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
                "package_id": package_id,
                "package_version": "1.0.0",
                "package_revision": package_revision,
            },
            "package_definitions": [definition],
            "outcome_declarations": [declaration],
            "capability_binding_requests": [
                {
                    "binding_ref": f"binding:{package_id}@1",
                    "capability_ref": "capability:production-output-custody@1",
                    "source_package_revision": package_revision,
                    "declaration_ref": declaration_ref,
                    "typed_read_requirements": [
                        {
                            "requirement_ref": f"requirement:{package_id}@1",
                            "predicate_family_ref": "predicate:construction-production-output-certified@1",
                            "subject_slot_ref": "slot:output-item@1",
                        }
                    ],
                    "proposal_effect_types": ["effect:production-output-custody@1"],
                }
            ],
            "dependency_and_conflict_refs": [],
            "replay_reader_refs": [],
            "verification_profile_refs": [],
        },
    }
    manifest = GameplayPatchManifest.model_validate(raw)
    return manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})


def _family_registry(*manifests: GameplayPatchManifest) -> GameplayPatchRegistry:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install_many(manifests)
    registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    return registry


def _inventory_for_certification(
    store: GameplayEventStore,
    *,
    package_registry: GameplayPatchRegistry,
    holder_ref: str,
    item_ref: str,
    container_id: str,
) -> InventoryAuthorityService:
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition(item_ref, "1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry, package_registry=package_registry)
    created = inventory.create_container(
        command_id=f"custody:container:{holder_ref}",
        actor_ref=holder_ref,
        spec=ContainerSpec(container_id, 100, 100, 4),
        idempotency_key=f"custody:container:{holder_ref}",
        causation_id="custody:bootstrap",
        correlation_id="custody:bootstrap",
    )
    assert created.committed, created.failure
    return inventory


@pytest.mark.parametrize(
    ("setup", "cert_intent", "package_id", "package_revision", "definition_ref", "item_ref", "holder_ref", "container_id", "policy"),
    [
        (
            _setup,
            certification_intent,
            "production-output-custody-bread",
            "package:production-output-custody:bread@1",
            "definition:production-output-custody-bread@1",
            "item:bread@1",
            "organization:bakery",
            "container:organization:bakery:production-output",
            "policy:inventory-production-output-custody@1",
        ),
        (
            _mill_setup,
            _mill_intent,
            "production-output-custody-flour",
            "package:production-output-custody:flour@1",
            "definition:production-output-custody-flour@1",
            "item:industrial-facilities:flour@1",
            "org:mill:1",
            "container:org:mill:1:stores",
            "policy:inventory-production-output-custody@1",
        ),
    ],
    ids=("bread", "flour"),
)
def test_production_output_custody_consumes_two_certified_contents_through_one_adapter(
    setup,
    cert_intent,
    package_id: str,
    package_revision: str,
    definition_ref: str,
    item_ref: str,
    holder_ref: str,
    container_id: str,
    policy: str,
) -> None:
    store, construction, finished_event_id = setup()
    certification_manifest = load_manifest(
        "production-output-certification-mill-demo-v1"
        if item_ref.endswith("flour@1")
        else "production-output-certification-demo-v1"
    )
    custody_manifest = _custody_manifest(
        package_id=package_id,
        package_revision=package_revision,
        definition_ref=definition_ref,
        output_item_ref=item_ref,
        holder_binding_ref=f"binding:holder:{holder_ref}@1",
        container_binding_ref=f"binding:container:{container_id}@1",
        policy_revision=policy,
    )
    registry = _family_registry(certification_manifest, custody_manifest)
    construction = ConstructionProductionAuthority(store=store, package_registry=registry)
    finished = store.get_event(finished_event_id)
    cert = construction.settle_production_output_certification(
        intent=cert_intent(finished_event_id)
    )
    assert cert.committed, cert.failure
    certification = store.get_event(cert.committed_event_ids[0])
    inventory = _inventory_for_certification(
        store, package_registry=registry, holder_ref=holder_ref, item_ref=item_ref, container_id=container_id
    )
    custody = inventory.settle_production_output_custody(
        intent=ProductionOutputCustodyIntent(
            certification_event_id=certification.event_id,
            expected_certification_revision=certification.stream_revision,
            expected_inventory_stream_revision=store.get_stream_head(
                f"gameplay:inventory:{holder_ref}"
            ),
            command_id=f"custody:{package_id}",
            correlation_id=f"custody:{package_id}",
            submitted_at="2026-08-31T00:00:00Z",
        )
    )
    assert custody.committed, custody.failure
    event = store.get_event(custody.committed_event_ids[0])
    assert event.event_type == "gameplay.inventory.production_output_received@1"
    assert event.payload["item_ref"] == item_ref
    assert event.payload["quantity"] == certification.payload["quantity"]
    assert event.payload["holder_ref"] == holder_ref
    assert event.payload["container_id"] == container_id
    assert event.payload["family_ref"] == "production_output_custody@1"
    assert event.payload["source_certification_provenance"]["package_revision"] == certification.payload["package_revision"]
    assert event.payload["source_certification_provenance"]["content_digest"] == certification.payload["content_digest"]
    assert event.payload["source_certification_provenance"]["declaration_digest"] == certification.payload["declaration_digest"]
    view = inventory.production_output_custody_view_for()
    tail_view = inventory.production_output_custody_view_for(checkpoint_at=certification.stream_revision)
    assert view["rows"] == tail_view["rows"]
    replay = inventory.settle_production_output_custody(
        intent=ProductionOutputCustodyIntent(
            certification_event_id=certification.event_id,
            expected_certification_revision=certification.stream_revision,
            expected_inventory_stream_revision=store.get_stream_head(
                f"gameplay:inventory:{holder_ref}"
            ) - 1,
            command_id=f"custody:{package_id}:replay",
            correlation_id=f"custody:{package_id}",
            submitted_at="2026-08-31T00:00:00Z",
        )
    )
    assert replay.committed
    assert replay.idempotency_status == "duplicate_replayed"


def test_production_output_custody_reader_rejects_checkpoint_beyond_store_head() -> None:
    inventory = InventoryAuthorityService(
        store=GameplayEventStore(),
        registry=InventoryDefinitionRegistry(),
    )

    with pytest.raises(InventoryRuntimeError, match="production_output_custody_checkpoint_invalid"):
        inventory.production_output_custody_view_for(checkpoint_at=1)


def test_production_output_custody_rejects_certification_without_provenance_before_append() -> None:
    store, construction, finished_event_id = _setup()
    certification = construction.settle_production_output_certification(
        intent=certification_intent(finished_event_id)
    )
    assert certification.committed
    certification_event = store.get_event(certification.committed_event_ids[0])
    tampered = certification_event.model_copy(
        update={
            "payload": {
                key: value
                for key, value in certification_event.payload.items()
                if key not in {"package_revision", "content_digest", "declaration_digest", "descriptor_ref", "descriptor_revision"}
            }
        },
        deep=True,
    )
    store._events[store._events.index(certification_event)] = tampered
    store._events_by_id[certification_event.event_id] = tampered
    inventory = _inventory_for_certification(
        store,
        package_registry=construction._package_registry,
        holder_ref="organization:bakery",
        item_ref="item:bread@1",
        container_id="container:organization:bakery:production-output",
    )
    result = inventory.settle_production_output_custody(
        intent=ProductionOutputCustodyIntent(
            certification_event_id=certification_event.event_id,
            expected_certification_revision=certification_event.stream_revision,
            expected_inventory_stream_revision=store.get_stream_head("gameplay:inventory:organization:bakery"),
            command_id="custody:missing-source-provenance",
            correlation_id="custody:missing-source-provenance",
            submitted_at="2026-08-31T00:00:00Z",
        )
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "production_output_custody_source_invalid"


def test_production_output_custody_supports_kiln_certified_output_with_same_adapter() -> None:
    store, construction, finished_event_id = _kiln_setup()
    certification_manifest = load_manifest("production-output-certification-kiln-demo-v1")
    custody_manifest = _custody_manifest(
        package_id="production-output-custody-kiln",
        package_revision="package:production-output-custody:kiln@1",
        definition_ref="definition:production-output-custody-kiln@1",
        output_item_ref="item:brick@1",
        holder_binding_ref="binding:holder:organization:kiln@1",
        container_binding_ref="binding:container:container:organization:kiln:production-output@1",
        policy_revision="policy:inventory-production-output-custody@1",
    )
    registry = _family_registry(certification_manifest, custody_manifest)
    construction = ConstructionProductionAuthority(store=store, package_registry=registry)
    certification = construction.settle_production_output_certification(
        intent=_kiln_intent(finished_event_id)
    )
    assert certification.committed, certification.failure
    certification_event = store.get_event(certification.committed_event_ids[0])
    inventory = _inventory_for_certification(
        store,
        package_registry=registry,
        holder_ref="organization:kiln",
        item_ref="item:brick@1",
        container_id="container:organization:kiln:production-output",
    )
    result = inventory.settle_production_output_custody(
        intent=ProductionOutputCustodyIntent(
            certification_event_id=certification_event.event_id,
            expected_certification_revision=certification_event.stream_revision,
            expected_inventory_stream_revision=store.get_stream_head("gameplay:inventory:organization:kiln"),
            command_id="custody:production-output-kiln",
            correlation_id="custody:production-output-kiln",
            submitted_at="2026-09-02T00:00:00Z",
        )
    )
    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["item_ref"] == "item:brick@1"
    assert event.payload["holder_ref"] == "organization:kiln"
    assert event.payload["container_id"] == "container:organization:kiln:production-output"
    assert inventory.production_output_custody_view_for()["rows"] == inventory.production_output_custody_view_for(
        checkpoint_at=certification_event.global_sequence
    )["rows"]
