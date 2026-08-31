from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.gameplay.closed_generic_gameplay_families import HARVEST_TO_CUSTODY_BLOCKER, HarvestToCustodyContent, HarvestToCustodyIntent
from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    ItemDefinition,
)
from app.gameplay.patch_runtime import (
    CapabilityBindingRequest,
    GameplayPatchManifest,
    GameplayPatchRegistry,
    OutcomeDeclarationAuthorInput,
    PackageDefinition,
    PackageIdentity,
    PlatformExtension,
    TypedReadRequirement,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from test_inf3_grain_harvest import _admit_envelope, _harvest_envelope, _seed
from test_inf3ab_grain_harvest_inventory_custody import _source as _narrow_source


def _digest(value: object) -> str:
    return "sha256:" + sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _holder_binding(holder_ref: str) -> str:
    return f"binding:holder:{holder_ref}@1"


def _container_binding(container_id: str) -> str:
    return f"binding:container:{container_id}@1"


def _manifest(
    *,
    package_revision: str,
    definition_ref: str,
    crop_definition_ref: str,
    item_definition_ref: str,
    holder_binding_ref: str,
    container_binding_ref: str,
    policy_revision_ref: str,
) -> GameplayPatchManifest:
    content = HarvestToCustodyContent(
        crop_definition_ref=crop_definition_ref,
        item_definition_ref=item_definition_ref,
        holder_binding_ref=holder_binding_ref,
        container_binding_ref=container_binding_ref,
        policy_revision_ref=policy_revision_ref,
    )
    definition = PackageDefinition(
        definition_ref=definition_ref,
        definition_schema_ref="schema:harvest-to-custody@1",
        source_package_revision=package_revision,
        typed_content=content.model_dump(mode="json"),
    )
    declaration_payload = {
        "declaration_ref": f"declaration:{package_revision.split(':', 1)[1]}",
        "outcome_family_ref": "outcome:harvest-to-custody@1",
        "definition_refs": (definition.definition_ref,),
        "eligibility_refs": ("predicate:ecology-grain-harvested@1",),
        "policy_revision_ref": policy_revision_ref,
        "source_package_revision": package_revision,
    }
    declaration = OutcomeDeclarationAuthorInput(
        **declaration_payload,
        declaration_digest=_digest(declaration_payload),
    ).normalized()
    request = CapabilityBindingRequest(
        binding_ref=f"binding:{package_revision.split(':', 1)[1]}",
        capability_ref="capability:harvest-to-custody@1",
        source_package_revision=package_revision,
        declaration_ref=declaration.declaration_ref,
        typed_read_requirements=(
            TypedReadRequirement(
                requirement_ref=f"requirement:{package_revision.split(':', 1)[1]}",
                predicate_family_ref="predicate:ecology-grain-harvested@1",
                subject_slot_ref="slot:crop@1",
            ),
        ),
        proposal_effect_types=("effect:harvest-to-custody@1",),
    )
    extension = PlatformExtension(
        platform_schema_version="1.0",
        package_identity=PackageIdentity(
            package_id=f"package:{package_revision.split(':', 1)[1].split('@', 1)[0]}",
            package_version="1.0.0",
            package_revision=package_revision,
        ),
        package_definitions=(definition,),
        outcome_declarations=(declaration.model_dump(mode="json"),),
        capability_binding_requests=(request,),
        dependency_and_conflict_refs=(),
        replay_reader_refs=(),
        verification_profile_refs=(),
    )
    manifest = GameplayPatchManifest.model_validate(
        {
            "manifest_schema_version": 2,
            "patch_id": extension.package_identity.package_id,
            "patch_version": "1.0.0",
            "patch_revision_id": package_revision,
            "content_digest": "sha256:" + "0" * 64,
            "author_id": "author:repo",
            "trust_policy_ref": "trust:repo",
            "dependencies": (),
            "state_group_ids": (),
            "state_group_migrations": (),
            "event_schemas": (),
            "rules": (),
            "requested_capabilities": (),
            "economic_outcomes": (),
            "granted_effect_types": (),
            "verification_profiles": (),
            "platform_extension": extension.model_dump(mode="json"),
        }
    )
    return manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})


def _source(
):
    store, source = _narrow_source()
    return store, source


