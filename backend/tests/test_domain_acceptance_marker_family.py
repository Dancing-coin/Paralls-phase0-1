from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gameplay.closed_generic_gameplay_families import CLOSED_GAMEPLAY_FAMILIES, DOMAIN_ACCEPTANCE_MARKER_BLOCKER, DomainAcceptanceMarkerIntent
from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from test_harvest_to_custody_family import _inventory as _generic_inventory, _manifest as _harvest_manifest, _variant_envelope
from test_inf3_grain_harvest import _admit_envelope, _harvest_envelope, _seed
from test_inf3ab_grain_harvest_inventory_custody import _inventory, _source
from app.gameplay.organization_government_runtime import OrganizationAuthority
from test_inf4v_production_work_contribution_acceptance import _prepared_case

MANIFEST_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-2"
)
FAMILY_MANIFEST_DIR = MANIFEST_DIR.parent / "closed-generic" / "domain-acceptance-marker"
FAMILY_MANIFEST_PATHS = (
    FAMILY_MANIFEST_DIR / "package-domain-acceptance-marker-grain-intake-v1.manifest.json",
    FAMILY_MANIFEST_DIR / "package-domain-acceptance-marker-production-work-v1.manifest.json",
)

GENERIC_FAMILY_MANIFEST_DIR = MANIFEST_DIR.parent / "closed-generic" / "domain-acceptance-marker"
GENERIC_FAMILY_MANIFEST_PATHS = (
    GENERIC_FAMILY_MANIFEST_DIR / "package-domain-acceptance-marker-wheat-v1.manifest.json",
    GENERIC_FAMILY_MANIFEST_DIR / "package-domain-acceptance-marker-barley-v1.manifest.json",
)



