from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from app.gameplay.closed_generic_gameplay_families import FacilityIdentityUpgradeContent
from app.gameplay.construction_production_runtime import Facility, Plot
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
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
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from test_infra_construction_mill_reinforcement import _setup as _mill_setup
from closed_generic_manifest_fixtures import load_manifest


PACKAGE_REVISION = "package:facility-upgrade-demo@1"
MILL_PACKAGE_REVISION = "package:facility-upgrade-mill-demo@1"


def _digest(value: object) -> str:
    return "sha256:" + sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _manifest() -> GameplayPatchManifest:
    return load_manifest("facility-identity-upgrade-demo-v1")


def _mill_manifest() -> GameplayPatchManifest:
    return load_manifest("facility-identity-upgrade-mill-demo-v1")


def _setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Facility]:
    store = GameplayEventStore()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    facility = Facility(
        facility_ref="facility:oven:1",
        plot_ref="plot:oven:1",
        facility_kind="oven",
        condition=0.8,
    )
    acquired = authority.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:local", owner_ref="organization:bakery"),
        facility=facility,
        command_id="command:acquire",
        idempotency_key="idempotency:acquire",
        causation_id="causation:acquire",
        correlation_id="correlation:acquire",
    )
    assert acquired.committed
    return store, authority, facility


def _mill_setup_family() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Facility]:
    store, _authority, _registry, source_id = _mill_setup()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _mill_manifest()
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    facility = authority.projector().facilities["facility:mill-reinforcement:1"]
    assert store.get_event(source_id).payload["facility_kind"] == "mill"
    return store, authority, facility


def _intent(facility: Facility) -> object:
    from app.gameplay.closed_generic_gameplay_families import FacilityIdentityUpgradeIntent

    return FacilityIdentityUpgradeIntent(
        facility_ref=facility.facility_ref,
        acquisition_event_id="event:construction:facility:oven:1:1",
        expected_stream_revision=1,
        expected_facility_revision=0,
        command_id="command:facility-upgrade",
        causation_id="causation:facility-upgrade",
        correlation_id="correlation:facility-upgrade",
        submitted_at="2026-08-30T00:00:00Z",
    )


def test_identity_upgrade_family_uses_typed_target_and_existing_construction_spine() -> None:
    store, authority, facility = _setup()
    source_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    intent = _intent(facility).model_copy(update={"acquisition_event_id": source_id})

    result = authority.settle_facility_identity_upgrade(intent=intent)

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.facility_transformed"
    assert event.payload["prior_kind"] == "oven"
    assert event.payload["next_kind"] == "kiln"
    assert event.payload["family_ref"] == "facility_identity_upgrade@1"
    assert event.payload["active_patch_set_revision"]
    assert authority.projector().facilities[facility.facility_ref].facility_kind == "kiln"


@pytest.mark.parametrize(
    ("setup", "expected_next_kind"),
    [
        (_setup, "kiln"),
        (_mill_setup_family, "mill_reinforced"),
    ],
)
def test_identity_upgrade_family_consumes_multiple_admitted_content_instances_through_one_adapter(
    setup,
    expected_next_kind: str,
) -> None:
    store, authority, facility = setup()
    source_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    intent = _intent(facility).model_copy(update={"acquisition_event_id": source_id})

    result = authority.settle_facility_identity_upgrade(intent=intent)

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["family_ref"] == "facility_identity_upgrade@1"
    assert event.payload["next_kind"] == expected_next_kind


def test_identity_upgrade_family_rejects_wrong_source_kind_without_writing() -> None:
    store, authority, facility = _setup()
    source_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    source = store.get_event(source_id)
    store._events_by_id[source_id] = source.model_copy(
        update={"payload": {**source.payload, "facility_kind": "bakery"}}, deep=True
    )
    before = tuple(store.read_events())

    result = authority.settle_facility_identity_upgrade(
        intent=_intent(facility).model_copy(update={"acquisition_event_id": source_id})
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "facility_identity_upgrade_source_conflict"
    assert tuple(store.read_events()) == before


def test_identity_upgrade_intent_rejects_caller_authority_coordinates() -> None:
    with pytest.raises(Exception):
        from app.gameplay.closed_generic_gameplay_families import FacilityIdentityUpgradeIntent

        FacilityIdentityUpgradeIntent.model_validate(
            {
                "facility_ref": "facility:oven:1",
                "acquisition_event_id": "event:source",
                "expected_stream_revision": 1,
                "expected_facility_revision": 0,
                "command_id": "command:upgrade",
                "causation_id": "cause:upgrade",
                "correlation_id": "corr:upgrade",
                "submitted_at": "2026-08-30T00:00:00Z",
                "owner_ref": "caller",
                "next_kind": "kiln",
            }
        )


def test_identity_upgrade_replays_identical_intent_and_rejects_changed_duplicate() -> None:
    store, authority, facility = _setup()
    source_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    intent = _intent(facility).model_copy(update={"acquisition_event_id": source_id})
    first = authority.settle_facility_identity_upgrade(intent=intent)
    before = tuple(store.read_events())

    replay = authority.settle_facility_identity_upgrade(intent=intent)
    changed = authority.settle_facility_identity_upgrade(
        intent=intent.model_copy(update={"correlation_id": "correlation:changed"})
    )

    assert replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert tuple(store.read_events()) == before


def test_identity_upgrade_full_and_checkpoint_tail_replay_match() -> None:
    store, authority, facility = _setup()
    source_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    assert authority.settle_facility_identity_upgrade(
        intent=_intent(facility).model_copy(update={"acquisition_event_id": source_id})
    ).committed

    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)

    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector


def test_identity_upgrade_rejects_tampered_activation_binding_without_writing() -> None:
    store, authority, facility = _setup()
    source_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    registry = authority._package_registry
    active = registry.active_patch_set
    assert active is not None
    assert len(active.capability_bindings) == 1
    registry._active = replace(
        active,
        capability_bindings=(
            replace(active.capability_bindings[0], family_ref="recipe_production@1"),
        ),
    )
    before = tuple(store.read_events())

    result = authority.settle_facility_identity_upgrade(
        intent=_intent(facility).model_copy(update={"acquisition_event_id": source_id})
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "facility_identity_upgrade_binding_invalid"
    assert tuple(store.read_events()) == before