def _inventory(
    store,
    *manifests: GameplayPatchManifest,
    runtime_item_definitions: tuple[str, ...],
    holder_ref: str,
    container_id: str,
) -> InventoryAuthorityService:
    registry = InventoryDefinitionRegistry()
    for definition_id in runtime_item_definitions:
        registry.register_item(ItemDefinition(definition_id, "1", 1, 1))
    package_registry = None
    if manifests:
        package_registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
        package_registry.install_many(manifests)
        package_registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    inventory = InventoryAuthorityService(store=store, registry=registry, package_registry=package_registry)
    created = inventory.create_container(
        command_id=f"container:{container_id}",
        actor_ref=holder_ref,
        spec=ContainerSpec(container_id, 100, 100, 4),
        idempotency_key=f"container:{container_id}",
        causation_id=f"cause:{container_id}",
        correlation_id=f"corr:{container_id}",
    )
    assert created.committed, created.failure
    return inventory


def _intent(
    source,
    store,
    *,
    holder_ref: str = "organization:district-milling-cooperative",
    command_id: str = "command:harvest-family",
    correlation_id: str = "corr:harvest-family",
) -> HarvestToCustodyIntent:
    return HarvestToCustodyIntent(
        harvest_event_id=source.event_id,
        expected_harvest_revision=source.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(f"gameplay:inventory:{holder_ref}"),
        command_id=command_id,
        correlation_id=correlation_id,
    )