def test_domain_acceptance_marker_derives_organization_from_committed_inventory_source() -> None:
    store, source = _source()
    inventory = _inventory(store)
    assert inventory.record_grain_harvest_custody_receipt(
        harvest_event_id=source.event_id,
        expected_harvest_revision=source.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head("gameplay:inventory:organization:district-milling-cooperative"),
        command_id="command:harvest",
        idempotency_key=f"inventory:grain-harvest-custody:{source.event_id}:{source.stream_revision}:1:v1",
        causation_id=source.event_id,
        correlation_id="corr:harvest",
    ).committed
    organization = OrganizationAuthority(store=store)
    result = organization.settle_domain_acceptance_marker(
        intent=DomainAcceptanceMarkerIntent(
            source_event_id=store.read_stream("gameplay:inventory:organization:district-milling-cooperative")[-1].event_id,
            command_id="command:acceptance-family",
            correlation_id="corr:acceptance-family",
        )
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["family_ref"] == "domain_acceptance_marker@1"
    assert event.payload["organization_ref"] == "organization:district-milling-cooperative"


def test_domain_acceptance_marker_rejects_caller_selected_owner_and_quantity() -> None:
    with pytest.raises(Exception):
        DomainAcceptanceMarkerIntent.model_validate(
            {
                "source_event_id": "event:inventory",
                "command_id": "command:acceptance",
                "correlation_id": "corr:acceptance",
                "organization_ref": "caller",
                "quantity": 99,
            }
        )


def test_domain_acceptance_marker_replays_duplicate_and_matches_tail() -> None:
    store, source = _source()
    inventory = _inventory(store)
    custody = inventory.record_grain_harvest_custody_receipt(
        harvest_event_id=source.event_id,
        expected_harvest_revision=source.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head("gameplay:inventory:organization:district-milling-cooperative"),
        command_id="command:harvest",
        idempotency_key=f"inventory:grain-harvest-custody:{source.event_id}:{source.stream_revision}:1:v1",
        causation_id=source.event_id,
        correlation_id="corr:harvest",
    )
    assert custody.committed
    authority = OrganizationAuthority(store=store)
    source_id = custody.committed_event_ids[0]
    intent = DomainAcceptanceMarkerIntent(
        source_event_id=source_id,
        command_id="command:acceptance-family",
        correlation_id="corr:acceptance-family",
    )
    first = authority.settle_domain_acceptance_marker(intent=intent)
    before = tuple(store.read_events())
    duplicate = authority.settle_domain_acceptance_marker(intent=intent)
    changed = authority.settle_domain_acceptance_marker(intent=intent.model_copy(update={"correlation_id": "corr:changed"}))
    full = authority.grain_intake_view_for(organization_ref="organization:district-milling-cooperative")
    tail = authority.grain_intake_view_for(organization_ref="organization:district-milling-cooperative", checkpoint_at=source.global_sequence)

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed and changed.failure is not None
    assert tuple(store.read_events()) == before
    assert full == tail


def test_domain_acceptance_marker_blocker_records_the_single_org_grain_row() -> None:
    assert DOMAIN_ACCEPTANCE_MARKER_BLOCKER.family_ref == "domain_acceptance_marker@1"
    assert any("grain" in value for value in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.candidate_values)
    assert DOMAIN_ACCEPTANCE_MARKER_BLOCKER.source_refs


def test_domain_acceptance_marker_blocker_matches_committed_manifest_and_sibling_acceptance_evidence() -> None:
    committed_manifests = {
        manifest_path.name: json.loads(manifest_path.read_text(encoding="utf-8"))
        for manifest_path in (
            MANIFEST_DIR / "package-industrial-facilities-v5-public-workshop-session.manifest.json",
            MANIFEST_DIR / "package-industrial-facilities-v6-public-milling-session.manifest.json",
            MANIFEST_DIR / "package-industrial-facilities-v7-reinforced-mill-flour-output-purchase.manifest.json",
            MANIFEST_DIR / "package-municipal-drought-services-v1.manifest.json",
        )
    }

    outcomes = [
        (manifest_name, outcome)
        for manifest_name, manifest in committed_manifests.items()
        for outcome in manifest["economic_outcomes"]
    ]

    assert all(
        outcome["capability_ref"] != "capability:domain-acceptance-marker@1"
        and outcome["outcome_ref"] != "outcome:domain-acceptance-marker@1"
        for _, outcome in outcomes
    )
    assert any("district-milling" in value for value in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.candidate_values)
    assert any(
        "production_work_contribution" in value or "production-work-contribution" in value
        for value in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.candidate_values + DOMAIN_ACCEPTANCE_MARKER_BLOCKER.source_refs
    )
    assert "backend/app/gameplay/organization_government_runtime.py:work_contribution_acceptance_view_for" in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.source_refs
    assert "backend/tests/test_inf4v_production_work_contribution_acceptance.py:test_inf4v_accepts_only_production_evidence_with_committed_organization_schedule" in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.source_refs


def test_domain_acceptance_marker_blocker_records_missing_family_manifests_and_real_privacy_mismatch() -> None:
    assert not any(manifest_path.exists() for manifest_path in FAMILY_MANIFEST_PATHS)
    assert any(
        "organization:summary" in value or "privacy mismatch" in value
        for value in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.candidate_values
    )
    assert any(
        "closed-generic/domain-acceptance-marker" in value.replace("\\", "/")
        for value in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.source_refs
    )
    assert any(
        "accept_production_work_contribution" in value
        for value in DOMAIN_ACCEPTANCE_MARKER_BLOCKER.source_refs
    )


def test_domain_acceptance_marker_rejects_forged_inventory_source_chain() -> None:
    family = next(item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == "domain_acceptance_marker@1")
    assert family.status == "generic_implemented"
    assert family.owner_ref == "actor_gameplay.organization_domain"
    assert family.stream_pattern == "gameplay:organization:{organization_ref}"

    store, source = _source()
    inventory = _inventory(store)
    custody = inventory.record_grain_harvest_custody_receipt(
        harvest_event_id=source.event_id,
        expected_harvest_revision=source.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head("gameplay:inventory:organization:district-milling-cooperative"),
        command_id="command:harvest:bounded",
        idempotency_key=f"inventory:grain-harvest-custody:{source.event_id}:{source.stream_revision}:1:v1",
        causation_id=source.event_id,
        correlation_id="corr:harvest:bounded",
    )
    assert custody.committed
    accepted_source_id = custody.committed_event_ids[0]
    forged = store.get_event(accepted_source_id).model_copy(
        update={"stream_id": "gameplay:inventory:organization:river-granary"},
        deep=True,
    )
    store._events_by_id[accepted_source_id] = forged
    store._events = [forged if item.event_id == accepted_source_id else item for item in store._events]
    before = store.export_snapshot()

    result = OrganizationAuthority(store=store).settle_domain_acceptance_marker(
        intent=DomainAcceptanceMarkerIntent(
            source_event_id=accepted_source_id,
            command_id="command:acceptance-family:bounded",
            correlation_id="corr:acceptance-family:bounded",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "domain_acceptance_marker_source_conflict"
    assert store.export_snapshot() == before


def test_domain_acceptance_marker_supports_wheat_and_barley_contents_through_one_adapter() -> None:
    assert all(path.is_file() for path in GENERIC_FAMILY_MANIFEST_PATHS)
    manifests = tuple(
        GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in GENERIC_FAMILY_MANIFEST_PATHS
    )
    assert all(manifest.content_digest == manifest.expected_content_digest() for manifest in manifests)
    assert {
        definition.typed_content["source_item_definition_ref"]
        for manifest in manifests
        for definition in manifest.platform_extension.package_definitions
    } == {"item:grain:wheat@1", "item:grain:barley@1"}


def _generic_custody(*, species: str, project_ref: str, plot_ref: str) -> tuple[object, object]:
    store = _seed()
    ecology = EcologyHazardAuthority(store=store)
    if species == "grain:wheat":
        admitted = ecology.admit_grain_crop(
            envelope=_admit_envelope(store),
            crop_ref="crop:inf3:grain:wheat",
            region_ref="region:inf3:grain",
            plot_ref="plot:inf3:grain:1",
        )
        harvested = ecology.harvest_grain_crop(envelope=_harvest_envelope(store))
    else:
        admitted = ecology.admit_barley_crop(
            envelope=_variant_envelope(
                store,
                command_type="gameplay.ecology.barley_crop.admit",
                project_ref=project_ref,
                crop_ref=f"crop:{species}",
                plot_ref=plot_ref,
                idempotency_key=f"ecology:barley-crop-admission:{project_ref}:crop:{species}:v1",
                causation_id=f"cause:{species}:admit",
                command_id=f"command:{species}:admit",
            ),
            crop_ref=f"crop:{species}",
            region_ref="region:inf3:grain",
            plot_ref=plot_ref,
        )
        admission_event = store.get_event(admitted.committed_event_ids[0])
        harvested = ecology.harvest_barley_crop(
            envelope=_variant_envelope(
                store,
                command_type="gameplay.ecology.barley_crop.harvest",
                project_ref=project_ref,
                crop_ref=f"crop:{species}",
                plot_ref=plot_ref,
                idempotency_key=f"ecology:barley-harvest:{admission_event.event_id}:{admission_event.stream_revision}:v1",
                causation_id=admission_event.event_id,
                command_id=f"command:{species}:harvest",
            )
        )
    assert admitted.committed, admitted.failure
    assert harvested.committed, harvested.failure
    source = store.get_event(harvested.committed_event_ids[0])
    holder_ref = "organization:district-milling-cooperative"
    container_id = (
        f"container:district-milling-cooperative:"
        f"{'grain-intake' if species == 'grain:wheat' else 'barley-intake'}"
    )
    manifest = _harvest_manifest(
        package_revision=f"package:domain-acceptance-source:{species.replace(':', '-') }@1",
        definition_ref=f"definition:domain-acceptance-source:{species.replace(':', '-') }@1",
        crop_definition_ref=f"definition:{species}@1",
        item_definition_ref=f"item:{species}@1",
        holder_binding_ref=f"binding:holder:{holder_ref}@1",
        container_binding_ref=f"binding:container:{container_id}@1",
        policy_revision_ref="policy:inventory-grain-harvest-custody@1",
    )
    inventory = _generic_inventory(
        store,
        manifest,
        runtime_item_definitions=(f"{species}@1",),
        holder_ref=holder_ref,
        container_id=container_id,
    )
    from app.gameplay.closed_generic_gameplay_families import HarvestToCustodyIntent

    result = inventory.settle_harvest_to_custody(
        intent=HarvestToCustodyIntent(
            harvest_event_id=source.event_id,
            expected_harvest_revision=source.stream_revision,
            expected_inventory_stream_revision=store.get_stream_head(
                "gameplay:inventory:organization:district-milling-cooperative"
            ),
            command_id=f"command:domain-acceptance-source:{species}",
            correlation_id=f"corr:domain-acceptance-source:{species}",
        )
    )
    assert result.committed, result.failure
    return store, store.get_event(result.committed_event_ids[0])


def test_domain_acceptance_marker_derives_an_alternate_organization_from_source() -> None:
    store, source = _generic_custody(
        species="grain:barley",
        project_ref="project:domain-acceptance-alternate-owner",
        plot_ref="plot:domain-acceptance-alternate-owner",
    )
    alternate_holder = "organization:river-granary"
    alternate_container = f"container:river-granary:barley-intake"
    source = source.model_copy(
        update={
            "stream_id": f"gameplay:inventory:{alternate_holder}",
            "payload": {
                **source.payload,
                "actor_ref": alternate_holder,
                "holder_ref": alternate_holder,
                "container_id": alternate_container,
            },
        },
        deep=True,
    )
    store._events_by_id[source.event_id] = source
    store._events = [
        source if event.event_id == source.event_id else event
        for event in store._events
    ]
    store._stream_heads[f"gameplay:inventory:{alternate_holder}"] = source.stream_revision

    authority, _registry = _domain_authority(store)
    result = authority.settle_domain_acceptance_marker(
        intent=DomainAcceptanceMarkerIntent(
            source_event_id=source.event_id,
            command_id="command:domain-acceptance:alternate-owner",
            correlation_id="corr:domain-acceptance:alternate-owner",
        )
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.stream_id == f"gameplay:organization:{alternate_holder}"
    assert event.payload["organization_ref"] == alternate_holder
    assert event.payload["container_id"] == alternate_container
    full = authority.domain_acceptance_marker_view_for(
        organization_ref=alternate_holder
    )
    tail = authority.domain_acceptance_marker_view_for(
        organization_ref=alternate_holder,
        checkpoint_at=source.global_sequence,
    )
    assert full == tail


def _domain_authority(store: object) -> tuple[OrganizationAuthority, GameplayPatchRegistry]:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifests = tuple(
        GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in GENERIC_FAMILY_MANIFEST_PATHS
    )
    registry.install_many(manifests)
    active = registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    assert active.capability_bindings
    return OrganizationAuthority(store=store, package_registry=registry), registry


def test_domain_acceptance_marker_generic_adapter_consumes_wheat_and_barley_source_content() -> None:
    wheat_store, wheat_source = _generic_custody(
        species="grain:wheat",
        project_ref="project:domain-acceptance-wheat",
        plot_ref="plot:domain-acceptance-wheat",
    )
    wheat_authority, wheat_registry = _domain_authority(wheat_store)
    wheat = wheat_authority.settle_domain_acceptance_marker(
        intent=DomainAcceptanceMarkerIntent(
            source_event_id=wheat_source.event_id,
            command_id="command:domain-acceptance:wheat",
            correlation_id="corr:domain-acceptance:wheat",
        )
    )
    assert wheat.committed, wheat.failure
    wheat_event = wheat_store.get_event(wheat.committed_event_ids[0])
    assert wheat_event.event_type == "gameplay.organization.grain_intake_recorded@1"
    assert wheat_event.visibility_policy == "project"
    assert wheat_event.stream_id == "gameplay:organization:organization:district-milling-cooperative"
    assert wheat_event.payload["item_ref"] == "grain:wheat@1"
    assert wheat_event.payload["quantity"] == 10
    assert wheat_event.payload["container_id"] == "container:district-milling-cooperative:grain-intake"
    assert wheat_event.payload["source_inventory_event_id"] == wheat_source.event_id
    assert wheat_event.payload["source_fact_family_ref"] == "fact:inventory-harvest-to-custody@1"
    assert wheat_event.payload["marker_definition_ref"] == "definition:organization-grain-intake-wheat@1"
    assert wheat_event.payload["package_revision"] == "package:domain-acceptance-marker:wheat@1"
    assert wheat_event.payload["content_digest"] == next(
        manifest.content_digest
        for manifest in wheat_registry.active_manifests(
            wheat_registry.active_patch_set.active_patch_set_revision
        )
        if manifest.patch_revision_id == "package:domain-acceptance-marker:wheat@1"
    )

    barley_store, barley_source = _generic_custody(
        species="grain:barley",
        project_ref="project:domain-acceptance-barley",
        plot_ref="plot:domain-acceptance-barley",
    )
    barley_authority, _barley_registry = _domain_authority(barley_store)
    barley = barley_authority.settle_domain_acceptance_marker(
        intent=DomainAcceptanceMarkerIntent(
            source_event_id=barley_source.event_id,
            command_id="command:domain-acceptance:barley",
            correlation_id="corr:domain-acceptance:barley",
        )
    )
    assert barley.committed, barley.failure
    barley_event = barley_store.get_event(barley.committed_event_ids[0])
    assert barley_event.event_type == wheat_event.event_type
    assert barley_event.visibility_policy == wheat_event.visibility_policy
    assert barley_event.payload["item_ref"] == "grain:barley@1"
    assert barley_event.payload["quantity"] == 8
    assert barley_event.payload["container_id"] == "container:district-milling-cooperative:barley-intake"
    assert barley_event.payload["source_inventory_event_id"] == barley_source.event_id


def test_domain_acceptance_marker_generic_adapter_replays_tail_and_changed_duplicate_zero_write() -> None:
    store, source = _generic_custody(
        species="grain:barley",
        project_ref="project:domain-acceptance-replay",
        plot_ref="plot:domain-acceptance-replay",
    )
    authority, _registry = _domain_authority(store)
    intent = DomainAcceptanceMarkerIntent(
        source_event_id=source.event_id,
        command_id="command:domain-acceptance:replay",
        correlation_id="corr:domain-acceptance:replay",
    )
    first = authority.settle_domain_acceptance_marker(intent=intent)
    assert first.committed, first.failure
    before = store.export_snapshot()
    duplicate = authority.settle_domain_acceptance_marker(intent=intent)
    changed = authority.settle_domain_acceptance_marker(
        intent=intent.model_copy(update={"correlation_id": "corr:domain-acceptance:changed"})
    )
    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "domain_acceptance_marker_idempotency_key_reused"
    assert store.export_snapshot() == before
    full = authority.domain_acceptance_marker_view_for(
        organization_ref="organization:district-milling-cooperative"
    )
    tail = authority.domain_acceptance_marker_view_for(
        organization_ref="organization:district-milling-cooperative",
        checkpoint_at=source.global_sequence,
    )
    assert full == tail