def test_harvest_to_custody_consumes_the_one_admitted_wheat_content(
) -> None:
    manifest = _manifest(
        package_revision="package:harvest-wheat-family@1",
        definition_ref="definition:harvest-wheat-family@1",
        crop_definition_ref="definition:grain:wheat@1",
        item_definition_ref="item:grain:wheat@1",
        holder_binding_ref=_holder_binding("organization:district-milling-cooperative"),
        container_binding_ref=_container_binding(
            "container:district-milling-cooperative:grain-intake"
        ),
        policy_revision_ref="policy:inventory-grain-harvest-custody@1",
    )
    runtime_item_ref = "grain:wheat@1"
    expected_holder_ref = "organization:district-milling-cooperative"
    expected_container_id = "container:district-milling-cooperative:grain-intake"
    expected_policy_revision = "policy:inventory-grain-harvest-custody@1"
    store, source = _source()
    inventory = _inventory(
        store,
        manifest,
        runtime_item_definitions=(runtime_item_ref,),
        holder_ref=expected_holder_ref,
        container_id=expected_container_id,
    )

    result = inventory.settle_harvest_to_custody(
        intent=_intent(
            source,
            store,
            holder_ref=expected_holder_ref,
            command_id=f"command:{manifest.patch_revision_id}",
            correlation_id=f"corr:{manifest.patch_revision_id}",
        )
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["family_ref"] == "harvest_to_custody@1"
    assert event.payload["holder_ref"] == expected_holder_ref
    assert event.payload["container_id"] == expected_container_id
    assert event.payload["item_ref"] == runtime_item_ref
    assert event.payload["definition_id"] == runtime_item_ref
    assert event.payload["policy_revision"] == expected_policy_revision
    assert event.payload["package_revision"] == manifest.patch_revision_id
    assert event.payload["declaration_ref"].startswith("declaration:")
    assert event.payload["descriptor_ref"] == "descriptor:inventory-harvest-to-custody@1"
    assert event.payload["active_patch_set_revision"]
    projection = inventory._projector.rebuild(expected_holder_ref, store.read_events())
    item_id = event.payload["item_id"]
    assert projection.items[item_id].definition_id == runtime_item_ref
    assert projection.locations[item_id] == expected_container_id


def test_harvest_to_custody_genericity_gate_verifies_two_committed_manifest_source_pairs() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_closed_generic_gameplay_families.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    report = json.loads(
        (root / ".harness" / "verification" / "closed-generic-gameplay-families-report.json")
        .read_text(encoding="utf-8")
    )
    gate = report["harvest_to_custody_genericity_gate"]
    assert gate["family_ref"] == "harvest_to_custody@1"
    assert gate["passed"] is True
    assert gate["committed_source_facts"] == ["grain:barley@1", "grain:wheat@1"]
    assert len(gate["committed_manifest_paths"]) == 2
    assert "harvest_to_custody@1" in report["genericity_evidence_family_refs"]


def test_harvest_to_custody_requires_admitted_package_binding() -> None:
    store, source = _source()
    inventory = _inventory(
        store,
        runtime_item_definitions=("grain:wheat@1",),
        holder_ref="organization:district-milling-cooperative",
        container_id="container:district-milling-cooperative:grain-intake",
    )
    before = tuple(store.read_events())

    result = inventory.settle_harvest_to_custody(intent=_intent(source, store))

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "harvest_to_custody_package_inactive"
    assert tuple(store.read_events()) == before


def test_harvest_to_custody_replays_duplicate_and_preserves_grain_row_replay() -> None:
    manifest = _manifest(
        package_revision="package:harvest-wheat-family@1",
        definition_ref="definition:harvest-wheat-family@1",
        crop_definition_ref="definition:grain:wheat@1",
        item_definition_ref="item:grain:wheat@1",
        holder_binding_ref=_holder_binding("organization:district-milling-cooperative"),
        container_binding_ref=_container_binding("container:district-milling-cooperative:grain-intake"),
        policy_revision_ref="policy:inventory-grain-harvest-custody@1",
    )
    store, source = _source()
    inventory = _inventory(
        store,
        manifest,
        runtime_item_definitions=("grain:wheat@1",),
        holder_ref="organization:district-milling-cooperative",
        container_id="container:district-milling-cooperative:grain-intake",
    )
    intent = _intent(source, store)
    first = inventory.settle_harvest_to_custody(intent=intent)
    before = tuple(store.read_events())

    duplicate = inventory.settle_harvest_to_custody(intent=intent)
    changed = inventory.settle_harvest_to_custody(
        intent=intent.model_copy(update={"correlation_id": "corr:harvest:changed"})
    )

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert tuple(store.read_events()) == before
    full = inventory.grain_harvest_custody_view_for()
    tail = inventory.grain_harvest_custody_view_for(checkpoint_at=source.global_sequence)
    assert full == tail


def test_harvest_to_custody_rejects_ambiguous_matching_bindings_without_write() -> None:
    store, source = _source()
    inventory = _inventory(
        store,
        _manifest(
            package_revision="package:harvest-wheat-family@1",
            definition_ref="definition:harvest-wheat-family@1",
            crop_definition_ref="definition:grain:wheat@1",
            item_definition_ref="item:grain:wheat@1",
            holder_binding_ref=_holder_binding("organization:district-milling-cooperative"),
            container_binding_ref=_container_binding("container:district-milling-cooperative:grain-intake"),
            policy_revision_ref="policy:inventory-grain-harvest-custody@1",
        ),
        _manifest(
            package_revision="package:harvest-wheat-family-duplicate@1",
            definition_ref="definition:harvest-wheat-family-duplicate@1",
            crop_definition_ref="definition:grain:wheat@1",
            item_definition_ref="item:grain:wheat@1",
            holder_binding_ref=_holder_binding("organization:district-milling-cooperative"),
            container_binding_ref=_container_binding("container:district-milling-cooperative:grain-intake"),
            policy_revision_ref="policy:inventory-grain-harvest-custody@1",
        ),
        runtime_item_definitions=("grain:wheat@1",),
        holder_ref="organization:district-milling-cooperative",
        container_id="container:district-milling-cooperative:grain-intake",
    )
    before = tuple(store.read_events())

    result = inventory.settle_harvest_to_custody(intent=_intent(source, store))

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "harvest_to_custody_binding_ambiguous"
    assert tuple(store.read_events()) == before


def test_harvest_to_custody_intent_rejects_caller_selected_holder_container_quantity() -> None:
    with pytest.raises(Exception):
        HarvestToCustodyIntent.model_validate(
            {
                "harvest_event_id": "event:harvest",
                "expected_harvest_revision": 1,
                "expected_inventory_stream_revision": 0,
                "command_id": "command:harvest",
                "correlation_id": "corr:harvest",
                "holder_ref": "caller",
                "container_id": "caller",
                "quantity": 99,
            }
        )


def test_harvest_to_custody_blocker_records_the_fixed_grain_row() -> None:
    assert HARVEST_TO_CUSTODY_BLOCKER.family_ref == "harvest_to_custody@1"
    assert any("grain:wheat" in value for value in HARVEST_TO_CUSTODY_BLOCKER.candidate_values)


def _variant_envelope(
    store,
    *,
    command_type: str,
    project_ref: str,
    crop_ref: str,
    plot_ref: str,
    idempotency_key: str,
    causation_id: str,
    command_id: str,
) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=command_id,
        command_type=command_type,
        command_version=1,
        principal_ref="authority:ecology",
        project_ref=project_ref,
        idempotency_key=idempotency_key,
        expected_revisions={"gameplay:ecology:region:inf3:grain": store.get_stream_head("gameplay:ecology:region:inf3:grain")},
        causation_id=causation_id,
        correlation_id=f"corr:{project_ref}",
        source_ref="authority:ecology",
        submitted_at="2026-08-30T00:00:00Z",
        payload={
            "visibility_scope": "project",
            "project_ref": project_ref,
            "crop_ref": crop_ref,
            "region_ref": "region:inf3:grain",
            "plot_ref": plot_ref,
            "target_region_ref": "region:inf3:grain",
        },
    )


def test_harvest_to_custody_consumes_wheat_and_barley_with_one_adapter() -> None:
    store = _seed()
    ecology = EcologyHazardAuthority(store=store)
    wheat_admitted = ecology.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref="region:inf3:grain",
        plot_ref="plot:inf3:grain:1",
    )
    assert wheat_admitted.committed
    wheat_harvested = ecology.harvest_grain_crop(envelope=_harvest_envelope(store))
    assert wheat_harvested.committed

    wheat_manifest = _manifest(
        package_revision="package:harvest-wheat-family@1",
        definition_ref="definition:harvest-wheat-family@1",
        crop_definition_ref="definition:grain:wheat@1",
        item_definition_ref="item:grain:wheat@1",
        holder_binding_ref=_holder_binding("organization:district-milling-cooperative"),
        container_binding_ref=_container_binding("container:district-milling-cooperative:grain-intake"),
        policy_revision_ref="policy:inventory-grain-harvest-custody@1",
    )
    barley_manifest = _manifest(
        package_revision="package:harvest-barley-family@1",
        definition_ref="definition:harvest-barley-family@1",
        crop_definition_ref="definition:grain:barley@1",
        item_definition_ref="item:grain:barley@1",
        holder_binding_ref=_holder_binding("organization:district-milling-cooperative"),
        container_binding_ref=_container_binding("container:district-milling-cooperative:barley-intake"),
        policy_revision_ref="policy:inventory-grain-harvest-custody@1",
    )
    inventory = _inventory(
        store,
        wheat_manifest,
        barley_manifest,
        runtime_item_definitions=("grain:wheat@1", "grain:barley@1"),
        holder_ref="organization:district-milling-cooperative",
        container_id="container:district-milling-cooperative:grain-intake",
    )
    created = inventory.create_container(
        command_id="container:district-milling-cooperative:barley-intake",
        actor_ref="organization:district-milling-cooperative",
        spec=ContainerSpec("container:district-milling-cooperative:barley-intake", 100, 100, 4),
        idempotency_key="container:district-milling-cooperative:barley-intake",
        causation_id="cause:barley:container",
        correlation_id="corr:barley:container",
    )
    assert created.committed, created.failure
    wheat_result = inventory.settle_harvest_to_custody(intent=_intent(
        store.get_event(wheat_harvested.committed_event_ids[0]),
        store,
        command_id="command:family:wheat",
    ))
    assert wheat_result.committed, wheat_result.failure

    barley_project = "project:inf3-barley"
    barley_crop = "crop:inf3:grain:barley"
    barley_plot = "plot:inf3:grain:barley:1"
    barley_admitted = ecology.admit_barley_crop(
        envelope=_variant_envelope(
            store,
            command_type="gameplay.ecology.barley_crop.admit",
            project_ref=barley_project,
            crop_ref=barley_crop,
            plot_ref=barley_plot,
            idempotency_key=f"ecology:barley-crop-admission:{barley_project}:{barley_crop}:v1",
            causation_id="cause:barley:admit",
            command_id="command:barley:admit",
        ),
        crop_ref=barley_crop,
        region_ref="region:inf3:grain",
        plot_ref=barley_plot,
    )
    assert barley_admitted.committed, barley_admitted.failure
    barley_admission_event = store.get_event(barley_admitted.committed_event_ids[0])
    barley_harvested = ecology.harvest_barley_crop(
        envelope=_variant_envelope(
            store,
            command_type="gameplay.ecology.barley_crop.harvest",
            project_ref=barley_project,
            crop_ref=barley_crop,
            plot_ref=barley_plot,
            idempotency_key=f"ecology:barley-harvest:{barley_admission_event.event_id}:{barley_admission_event.stream_revision}:v1",
            causation_id=barley_admission_event.event_id,
            command_id="command:barley:harvest",
        )
    )
    assert barley_harvested.committed, barley_harvested.failure
    barley_source = store.get_event(barley_harvested.committed_event_ids[0])
    barley_result = inventory.settle_harvest_to_custody(
        intent=HarvestToCustodyIntent(
            harvest_event_id=barley_source.event_id,
            expected_harvest_revision=barley_source.stream_revision,
            expected_inventory_stream_revision=store.get_stream_head("gameplay:inventory:organization:district-milling-cooperative"),
            command_id="command:family:barley",
            correlation_id="corr:family:barley",
        )
    )
    assert barley_result.committed, barley_result.failure
    barley_event = store.get_event(barley_result.committed_event_ids[0])
    assert barley_event.payload["item_ref"] == "grain:barley@1"
    assert barley_event.payload["container_id"] == "container:district-milling-cooperative:barley-intake"
    assert barley_event.payload["quantity"] == 8
    assert barley_event.payload["family_ref"] == "harvest_to_custody@1"


def test_harvest_to_custody_barley_replay_and_changed_duplicate_are_zero_write() -> None:
    store = _seed()
    ecology = EcologyHazardAuthority(store=store)
    project_ref = "project:inf3-barley"
    crop_ref = "crop:inf3:grain:barley"
    plot_ref = "plot:inf3:grain:barley:replay"
    admitted = ecology.admit_barley_crop(
        envelope=_variant_envelope(
            store,
            command_type="gameplay.ecology.barley_crop.admit",
            project_ref=project_ref,
            crop_ref=crop_ref,
            plot_ref=plot_ref,
            idempotency_key=f"ecology:barley-crop-admission:{project_ref}:{crop_ref}:v1",
            causation_id="cause:barley:replay:admit",
            command_id="command:barley:replay:admit",
        ),
        crop_ref=crop_ref,
        region_ref="region:inf3:grain",
        plot_ref=plot_ref,
    )
    assert admitted.committed
    admission_event = store.get_event(admitted.committed_event_ids[0])
    harvested = ecology.harvest_barley_crop(
        envelope=_variant_envelope(
            store,
            command_type="gameplay.ecology.barley_crop.harvest",
            project_ref=project_ref,
            crop_ref=crop_ref,
            plot_ref=plot_ref,
            idempotency_key=f"ecology:barley-harvest:{admission_event.event_id}:{admission_event.stream_revision}:v1",
            causation_id=admission_event.event_id,
            command_id="command:barley:replay:harvest",
        )
    )
    assert harvested.committed
    source = store.get_event(harvested.committed_event_ids[0])
    manifest = _manifest(
        package_revision="package:harvest-barley-replay@1",
        definition_ref="definition:harvest-barley-replay@1",
        crop_definition_ref="definition:grain:barley@1",
        item_definition_ref="item:grain:barley@1",
        holder_binding_ref=_holder_binding("organization:district-milling-cooperative"),
        container_binding_ref=_container_binding("container:district-milling-cooperative:barley-intake"),
        policy_revision_ref="policy:inventory-grain-harvest-custody@1",
    )
    inventory = _inventory(
        store,
        manifest,
        runtime_item_definitions=("grain:barley@1",),
        holder_ref="organization:district-milling-cooperative",
        container_id="container:district-milling-cooperative:barley-intake",
    )
    intent = HarvestToCustodyIntent(
        harvest_event_id=source.event_id,
        expected_harvest_revision=source.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head("gameplay:inventory:organization:district-milling-cooperative"),
        command_id="command:barley:replay:custody",
        correlation_id="corr:barley:replay",
    )
    first = inventory.settle_harvest_to_custody(intent=intent)
    assert first.committed
    before = store.export_snapshot()
    duplicate = inventory.settle_harvest_to_custody(intent=intent)
    changed = inventory.settle_harvest_to_custody(
        intent=intent.model_copy(update={"correlation_id": "corr:barley:changed"})
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before
    assert inventory.harvest_to_custody_view_for() == inventory.harvest_to_custody_view_for(
        checkpoint_at=source.global_sequence
    )
